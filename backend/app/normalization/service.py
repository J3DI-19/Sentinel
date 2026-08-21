from __future__ import annotations

from uuid import UUID

from pydantic import ValidationError

from app.evidence.authorization import DEFAULT_VALIDATION_AUTHORITY, ValidationAuthority
from app.evidence.hashing import sha256_record
from app.evidence.schemas import (
    EvidenceMetadata,
    EvidenceSource,
    ValidatedBatchRecord,
    ValidatedLiveTelemetry,
)
from app.normalization.adapters import (
    AdapterRejection,
    CasasSmartHomeAdapter,
    CanonicalAdapter,
    CicIot2023NetworkAdapter,
    GenericAdapter,
    LiveTelemetryAdapter,
    SimulatedAdapter,
    SimulationAdapter,
    TonIotNetworkAdapter,
    CasasAdapter,
    TonIotFridgeTelemetryAdapter,
    TonIotTelemetryAdapter,
)
from app.normalization.schemas import (
    CanonicalSourceType,
    EventOrigin,
    NormalizationContext,
    NormalizationIssue,
    NormalizationResult,
    NormalizationStatus,
)
from app.normalization.helpers import AmbiguousRecordFields


_BATCH_SOURCE_MAP = {
    EvidenceSource.CASAS: CanonicalSourceType.CASAS,
    EvidenceSource.CASAS_SMART_HOME: CanonicalSourceType.CASAS_SMART_HOME,
    EvidenceSource.TON_IOT_TELEMETRY: CanonicalSourceType.TON_IOT_TELEMETRY,
    EvidenceSource.TON_IOT_FRIDGE_TELEMETRY: CanonicalSourceType.TON_IOT_FRIDGE_TELEMETRY,
    EvidenceSource.SIMULATED: CanonicalSourceType.SIMULATED,
    EvidenceSource.SIMULATION: CanonicalSourceType.SIMULATION,
    EvidenceSource.TON_IOT_NETWORK: CanonicalSourceType.TON_IOT_NETWORK,
    EvidenceSource.CICIOT2023_NETWORK: CanonicalSourceType.CICIOT2023_NETWORK,
    EvidenceSource.GENERIC: CanonicalSourceType.GENERIC,
}


