from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from ipaddress import ip_address
from typing import Any

from app.evidence.hashing import sha256_record
from app.normalization.schemas import CanonicalScalar, NormalizationIssue


_NAME_SEPARATOR = re.compile(r"[^a-z0-9]+")
_MAC_COMPACT = re.compile(r"^[0-9a-f]{12}$")
_INTEGER_TEXT = re.compile(r"^-?(?:0|[1-9][0-9]*)$")
_FLOAT_TEXT = re.compile(
    r"^-?(?:(?:0|[1-9][0-9]*)\.[0-9]+|(?:0|[1-9][0-9]*)(?:[eE][+-]?[0-9]+)|"
    r"(?:0|[1-9][0-9]*)\.[0-9]+(?:[eE][+-]?[0-9]+))$"
)


def normalized_key(value: str) -> str:
    return _NAME_SEPARATOR.sub("_", value.strip().casefold()).strip("_")


def normalized_token(value: Any) -> str | None:
    if value is None:
        return None
    token = normalized_key(str(value))
    return token or None


def record_hash(record: dict[str, Any]) -> str:
    return sha256_record(record)


def parse_timestamp(
    value: Any,
    *,
    field: str,
    warnings: list[NormalizationIssue],
    required: bool,
) -> datetime | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ValueError(f"{field} is required")
        warnings.append(
            NormalizationIssue(
                code="OBSERVED_TIME_UNAVAILABLE",
                message="The source record does not contain an observed timestamp",
                field=field,
            )
        )
        return None

    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        try:
            number = float(text)
        except ValueError:
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError(f"{field} is not a supported timestamp") from exc
        else:
            if not math.isfinite(number) or number < 0:
                raise ValueError(f"{field} must be a finite non-negative timestamp")
            if number >= 100_000_000_000_000:
                number /= 1_000_000
            elif number >= 100_000_000_000:
                number /= 1_000
            try:
                parsed = datetime.fromtimestamp(number, tz=timezone.utc)
            except (OSError, OverflowError, ValueError) as exc:
                raise ValueError(f"{field} is outside the supported timestamp range") from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        warnings.append(
            NormalizationIssue(
                code="ASSUMED_UTC",
                message="A timezone-naive source timestamp was explicitly interpreted as UTC",
                field=field,
                source_value=str(value)[:256],
            )
        )
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_ip(
    value: Any,
    *,
    field: str,
    warnings: list[NormalizationIssue],
) -> str | None:
    if value is None or not str(value).strip():
        return None
    try:
        return str(ip_address(str(value).strip()))
    except ValueError:
        warnings.append(
            NormalizationIssue(
                code="INVALID_OPTIONAL_IP",
                message="An optional IP address could not be normalized and was omitted",
                field=field,
                source_value=str(value)[:256],
            )
        )
        return None


def parse_nonnegative_int(
    value: Any,
    *,
    field: str,
    warnings: list[NormalizationIssue],
    maximum: int | None = None,
) -> int | None:
    if value is None or not str(value).strip():
        return None
    try:
        number = float(str(value).strip())
    except ValueError:
        number = math.nan
    if not math.isfinite(number) or number < 0 or not number.is_integer():
        warnings.append(
            NormalizationIssue(
                code="INVALID_OPTIONAL_INTEGER",
                message="An optional integer could not be normalized and was omitted",
                field=field,
                source_value=str(value)[:256],
            )
        )
        return None
    integer = int(number)
    if maximum is not None and integer > maximum:
        warnings.append(
            NormalizationIssue(
                code="OPTIONAL_INTEGER_OUT_OF_RANGE",
                message=f"An optional integer exceeded the maximum {maximum} and was omitted",
                field=field,
                source_value=str(value)[:256],
            )
        )
        return None
    return integer


def normalize_mac(
    value: Any,
    *,
    field: str,
    warnings: list[NormalizationIssue],
) -> str | None:
    if value is None or not str(value).strip():
        return None
    compact = re.sub(r"[^0-9a-f]", "", str(value).casefold())
    if not _MAC_COMPACT.fullmatch(compact):
        warnings.append(
            NormalizationIssue(
                code="INVALID_OPTIONAL_MAC",
                message="An optional MAC address could not be normalized and was omitted",
                field=field,
                source_value=str(value)[:256],
            )
        )
        return None
    return ":".join(compact[index : index + 2] for index in range(0, 12, 2))


def scalar_attributes(
    record: dict[str, Any],
    *,
    excluded_keys: set[str],
    warnings: list[NormalizationIssue],
) -> dict[str, CanonicalScalar]:
    attributes: dict[str, CanonicalScalar] = {}
    for original_key, value in record.items():
        key = normalized_key(str(original_key))
        if not key or key in excluded_keys:
            continue
        if isinstance(value, str):
            scalar = infer_scalar(value)
        elif isinstance(value, (int, bool)) or value is None:
            scalar: CanonicalScalar = value
        elif isinstance(value, float) and math.isfinite(value):
            scalar = value
        else:
            warnings.append(
                NormalizationIssue(
                    code="UNSUPPORTED_ATTRIBUTE_VALUE",
                    message="A non-scalar or non-finite attribute was omitted",
                    field=str(original_key),
                )
            )
            continue
        if key in attributes:
            warnings.append(
                NormalizationIssue(
                    code="ATTRIBUTE_NAME_COLLISION",
                    message="Two source fields normalized to the same attribute name; the later value was omitted",
                    field=str(original_key),
                )
            )
            continue
        attributes[key] = scalar
    return attributes


def infer_scalar(value: str) -> CanonicalScalar:
    """Conservatively type flat CSV values while preserving ambiguous identifiers."""

    stripped = value.strip()
    folded = stripped.casefold()
    if folded == "true":
        return True
    if folded == "false":
        return False
    if _INTEGER_TEXT.fullmatch(stripped):
        return int(stripped)
    if _FLOAT_TEXT.fullmatch(stripped):
        parsed = float(stripped)
        if math.isfinite(parsed):
            return parsed
    return value


class AmbiguousRecordFields(ValueError):
    def __init__(self, normalized_name: str, first_name: str, second_name: str):
        self.normalized_name = normalized_name
        self.first_name = first_name
        self.second_name = second_name
        super().__init__(
            f"{first_name!r} and {second_name!r} both normalize to {normalized_name!r}"
        )


class RecordView:
    def __init__(self, record: dict[str, Any]):
        self.original = record
        self.values: dict[str, Any] = {}
        source_names: dict[str, str] = {}
        for key, value in record.items():
            source_name = str(key)
            normalized_name = normalized_key(source_name)
            if normalized_name in self.values:
                raise AmbiguousRecordFields(
                    normalized_name,
                    source_names[normalized_name],
                    source_name,
                )
            self.values[normalized_name] = value
            source_names[normalized_name] = source_name

    def get(self, *aliases: str) -> Any:
        for alias in aliases:
            key = normalized_key(alias)
            if key in self.values:
                return self.values[key]
        return None

    @staticmethod
    def keys(*aliases: str) -> set[str]:
        return {normalized_key(alias) for alias in aliases}
