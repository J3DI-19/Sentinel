import sqlite3
from pathlib import Path
from uuid import UUID

from app.evidence.schemas import EvidenceValidationReport


class SQLiteRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.connection: sqlite3.Connection | None = None

    def _database_path(self) -> str:
        if self.database_url == "sqlite:///:memory:":
            return ":memory:"
        if not self.database_url.startswith("sqlite:///"):
            raise ValueError("DATABASE_URL must use the sqlite:/// scheme")
        path = self.database_url.removeprefix("sqlite:///")
        database_path = Path(path)
        if not database_path.is_absolute():
            database_path = Path.cwd() / database_path
        database_path.parent.mkdir(parents=True, exist_ok=True)
        return str(database_path)

    def initialize(self) -> None:
        if self.connection is None:
            self.connection = sqlite3.connect(self._database_path())
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS evidence_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER,
                source_name TEXT NOT NULL,
                source_hash TEXT,
                adapter_version TEXT,
                evidence_id TEXT UNIQUE,
                original_filename TEXT,
                sanitized_filename TEXT,
                media_type TEXT,
                byte_size INTEGER,
                source_type TEXT,
                dataset_profile TEXT,
                validator_version TEXT,
                validation_status TEXT,
                total_records INTEGER,
                accepted_records INTEGER,
                rejected_records INTEGER,
                received_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (case_id) REFERENCES cases(id)
            );

            CREATE TABLE IF NOT EXISTS evidence_validation_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evidence_metadata_id INTEGER NOT NULL,
                level TEXT NOT NULL,
                error_code TEXT NOT NULL,
                message TEXT NOT NULL,
                row_number INTEGER,
                field_name TEXT,
                rejected_value TEXT,
                FOREIGN KEY (evidence_metadata_id) REFERENCES evidence_metadata(id)
            );

            CREATE TABLE IF NOT EXISTS configuration_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        self._migrate_evidence_metadata()
        self.connection.commit()

    def _migrate_evidence_metadata(self) -> None:
        """Add Step 3 columns when opening a database created by Step 1."""

        if self.connection is None:
            raise RuntimeError("repository is not initialized")
        existing = {
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(evidence_metadata)").fetchall()
        }
        columns = {
            "evidence_id": "TEXT",
            "original_filename": "TEXT",
            "sanitized_filename": "TEXT",
            "media_type": "TEXT",
            "byte_size": "INTEGER",
            "source_type": "TEXT",
            "dataset_profile": "TEXT",
            "validator_version": "TEXT",
            "validation_status": "TEXT",
            "total_records": "INTEGER",
            "accepted_records": "INTEGER",
            "rejected_records": "INTEGER",
            "received_at": "TEXT",
        }
        for name, definition in columns.items():
            if name not in existing:
                # Names and definitions are constants declared above, never user input.
                self.connection.execute(
                    f"ALTER TABLE evidence_metadata ADD COLUMN {name} {definition}"
                )
        self.connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_evidence_metadata_evidence_id
            ON evidence_metadata(evidence_id)
            WHERE evidence_id IS NOT NULL
            """
        )

    def is_available(self) -> bool:
        if self.connection is None:
            return False
        self.connection.execute("SELECT 1").fetchone()
        return True

    def find_evidence_by_hash(self, case_id: int, source_hash: str) -> UUID | None:
        if self.connection is None:
            raise RuntimeError("repository is not initialized")
        row = self.connection.execute(
            """
            SELECT evidence_id
            FROM evidence_metadata
            WHERE case_id = ? AND source_hash = ? AND evidence_id IS NOT NULL
            ORDER BY id ASC
            LIMIT 1
            """,
            (case_id, source_hash),
        ).fetchone()
        return UUID(row["evidence_id"]) if row is not None else None

    def store_evidence_validation(self, report: EvidenceValidationReport) -> None:
        if self.connection is None:
            raise RuntimeError("repository is not initialized")
        metadata = report.metadata
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO evidence_metadata (
                    case_id, source_name, source_hash, adapter_version,
                    evidence_id, original_filename, sanitized_filename, media_type,
                    byte_size, source_type, dataset_profile, validator_version,
                    validation_status, total_records, accepted_records, rejected_records,
                    received_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metadata.case_id,
                    metadata.sanitized_filename,
                    metadata.sha256,
                    None,
                    str(metadata.evidence_id),
                    metadata.original_filename,
                    metadata.sanitized_filename,
                    metadata.media_type,
                    metadata.byte_size,
                    metadata.source_type.value,
                    metadata.dataset_profile,
                    metadata.validator_version,
                    report.status.value,
                    report.total_records,
                    report.accepted_records,
                    report.rejected_records,
                    metadata.received_at.isoformat(),
                ),
            )
            evidence_metadata_id = cursor.lastrowid
            self.connection.executemany(
                """
                INSERT INTO evidence_validation_issues (
                    evidence_metadata_id, level, error_code, message,
                    row_number, field_name, rejected_value
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        evidence_metadata_id,
                        issue.level.value,
                        issue.code,
                        issue.message,
                        issue.row_number,
                        issue.field,
                        issue.rejected_value,
                    )
                    for issue in report.issues
                ],
            )

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

