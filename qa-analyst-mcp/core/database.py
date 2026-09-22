"""
database.py — Capa de persistencia SQLite para el QA Intelligence Suite v2.0

Tablas:
  - operations_log    : registro de cada operacion del pipeline
  - token_usage       : historial de uso de tokens por sesion
  - documents         : documentos procesados con metadatos
  - test_cases        : casos de prueba generados
  - sessions          : sesiones de trabajo
  - audit_trail       : auditoria completa de acciones
"""
from __future__ import annotations

import sqlite3
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


DB_PATH = Path("output/qa_suite.db")


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Crea todas las tablas si no existen."""
    with get_connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id          TEXT PRIMARY KEY,
            project     TEXT NOT NULL,
            doc_name    TEXT,
            started_at  TEXT NOT NULL,
            ended_at    TEXT,
            status      TEXT DEFAULT 'active',
            org_mode    INTEGER DEFAULT 2,
            detail_level INTEGER DEFAULT 3
        );

        CREATE TABLE IF NOT EXISTS operations_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT,
            timestamp   TEXT NOT NULL,
            level       TEXT NOT NULL,
            module      TEXT NOT NULL,
            action      TEXT NOT NULL,
            message     TEXT,
            details     TEXT,
            duration_ms INTEGER,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );

        CREATE TABLE IF NOT EXISTS token_usage (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id        TEXT,
            timestamp         TEXT NOT NULL,
            agent_type        TEXT NOT NULL,
            model             TEXT,
            prompt_tokens     INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            total_tokens      INTEGER DEFAULT 0,
            cost_usd          REAL DEFAULT 0.0,
            project           TEXT,
            action            TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );

        CREATE TABLE IF NOT EXISTS documents (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            project      TEXT NOT NULL,
            doc_name     TEXT NOT NULL,
            doc_hash     TEXT NOT NULL,
            version      INTEGER DEFAULT 1,
            rules_count  INTEGER DEFAULT 0,
            cases_count  INTEGER DEFAULT 0,
            processed_at TEXT NOT NULL,
            deliverables TEXT,
            status       TEXT DEFAULT 'completed'
        );

        CREATE TABLE IF NOT EXISTS test_cases (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id         TEXT NOT NULL,
            document_id     INTEGER,
            project         TEXT NOT NULL,
            name            TEXT NOT NULL,
            dimension       TEXT,
            objective       TEXT,
            precondition    TEXT,
            steps           TEXT,
            test_data       TEXT,
            expected_result TEXT,
            priority        TEXT,
            level           TEXT,
            type            TEXT,
            technique       TEXT,
            requirement_ref TEXT,
            risk            TEXT,
            automation      TEXT,
            estimated_min   INTEGER,
            created_at      TEXT NOT NULL,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        );

        CREATE TABLE IF NOT EXISTS audit_trail (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            session_id  TEXT,
            user_action TEXT NOT NULL,
            entity_type TEXT,
            entity_id   TEXT,
            old_value   TEXT,
            new_value   TEXT,
            ip_address  TEXT DEFAULT 'localhost'
        );

        CREATE INDEX IF NOT EXISTS idx_ops_session   ON operations_log(session_id);
        CREATE INDEX IF NOT EXISTS idx_ops_level     ON operations_log(level);
        CREATE INDEX IF NOT EXISTS idx_tokens_session ON token_usage(session_id);
        CREATE INDEX IF NOT EXISTS idx_docs_project  ON documents(project);
        CREATE INDEX IF NOT EXISTS idx_cases_doc     ON test_cases(document_id);
        CREATE INDEX IF NOT EXISTS idx_cases_req     ON test_cases(requirement_ref);
        """)
    print("[DB] Base de datos inicializada correctamente.")


