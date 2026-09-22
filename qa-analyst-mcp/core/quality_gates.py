"""
quality_gates.py — Gates G1-G7 con decisión PROCEED / WARN / BLOCK.
Cada gate devuelve un GateResult con la decisión, mensajes y detalles.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GateDecision(str, Enum):
    PROCEED = "PROCEED"
    WARN    = "WARN"
    BLOCK   = "BLOCK"


@dataclass
class GateResult:
    gate:     str
    decision: GateDecision
    messages: list[str]     = field(default_factory=list)
    details:  dict[str, Any]= field(default_factory=dict)

    def is_blocked(self) -> bool:
        return self.decision == GateDecision.BLOCK

    def __str__(self) -> str:
        lines = [f"[{self.gate}] {self.decision}"]
        for m in self.messages:
            lines.append(f"  • {m}")
        return "\n".join(lines)


# Lenguaje técnico prohibido en casos de prueba (R2)
_TECH_PATTERNS = re.compile(
    r"\b(SELECT|INSERT|UPDATE|DELETE|FROM|WHERE|JOIN|ALTER|DROP|CREATE|TABLE|"
    r"varchar|int|boolean|null|endpoint|payload|request|response|"
    r"JSON|XML|HTTP|REST|API|SQL|BD|DB|campo_\w+|tbl_\w+|col_\w+|"
    r"localhost|127\.0\.0\.1|uuid|token|jwt|bearer)\b",
    re.IGNORECASE,
)


class QualityGates:

    # ------------------------------------------------------------------ G1
    @staticmethod
    def g1_ingesta(content: str, sections: list[str], doc_hash: str) -> GateResult:
        messages = []
        decision = GateDecision.PROCEED

        if len(content) <= 50:
            messages.append(f"Contenido insuficiente: {len(content)} caracteres (mínimo 50). [BLOCK]")
            return GateResult("G1-Ingesta", GateDecision.BLOCK, messages)

        if not doc_hash:
            messages.append("Hash SHA-256 no calculado. [BLOCK]")
            return GateResult("G1-Ingesta", GateDecision.BLOCK, messages)

        if len(sections) < 3:
            messages.append(f"Solo {len(sections)} sección(es) detectadas (recomendado ≥3). [WARN]")
            decision = GateDecision.WARN
        else:
            messages.append(f"{len(sections)} secciones detectadas.")

        messages.append(f"Hash: {doc_hash[:16]}…")
        return GateResult("G1-Ingesta", decision, messages,
                          {"content_length": len(content), "sections": len(sections)})

    # ------------------------------------------------------------------ G2
    @staticmethod
    def g2_version(decision_str: str, version: int, old_hash: str | None) -> GateResult:
        valid = {"REUSE", "NEW", "INCREMENTAL_UPDATE"}
        if decision_str not in valid:
            return GateResult("G2-Version", GateDecision.BLOCK,
                              [f"Decisión de versión no determinada: '{decision_str}'. [BLOCK]"])
        msgs = [f"Decisión: {decision_str} | Versión: v{version}"]
        if old_hash:
            msgs.append(f"Hash anterior: {old_hash[:16]}…")
        return GateResult("G2-Version", GateDecision.PROCEED, msgs,
                          {"decision": decision_str, "version": version})

    # ------------------------------------------------------------------ G3
    @staticmethod
    def g3_analisis(rules: dict, contradictions: list[str]) -> GateResult:
        messages = []
        decision = GateDecision.PROCEED

        if not rules:
            messages.append("No se encontró ninguna regla de negocio ni criterio de aceptación. [BLOCK]")
            return GateResult("G3-Analisis", GateDecision.BLOCK, messages)

        messages.append(f"{len(rules)} reglas/CA extraídas.")

        if contradictions:
            decision = GateDecision.WARN
            messages.append(f"Contradicciones detectadas ({len(contradictions)}): se debe confirmar antes de diseñar. [WARN]")
            for c in contradictions:
                messages.append(f"  - {c}")

        # Verificar reglas no verificables (demasiado ambiguas)
        ambiguous = []
        for rid, text in rules.items():
            if len(text.split()) < 4:
                ambiguous.append(rid)
        if ambiguous:
            decision = GateDecision.WARN
            messages.append(f"Reglas posiblemente no verificables (texto muy corto): {ambiguous}. [WARN]")

        return GateResult("G3-Analisis", decision, messages,
                          {"rules_count": len(rules), "contradictions": contradictions,
                           "ambiguous": ambiguous})

    # ------------------------------------------------------------------ G4
    @staticmethod
    def g4_diseno(
        user_confirmed: bool,
        test_cases: list[dict],
        rules: dict,
    ) -> GateResult:
        messages = []
        decision = GateDecision.PROCEED

        if not user_confirmed:
            messages.append("El usuario no ha confirmado el resumen de análisis. [BLOCK]")
            return GateResult("G4-Diseno", GateDecision.BLOCK, messages)

        # Verificar lenguaje técnico prohibido (R2)
        tech_violations = []
        for tc in test_cases:
            text = " ".join([
                tc.get("name", ""),
                tc.get("objective", ""),
                " ".join(tc.get("steps", [])),
                tc.get("expected_result", ""),
                tc.get("test_data", ""),
            ])
            if _TECH_PATTERNS.search(text):
                match = _TECH_PATTERNS.search(text)
                tech_violations.append(f"{tc.get('id', '?')}: '{match.group()}'")

        if tech_violations:
            messages.append(f"VIOLACIÓN R2 — Lenguaje técnico prohibido detectado en {len(tech_violations)} caso(s). [BLOCK]")
            for v in tech_violations[:10]:
                messages.append(f"  - {v}")
            return GateResult("G4-Diseno", GateDecision.BLOCK, messages, {"violations": tech_violations})

        # Verificar cobertura de RN
        covered_refs: set[str] = set()
        for tc in test_cases:
            ref = tc.get("requirement_ref", "")
            if ref:
                covered_refs.update(re.findall(r"(?:RN|CA|REQ|RF|HU|US|BR|AC)[-_]?\d+", ref.upper()))

        gaps = [rid for rid in rules if rid not in covered_refs]
        if gaps:
            decision = GateDecision.WARN
            messages.append(f"Gaps de cobertura: {len(gaps)} RN sin casos → {gaps}. [WARN]")

        # Verificar resultados esperados verificables
        empty_expected = [tc.get("id") for tc in test_cases if not tc.get("expected_result", "").strip()]
        if empty_expected:
            decision = GateDecision.WARN
            messages.append(f"Resultados esperados vacíos en: {empty_expected}. [WARN]")

        messages.append(f"{len(test_cases)} casos diseñados. Cobertura: {len(covered_refs)}/{len(rules)} RN.")
        return GateResult("G4-Diseno", decision, messages,
                          {"total_cases": len(test_cases), "gaps": gaps})

    # ------------------------------------------------------------------ G5
    @staticmethod
    def g5_cobertura(coverage_report: dict) -> GateResult:
        messages = []
        decision = GateDecision.PROCEED

        req_coverage = coverage_report.get("requirements_coverage_pct", 0)
        if req_coverage < 100:
            messages.append(
                f"Cobertura de requerimientos {req_coverage:.1f}% < 100%. [BLOCK]"
            )
            return GateResult("G5-Cobertura", GateDecision.BLOCK, messages, coverage_report)

        for metric, threshold, label in [
            ("bva_coverage_pct",        100, "BVA"),
            ("partition_coverage_pct",  100, "Partición de Equivalencia"),
            ("decision_table_coverage_pct", 100, "Tabla de Decisión"),
        ]:
            val = coverage_report.get(metric)
            if val is not None and val < threshold:
                decision = GateDecision.WARN
                messages.append(f"Cobertura {label}: {val:.1f}% < {threshold}%. [WARN]")

        messages.append(f"Cobertura de requerimientos: {req_coverage:.1f}%.")
        return GateResult("G5-Cobertura", decision, messages, coverage_report)

    # ------------------------------------------------------------------ G7
    @staticmethod
    def g7_entregables(
        files: list[str],
        csv_row_count: int,
        excel_row_count: int,
    ) -> GateResult:
        messages = []
        decision = GateDecision.PROCEED
        import os

        for f in files:
            if not os.path.exists(f):
                messages.append(f"Archivo no existe: {f}. [BLOCK]")
                return GateResult("G7-Entregables", GateDecision.BLOCK, messages)
            if os.path.getsize(f) == 0:
                messages.append(f"Archivo vacío: {f}. [BLOCK]")
                return GateResult("G7-Entregables", GateDecision.BLOCK, messages)

        if csv_row_count != excel_row_count:
            messages.append(
                f"CSV ({csv_row_count} filas) no coincide con Excel ({excel_row_count} filas). [BLOCK]"
            )
            return GateResult("G7-Entregables", GateDecision.BLOCK, messages)

        messages.append(f"{len(files)} entregables válidos. CSV y Excel sincronizados ({csv_row_count} filas).")
        return GateResult("G7-Entregables", decision, messages,
                          {"files": files, "row_count": csv_row_count})
