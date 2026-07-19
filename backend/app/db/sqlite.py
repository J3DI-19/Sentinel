import sqlite3
from pathlib import Path


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
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (case_id) REFERENCES cases(id)
            );

            CREATE TABLE IF NOT EXISTS configuration_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        self.connection.commit()

    def is_available(self) -> bool:
        if self.connection is None:
            return False
        self.connection.execute("SELECT 1").fetchone()
        return True

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

