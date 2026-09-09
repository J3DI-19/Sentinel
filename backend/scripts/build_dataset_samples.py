"""Build deterministic, human-sized dataset samples for Traceveil.

Most samples contain 1,000 records. HAI is capped at 300 because every row has
dozens of independently analysed metrics. HAI ground-truth labels are used only
to choose a useful time window and are never copied into the blind evidence file.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import zipfile
from collections import defaultdict
from pathlib import Path


SAMPLE_ROWS = 1_000
HAI_SAMPLE_ROWS = 300


def write_rows(path: Path, fields: list[str], rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_casas(source: Path, target: Path) -> None:
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(itertools.islice(reader, SAMPLE_ROWS))
        fields = list(reader.fieldnames or [])
    if len(rows) != SAMPLE_ROWS:
        raise ValueError(f"CASAS source has only {len(rows)} rows")
    write_rows(target, fields, rows)


def build_ton(source: Path, target: Path) -> None:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        for row in reader:
            grouped[row.get("type", "")].append(row)

    classes = sorted(grouped)
    if not classes:
        raise ValueError("TON_IoT source contains no attack-type classes")
    base, remainder = divmod(SAMPLE_ROWS, len(classes))
    selected: list[dict[str, str]] = []
    for index, label in enumerate(classes):
        quota = base + (1 if index < remainder else 0)
        if len(grouped[label]) < quota:
            raise ValueError(f"TON_IoT class {label!r} has only {len(grouped[label])} rows")
        selected.extend(grouped[label][:quota])
    selected.sort(key=lambda row: (row.get("date", ""), row.get("time", ""), row.get("type", "")))
    write_rows(target, fields, selected)


def build_hai(source_zip: Path, target: Path) -> None:
    start = "2022-08-12 16:20:00"
    with zipfile.ZipFile(source_zip) as archive:
        csv_name = next(name for name in archive.namelist() if name.endswith(".csv"))
        with archive.open(csv_name) as raw:
            import io

            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
            telemetry_fields = [field for field in (reader.fieldnames or []) if field != "timestamp"]
            selected = []
            for row in reader:
                if row["timestamp"] < start:
                    continue
                selected.append(
                    {
                        "timestamp": row["timestamp"],
                        "device_id": "hai-testbed-01",
                        "device_name": "HAI 23.05 industrial testbed",
                        "device_type": "industrial_control_system",
                        **{field: row.get(field, "") for field in telemetry_fields},
                    }
                )
                if len(selected) == HAI_SAMPLE_ROWS:
                    break
    if len(selected) != HAI_SAMPLE_ROWS:
        raise ValueError(f"HAI source yielded only {len(selected)} rows from {start}")
    write_rows(
        target,
        ["timestamp", "device_id", "device_name", "device_type", *telemetry_fields],
        selected,
    )


def build_hai_full(source_dir: Path, target: Path) -> int:
    """Combine the complete HAI 23.05 telemetry release into one importable CSV."""
    archives = [
        *(source_dir / f"hai-train{index}.csv.zip" for index in range(1, 5)),
        *(source_dir / f"hai-test{index}.csv.zip" for index in range(1, 3)),
    ]
    target.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    expected_fields: list[str] | None = None
    with target.open("w", encoding="utf-8", newline="") as output:
        writer: csv.DictWriter | None = None
        for source_zip in archives:
            with zipfile.ZipFile(source_zip) as archive:
                csv_name = next(name for name in archive.namelist() if name.endswith(".csv"))
                with archive.open(csv_name) as raw:
                    import io

                    reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
                    source_fields = list(reader.fieldnames or [])
                    if expected_fields is None:
                        expected_fields = source_fields
                        fields = ["timestamp", "device_id", "device_name", "device_type", *source_fields[1:]]
                        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
                        writer.writeheader()
                    elif source_fields != expected_fields:
                        raise ValueError(f"HAI schema differs in {source_zip.name}")
                    assert writer is not None
                    for row in reader:
                        writer.writerow(
                            {
                                "timestamp": row["timestamp"],
                                "device_id": "hai-testbed-01",
                                "device_name": "HAI 23.05 industrial testbed",
                                "device_type": "industrial_control_system",
                                **{field: row.get(field, "") for field in source_fields[1:]},
                            }
                        )
                        count += 1
    return count


def read_iot23_flows(path: Path):
    fields: list[str] | None = None
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("#fields"):
                raw_fields = line.rstrip("\r\n").split("\t")[1:]
                fields = [*raw_fields[:-1], *raw_fields[-1].split("   ")]
                continue
            if line.startswith("#") or not line.strip():
                continue
            if fields is None:
                raise ValueError(f"IoT-23 file has no #fields header: {path}")
            raw_values = line.rstrip("\r\n").split("\t")
            values = [*raw_values[:-1], *raw_values[-1].split("   ")]
            if len(values) != len(fields):
                continue
            yield dict(zip(fields, values))


def build_iot23(source_root: Path, target: Path) -> None:
    scenarios = [
        ("CTU-Honeypot-Capture-4-1", "iot23-philips-hue-01", "Philips Hue smart LED lamp", "smart_light", False, 290),
        ("CTU-Honeypot-Capture-5-1", "iot23-amazon-echo-01", "Amazon Echo smart assistant", "smart_assistant", False, 290),
        # The complete Somfy capture contains only 130 flows, so all are retained.
        ("CTU-Honeypot-Capture-7-1", "iot23-somfy-lock-01", "Somfy smart door lock", "smart_door_lock", False, 130),
        ("CTU-IoT-Malware-Capture-34-1", "iot23-raspberry-pi-capture-34", "Raspberry Pi malware capture 34", "single_board_computer", True, 290),
    ]
    source_fields = [
        "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p", "proto", "service",
        "duration", "orig_bytes", "resp_bytes", "orig_pkts", "resp_pkts", "conn_state",
    ]
    rows: list[dict[str, str]] = []
    for scenario, device_id, device_name, device_type, malicious_only, quota in scenarios:
        path = next(path for path in source_root.rglob("conn.log.labeled") if scenario in str(path))
        selected = []
        for row in read_iot23_flows(path):
            is_malicious = row.get("label", "").casefold() != "benign"
            if malicious_only and not is_malicious:
                continue
            selected.append(
                {
                    "ts": row["ts"],
                    "device_id": device_id,
                    "device_name": device_name,
                    "device_type": device_type,
                    **{field: row.get(field, "") for field in source_fields},
                    "capture_scenario": scenario,
                }
            )
            if len(selected) == quota:
                break
        if len(selected) != quota:
            raise ValueError(f"IoT-23 scenario {scenario} yielded only {len(selected)} rows")
        rows.extend(selected)
    write_rows(
        target,
        ["ts", "device_id", "device_name", "device_type", *source_fields, "capture_scenario"],
        rows,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[2])
    parser.add_argument("--only", choices=("all", "casas", "ton", "hai", "iot23"), default="all")
    args = parser.parse_args()
    root = args.root.resolve()
    full = root / "datasets" / "full"
    sample = root / "datasets" / "sample"
    if args.only in ("all", "casas"):
        build_casas(full / "import-ready" / "casas-milan-full.csv", sample / "casas-milan-sample.csv")
    if args.only in ("all", "ton"):
        build_ton(full / "import-ready" / "ton-iot-fridge-full.csv", sample / "ton-iot-fridge-sample.csv")
    if args.only in ("all", "hai"):
        build_hai(full / "originals" / "hai-kaggle" / "hai-test1.csv.zip", sample / "hai-ics-blind-sample.csv")
        build_hai_full(
            full / "originals" / "hai-kaggle",
            full / "import-ready" / "hai-23.05-full.csv",
        )
    if args.only in ("all", "iot23"):
        build_iot23(full / "originals" / "iot23-official", sample / "iot23-zeek-blind-sample.csv")


if __name__ == "__main__":
    main()
