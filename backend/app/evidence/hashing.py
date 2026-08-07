import hashlib
import json
from typing import Any


def sha256_bytes(content: bytes) -> str:
    """Return the lowercase SHA-256 digest of the original evidence bytes."""

    return hashlib.sha256(content).hexdigest()


def sha256_record(record: dict[str, Any]) -> str:
    """Return a stable SHA-256 digest for a parsed evidence record."""

    serialized = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()