class Logger:
    """Logger que escribe en SQLite y en consola simultaneamente."""

    LEVELS = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40}

    def __init__(self, module: str, session_id: Optional[str] = None,
                 min_level: str = "INFO"):
        self.module     = module
        self.session_id = session_id
        self.min_level  = self.LEVELS.get(min_level, 20)

    def _write(self, level: str, action: str, message: str,
               details: Any = None, duration_ms: int = 0) -> None:
        if self.LEVELS.get(level, 0) < self.min_level:
            return
        ts = datetime.now(timezone.utc).isoformat()
        det_str = json.dumps(details, ensure_ascii=False) if details else None

        # Consola
        prefix = {"DEBUG": "[DBG]", "INFO": "[INF]", "WARN": "[WRN]", "ERROR": "[ERR]"}.get(level, "[INF]")
        print(f"{prefix} {self.module}.{action}: {message}")

        # SQLite
        try:
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO operations_log "
                    "(session_id, timestamp, level, module, action, message, details, duration_ms) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (self.session_id, ts, level, self.module,
                     action, message, det_str, duration_ms)
                )
        except Exception:
            pass  # No romper el flujo si falla el log

    def debug(self, action: str, msg: str, details: Any = None) -> None:
        self._write("DEBUG", action, msg, details)

    def info(self, action: str, msg: str, details: Any = None) -> None:
        self._write("INFO", action, msg, details)

    def warn(self, action: str, msg: str, details: Any = None) -> None:
        self._write("WARN", action, msg, details)

    def error(self, action: str, msg: str, details: Any = None) -> None:
        self._write("ERROR", action, msg, details)