class NormalizationService:
    def __init__(self, validation_authority: ValidationAuthority | None = None) -> None:
        adapters: list[CanonicalAdapter] = [
            CasasAdapter(),
            CasasSmartHomeAdapter(),
            TonIotTelemetryAdapter(),
            TonIotFridgeTelemetryAdapter(),
            SimulatedAdapter(),
            SimulationAdapter(),
            TonIotNetworkAdapter(),
            CicIot2023NetworkAdapter(),
            GenericAdapter(),
            LiveTelemetryAdapter(),
        ]
        self.adapters = {adapter.source_type: adapter for adapter in adapters}
        self.validation_authority = validation_authority or DEFAULT_VALIDATION_AUTHORITY

    def normalize_batch_record(
        self,
        *,
        metadata: EvidenceMetadata,
        validated_record: ValidatedBatchRecord,
    ) -> NormalizationResult:
        source_reference = f"row:{validated_record.row_number}"
        if metadata.case_id is None:
            return self._rejected(
                source_reference,
                "CASE_ID_REQUIRED",
                "Evidence must be registered to a case before normalization",
                "case_id",
            )
        expected_handoff = (
            validated_record.evidence_id == metadata.evidence_id
            and validated_record.source_type == metadata.source_type
            and validated_record.dataset_profile == metadata.dataset_profile
            and validated_record.validator_version == metadata.validator_version
        )
        if not expected_handoff:
            return self._rejected(
                source_reference,
                "VALIDATED_RECORD_MISMATCH",
                "The validated row does not belong to the supplied evidence metadata",
            )
        if sha256_record(validated_record.record) != validated_record.raw_record_hash:
            return self._rejected(
                source_reference,
                "VALIDATED_RECORD_HASH_MISMATCH",
                "The validated row changed after Step 3 accepted it",
                "raw_record_hash",
            )
        if not self.validation_authority.verify(
            validation_seal=validated_record.validation_seal,
            evidence_id=validated_record.evidence_id,
            source_type=validated_record.source_type,
            dataset_profile=validated_record.dataset_profile,
            validator_version=validated_record.validator_version,
            source_hash=metadata.sha256,
            row_number=validated_record.row_number,
            raw_record_hash=validated_record.raw_record_hash,
        ):
            return self._rejected(
                source_reference,
                "VALIDATION_SEAL_INVALID",
                "The validated row was not authorized by this Step 3 validation boundary",
                "validation_seal",
            )
        source_type = _BATCH_SOURCE_MAP[metadata.source_type]
        try:
            context = NormalizationContext(
                case_id=metadata.case_id,
                evidence_id=metadata.evidence_id,
                source_type=source_type,
                origin=EventOrigin.BATCH,
                source_name=metadata.sanitized_filename,
                source_hash=metadata.sha256,
                source_record_reference=source_reference,
                ingested_at=metadata.received_at,
            )
        except ValidationError as exc:
            return self._schema_rejection(source_reference, "NORMALIZATION_CONTEXT_INVALID", exc)
        return self._normalize(validated_record.record, context)

    def normalize_live_telemetry(
        self,
        *,
        accepted: ValidatedLiveTelemetry,
        evidence_id: UUID,
        source_hash: str,
        source_name: str = "controlled-live-telemetry",
    ) -> NormalizationResult:
        telemetry = accepted.telemetry
        source_reference = (
            f"sequence:{telemetry.sequence}"
            if telemetry.sequence is not None
            else f"event:{evidence_id}"
        )
        try:
            context = NormalizationContext(
                case_id=telemetry.case_id,
                evidence_id=evidence_id,
                source_type=CanonicalSourceType.LIVE_TELEMETRY,
                origin=EventOrigin.LIVE,
                source_name=source_name,
                source_id=telemetry.source_id,
                source_hash=source_hash,
                source_record_reference=source_reference,
                ingested_at=accepted.ingested_at,
            )
        except ValidationError as exc:
            return self._schema_rejection(source_reference, "NORMALIZATION_CONTEXT_INVALID", exc)
        record = telemetry.model_dump(mode="json")
        return self._normalize(record, context)

    def _normalize(
        self, record: dict[str, object], context: NormalizationContext
    ) -> NormalizationResult:
        adapter = self.adapters[context.source_type]
        try:
            event = adapter.normalize(record.copy(), context)
        except AdapterRejection as exc:
            return NormalizationResult(
                status=NormalizationStatus.REJECTED,
                source_record_reference=context.source_record_reference,
                issues=[exc.issue],
            )
        except AmbiguousRecordFields as exc:
            return self._rejected(
                context.source_record_reference,
                "AMBIGUOUS_SOURCE_FIELDS",
                str(exc),
                exc.second_name,
            )
        except ValidationError as exc:
            return self._schema_rejection(
                context.source_record_reference,
                "CANONICAL_SCHEMA_REJECTED",
                exc,
            )
        return NormalizationResult(
            status=NormalizationStatus.NORMALIZED,
            source_record_reference=context.source_record_reference,
            event=event,
        )

    @staticmethod
    def _rejected(
        source_reference: str,
        code: str,
        message: str,
        field: str | None = None,
    ) -> NormalizationResult:
        return NormalizationResult(
            status=NormalizationStatus.REJECTED,
            source_record_reference=source_reference,
            issues=[NormalizationIssue(code=code, message=message, field=field)],
        )

    @staticmethod
    def _schema_rejection(
        source_reference: str, code: str, error: ValidationError
    ) -> NormalizationResult:
        first = error.errors(include_url=False)[0]
        field = ".".join(str(part) for part in first.get("loc", ())) or None
        return NormalizationResult(
            status=NormalizationStatus.REJECTED,
            source_record_reference=source_reference,
            issues=[
                NormalizationIssue(
                    code=code,
                    message=first["msg"],
                    field=field,
                )
            ],
        )
