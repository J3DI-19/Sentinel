from pathlib import Path

from export_openapi import rendered_schema


def test_checked_in_openapi_contract_has_not_drifted():
    contract = Path(__file__).parents[2] / "frontend" / "src" / "api" / "openapi.json"
    assert contract.read_text(encoding="utf-8") == rendered_schema(), (
        "OpenAPI drift detected; run backend/export_openapi.py and npm run api:types"
    )
