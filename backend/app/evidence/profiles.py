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
