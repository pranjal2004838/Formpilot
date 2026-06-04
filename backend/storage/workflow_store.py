"""SQLite persistence for workflow history and audit trails."""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class WorkflowStore:
    """Persist workflow outcomes and audit events to SQLite."""

    def __init__(self, database_url: str = "sqlite:///./formpilot.db") -> None:
        self.db_path = self._resolve_db_path(database_url)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @staticmethod
    def _resolve_db_path(database_url: str) -> Path:
        prefix = "sqlite:///"
        if not database_url.startswith(prefix):
            raise ValueError("Only sqlite:/// DATABASE_URL is supported.")

        raw = database_url[len(prefix) :]
        path = Path(raw)
        if path.is_absolute():
            return path

        repo_root = Path(__file__).resolve().parents[2]
        return (repo_root / path).resolve()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workflows (
                    workflow_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    step INTEGER DEFAULT 0,
                    step_name TEXT,
                    progress INTEGER DEFAULT 0,
                    message TEXT,
                    document_type TEXT,
                    country TEXT,
                    app_type TEXT,
                    airia_invoked INTEGER DEFAULT 0,
                    slack_sent INTEGER DEFAULT 0,
                    sharepoint_url TEXT,
                    pdf_file_name TEXT,
                    created_at TEXT,
                    completed_at TEXT,
                    duration_ms INTEGER,
                    compliance_score INTEGER,
                    risk_level TEXT,
                    failed_checks INTEGER DEFAULT 0,
                    regulation_tags TEXT,
                    error_text TEXT,
                    result_json TEXT,
                    audit_count INTEGER DEFAULT 0
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS company_accounts (
                    account_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS employee_profiles (
                    profile_id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    dob TEXT,
                    created_at TEXT,
                    status TEXT DEFAULT 'incomplete',
                    FOREIGN KEY (account_id) REFERENCES company_accounts(account_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    event TEXT NOT NULL,
                    details_json TEXT,
                    FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_workflow_audit_lookup
                ON workflow_audit (workflow_id, timestamp)
                """
            )

        # Backwards-compatible schema migration for existing DB files.
        self._ensure_column("workflows", "compliance_score", "INTEGER")
        self._ensure_column("workflows", "risk_level", "TEXT")
        self._ensure_column("workflows", "failed_checks", "INTEGER DEFAULT 0")
        self._ensure_column("workflows", "regulation_tags", "TEXT")
        self._ensure_column("workflows", "profile_id", "TEXT")

    def _ensure_column(self, table_name: str, column_name: str, column_type: str) -> None:
        with self._connect() as conn:
            columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            existing = {row["name"] for row in columns}
            if column_name in existing:
                return
            conn.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
            )

    @staticmethod
    def _duration_ms(created_at: Optional[str], completed_at: Optional[str]) -> Optional[int]:
        if not created_at or not completed_at:
            return None
        try:
            start = datetime.fromisoformat(created_at)
            end = datetime.fromisoformat(completed_at)
            return max(int((end - start).total_seconds() * 1000), 0)
        except ValueError:
            return None

    def persist_workflow(
        self,
        workflow_id: str,
        state: Dict[str, Any],
        request_meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        request_meta = request_meta or {}
        created_at = state.get("created_at")
        completed_at = state.get("completed_at")
        duration_ms = self._duration_ms(created_at, completed_at)

        errors = state.get("errors") or []
        error_text = " | ".join(errors) if errors else None

        validation = state.get("validation") if isinstance(state.get("validation"), dict) else {}
        compliance_score = validation.get("complianceScore")
        try:
            compliance_score = int(compliance_score) if compliance_score is not None else None
        except (TypeError, ValueError):
            compliance_score = None
        risk_level = validation.get("riskLevel")
        failed_checks = len(
            [
                check
                for check in validation.get("validationResults", [])
                if not check.get("passed", False)
            ]
        )
        regulation_tags_json = json.dumps(validation.get("regulationTags") or [])

        result_payload = {
            "profile": state.get("profile"),
            "validation": state.get("validation"),
            "mappings": state.get("mappings"),
            "portal_fields": state.get("portal_fields"),
            "browser_submission": state.get("browser_submission"),
            "pdf_base64": state.get("pdf_base64"),
            "pdf_file_name": state.get("pdf_file_name"),
            "slack_sent": state.get("slack_sent", False),
            "sharepoint_url": state.get("sharepoint_url"),
            "airia_invoked": state.get("orchestrator_invoked", state.get("airia_invoked", False)),
            "mode": state.get("mode", "real"),
            "errors": errors,
            "message": state.get("message"),
        }
        result_json = json.dumps(result_payload, default=str)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO workflows (
                    workflow_id, status, step, step_name, progress, message,
                    document_type, country, app_type, airia_invoked, slack_sent,
                    sharepoint_url, pdf_file_name, created_at, completed_at,
                    duration_ms, compliance_score, risk_level, failed_checks,
                    regulation_tags, error_text, result_json, audit_count, profile_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workflow_id) DO UPDATE SET
                    status = excluded.status,
                    step = excluded.step,
                    step_name = excluded.step_name,
                    progress = excluded.progress,
                    message = excluded.message,
                    document_type = COALESCE(workflows.document_type, excluded.document_type),
                    country = COALESCE(workflows.country, excluded.country),
                    app_type = COALESCE(workflows.app_type, excluded.app_type),
                    airia_invoked = excluded.airia_invoked,
                    slack_sent = excluded.slack_sent,
                    sharepoint_url = excluded.sharepoint_url,
                    pdf_file_name = excluded.pdf_file_name,
                    completed_at = excluded.completed_at,
                    duration_ms = excluded.duration_ms,
                    compliance_score = excluded.compliance_score,
                    risk_level = excluded.risk_level,
                    failed_checks = excluded.failed_checks,
                    regulation_tags = excluded.regulation_tags,
                    error_text = excluded.error_text,
                    result_json = excluded.result_json,
                    audit_count = excluded.audit_count,
                    profile_id = COALESCE(workflows.profile_id, excluded.profile_id)
                """,
                (
                    workflow_id,
                    state.get("status", "running"),
                    state.get("step", 0),
                    state.get("step_name"),
                    state.get("progress", 0),
                    state.get("message"),
                    request_meta.get("document_type") or state.get("document_type"),
                    request_meta.get("country") or state.get("country"),
                    request_meta.get("app_type") or state.get("app_type"),
                    int(bool(state.get("orchestrator_invoked", state.get("airia_invoked", False)))),
                    int(bool(state.get("slack_sent", False))),
                    state.get("sharepoint_url"),
                    state.get("pdf_file_name"),
                    created_at,
                    completed_at,
                    duration_ms,
                    compliance_score,
                    risk_level,
                    failed_checks,
                    regulation_tags_json,
                    error_text,
                    result_json,
                    len(state.get("audit_log") or []),
                    state.get("profile_id")
                ),
            )

            audit_log = state.get("audit_log") or []
            persisted_count = int(state.get("_persisted_audit_count", 0))
            for entry in audit_log[persisted_count:]:
                timestamp = entry.get("timestamp") or datetime.now().isoformat()
                event = entry.get("event", "event")
                details = {
                    k: v for k, v in entry.items() if k not in {"timestamp", "event"}
                }
                conn.execute(
                    """
                    INSERT INTO workflow_audit (workflow_id, timestamp, event, details_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    (workflow_id, timestamp, event, json.dumps(details, default=str)),
                )

            state["_persisted_audit_count"] = len(audit_log)

    def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM workflows WHERE workflow_id = ?", (workflow_id,)
            ).fetchone()
            if not row:
                return None

        record = dict(row)
        payload = {}
        if record.get("result_json"):
            try:
                payload = json.loads(record["result_json"])
            except json.JSONDecodeError:
                payload = {}

        try:
            regulation_tags = json.loads(record.get("regulation_tags") or "[]")
        except json.JSONDecodeError:
            regulation_tags = []

        return {
            "workflow_id": record["workflow_id"],
            "status": record["status"],
            "step": record["step"],
            "step_name": record["step_name"],
            "progress": record["progress"],
            "message": record["message"],
            "document_type": record.get("document_type"),
            "country": record.get("country"),
            "app_type": record.get("app_type"),
            "airia_invoked": bool(record.get("airia_invoked")),
            "compliance_score": record.get("compliance_score"),
            "risk_level": record.get("risk_level"),
            "failed_checks": record.get("failed_checks", 0),
            "regulation_tags": regulation_tags,
            "created_at": record.get("created_at"),
            "completed_at": record.get("completed_at"),
            "audit_count": record.get("audit_count", 0),
            **payload,
        }

    def list_workflows(
        self,
        *,
        limit: int = 100,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        limit = max(1, min(limit, 500))

        query = """
            SELECT workflow_id, status, step, step_name, progress, message,
                   document_type, country, app_type, airia_invoked,
                   created_at, completed_at, duration_ms, audit_count,
                   compliance_score, risk_level, failed_checks
            FROM workflows
        """
        params: List[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY datetime(created_at) DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [
            {
                "workflow_id": r["workflow_id"],
                "status": r["status"],
                "step": r["step"],
                "step_name": r["step_name"],
                "progress": r["progress"],
                "message": r["message"],
                "document_type": r["document_type"],
                "country": r["country"],
                "app_type": r["app_type"],
                "airia_invoked": bool(r["airia_invoked"]),
                "created_at": r["created_at"],
                "completed_at": r["completed_at"],
                "duration_ms": r["duration_ms"],
                "audit_count": r["audit_count"],
                "compliance_score": r["compliance_score"],
                "risk_level": r["risk_level"],
                "failed_checks": r["failed_checks"],
            }
            for r in rows
        ]

    def get_audit_events(self, workflow_id: str) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT timestamp, event, details_json
                FROM workflow_audit
                WHERE workflow_id = ?
                ORDER BY id ASC
                """,
                (workflow_id,),
            ).fetchall()

        events: List[Dict[str, Any]] = []
        for row in rows:
            details = {}
            if row["details_json"]:
                try:
                    details = json.loads(row["details_json"])
                except json.JSONDecodeError:
                    details = {}
            events.append(
                {
                    "timestamp": row["timestamp"],
                    "event": row["event"],
                    **details,
                }
            )
        return events

    def summary_metrics(self) -> Dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS count FROM workflows GROUP BY status"
            ).fetchall()
            status_counts = {r["status"]: r["count"] for r in rows}

            total = sum(status_counts.values())

            avg_duration_row = conn.execute(
                """
                SELECT AVG(duration_ms) AS avg_duration_ms
                FROM workflows
                WHERE status = 'completed' AND duration_ms IS NOT NULL
                """
            ).fetchone()

            avg_compliance_row = conn.execute(
                """
                SELECT AVG(compliance_score) AS avg_compliance_score
                FROM workflows
                WHERE compliance_score IS NOT NULL
                """
            ).fetchone()

            compliant_row = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM workflows
                WHERE status = 'completed' AND risk_level = 'low'
                """
            ).fetchone()

            hitl_triggered = conn.execute(
                "SELECT COUNT(*) AS c FROM workflow_audit WHERE event = 'hitl_triggered'"
            ).fetchone()["c"]

            hitl_decisions = conn.execute(
                "SELECT details_json FROM workflow_audit WHERE event = 'hitl_decision'"
            ).fetchall()

        approved = 0
        rejected = 0
        for row in hitl_decisions:
            try:
                details = json.loads(row["details_json"] or "{}")
            except json.JSONDecodeError:
                details = {}
            if details.get("decision") == "approved":
                approved += 1
            if details.get("decision") == "rejected":
                rejected += 1

        return {
            "total_workflows": total,
            "status_counts": status_counts,
            "completion_rate": (
                round((status_counts.get("completed", 0) / total) * 100, 2)
                if total
                else 0.0
            ),
            "avg_duration_ms": int(avg_duration_row["avg_duration_ms"] or 0),
            "avg_compliance_score": round(float(avg_compliance_row["avg_compliance_score"] or 0.0), 2),
            "compliant_workflows": int(compliant_row["c"] or 0),
            "hitl_triggered": hitl_triggered,
            "hitl_approved": approved,
            "hitl_rejected": rejected,
        }

    def compliance_dashboard(self, *, limit: int = 25) -> Dict[str, Any]:
        """Return compliance KPIs, top violations, and recent workflow history."""
        limit = max(1, min(limit, 200))

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT workflow_id, status, document_type, country, app_type,
                       created_at, completed_at, duration_ms,
                       compliance_score, risk_level, failed_checks,
                       result_json
                FROM workflows
                ORDER BY datetime(created_at) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        total = len(rows)
        eligible_count = 0
        high_risk_count = 0
        score_sum = 0.0
        score_count = 0

        top_violations: Dict[str, int] = defaultdict(int)
        document_breakdown: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"total": 0, "eligible": 0, "score_sum": 0.0, "violations": 0}
        )
        recent_workflows: List[Dict[str, Any]] = []

        for row in rows:
            payload = {}
            if row["result_json"]:
                try:
                    payload = json.loads(row["result_json"])
                except json.JSONDecodeError:
                    payload = {}

            validation = payload.get("validation") if isinstance(payload, dict) else {}
            if not isinstance(validation, dict):
                validation = {}

            checks = validation.get("validationResults") or []
            violations = [check for check in checks if not check.get("passed", False)]
            for violation in violations:
                name = violation.get("check") or "unknown_violation"
                top_violations[name] += 1

            score = row["compliance_score"]
            if score is None:
                score = validation.get("complianceScore")

            if score is not None:
                score_sum += float(score)
                score_count += 1

            risk_level = row["risk_level"] or validation.get("riskLevel") or "unknown"
            if risk_level == "high":
                high_risk_count += 1

            eligible = bool(validation.get("eligible", row["status"] == "completed"))
            if eligible:
                eligible_count += 1

            document_type = row["document_type"] or validation.get("document_type") or "unknown"
            doc_bucket = document_breakdown[document_type]
            doc_bucket["total"] += 1
            doc_bucket["eligible"] += int(eligible)
            doc_bucket["violations"] += len(violations)
            if score is not None:
                doc_bucket["score_sum"] += float(score)

            recent_workflows.append(
                {
                    "workflow_id": row["workflow_id"],
                    "status": row["status"],
                    "document_type": document_type,
                    "country": row["country"],
                    "app_type": row["app_type"],
                    "created_at": row["created_at"],
                    "completed_at": row["completed_at"],
                    "duration_ms": row["duration_ms"],
                    "compliance_score": score,
                    "risk_level": risk_level,
                    "eligible": eligible,
                    "violation_count": len(violations),
                }
            )

        doc_rows: List[Dict[str, Any]] = []
        for document_type, stats in sorted(document_breakdown.items(), key=lambda item: item[0]):
            total_doc = stats["total"]
            doc_rows.append(
                {
                    "document_type": document_type,
                    "total": total_doc,
                    "eligible": stats["eligible"],
                    "compliance_rate": round((stats["eligible"] / total_doc) * 100, 2) if total_doc else 0.0,
                    "avg_compliance_score": round((stats["score_sum"] / total_doc), 2) if total_doc else 0.0,
                    "total_violations": stats["violations"],
                }
            )

        sorted_violations = [
            {"check": check, "count": count}
            for check, count in sorted(top_violations.items(), key=lambda item: item[1], reverse=True)[:10]
        ]

        return {
            "summary": {
                "total_workflows": total,
                "eligible_workflows": eligible_count,
                "compliance_rate": round((eligible_count / total) * 100, 2) if total else 0.0,
                "high_risk_workflows": high_risk_count,
                "avg_compliance_score": round((score_sum / score_count), 2) if score_count else 0.0,
            },
            "top_violations": sorted_violations,
            "document_breakdown": doc_rows,
            "recent_workflows": recent_workflows,
            "generated_at": datetime.now().isoformat(),
        }

    # --- Bulk & Entity Resolution Methods ---

    def create_company_account(self, name: str, account_id: Optional[str] = None) -> str:
        """Create a new company account."""
        import uuid
        if not account_id:
            account_id = str(uuid.uuid4())
        
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO company_accounts (account_id, name, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(account_id) DO NOTHING
                """,
                (account_id, name, datetime.now().isoformat())
            )
        return account_id

    def create_employee_profile(self, account_id: str, full_name: str, dob: Optional[str] = None, profile_id: Optional[str] = None) -> str:
        """Create a new employee profile under an account."""
        import uuid
        if not profile_id:
            profile_id = str(uuid.uuid4())
            
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO employee_profiles (profile_id, account_id, full_name, dob, created_at, status)
                VALUES (?, ?, ?, ?, ?, 'incomplete')
                ON CONFLICT(profile_id) DO NOTHING
                """,
                (profile_id, account_id, full_name, dob, datetime.now().isoformat())
            )
        return profile_id

    def get_company_profiles(self, account_id: str) -> List[Dict[str, Any]]:
        """Get all employee profiles and their associated workflows for a company account."""
        with self._connect() as conn:
            profiles = conn.execute(
                """
                SELECT profile_id, full_name, dob, created_at, status
                FROM employee_profiles
                WHERE account_id = ?
                """,
                (account_id,)
            ).fetchall()
            
            result = []
            for profile in profiles:
                p_dict = dict(profile)
                
                # Fetch related workflows
                workflows = conn.execute(
                    """
                    SELECT workflow_id, document_type, status, compliance_score
                    FROM workflows
                    WHERE profile_id = ?
                    """,
                    (p_dict["profile_id"],)
                ).fetchall()
                
                p_dict["documents"] = [dict(w) for w in workflows]
                result.append(p_dict)
                
        return result
