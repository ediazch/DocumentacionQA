"""
pipeline_state.py — FSM con write-ahead log e idempotencia.
Estados: INIT → INGESTING → INGESTED → VERSION_CHECKING → VERSION_CHECKED →
         ANALYZING → ANALYZED → AWAITING_CONFIRMATION → CONFIRMED →
         DESIGNING → DESIGNED → ASSESSING_RISKS → RISKS_ASSESSED →
         DELIVERING → DELIVERED → COMPLETED  (o FAILED)
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class State(str, Enum):
    INIT                  = "INIT"
    INGESTING             = "INGESTING"
    INGESTED              = "INGESTED"
    VERSION_CHECKING      = "VERSION_CHECKING"
    VERSION_CHECKED       = "VERSION_CHECKED"
    ANALYZING             = "ANALYZING"
    ANALYZED              = "ANALYZED"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    CONFIRMED             = "CONFIRMED"
    DESIGNING             = "DESIGNING"
    DESIGNED              = "DESIGNED"
    ASSESSING_RISKS       = "ASSESSING_RISKS"
    RISKS_ASSESSED        = "RISKS_ASSESSED"
    DELIVERING            = "DELIVERING"
    DELIVERED             = "DELIVERED"
    COMPLETED             = "COMPLETED"
    FAILED                = "FAILED"


_TRANSITIONS: dict[State, State] = {
    State.INIT:                  State.INGESTING,
    State.INGESTING:             State.INGESTED,
    State.INGESTED:              State.VERSION_CHECKING,
    State.VERSION_CHECKING:      State.VERSION_CHECKED,
    State.VERSION_CHECKED:       State.ANALYZING,
    State.ANALYZING:             State.ANALYZED,
    State.ANALYZED:              State.AWAITING_CONFIRMATION,
    State.AWAITING_CONFIRMATION: State.CONFIRMED,
    State.CONFIRMED:             State.DESIGNING,
    State.DESIGNING:             State.DESIGNED,
    State.DESIGNED:              State.ASSESSING_RISKS,
    State.ASSESSING_RISKS:       State.RISKS_ASSESSED,
    State.RISKS_ASSESSED:        State.DELIVERING,
    State.DELIVERING:            State.DELIVERED,
    State.DELIVERED:             State.COMPLETED,
}


class PipelineState:
    """
    Gestiona el estado del pipeline con write-ahead log persistido en JSON.
    Cada transición se escribe como PENDING antes de ejecutarse y se marca
    DONE al terminar, lo que permite reanudación idempotente.
    """

    def __init__(self, session_id: str, log_dir: Path = Path("output")):
        self.session_id = session_id
        self.log_dir    = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path   = self.log_dir / f"wal_{session_id}.json"
        self.state      = State.INIT
        self.context: dict[str, Any] = {}
        self._log: list[dict] = []
        self._load()

    # ------------------------------------------------------------------ I/O
    def _load(self) -> None:
        if not self.log_path.exists():
            return
        with open(self.log_path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.state   = State(data.get("current_state", State.INIT))
        self.context = data.get("context", {})
        self._log    = data.get("log", [])
        # Reanudación: si la última op quedó PENDING → reintentarla
        if self._log:
            last = self._log[-1]
            if last.get("status") == "PENDING":
                print(
                    f"[WAL] Operación pendiente detectada: {last['operation_id']} "
                    f"({last['from_state']} → {last['to_state']}). Reintentando…"
                )
                # Revertir al estado anterior para que advance() lo reintente
                self.state = State(last["from_state"])

    def _save(self) -> None:
        with open(self.log_path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "session_id":    self.session_id,
                    "current_state": self.state.value,
                    "context":       self.context,
                    "log":           self._log,
                    "updated_at":    datetime.now(timezone.utc).isoformat(),
                },
                fh,
                ensure_ascii=False,
                indent=2,
            )

    # -------------------------------------------------------------- FSM API
    def advance(self, payload: Optional[dict] = None) -> State:
        """Avanza al siguiente estado válido con write-ahead log."""
        if self.state not in _TRANSITIONS:
            raise RuntimeError(f"Estado terminal o desconocido: {self.state}")
        next_state = _TRANSITIONS[self.state]
        op_id = str(uuid.uuid4())
        entry = {
            "operation_id": op_id,
            "from_state":   self.state.value,
            "to_state":     next_state.value,
            "timestamp":    datetime.now(timezone.utc).isoformat(),
            "status":       "PENDING",
            "payload":      payload or {},
        }
        self._log.append(entry)
        self._save()          # write-ahead: persiste PENDING antes de ejecutar
        self.state = next_state
        if payload:
            self.context.update(payload)
        entry["status"] = "DONE"
        self._save()          # persiste DONE
        return self.state

    def fail(self, reason: str) -> None:
        self.state = State.FAILED
        self.context["failure_reason"] = reason
        self._save()

    def set_context(self, key: str, value: Any) -> None:
        self.context[key] = value
        self._save()

    def get_context(self, key: str, default: Any = None) -> Any:
        return self.context.get(key, default)

    def __repr__(self) -> str:
        return f"<PipelineState session={self.session_id} state={self.state}>"
