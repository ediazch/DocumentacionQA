"""
corpus_manager.py — Persistencia de documentos procesados y metadatos.
Almacena en output/corpus.json el registro de todos los documentos procesados,
sus hashes, versiones, rutas de entregables y reglas extraídas.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


class CorpusManager:
    """
    Registro persistente de documentos procesados.
    corpus.json estructura:
    {
      "{project}::{doc_name}": {
        "hash": str,
        "version": int,
        "content": str,
        "rules": {...},
        "deliverables": [...],
        "processed_at": str
      }
    }
    """

    def __init__(self, corpus_path: Path = Path("output/corpus.json")):
        self.corpus_path = corpus_path
        self.corpus_path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = {}
        self._load()

    def _key(self, project: str, doc_name: str) -> str:
        return f"{project}::{doc_name}"

    def _load(self) -> None:
        if self.corpus_path.exists():
            with open(self.corpus_path, encoding="utf-8") as fh:
                self._data = json.load(fh)

    def _save(self) -> None:
        with open(self.corpus_path, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, ensure_ascii=False, indent=2)

    # ---------------------------------------------------------------- CRUD
    def get_document(self, project: str, doc_name: str) -> Optional[dict]:
        return self._data.get(self._key(project, doc_name))

    def save_document(
        self,
        project: str,
        doc_name: str,
        content: str,
        doc_hash: str,
        version: int,
        rules: dict,
        deliverables: Optional[list] = None,
    ) -> None:
        self._data[self._key(project, doc_name)] = {
            "hash":         doc_hash,
            "version":      version,
            "content":      content,
            "rules":        rules,
            "deliverables": deliverables or [],
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save()

    def add_deliverable(self, project: str, doc_name: str, path: str) -> None:
        key = self._key(project, doc_name)
        if key in self._data:
            self._data[key].setdefault("deliverables", []).append(path)
            self._save()

    def mark_cases_obsolete(self, project: str, doc_name: str, rule_ids: list[str]) -> None:
        key = self._key(project, doc_name)
        if key in self._data:
            obs = self._data[key].setdefault("obsolete_rules", [])
            for rid in rule_ids:
                if rid not in obs:
                    obs.append(rid)
            self._save()

    def list_documents(self) -> list[dict]:
        return [
            {"key": k, **{fk: fv for fk, fv in v.items() if fk != "content"}}
            for k, v in self._data.items()
        ]

    def get_deliverables(self, project: str, doc_name: str) -> list[str]:
        rec = self.get_document(project, doc_name)
        return rec.get("deliverables", []) if rec else []
