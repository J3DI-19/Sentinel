import sqlite3

from app.db.sqlite import SQLiteRepository


def test_step_one_database_is_migrated_without_losing_existing_metadata(tmp_path):
    database_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(database_path)
    connection.executescript(
        """
        CREATE TABLE cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE evidence_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER,
            source_name TEXT NOT NULL,
            source_hash TEXT,
            adapter_version TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO evidence_metadata (source_name, source_hash)
        VALUES ('existing.csv', 'existing-hash');
        """
    )
    connection.close()

    repository = SQLiteRepository(f"sqlite:///{database_path}")
    repository.initialize()

    columns = {
        row["name"]
        for row in repository.connection.execute("PRAGMA table_info(evidence_metadata)")
    }
    case_columns = {
        row["name"]
        for row in repository.connection.execute("PRAGMA table_info(cases)")
    }
    tables = {
        row["name"]
        for row in repository.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    existing = repository.connection.execute(
        "SELECT source_name, source_hash FROM evidence_metadata"
    ).fetchone()
    assert {"evidence_id", "validator_version", "validation_status"} <= columns
    assert {"description", "status"} <= case_columns
    assert {"canonical_events", "analysis_runs"} <= tables
    assert dict(existing) == {
        "source_name": "existing.csv",
        "source_hash": "existing-hash",
    }
    repository.close()
