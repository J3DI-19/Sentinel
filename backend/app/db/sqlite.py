import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from app.analysis.schemas import AnalysisResult
from app.evidence.schemas import (
    EvidenceMetadata,
    EvidenceSource,
    EvidenceValidationIssue,
    EvidenceValidationReport,
    IssueLevel,
    ValidationStatus,
)
from app.investigation.schemas import AnalysisRunSummary, CaseCreate, CaseRecord
from app.normalization.schemas import CanonicalEvent


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
                description TEXT,
                status TEXT NOT NULL DEFAULT 'open',
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

            CREATE TABLE IF NOT EXISTS canonical_events (
                event_id TEXT PRIMARY KEY,
                case_id INTEGER NOT NULL,
                evidence_id TEXT NOT NULL,
                observed_at TEXT,
                ingested_at TEXT NOT NULL,
                event_type TEXT NOT NULL,
                origin TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (case_id) REFERENCES cases(id)
            );

            CREATE INDEX IF NOT EXISTS idx_canonical_events_case
            ON canonical_events(case_id, observed_at, ingested_at, event_id);

            CREATE INDEX IF NOT EXISTS idx_canonical_events_evidence
            ON canonical_events(evidence_id);

            CREATE TABLE IF NOT EXISTS analysis_runs (
                analysis_id TEXT PRIMARY KEY,
                case_id INTEGER NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (case_id) REFERENCES cases(id)
            );

            CREATE INDEX IF NOT EXISTS idx_analysis_runs_case
            ON analysis_runs(case_id, created_at DESC, analysis_id);
            """
        )
        self._migrate_cases()
        self._migrate_evidence_metadata()
        self.connection.commit()

    def _migrate_cases(self) -> None:
        if self.connection is None:
            raise RuntimeError("repository is not initialized")
        existing = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(cases)")
        }
        additions = {"description": "TEXT", "status": "TEXT NOT NULL DEFAULT 'open'"}
        for name, definition in additions.items():
            if name not in existing:
                self.connection.execute(
                    f"ALTER TABLE cases ADD COLUMN {name} {definition}"
                )

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

    def create_case(self, case: CaseCreate) -> CaseRecord:
        connection = self._require_connection()
        now = datetime.now(timezone.utc).isoformat()
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO cases (name, description, status, created_at)
                VALUES (?, ?, 'open', ?)
                """,
                (case.name, case.description, now),
            )
        created = self.get_case(cursor.lastrowid)
        if created is None:
            raise RuntimeError("created case could not be read back")
        return created

    def list_cases(self) -> list[CaseRecord]:
        connection = self._require_connection()
        rows = connection.execute(
            "SELECT id, name, description, status, created_at FROM cases ORDER BY id"
        ).fetchall()
        return [self._case_from_row(row) for row in rows]

    def get_case(self, case_id: int) -> CaseRecord | None:
        connection = self._require_connection()
        row = connection.execute(
            """
            SELECT id, name, description, status, created_at
            FROM cases WHERE id = ?
            """,
            (case_id,),
        ).fetchone()
        return self._case_from_row(row) if row is not None else None

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

    def list_evidence(self, case_id: int) -> list[EvidenceValidationReport]:
        connection = self._require_connection()
        rows = connection.execute(
            """
            SELECT * FROM evidence_metadata
            WHERE case_id = ? AND evidence_id IS NOT NULL
            ORDER BY id
            """,
            (case_id,),
        ).fetchall()
        return [self._evidence_report_from_row(row) for row in rows]

    def get_evidence(
        self, case_id: int, evidence_id: UUID
    ) -> EvidenceValidationReport | None:
        connection = self._require_connection()
        row = connection.execute(
            """
            SELECT * FROM evidence_metadata
            WHERE case_id = ? AND evidence_id = ?
            """,
            (case_id, str(evidence_id)),
        ).fetchone()
        return self._evidence_report_from_row(row) if row is not None else None

    def store_canonical_events(self, events: list[CanonicalEvent]) -> None:
        if not events:
            return
        connection = self._require_connection()
        with connection:
            for event in events:
                payload = event.model_dump_json()
                existing = connection.execute(
                    "SELECT payload_json FROM canonical_events WHERE event_id = ?",
                    (str(event.event_id),),
                ).fetchone()
                if existing is not None:
                    if existing["payload_json"] != payload:
                        raise ValueError(
                            "a canonical event ID cannot be reused for different content"
                        )
                    continue
                connection.execute(
                    """
                    INSERT INTO canonical_events (
                        event_id, case_id, evidence_id, observed_at, ingested_at,
                        event_type, origin, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(event.event_id),
                        event.case_id,
                        str(event.provenance.evidence_id),
                        event.observed_at.isoformat() if event.observed_at else None,
                        event.ingested_at.isoformat(),
                        event.event_type,
                        event.provenance.origin.value,
                        payload,
                    ),
                )

    def list_canonical_events(self, case_id: int) -> list[CanonicalEvent]:
        connection = self._require_connection()
        rows = connection.execute(
            """
            SELECT payload_json FROM canonical_events
            WHERE case_id = ?
            ORDER BY observed_at IS NULL, observed_at, ingested_at, event_id
            """,
            (case_id,),
        ).fetchall()
        return [CanonicalEvent.model_validate_json(row["payload_json"]) for row in rows]

    def get_canonical_event(
        self, case_id: int, event_id: UUID
    ) -> CanonicalEvent | None:
        connection = self._require_connection()
        row = connection.execute(
            """
            SELECT payload_json FROM canonical_events
            WHERE case_id = ? AND event_id = ?
            """,
            (case_id, str(event_id)),
        ).fetchone()
        return CanonicalEvent.model_validate_json(row["payload_json"]) if row else None

    def store_analysis(self, result: AnalysisResult) -> None:
        connection = self._require_connection()
        now = datetime.now(timezone.utc).isoformat()
        with connection:
            payload = result.model_dump_json()
            existing = connection.execute(
                "SELECT result_json FROM analysis_runs WHERE analysis_id = ?",
                (str(result.analysis_id),),
            ).fetchone()
            if existing is not None:
                if existing["result_json"] != payload:
                    raise ValueError(
                        "an analysis ID cannot be reused for different content"
                    )
                return
            connection.execute(
                """
                INSERT INTO analysis_runs (analysis_id, case_id, result_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (str(result.analysis_id), result.case_id, payload, now),
            )

    def get_analysis(
        self, case_id: int, analysis_id: UUID
    ) -> AnalysisResult | None:
        connection = self._require_connection()
        row = connection.execute(
            """
            SELECT result_json FROM analysis_runs
            WHERE case_id = ? AND analysis_id = ?
            """,
            (case_id, str(analysis_id)),
        ).fetchone()
        return AnalysisResult.model_validate_json(row["result_json"]) if row else None

    def get_latest_analysis(self, case_id: int) -> AnalysisResult | None:
        connection = self._require_connection()
        row = connection.execute(
            """
            SELECT result_json FROM analysis_runs
            WHERE case_id = ?
            ORDER BY created_at DESC, analysis_id DESC LIMIT 1
            """,
            (case_id,),
        ).fetchone()
        return AnalysisResult.model_validate_json(row["result_json"]) if row else None

    def list_analysis_runs(self, case_id: int) -> list[AnalysisRunSummary]:
        connection = self._require_connection()
        rows = connection.execute(
            """
            SELECT result_json, created_at FROM analysis_runs
            WHERE case_id = ? ORDER BY created_at DESC, analysis_id DESC
            """,
            (case_id,),
        ).fetchall()
        summaries = []
        for row in rows:
            result = AnalysisResult.model_validate_json(row["result_json"])
            summaries.append(
                AnalysisRunSummary(
                    analysis_id=result.analysis_id,
                    case_id=result.case_id,
                    analyzed_event_count=result.analyzed_event_count,
                    finding_count=len(result.findings),
                    alert_count=len(result.alerts),
                    incident_count=len(result.incidents),
                    filter=result.filter,
                    created_at=row["created_at"],
                )
            )
        return summaries

    def _evidence_report_from_row(self, row: sqlite3.Row) -> EvidenceValidationReport:
        connection = self._require_connection()
        issue_rows = connection.execute(
            """
            SELECT level, error_code, message, row_number, field_name, rejected_value
            FROM evidence_validation_issues
            WHERE evidence_metadata_id = ? ORDER BY id
            """,
            (row["id"],),
        ).fetchall()
        metadata = EvidenceMetadata(
            evidence_id=row["evidence_id"],
            case_id=row["case_id"],
            original_filename=row["original_filename"],
            sanitized_filename=row["sanitized_filename"],
            media_type=row["media_type"],
            byte_size=row["byte_size"],
            sha256=row["source_hash"],
            source_type=EvidenceSource(row["source_type"]),
            dataset_profile=row["dataset_profile"],
            validator_version=row["validator_version"],
            received_at=row["received_at"],
        )
        return EvidenceValidationReport(
            metadata=metadata,
            status=ValidationStatus(row["validation_status"]),
            total_records=row["total_records"],
            accepted_records=row["accepted_records"],
            rejected_records=row["rejected_records"],
            issues=[
                EvidenceValidationIssue(
                    level=IssueLevel(issue["level"]),
                    code=issue["error_code"],
                    message=issue["message"],
                    row_number=issue["row_number"],
                    field=issue["field_name"],
                    rejected_value=issue["rejected_value"],
                )
                for issue in issue_rows
            ],
        )

    @staticmethod
    def _case_from_row(row: sqlite3.Row) -> CaseRecord:
        return CaseRecord(
            case_id=row["id"],
            name=row["name"],
            description=row["description"],
            status=row["status"],
            created_at=row["created_at"],
        )

    def _require_connection(self) -> sqlite3.Connection:
        if self.connection is None:
            raise RuntimeError("repository is not initialized")
        return self.connection

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

