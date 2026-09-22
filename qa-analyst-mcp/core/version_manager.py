"""
version_manager.py — Versionamiento SHA-256 + diff semántico 3 niveles.

Nivel 1: hash SHA-256 → REUTILIZAR si coincide
Nivel 2: diff estructural por secciones
Nivel 3: diff semántico por reglas con matching difuso
         similitud = 0.5 × SequenceMatcher + 0.5 × Jaccard de tokens
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import Enum
from typing import Optional


class RuleStatus(str, Enum):
    UNCHANGED  = "UNCHANGED"
    MODIFIED   = "MODIFIED"
    CANDIDATE  = "CANDIDATE"   # requiere confirmación humana
    ADDED      = "ADDED"
    REMOVED    = "REMOVED"
    REFINED    = "REFINED"     # cambio cosmético, no regenera
    OBSOLETE   = "OBSOLETE"    # regla eliminada, casos marcados obsoletos


class VersionDecision(str, Enum):
    REUSE               = "REUSE"
    NEW                 = "NEW"
    INCREMENTAL_UPDATE  = "INCREMENTAL_UPDATE"


@dataclass
class RuleDiff:
    rule_id:     str
    status:      RuleStatus
    old_text:    Optional[str] = None
    new_text:    Optional[str] = None
    similarity:  float = 1.0
    remapped_id: Optional[str] = None  # si hubo renumeración


@dataclass
class VersionResult:
    decision:       VersionDecision
    old_hash:       Optional[str]
    new_hash:       str
    version_number: int
    rule_diffs:     list[RuleDiff] = field(default_factory=list)
    candidates:     list[RuleDiff] = field(default_factory=list)   # requieren confirmación
    section_diffs:  list[str]      = field(default_factory=list)
    regeneration_plan: dict        = field(default_factory=dict)


# ------------------------------------------------------------------ helpers
def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _jaccard(a: str, b: str) -> float:
    ta = set(re.findall(r"\w+", a.lower()))
    tb = set(re.findall(r"\w+", b.lower()))
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _sequence(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def hybrid_similarity(a: str, b: str) -> float:
    return 0.5 * _sequence(a, b) + 0.5 * _jaccard(a, b)


def _is_cosmetic(a: str, b: str) -> bool:
    """Detecta cambios cosméticos: mismos números, montos y condiciones semánticas."""
    nums_a = set(re.findall(r"\d[\d.,]*", a))
    nums_b = set(re.findall(r"\d[\d.,]*", b))
    keywords_a = set(re.findall(r"\b(?:si|cuando|entre|mayor|menor|igual|y|o)\b", a.lower()))
    keywords_b = set(re.findall(r"\b(?:si|cuando|entre|mayor|menor|igual|y|o)\b", b.lower()))
    return nums_a == nums_b and keywords_a == keywords_b


def _extract_sections(text: str) -> list[str]:
    """Divide el documento en secciones por encabezados."""
    return re.split(r"\n(?=#{1,3}\s|\d+\.\s+[A-Z])", text)


def _extract_rules(text: str) -> dict[str, str]:
    """
    Extrae reglas de negocio del texto.
    Busca patrones: RN-001, RN001, CA-001, REQ-001, etc.
    Devuelve {id: texto_completo}
    """
    pattern = re.compile(
        r"((?:RN|CA|REQ|RF|HU|US|BR|AC)[-_]?\d{1,4})[:\.\)]\s*(.+?)(?=(?:RN|CA|REQ|RF|HU|US|BR|AC)[-_]?\d{1,4}[:\.\)]|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    rules = {}
    for m in pattern.finditer(text):
        rid  = m.group(1).upper().replace("_", "-")
        body = m.group(2).strip()
        rules[rid] = body
    return rules


# ------------------------------------------------------------------ manager
class VersionManager:
    """
    Gestiona el versionamiento de documentos procesados.
    corpus_manager se inyecta para persistencia.
    """

    def __init__(self, corpus_manager):
        self.corpus = corpus_manager

    def check(self, project: str, doc_name: str, content: str) -> VersionResult:
        new_hash = sha256(content)
        record   = self.corpus.get_document(project, doc_name)

        # --- Nivel 1: hash idéntico → reutilizar
        if record and record.get("hash") == new_hash:
            return VersionResult(
                decision=VersionDecision.REUSE,
                old_hash=new_hash,
                new_hash=new_hash,
                version_number=record.get("version", 1),
            )

        # --- Documento nuevo
        if not record:
            return VersionResult(
                decision=VersionDecision.NEW,
                old_hash=None,
                new_hash=new_hash,
                version_number=1,
            )

        # --- Nivel 2: diff estructural por secciones
        old_sections = _extract_sections(record.get("content", ""))
        new_sections = _extract_sections(content)
        section_diffs = []
        for i, (old_s, new_s) in enumerate(
            zip(old_sections, new_sections + [""] * max(0, len(old_sections) - len(new_sections)))
        ):
            if old_s.strip() != new_s.strip():
                section_diffs.append(f"Sección {i+1} modificada")
        for i in range(len(old_sections), len(new_sections)):
            section_diffs.append(f"Sección {i+1} agregada")

        # --- Nivel 3: diff semántico por reglas
        old_rules = _extract_rules(record.get("content", ""))
        new_rules = _extract_rules(content)
        rule_diffs: list[RuleDiff] = []
        candidates: list[RuleDiff] = []
        processed_new: set[str] = set()

        for rid, old_text in old_rules.items():
            if rid in new_rules:
                new_text = new_rules[rid]
                processed_new.add(rid)
                sim = hybrid_similarity(old_text, new_text)
                if sim >= 0.99:
                    rule_diffs.append(RuleDiff(rid, RuleStatus.UNCHANGED, old_text, new_text, sim))
                elif sim >= 0.85:
                    if _is_cosmetic(old_text, new_text):
                        rule_diffs.append(RuleDiff(rid, RuleStatus.REFINED, old_text, new_text, sim))
                    else:
                        rule_diffs.append(RuleDiff(rid, RuleStatus.MODIFIED, old_text, new_text, sim))
                elif sim >= 0.60:
                    # Cambio significativo detectado por ID — CANDIDATE (requiere confirmación)
                    rd = RuleDiff(rid, RuleStatus.CANDIDATE, old_text, new_text, sim)
                    candidates.append(rd)
                    # Se trata como MODIFIED para el plan de regeneración
                    rule_diffs.append(RuleDiff(rid, RuleStatus.MODIFIED, old_text, new_text, sim))
                else:
                    # Cambio drástico con mismo ID → MODIFIED (texto completamente distinto)
                    rule_diffs.append(RuleDiff(rid, RuleStatus.MODIFIED, old_text, new_text, sim))
            else:
                # Buscar sin ID: matching difuso en reglas nuevas sin asignar
                best_sim   = 0.0
                best_new_id = None
                for nid, new_text in new_rules.items():
                    if nid in processed_new:
                        continue
                    s = hybrid_similarity(old_text, new_text)
                    if s > best_sim:
                        best_sim    = s
                        best_new_id = nid
                if best_sim >= 0.85 and best_new_id:
                    processed_new.add(best_new_id)
                    rule_diffs.append(
                        RuleDiff(rid, RuleStatus.MODIFIED, old_text, new_rules[best_new_id],
                                 best_sim, remapped_id=best_new_id)
                    )
                elif best_sim >= 0.60 and best_new_id:
                    processed_new.add(best_new_id)
                    rd = RuleDiff(rid, RuleStatus.CANDIDATE, old_text, new_rules[best_new_id],
                                  best_sim, remapped_id=best_new_id)
                    candidates.append(rd)
                else:
                    rule_diffs.append(RuleDiff(rid, RuleStatus.REMOVED, old_text, None, 0.0))

        # Reglas nuevas sin match
        for nid, new_text in new_rules.items():
            if nid not in processed_new:
                rule_diffs.append(RuleDiff(nid, RuleStatus.ADDED, None, new_text, 0.0))

        # Plan de regeneración
        regen_plan = {
            "generate":  [d.rule_id for d in rule_diffs if d.status == RuleStatus.ADDED],
            "regenerate":[d.rule_id for d in rule_diffs if d.status == RuleStatus.MODIFIED],
            "obsolete":  [d.rule_id for d in rule_diffs if d.status == RuleStatus.REMOVED],
            "unchanged": [d.rule_id for d in rule_diffs if d.status in (RuleStatus.UNCHANGED, RuleStatus.REFINED)],
        }

        return VersionResult(
            decision=VersionDecision.INCREMENTAL_UPDATE,
            old_hash=record.get("hash"),
            new_hash=new_hash,
            version_number=record.get("version", 1) + 1,
            rule_diffs=rule_diffs,
            candidates=candidates,
            section_diffs=section_diffs,
            regeneration_plan=regen_plan,
        )
