from __future__ import annotations

import hmac
import json
import secrets
from hashlib import sha256
from uuid import UUID

from app.evidence.schemas import EvidenceSource


class ValidationAuthority:
    """Issues and verifies process-local authorization seals for validated rows."""

    def __init__(self, key: bytes | None = None) -> None:
        self._key = key or secrets.token_bytes(32)
        if len(self._key) < 32:
            raise ValueError("validation authority keys must contain at least 32 bytes")

    def seal(
        self,
        *,
        evidence_id: UUID,
        source_type: EvidenceSource,
        dataset_profile: str,
        validator_version: str,
        source_hash: str,
        row_number: int,
        raw_record_hash: str,
    ) -> str:
        material = json.dumps(
            [
                str(evidence_id),
                source_type.value,
                dataset_profile,
                validator_version,
                source_hash,
                row_number,
                raw_record_hash,
            ],
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hmac.new(self._key, material, sha256).hexdigest()

    def verify(
        self,
        *,
        validation_seal: str,
        evidence_id: UUID,
        source_type: EvidenceSource,
        dataset_profile: str,
        validator_version: str,
        source_hash: str,
        row_number: int,
        raw_record_hash: str,
    ) -> bool:
        expected = self.seal(
            evidence_id=evidence_id,
            source_type=source_type,
            dataset_profile=dataset_profile,
            validator_version=validator_version,
            source_hash=source_hash,
            row_number=row_number,
            raw_record_hash=raw_record_hash,
        )
        return hmac.compare_digest(validation_seal, expected)


DEFAULT_VALIDATION_AUTHORITY = ValidationAuthority()
