from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID, uuid5

from app.normalization.helpers import (
    RecordView,
    normalize_mac,
    normalized_token,
    parse_ip,
    parse_nonnegative_int,
    parse_timestamp,
    record_hash,
    scalar_attributes,
)
from app.normalization.schemas import (
    CanonicalEntity,
    CanonicalEvent,
    CanonicalNetwork,
    CanonicalProvenance,
    CanonicalSourceType,
    EntityKind,
    NormalizationContext,
    NormalizationIssue,
)


_EVENT_NAMESPACE = UUID("6683ec77-30f5-5e74-9b3e-eec50f965be8")


class AdapterRejection(ValueError):
    def __init__(self, issue: NormalizationIssue):
        super().__init__(issue.message)
        self.issue = issue


class CanonicalAdapter(ABC):
    source_type: CanonicalSourceType
    name: str
    version = "1.0"

    @abstractmethod
    def normalize(self, record: dict[str, Any], context: NormalizationContext) -> CanonicalEvent:
        raise NotImplementedError

    def _build_event(
        self,
        *,
        record: dict[str, Any],
        context: NormalizationContext,
        observed_at,
        event_type: str,
        source_event_type: str | None,
        source_label: str | None,
        warnings: list[NormalizationIssue],
        device: CanonicalEntity | None = None,
        actor: CanonicalEntity | None = None,
        target: CanonicalEntity | None = None,
        network: CanonicalNetwork | None = None,
        action: str | None = None,
        outcome: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> CanonicalEvent:
        if context.source_type != self.source_type:
            raise AdapterRejection(
                NormalizationIssue(
                    code="SOURCE_ADAPTER_MISMATCH",
                    message=f"Adapter {self.name} cannot process {context.source_type.value}",
                )
            )
        raw_hash = record_hash(record)
        event_key = ":".join(
            (
                str(context.case_id),
                str(context.evidence_id),
                context.source_record_reference,
                self.name,
                self.version,
                raw_hash,
            )
        )
        return CanonicalEvent(
            event_id=uuid5(_EVENT_NAMESPACE, event_key),
            case_id=context.case_id,
            observed_at=observed_at,
            ingested_at=context.ingested_at,
            event_type=event_type,
            source_event_type=source_event_type,
            source_label=source_label,
            device=device,
            actor=actor,
            target=target,
            network=network,
            action=action,
            outcome=outcome,
            attributes=attributes or {},
            provenance=CanonicalProvenance(
                evidence_id=context.evidence_id,
                origin=context.origin,
                source_type=context.source_type,
                source_name=context.source_name,
                source_id=context.source_id,
                source_hash=context.source_hash,
                source_record_reference=context.source_record_reference,
                raw_record_hash=raw_hash,
                adapter_name=self.name,
                adapter_version=self.version,
            ),
            normalization_warnings=warnings,
        )


class CasasAdapter(CanonicalAdapter):
    source_type = CanonicalSourceType.CASAS
    name = "casas_canonical"

    def normalize(self, record: dict[str, Any], context: NormalizationContext) -> CanonicalEvent:
        view = RecordView(record); warnings: list[NormalizationIssue] = []
        try: observed_at = parse_timestamp(view.get("timestamp"), field="timestamp", warnings=warnings, required=True)
        except ValueError as exc: raise AdapterRejection(NormalizationIssue(code="INVALID_TIMESTAMP", message=str(exc), field="timestamp")) from exc
        sensor_id = _required_text(view.get("sensor_id"), "sensor_id"); message = _required_text(view.get("message"), "message")
        device = CanonicalEntity(id=sensor_id, kind=EntityKind.DEVICE, name=sensor_id, device_type=_optional_text(view.get("sensor_type")))
        excluded = RecordView.keys("timestamp", "sensor_id", "sensor_type", "message", "activity", "resident")
        attributes = scalar_attributes(record, excluded_keys=excluded, warnings=warnings)
        if view.get("resident") is not None: attributes["resident"] = str(view.get("resident"))
        return self._build_event(record=record, context=context, observed_at=observed_at, event_type="sensor_state",
            source_event_type=message, source_label=_optional_text(view.get("activity")), warnings=warnings,
            device=device, target=device, action=normalized_token(message), attributes=attributes)


class TonIotTelemetryAdapter(CanonicalAdapter):
    source_type = CanonicalSourceType.TON_IOT_TELEMETRY
    name = "ton_iot_telemetry"

    def normalize(self, record: dict[str, Any], context: NormalizationContext) -> CanonicalEvent:
        view = RecordView(record); warnings: list[NormalizationIssue] = []
        try: observed_at = parse_timestamp(view.get("ts"), field="ts", warnings=warnings, required=True)
        except ValueError as exc: raise AdapterRejection(NormalizationIssue(code="INVALID_TIMESTAMP", message=str(exc), field="ts")) from exc
        source_type = _required_text(view.get("type"), "type")
        device_id = _optional_text(view.get("device_id", "sensor_id")) or f"ton:{normalized_token(source_type) or 'telemetry'}"
        device = CanonicalEntity(id=device_id, kind=EntityKind.DEVICE, name=device_id, device_type=normalized_token(source_type))
        excluded = RecordView.keys("ts", "label", "type", "device_id", "sensor_id")
        return self._build_event(record=record, context=context, observed_at=observed_at, event_type="telemetry",
            source_event_type=source_type, source_label=_optional_text(view.get("label")), warnings=warnings,
            device=device, target=device, attributes=scalar_attributes(record, excluded_keys=excluded, warnings=warnings))


class SimulatedAdapter(CanonicalAdapter):
    source_type = CanonicalSourceType.SIMULATED
    name = "simulated"

    def normalize(self, record: dict[str, Any], context: NormalizationContext) -> CanonicalEvent:
        view = RecordView(record)
        warnings: list[NormalizationIssue] = []
        try:
            observed_at = parse_timestamp(
                view.get("timestamp"), field="timestamp", warnings=warnings, required=True
            )
        except ValueError as exc:
            raise AdapterRejection(
                NormalizationIssue(code="INVALID_TIMESTAMP", message=str(exc), field="timestamp")
            ) from exc
        device_id = _required_text(view.get("device_id"), "device_id")
        source_event_type = _required_text(view.get("event_type"), "event_type")
        event_type = normalized_token(source_event_type)
        if event_type is None:
            raise AdapterRejection(
                NormalizationIssue(
                    code="INVALID_EVENT_TYPE",
                    message="event_type cannot be normalized",
                    field="event_type",
                )
            )
        device_ip = parse_ip(view.get("device_ip", "ip", "dst_ip"), field="device_ip", warnings=warnings)
        device = CanonicalEntity(
            id=device_id,
            kind=EntityKind.DEVICE,
            name=_optional_text(view.get("device_name")),
            device_type=_optional_text(view.get("device_type")),
            ip=device_ip,
            mac=normalize_mac(view.get("mac", "device_mac"), field="mac", warnings=warnings),
        )
        source_ip = parse_ip(view.get("source_ip", "src_ip"), field="source_ip", warnings=warnings)
        destination_ip = parse_ip(
            view.get("destination_ip", "dst_ip"), field="destination_ip", warnings=warnings
        )
        actor = (
            CanonicalEntity(id=f"ip:{source_ip}", kind=EntityKind.IP_ADDRESS, ip=source_ip)
            if source_ip
            else None
        )
        network = _network(view, warnings, source_ip=source_ip, destination_ip=destination_ip)
        excluded = RecordView.keys(
            "timestamp", "device_id", "event_type", "device_ip", "ip", "dst_ip",
            "device_name", "device_type", "mac", "device_mac", "source_ip", "src_ip",
            "destination_ip", "source_port", "src_port", "destination_port", "dst_port",
            "protocol", "proto", "bytes_sent", "src_bytes", "bytes_received", "dst_bytes",
            "packets_sent", "src_pkts", "packets_received", "dst_pkts", "label", "type",
            "action", "outcome",
        )
        return self._build_event(
            record=record,
            context=context,
            observed_at=observed_at,
            event_type=event_type,
            source_event_type=source_event_type,
            source_label=_optional_text(view.get("label", "type")),
            warnings=warnings,
            device=device,
            actor=actor,
            target=device,
            network=network,
            action=normalized_token(view.get("action")),
            outcome=normalized_token(view.get("outcome")),
            attributes=scalar_attributes(record, excluded_keys=excluded, warnings=warnings),
        )


class SimulationAdapter(SimulatedAdapter):
    source_type = CanonicalSourceType.SIMULATION
    name = "simulation"


class TonIotNetworkAdapter(CanonicalAdapter):
    source_type = CanonicalSourceType.TON_IOT_NETWORK
    name = "ton_iot_network"

    def normalize(self, record: dict[str, Any], context: NormalizationContext) -> CanonicalEvent:
        view = RecordView(record)
        warnings: list[NormalizationIssue] = []
        try:
            observed_at = parse_timestamp(view.get("ts"), field="ts", warnings=warnings, required=True)
        except ValueError as exc:
            raise AdapterRejection(
                NormalizationIssue(code="INVALID_TIMESTAMP", message=str(exc), field="ts")
            ) from exc
        source_ip = _required_ip(view.get("src_ip"), "src_ip")
        destination_ip = _required_ip(view.get("dst_ip"), "dst_ip")
        source_label = _required_text(view.get("label"), "label")
        actor = CanonicalEntity(id=f"ip:{source_ip}", kind=EntityKind.IP_ADDRESS, ip=source_ip)
        target = CanonicalEntity(
            id=f"ip:{destination_ip}", kind=EntityKind.IP_ADDRESS, ip=destination_ip
        )
        supplied_device_id = _optional_text(view.get("device_id"))
        if supplied_device_id is None:
            warnings.append(
                NormalizationIssue(
                    code="DEVICE_ID_UNAVAILABLE",
                    message="The TON_IoT network record does not expose a trusted device identity",
                    field="device_id",
                )
            )
        device = (
            CanonicalEntity(
                id=supplied_device_id,
                kind=EntityKind.DEVICE,
                ip=destination_ip,
            )
            if supplied_device_id
            else None
        )
        network = _network(view, warnings, source_ip=source_ip, destination_ip=destination_ip)
        excluded = RecordView.keys(
            "ts", "src_ip", "dst_ip", "src_port", "dst_port", "proto", "protocol",
            "src_bytes", "dst_bytes", "src_pkts", "dst_pkts", "label", "type",
            "device_id", "conn_state",
        )
        return self._build_event(
            record=record,
            context=context,
            observed_at=observed_at,
            event_type="network_flow",
            source_event_type=_optional_text(view.get("type")),
            source_label=source_label,
            warnings=warnings,
            device=device,
            actor=actor,
            target=target,
            network=network,
            action="network_communication",
            outcome=normalized_token(view.get("conn_state")),
            attributes=scalar_attributes(record, excluded_keys=excluded, warnings=warnings),
        )


class CicIot2023NetworkAdapter(CanonicalAdapter):
    source_type = CanonicalSourceType.CICIOT2023_NETWORK
    name = "ciciot2023_network"

    def normalize(self, record: dict[str, Any], context: NormalizationContext) -> CanonicalEvent:
        view = RecordView(record)
        warnings: list[NormalizationIssue] = []
        _required_text(view.get("flow_duration"), "flow_duration")
        _required_text(view.get("protocol type"), "Protocol Type")
        source_label = _required_text(view.get("label"), "label")
        try:
            observed_at = parse_timestamp(
                view.get("timestamp", "ts", "time"),
                field="timestamp",
                warnings=warnings,
                required=False,
            )
        except ValueError as exc:
            raise AdapterRejection(
                NormalizationIssue(code="INVALID_TIMESTAMP", message=str(exc), field="timestamp")
            ) from exc
        source_ip = parse_ip(view.get("src_ip", "source_ip"), field="src_ip", warnings=warnings)
        destination_ip = parse_ip(
            view.get("dst_ip", "destination_ip"), field="dst_ip", warnings=warnings
        )
        actor = (
            CanonicalEntity(id=f"ip:{source_ip}", kind=EntityKind.IP_ADDRESS, ip=source_ip)
            if source_ip
            else None
        )
        target = (
            CanonicalEntity(
                id=f"ip:{destination_ip}", kind=EntityKind.IP_ADDRESS, ip=destination_ip
            )
            if destination_ip
            else None
        )
        device_id = _optional_text(view.get("device_id", "device"))
        if device_id is None:
            warnings.append(
                NormalizationIssue(
                    code="DEVICE_ID_UNAVAILABLE",
                    message="The selected CICIoT2023 record does not expose a device identity",
                    field="device_id",
                )
            )
        device = (
            CanonicalEntity(
                id=device_id,
                kind=EntityKind.DEVICE,
                ip=destination_ip,
            )
            if device_id
            else None
        )
        network = _network(view, warnings, source_ip=source_ip, destination_ip=destination_ip)
        excluded = RecordView.keys(
            "timestamp", "ts", "time", "src_ip", "source_ip", "dst_ip",
            "destination_ip", "src_port", "source_port", "dst_port", "destination_port",
            "protocol type", "protocol", "proto", "label", "device_id", "device",
        )
        return self._build_event(
            record=record,
            context=context,
            observed_at=observed_at,
            event_type="network_flow",
            source_event_type=None,
            source_label=source_label,
            warnings=warnings,
            device=device,
            actor=actor,
            target=target,
            network=network,
            action="network_communication",
            attributes=scalar_attributes(record, excluded_keys=excluded, warnings=warnings),
        )


class GenericAdapter(CanonicalAdapter):
    source_type = CanonicalSourceType.GENERIC
    name = "generic"

    def normalize(self, record: dict[str, Any], context: NormalizationContext) -> CanonicalEvent:
        view = RecordView(record)
        warnings: list[NormalizationIssue] = []
        try:
            observed_at = parse_timestamp(
                view.get("timestamp", "ts", "time"),
                field="timestamp",
                warnings=warnings,
                required=False,
            )
        except ValueError as exc:
            raise AdapterRejection(
                NormalizationIssue(code="INVALID_TIMESTAMP", message=str(exc), field="timestamp")
            ) from exc
        source_event_type = _optional_text(view.get("event_type", "type"))
        event_type = normalized_token(source_event_type) or "generic_event"
        device_id = _optional_text(view.get("device_id", "device"))
        if device_id is None:
            warnings.append(
                NormalizationIssue(
                    code="DEVICE_ID_UNAVAILABLE",
                    message="The generic record does not expose a device identity",
                    field="device_id",
                )
            )
        device = (
            CanonicalEntity(id=device_id, kind=EntityKind.DEVICE) if device_id else None
        )
        excluded = RecordView.keys("timestamp", "ts", "time", "event_type", "type", "device_id", "device", "label")
        source_label = _optional_text(view.get("label"))
        attributes = scalar_attributes(record, excluded_keys=excluded, warnings=warnings)
        if (
            observed_at is None
            and source_event_type is None
            and device is None
            and source_label is None
            and not attributes
        ):
            raise AdapterRejection(
                NormalizationIssue(
                    code="EMPTY_CANONICAL_RECORD",
                    message="The generic record contains no meaningful canonical event data",
                )
            )
        return self._build_event(
            record=record,
            context=context,
            observed_at=observed_at,
            event_type=event_type,
            source_event_type=source_event_type,
            source_label=source_label,
            warnings=warnings,
            device=device,
            target=device,
            attributes=attributes,
        )


class LiveTelemetryAdapter(CanonicalAdapter):
    source_type = CanonicalSourceType.LIVE_TELEMETRY
    name = "live_telemetry"

    def normalize(self, record: dict[str, Any], context: NormalizationContext) -> CanonicalEvent:
        view = RecordView(record)
        warnings: list[NormalizationIssue] = []
        try:
            observed_at = parse_timestamp(
                view.get("observed_at"), field="observed_at", warnings=warnings, required=True
            )
        except ValueError as exc:
            raise AdapterRejection(
                NormalizationIssue(code="INVALID_TIMESTAMP", message=str(exc), field="observed_at")
            ) from exc
        device_id = _required_text(view.get("device_id"), "device_id")
        source_event_type = _required_text(view.get("event_type"), "event_type")
        event_type = normalized_token(source_event_type)
        if event_type is None:
            raise AdapterRejection(
                NormalizationIssue(
                    code="INVALID_EVENT_TYPE",
                    message="event_type cannot be normalized",
                    field="event_type",
                )
            )
        metrics = record.get("metrics", {})
        attributes = dict(metrics) if isinstance(metrics, dict) else {}
        action = normalized_token(metrics.get("action")) if isinstance(metrics, dict) else None
        outcome = normalized_token(metrics.get("outcome")) if isinstance(metrics, dict) else None
        if event_type == "authentication" and outcome in {"denied", "failure", "failed"}:
            event_type = "authentication_failure"
        sequence = view.get("sequence")
        if sequence is not None:
            attributes["sequence"] = sequence
        device = CanonicalEntity(id=device_id, kind=EntityKind.DEVICE)
        return self._build_event(
            record=record,
            context=context,
            observed_at=observed_at,
            event_type=event_type,
            source_event_type=source_event_type,
            source_label=None,
            warnings=warnings,
            device=device,
            target=device,
            action=action,
            outcome=outcome,
            attributes=attributes,
        )


def _required_text(value: Any, field: str) -> str:
    if value is None or not str(value).strip():
        raise AdapterRejection(
            NormalizationIssue(
                code="MISSING_REQUIRED_FIELD",
                message=f"{field} is required",
                field=field,
            )
        )
    return str(value).strip()


def _optional_text(value: Any) -> str | None:
    if value is None or not str(value).strip():
        return None
    return str(value).strip()[:256]


def _required_ip(value: Any, field: str) -> str:
    warnings: list[NormalizationIssue] = []
    parsed = parse_ip(value, field=field, warnings=warnings)
    if parsed is None:
        raise AdapterRejection(
            NormalizationIssue(
                code="INVALID_REQUIRED_IP",
                message=f"{field} must contain a valid IP address",
                field=field,
            )
        )
    return parsed


def _network(
    view: RecordView,
    warnings: list[NormalizationIssue],
    *,
    source_ip: str | None,
    destination_ip: str | None,
) -> CanonicalNetwork | None:
    source_port = parse_nonnegative_int(
        view.get("source_port", "src_port"), field="source_port", warnings=warnings, maximum=65535
    )
    destination_port = parse_nonnegative_int(
        view.get("destination_port", "dst_port"), field="destination_port", warnings=warnings, maximum=65535
    )
    protocol = normalized_token(view.get("protocol", "proto", "protocol type"))
    bytes_sent = parse_nonnegative_int(
        view.get("bytes_sent", "src_bytes"), field="bytes_sent", warnings=warnings
    )
    bytes_received = parse_nonnegative_int(
        view.get("bytes_received", "dst_bytes"), field="bytes_received", warnings=warnings
    )
    packets_sent = parse_nonnegative_int(
        view.get("packets_sent", "src_pkts"), field="packets_sent", warnings=warnings
    )
    packets_received = parse_nonnegative_int(
        view.get("packets_received", "dst_pkts"), field="packets_received", warnings=warnings
    )
    values = (
        source_ip,
        destination_ip,
        source_port,
        destination_port,
        protocol,
        bytes_sent,
        bytes_received,
        packets_sent,
        packets_received,
    )
    if all(value is None for value in values):
        return None
    return CanonicalNetwork(
        source_ip=source_ip,
        source_port=source_port,
        destination_ip=destination_ip,
        destination_port=destination_port,
        protocol=protocol,
        bytes_sent=bytes_sent,
        bytes_received=bytes_received,
        packets_sent=packets_sent,
        packets_received=packets_received,
    )
