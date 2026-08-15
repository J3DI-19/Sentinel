from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.main import create_app


def rendered_schema() -> str:
    return json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Traceveil's deterministic OpenAPI contract")
    parser.add_argument("output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = rendered_schema()
    if args.check:
        return 0 if args.output.exists() and args.output.read_text(encoding="utf-8") == rendered else 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