class SessionManager:
    """Gestiona sesiones de trabajo en SQLite."""

    @staticmethod
    def create(project: str, doc_name: str = "",
               org_mode: int = 2, detail_level: int = 3) -> str:
        sid = str(uuid.uuid4())[:8]
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO sessions (id, project, doc_name, started_at, org_mode, detail_level) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (sid, project, doc_name,
                 datetime.now(timezone.utc).isoformat(),
                 org_mode, detail_level)
            )
        return sid

    @staticmethod
    def close(session_id: str, status: str = "completed") -> None:
        with get_connection() as conn:
            conn.execute(
                "UPDATE sessions SET ended_at=?, status=? WHERE id=?",
                (datetime.now(timezone.utc).isoformat(), status, session_id)
            )

    @staticmethod
    def list_sessions(project: Optional[str] = None) -> list[dict]:
        with get_connection() as conn:
            if project:
                rows = conn.execute(
                    "SELECT * FROM sessions WHERE project=? ORDER BY started_at DESC",
                    (project,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sessions ORDER BY started_at DESC LIMIT 20"
                ).fetchall()
        return [dict(r) for r in rows]


class DocumentRepository:
    """Repositorio de documentos procesados."""

    @staticmethod
    def save(project: str, doc_name: str, doc_hash: str,
             version: int, rules_count: int, cases_count: int,
             deliverables: list[str]) -> int:
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO documents "
                "(project, doc_name, doc_hash, version, rules_count, cases_count, "
                "processed_at, deliverables) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (project, doc_name, doc_hash, version, rules_count, cases_count,
                 datetime.now(timezone.utc).isoformat(),
                 json.dumps(deliverables))
            )
            return cur.lastrowid

    @staticmethod
    def get_by_hash(doc_hash: str) -> Optional[dict]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE doc_hash=? ORDER BY version DESC LIMIT 1",
                (doc_hash,)
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def list_documents(project: Optional[str] = None) -> list[dict]:
        with get_connection() as conn:
            if project:
                rows = conn.execute(
                    "SELECT * FROM documents WHERE project=? ORDER BY processed_at DESC",
                    (project,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM documents ORDER BY processed_at DESC"
                ).fetchall()
        return [dict(r) for r in rows]


class TestCaseRepository:
    """Repositorio de casos de prueba."""

    @staticmethod
    def save_batch(cases: list[dict], project: str,
                   document_id: Optional[int] = None) -> int:
        ts = datetime.now(timezone.utc).isoformat()
        records = [
            (
                tc.get("id", ""),
                document_id,
                project,
                tc.get("name", ""),
                tc.get("dimension", ""),
                tc.get("objective", ""),
                tc.get("precondition", ""),
                json.dumps(tc.get("steps", []), ensure_ascii=False),
                tc.get("test_data", ""),
                tc.get("expected_result", ""),
                tc.get("priority", ""),
                tc.get("level", ""),
                tc.get("type", ""),
                tc.get("technique", ""),
                tc.get("requirement_ref", ""),
                tc.get("risk", ""),
                tc.get("automation_label", ""),
                tc.get("estimated_min", 10),
                ts,
            )
            for tc in cases
        ]
        with get_connection() as conn:
            conn.executemany(
                "INSERT INTO test_cases "
                "(case_id, document_id, project, name, dimension, objective, "
                "precondition, steps, test_data, expected_result, priority, "
                "level, type, technique, requirement_ref, risk, automation, "
                "estimated_min, created_at) VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                records
            )
        return len(records)

    @staticmethod
    def get_by_project(project: str) -> list[dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM test_cases WHERE project=? ORDER BY case_id",
                (project,)
            ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def stats(project: str) -> dict:
        with get_connection() as conn:
            total = conn.execute(
                "SELECT COUNT(*) as n FROM test_cases WHERE project=?",
                (project,)
            ).fetchone()["n"]
            by_dim = conn.execute(
                "SELECT dimension, COUNT(*) as n FROM test_cases "
                "WHERE project=? GROUP BY dimension",
                (project,)
            ).fetchall()
            by_tech = conn.execute(
                "SELECT technique, COUNT(*) as n FROM test_cases "
                "WHERE project=? GROUP BY technique",
                (project,)
            ).fetchall()
            by_prio = conn.execute(
                "SELECT priority, COUNT(*) as n FROM test_cases "
                "WHERE project=? GROUP BY priority",
                (project,)
            ).fetchall()
        return {
            "total":      total,
            "dimension":  {r["dimension"]: r["n"] for r in by_dim},
            "technique":  {r["technique"]: r["n"] for r in by_tech},
            "priority":   {r["priority"]:  r["n"] for r in by_prio},
        }


class TokenRepository:
    """Repositorio de uso de tokens."""

    @staticmethod
    def record(session_id: str, agent_type: str, model: str,
               prompt_tokens: int, completion_tokens: int,
               cost_usd: float, project: str, action: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO token_usage "
                "(session_id, timestamp, agent_type, model, prompt_tokens, "
                "completion_tokens, total_tokens, cost_usd, project, action) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id,
                 datetime.now(timezone.utc).isoformat(),
                 agent_type, model,
                 prompt_tokens, completion_tokens,
                 prompt_tokens + completion_tokens,
                 cost_usd, project, action)
            )

    @staticmethod
    def summary(project: Optional[str] = None) -> dict:
        with get_connection() as conn:
            q = "SELECT * FROM token_usage"
            if project:
                q += f" WHERE project='{project}'"
            rows = conn.execute(q).fetchall()

        total_tokens = sum(r["total_tokens"] for r in rows)
        total_cost   = sum(r["cost_usd"] for r in rows)
        by_agent     = {}
        for r in rows:
            a = r["agent_type"]
            by_agent[a] = by_agent.get(a, 0) + r["total_tokens"]

        return {
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 4),
            "by_agent": by_agent,
            "total_calls": len(rows),
        }


class AuditTrail:
    """Registro de auditoria de acciones del usuario."""

    @staticmethod
    def log(session_id: str, user_action: str, entity_type: str = "",
            entity_id: str = "", old_value: str = "", new_value: str = "") -> None:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO audit_trail "
                "(timestamp, session_id, user_action, entity_type, entity_id, "
                "old_value, new_value) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(),
                 session_id, user_action, entity_type,
                 entity_id, old_value, new_value)
            )

    @staticmethod
    def get_history(session_id: Optional[str] = None) -> list[dict]:
        with get_connection() as conn:
            if session_id:
                rows = conn.execute(
                    "SELECT * FROM audit_trail WHERE session_id=? ORDER BY timestamp",
                    (session_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM audit_trail ORDER BY timestamp DESC LIMIT 100"
                ).fetchall()
        return [dict(r) for r in rows]


# Inicializar la BD al importar el modulo
init_db()
