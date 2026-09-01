from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from ipaddress import ip_address
import math
from typing import Callable

from app.evidence.schemas import EvidenceSource


ValueValidator = Callable[[str], bool]


def _nonempty(value: str) -> bool:
    return bool(value.strip())


def _nonnegative_number(value: str) -> bool:
    try:
        number = float(value)
        return math.isfinite(number) and number >= 0
    except (TypeError, ValueError):
        return False


def _finite_number(value: str) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _ton_iot_date(value: str) -> bool:
    try:
        datetime.strptime(value.strip(), "%d-%b-%y")
        return True
    except ValueError:
        return False


def _clock_time(value: str) -> bool:
    try:
        datetime.strptime(value.strip(), "%H:%M:%S")
        return True
    except ValueError:
        return False


def _binary_label(value: str) -> bool:
    return value.strip() in {"0", "1"}


def _timestamp(value: str) -> bool:
    value = value.strip()
    if not value:
        return False
    try:
        number = float(value)
        return math.isfinite(number) and number >= 0
    except ValueError:
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            return True
        except ValueError:
            return False


def _ip(value: str) -> bool:
    try:
        ip_address(value.strip())
        return True
    except ValueError:
        return False


@dataclass(frozen=True)
class DatasetProfile:
    name: str
    source: EvidenceSource
    required_columns: tuple[str, ...]
    validators: dict[str, tuple[str, ValueValidator]]


PROFILES: dict[EvidenceSource, DatasetProfile] = {
    EvidenceSource.CASAS: DatasetProfile(
        name="casas_canonical@1.0",
        source=EvidenceSource.CASAS,
        required_columns=("timestamp", "sensor_id", "message"),
        validators={
            "timestamp": ("INVALID_TIMESTAMP", _timestamp),
            "sensor_id": ("MISSING_VALUE", _nonempty),
            "message": ("MISSING_VALUE", _nonempty),
        },
    ),
    EvidenceSource.CASAS_SMART_HOME: DatasetProfile(
        name="casas_milan@1.0",
        source=EvidenceSource.CASAS_SMART_HOME,
        required_columns=("timestamp", "sensor_id", "sensor_message"),
        validators={
            "timestamp": ("INVALID_TIMESTAMP", _timestamp),
            "sensor_id": ("MISSING_SENSOR_ID", _nonempty),
            "sensor_message": ("MISSING_SENSOR_MESSAGE", _nonempty),
        },
    ),
    EvidenceSource.TON_IOT_FRIDGE_TELEMETRY: DatasetProfile(
        name="ton_iot_fridge_telemetry@1.0",
        source=EvidenceSource.TON_IOT_FRIDGE_TELEMETRY,
        required_columns=(
            "date",
            "time",
            "fridge_temperature",
            "temp_condition",
            "label",
            "type",
        ),
        validators={
            "date": ("INVALID_DATE", _ton_iot_date),
            "time": ("INVALID_TIME", _clock_time),
            "fridge_temperature": ("INVALID_TEMPERATURE", _finite_number),
            "temp_condition": ("MISSING_DEVICE_STATE", _nonempty),
            "label": ("INVALID_BINARY_LABEL", _binary_label),
            "type": ("MISSING_ATTACK_TYPE", _nonempty),
        },
    ),
    EvidenceSource.TON_IOT_TELEMETRY: DatasetProfile(
        name="ton_iot_telemetry@1.0",
        source=EvidenceSource.TON_IOT_TELEMETRY,
        required_columns=("ts", "label", "type"),
        validators={
            "ts": ("INVALID_TIMESTAMP", _timestamp),
            "label": ("MISSING_VALUE", _nonempty),
            "type": ("MISSING_VALUE", _nonempty),
        },
    ),
    EvidenceSource.SIMULATED: DatasetProfile(
        name="simulated@1.0",
        source=EvidenceSource.SIMULATED,
        required_columns=("timestamp", "device_id", "event_type"),
        validators={
            "timestamp": ("INVALID_TIMESTAMP", _timestamp),
            "device_id": ("MISSING_VALUE", _nonempty),
            "event_type": ("MISSING_VALUE", _nonempty),
        },
    ),
    EvidenceSource.SIMULATION: DatasetProfile(
        name="simulation@1.0",
        source=EvidenceSource.SIMULATION,
        required_columns=("timestamp", "device_id", "event_type"),
        validators={
            "timestamp": ("INVALID_TIMESTAMP", _timestamp),
            "device_id": ("MISSING_VALUE", _nonempty),
            "event_type": ("MISSING_VALUE", _nonempty),
        },
    ),
    EvidenceSource.TON_IOT_NETWORK: DatasetProfile(
        name="ton_iot_network@1.0",
        source=EvidenceSource.TON_IOT_NETWORK,
        required_columns=("ts", "src_ip", "dst_ip", "label"),
        validators={
            "ts": ("INVALID_TIMESTAMP", _timestamp),
            "src_ip": ("INVALID_IP_ADDRESS", _ip),
            "dst_ip": ("INVALID_IP_ADDRESS", _ip),
            "label": ("MISSING_VALUE", _nonempty),
        },
    ),
    EvidenceSource.CICIOT2023_NETWORK: DatasetProfile(
        name="ciciot2023_network@1.0",
        source=EvidenceSource.CICIOT2023_NETWORK,
        required_columns=("flow_duration", "protocol type", "label"),
        validators={
            "flow_duration": ("INVALID_NUMBER", _nonnegative_number),
            "protocol type": ("INVALID_NUMBER", _nonnegative_number),
            "label": ("MISSING_VALUE", _nonempty),
        },
    ),
    EvidenceSource.GENERIC: DatasetProfile(
        name="generic@1.0",
        source=EvidenceSource.GENERIC,
        required_columns=(),
        validators={},
    ),
}


def get_profile(source: EvidenceSource) -> DatasetProfile:
    return PROFILES[source]
