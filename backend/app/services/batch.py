from __future__ import annotations

import json
from queue import Empty, Full, Queue
from threading import Event, Thread
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from app.analysis.service import AnalysisService
from app.db.sqlite import SQLiteRepository
from app.evidence.authorization import ValidationAuthority
from app.evidence.hashing import sha256_bytes
from app.evidence.schemas import EvidenceSource, EvidenceValidationReport, ValidationStatus
from app.evidence.service import EvidenceValidationService
from app.normalization.schemas import CanonicalEvent
from app.normalization.service import NormalizationService


def utcnow() -> str: return datetime.now(timezone.utc).isoformat()


class BatchInvestigationService:
    def __init__(self, repository: SQLiteRepository, storage_path: str, max_file_size: int, max_issues: int):
        self.repository = repository; self.storage = Path(storage_path).resolve()
        self.storage.mkdir(parents=True, exist_ok=True)
        self.validation_authority = ValidationAuthority()
        self.validator = EvidenceValidationService(
            None,
            max_file_size_bytes=max_file_size,
            max_issues=max_issues,
            validation_authority=self.validation_authority,
        )
        self.normalizer = NormalizationService(self.validation_authority); self.analyzer = AnalysisService()
        self.queue: Queue[tuple[str, str, object | None]] = Queue(maxsize=8)
        self.stop_event = Event()
        self.worker = Thread(target=self._run_worker, name="traceveil-batch-worker", daemon=True)
        self._recover_jobs()
        self.worker.start()

    @property
    def db(self):
        if self.repository.connection is None: raise RuntimeError("repository unavailable")
        return self.repository.connection

    def create_case(self, name: str, description: str, owner: str) -> dict:
        now = utcnow()
        with self.repository.write_lock, self.db:
            cursor = self.db.execute("INSERT INTO cases(name,description,case_type,status,owner,created_at,updated_at) VALUES(?,?,?,?,?,?,?)", (name, description, "batch", "active", owner, now, now))
        return self.get_case(cursor.lastrowid)

    def get_case(self, case_id: int) -> dict:
        with self.repository.write_lock:
            row = self.db.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
        if row is None: raise KeyError("case_not_found")
        return dict(row)

    def start_import(self, case_id: int, filename: str, content: bytes, source: EvidenceSource, configuration: dict, media_type: str | None) -> dict:
        self.get_case(case_id); digest = sha256_bytes(content); import_id = str(uuid4()); now = utcnow()
        directory = (self.storage / digest[:2] / digest).resolve()
        if self.storage not in directory.parents: raise ValueError("unsafe evidence path")
        directory.mkdir(parents=True, exist_ok=True); path = directory / "source"
        if not path.exists(): path.write_bytes(content)
        duplicate = self.repository.find_evidence_by_hash(case_id, digest)
        status = "duplicate" if duplicate else "queued"
        with self.repository.write_lock, self.db:
            self.db.execute("INSERT INTO import_jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (import_id,case_id,str(duplicate) if duplicate else None,filename,str(path),source.value,json.dumps(configuration),status,None,None,now,now))
        if not duplicate: self._enqueue("validate", import_id, media_type)
        return self.get_import(import_id)

    def _enqueue(self, operation: str, import_id: str, argument: object | None = None) -> None:
        try: self.queue.put_nowait((operation, import_id, argument))
        except Full:
            self._job(import_id, "failed", {"code": "worker_queue_full", "message": "The import queue is full.", "retryable": True})

    def _run_worker(self) -> None:
        while not self.stop_event.is_set():
            try: operation, import_id, argument = self.queue.get(timeout=0.2)
            except Empty: continue
            try:
                if operation == "validate": self.validate_import(import_id, argument if isinstance(argument, str) else None)
                else: self.commit_import(import_id, bool(argument))
            except Exception as exc:
                code = (
                    "evidence_content_hash_mismatch"
                    if str(exc) == "evidence_content_hash_mismatch"
                    else f"{operation}_failed"
                )
                try: self._job(import_id, "failed", {"code": code, "message": str(exc), "retryable": False})
                except Exception: pass
            finally: self.queue.task_done()

    def _recover_jobs(self) -> None:
        with self.repository.write_lock, self.db:
            self.db.execute("UPDATE import_jobs SET status='queued' WHERE status='validating'")
            self.db.execute("UPDATE import_jobs SET status='commit_queued' WHERE status IN ('normalizing','analyzing')")
        for row in self.db.execute("SELECT import_id,status,configuration_json FROM import_jobs WHERE status IN ('queued','commit_queued') ORDER BY created_at").fetchall():
            config = json.loads(row["configuration_json"])
            self._enqueue("validate" if row["status"] == "queued" else "commit", row["import_id"], config.get("_media_type") if row["status"] == "queued" else config.get("_allow_partial", False))

    def shutdown(self) -> None:
        self.stop_event.set(); self.worker.join(timeout=2)

    def validate_import(self, import_id: str, media_type: str | None = None) -> None:
        job = self.get_import(import_id); self._job(import_id, "validating")
        if job["status"] == "cancelled": return
        try:
            outcome = self.validator.validate_with_records(filename=job["filename"], content=Path(job["file_path"]).read_bytes(), source_type=EvidenceSource(job["source_type"]), case_id=job["case_id"], media_type=media_type)
            if self.get_import(import_id)["status"] == "cancelled": return
            self.repository.store_evidence_validation(outcome.report)
            status = "rejected" if outcome.report.status == ValidationStatus.REJECTED else "awaiting_commit"
            with self.repository.write_lock, self.db:
                self.db.execute("UPDATE import_jobs SET evidence_id=?,status=?,validation_json=?,updated_at=? WHERE import_id=?", (str(outcome.report.metadata.evidence_id),status,outcome.report.model_dump_json(),utcnow(),import_id))
                self.db.execute("UPDATE evidence_metadata SET file_path=? WHERE evidence_id=?", (job["file_path"],str(outcome.report.metadata.evidence_id)))
        except Exception as exc:
            self._job(import_id, "failed", {"code":"validation_failed","message":str(exc),"retryable":False})

    def request_commit(self, import_id: str, allow_partial: bool) -> dict:
        job = self.get_import(import_id)
        if job["status"] != "awaiting_commit": raise ValueError("import_not_ready")
        report = json.loads(job["validation_json"])
        if report["rejected_records"] and not allow_partial: raise ValueError("partial_confirmation_required")
        config = json.loads(job["configuration_json"]); config["_allow_partial"] = allow_partial
        with self.repository.write_lock, self.db:
            self.db.execute("UPDATE import_jobs SET status='commit_queued',configuration_json=?,updated_at=? WHERE import_id=?", (json.dumps(config), utcnow(), import_id))
        self._enqueue("commit", import_id, allow_partial)
        return self.get_import(import_id)

    def commit_import(self, import_id: str, allow_partial: bool) -> dict:
        job = self.get_import(import_id)
        if job["status"] not in {"awaiting_commit", "commit_queued"}: raise ValueError("import_not_ready")
        report = json.loads(job["validation_json"])
        if report["rejected_records"] and not allow_partial: raise ValueError("partial_confirmation_required")
        self._job(import_id, "normalizing")
        original_report = EvidenceValidationReport.model_validate_json(job["validation_json"])
        stored_content = Path(job["file_path"]).read_bytes()
        if sha256_bytes(stored_content) != original_report.metadata.sha256:
            raise ValueError("evidence_content_hash_mismatch")
        outcome = self.validator.validate_with_records(filename=job["filename"], content=stored_content, source_type=EvidenceSource(job["source_type"]), case_id=job["case_id"])
        fixed_metadata = outcome.report.metadata.model_copy(
            update={
                "evidence_id": UUID(job["evidence_id"]),
                "received_at": original_report.metadata.received_at,
            }
        )
        accepted_records = []
        for record in outcome.accepted_records:
            evidence_id = UUID(job["evidence_id"])
            accepted_records.append(
                record.model_copy(
                    update={
                        "evidence_id": evidence_id,
                        "validation_seal": self.validation_authority.seal(
                            evidence_id=evidence_id,
                            source_type=record.source_type,
                            dataset_profile=record.dataset_profile,
                            validator_version=record.validator_version,
                            source_hash=fixed_metadata.sha256,
                            row_number=record.row_number,
                            raw_record_hash=record.raw_record_hash,
                        ),
                    }
                )
            )
        outcome = outcome.model_copy(
            update={
                "report": outcome.report.model_copy(update={"metadata": fixed_metadata}),
                "accepted_records": accepted_records,
            }
        )
        events: list[tuple[CanonicalEvent, dict]] = []
        for record in outcome.accepted_records:
            result = self.normalizer.normalize_batch_record(metadata=outcome.report.metadata, validated_record=record)
            if result.event is None: raise ValueError("normalization_rejected_validated_record")
            events.append((result.event, record.record))
        prior = [CanonicalEvent.model_validate_json(row[0]) for row in self.db.execute("SELECT canonical_json FROM canonical_events WHERE case_id=?", (job["case_id"],)).fetchall()]
        result = self.analyzer.analyze(case_id=job["case_id"], events=prior + [event for event,_ in events])
        if self.get_import(import_id)["status"] == "cancelled": return self.get_import(import_id)
        final_status = "partial_success" if report["rejected_records"] else "completed"; now=utcnow()
        with self.repository.write_lock, self.db:
            for event, raw in events:
                entity = event.device or event.target or event.actor
                self.db.execute("INSERT OR IGNORE INTO canonical_events VALUES(?,?,?,?,?,?,?,?,?,?,?)", (str(event.event_id),event.case_id,str(event.provenance.evidence_id),event.observed_at.isoformat() if event.observed_at else None,event.ingested_at.isoformat(),event.provenance.origin.value,event.event_type,entity.id if entity else None,event.source_label,json.dumps(raw,sort_keys=True),event.model_dump_json()))
            self._persist_analysis(result, now)
            self.db.execute("UPDATE evidence_metadata SET committed_at=? WHERE evidence_id=?", (now,job["evidence_id"]))
            self.db.execute("UPDATE import_jobs SET status=?,updated_at=? WHERE import_id=?", (final_status,now,import_id))
            self.db.execute("UPDATE cases SET updated_at=? WHERE id=?", (now,job["case_id"]))
        return self.get_import(import_id)

    def _store_artifacts(self, result) -> None:
        groups = {"finding":result.findings,"alert":result.alerts,"incident":result.incidents,"timeline":result.timeline,"graph_node":result.graph.nodes,"graph_edge":result.graph.edges,"aggregate":result.chart_points}
        for kind, items in groups.items():
            for index,item in enumerate(items):
                data=item.model_dump(mode="json"); item_id=str(data.get(f"{kind}_id") or data.get("entry_id") or data.get("node_id") or data.get("edge_id") or f"{kind}:{index}")
                occurred=data.get("occurred_at") or data.get("triggered_at") or data.get("started_at"); severity=data.get("severity"); risk=data.get("risk_score") or data.get("maximum_risk") or (data.get("risk") or {}).get("score")
                self.db.execute("INSERT INTO analysis_artifacts VALUES(?,?,?,?,?,?,?,?)", (str(result.analysis_id),result.case_id,kind,item_id,occurred,severity,risk,json.dumps(data,sort_keys=True)))

    def _persist_analysis(self, result, created_at: str) -> str:
        """Persist a deterministic result once and reject identifier reuse."""

        analysis_id = str(result.analysis_id)
        payload = result.model_dump_json()
        existing = self.db.execute(
            "SELECT result_json, created_at FROM analysis_runs WHERE analysis_id=?",
            (analysis_id,),
        ).fetchone()
        if existing is not None:
            if existing["result_json"] != payload:
                raise ValueError("analysis_id_content_mismatch")
            return existing["created_at"]
        self.db.execute(
            "INSERT INTO analysis_runs VALUES(?,?,?,?,?)",
            (analysis_id, result.case_id, "completed", payload, created_at),
        )
        self._store_artifacts(result)
        return created_at

    def get_import(self, import_id: str) -> dict:
        with self.repository.write_lock:
            row=self.db.execute("SELECT * FROM import_jobs WHERE import_id=?",(import_id,)).fetchone()
        if row is None: raise KeyError("import_not_found")
        return dict(row)

    def _job(self, import_id: str, status: str, error: dict|None=None):
        with self.repository.write_lock, self.db: self.db.execute("UPDATE import_jobs SET status=?,error_json=?,updated_at=? WHERE import_id=?",(status,json.dumps(error) if error else None,utcnow(),import_id))

    def cancel(self, import_id: str) -> dict:
        job=self.get_import(import_id)
        if job["status"] in {"completed","partial_success"}: raise ValueError("completed_import_immutable")
        self._job(import_id,"cancelled"); return self.get_import(import_id)

    def reanalyze(self, case_id: int) -> dict:
        self.get_case(case_id); events=[CanonicalEvent.model_validate_json(row[0]) for row in self.db.execute("SELECT canonical_json FROM canonical_events WHERE case_id=? ORDER BY COALESCE(observed_at,ingested_at),event_id",(case_id,)).fetchall()]
        result=self.analyzer.analyze(case_id=case_id,events=events); now=utcnow()
        existing=self.db.execute("SELECT 1 FROM analysis_runs WHERE analysis_id=?",(str(result.analysis_id),)).fetchone() is not None
        with self.repository.write_lock, self.db:
            created_at = self._persist_analysis(result, now)
        return {"analysis_id":str(result.analysis_id),"case_id":case_id,"status":"completed","created_at":created_at,"reused_existing":existing}
