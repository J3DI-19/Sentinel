"""Prepare label-free HAI or IoT-23 CSV evidence without copying ground truth.

The input remains untouched. The output is deterministic and refuses to retain known
answer columns. Device identity is supplied explicitly so independently prepared
sources can converge on the same canonical device inside one Traceveil case.
"""
from __future__ import annotations

import argparse
import csv
import itertools
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path


FORBIDDEN = {"label", "detailed-label", "detailed_label", "type", "attack", "attack_type", "attack_label", "class", "category"}


def identity(device_id: str, device_name: str | None, device_type: str | None) -> dict[str, str]:
    result = {"device_id": device_id}
    if device_name:
        result["device_name"] = device_name
    if device_type:
        result["device_type"] = device_type
    return result


def prepare_hai(input_path: Path, output_path: Path, device_id: str, timestamp_column: str, device_name: str | None, device_type: str | None) -> None:
    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        require(fields, timestamp_column)
        retained = [field for field in fields if field.casefold() not in FORBIDDEN and field != timestamp_column and field not in {"device_id", "device_name", "device_type"}]
        identifiers = identity(device_id, device_name, device_type)
        write_csv(output_path, ["timestamp", *identifiers, *retained], (
            {"timestamp": row[timestamp_column], **identifiers, **{field: row.get(field, "") for field in retained}}
            for row in reader
        ))


def prepare_iot23(input_path: Path, output_path: Path, device_id: str, device_name: str | None, device_type: str | None) -> None:
    with iot23_reader(input_path) as (rows, fields):
        for field in ("ts", "id.orig_h", "id.resp_h", "proto"):
            require(fields, field)
        retained = [field for field in fields if field.casefold() not in FORBIDDEN and field not in {"device_id", "device_name", "device_type"}]
        identifiers = identity(device_id, device_name, device_type)
        write_csv(output_path, [*identifiers, *retained], (
            {**identifiers, **{field: row.get(field, "") for field in retained}}
            for row in rows
        ))


@contextmanager
def iot23_reader(path: Path) -> Iterator[tuple[Iterator[dict[str, str]], list[str]]]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        first = handle.readline()
        handle.seek(0)
        if first.startswith("#separator"):
            fields: list[str] = []

            def zeek_rows():
                nonlocal fields
                for line in handle:
                    if line.startswith("#fields"):
                        raw = line.rstrip("\r\n").split("\t")[1:]
                        fields = [*raw[:-1], *raw[-1].split("   ")]
                        continue
                    if line.startswith("#") or not line.strip():
                        continue
                    raw = line.rstrip("\r\n").split("\t")
                    values = [*raw[:-1], *raw[-1].split("   ")]
                    if len(values) == len(fields):
                        yield dict(zip(fields, values))

            rows = zeek_rows()
            try:
                first_row = next(rows)
            except StopIteration as exc:
                raise ValueError("input has no Zeek flow records") from exc
            yield itertools.chain((first_row,), rows), fields
            return
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("input has no CSV header")
        yield iter(reader), list(reader.fieldnames)


def require(fields: list[str], field: str) -> None:
    if field not in fields:
        raise ValueError(f"required source column {field!r} is missing")


def write_csv(path: Path, fields: list[str], rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("hai", "iot23"))
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--device-id", required=True, help="Stable physical/logical device ID used across evidence sources")
    parser.add_argument("--device-name", help="Human-readable physical device or testbed name")
    parser.add_argument("--device-type", help="Normalized device type shown in Traceveil")
    parser.add_argument("--timestamp-column", default="timestamp", help="HAI timestamp column; output is always named timestamp")
    args = parser.parse_args()
    if args.kind == "hai":
        prepare_hai(args.input, args.output, args.device_id, args.timestamp_column, args.device_name, args.device_type)
    else:
        prepare_iot23(args.input, args.output, args.device_id, args.device_name, args.device_type)


if __name__ == "__main__":
    main()
