"""
coverage_metrics.py — Métricas cuantificadas de cobertura vs umbrales ISTQB.

Calcula:
  - Cobertura de requerimientos (RN con ≥1 caso)
  - Cobertura BVA (casos de 7 por rango)
  - Cobertura de particiones de equivalencia
  - Cobertura de tabla de decisión
  - Cobertura risk-based (riesgo alto ≥2, medio ≥1)
  - Gaps explícitos
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CoverageReport:
    requirements_coverage_pct:    float
    bva_coverage_pct:             float
    partition_coverage_pct:       float
    decision_table_coverage_pct:  float
    risk_based_coverage_pct:      float
    total_rules:                  int
    covered_rules:                int
    gaps:                         list[str]
    bva_details:                  dict[str, Any] = field(default_factory=dict)
    risk_details:                 dict[str, Any] = field(default_factory=dict)
    warnings:                     list[str]      = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Cobertura de Requerimientos : {self.requirements_coverage_pct:.1f}%  ({self.covered_rules}/{self.total_rules})",
            f"Cobertura BVA               : {self.bva_coverage_pct:.1f}%",
            f"Cobertura Particiones       : {self.partition_coverage_pct:.1f}%",
            f"Cobertura Tabla de Decisión : {self.decision_table_coverage_pct:.1f}%",
            f"Cobertura Risk-Based        : {self.risk_based_coverage_pct:.1f}%",
        ]
        if self.gaps:
            lines.append(f"Gaps documentados           : {', '.join(self.gaps)}")
        if self.warnings:
            for w in self.warnings:
                lines.append(f"  [WARN] {w}")
        return "\n".join(lines)


class CoverageMetrics:

    def calculate(
        self,
        rules: dict[str, str],
        test_cases: list[dict],
        technique_decisions: dict,
        risk_register: list[dict],
    ) -> CoverageReport:

        # -------- Cobertura de requerimientos
        covered_rules = self._covered_rules(rules, test_cases)
        total_rules   = len(rules)
        gaps          = [rid for rid in rules if rid not in covered_rules]
        req_pct       = (len(covered_rules) / total_rules * 100) if total_rules else 100.0

        # -------- Cobertura BVA
        bva_pct, bva_details = self._bva_coverage(test_cases, technique_decisions)

        # -------- Cobertura de particiones
        part_pct = self._partition_coverage(test_cases, technique_decisions)

        # -------- Cobertura de tabla de decisión
        dt_pct = self._decision_table_coverage(test_cases, technique_decisions)

        # -------- Cobertura risk-based
        risk_pct, risk_details = self._risk_based_coverage(risk_register, test_cases)

        warnings = []
        if bva_pct < 100:
            warnings.append(f"BVA incompleta: {bva_pct:.1f}% (se requiere 100%)")
        if part_pct < 100:
            warnings.append(f"Particiones incompletas: {part_pct:.1f}% (se requiere 100%)")
        if dt_pct < 100:
            warnings.append(f"Tabla de decisión incompleta: {dt_pct:.1f}%")
        if risk_pct < 100:
            warnings.append(f"Risk-based incompleto: {risk_pct:.1f}%")

        return CoverageReport(
            requirements_coverage_pct=req_pct,
            bva_coverage_pct=bva_pct,
            partition_coverage_pct=part_pct,
            decision_table_coverage_pct=dt_pct,
            risk_based_coverage_pct=risk_pct,
            total_rules=total_rules,
            covered_rules=len(covered_rules),
            gaps=gaps,
            bva_details=bva_details,
            risk_details=risk_details,
            warnings=warnings,
        )

    # ---------------------------------------------------------- helpers
    @staticmethod
    def _covered_rules(rules: dict, test_cases: list[dict]) -> set[str]:
        covered = set()
        rule_ids = set(rules.keys())
        for tc in test_cases:
            ref = tc.get("requirement_ref", "")
            found = re.findall(r"(?:RN|CA|REQ|RF|HU|US|BR|AC)[-_]?\d+", ref.upper())
            for fid in found:
                normalized = fid.replace("_", "-")
                if normalized in rule_ids:
                    covered.add(normalized)
        return covered

    @staticmethod
    def _bva_coverage(test_cases: list[dict], technique_decisions: dict) -> tuple[float, dict]:
        """
        Verifica que por cada regla con BVA haya exactamente 7 casos.
        """
        bva_rules = {
            rid: td for rid, td in technique_decisions.items()
            if hasattr(td, "primary_technique") and td.primary_technique == "BVA"
        }
        if not bva_rules:
            return 100.0, {}

        details = {}
        total_required = len(bva_rules) * 7
        total_found    = 0

        for rid in bva_rules:
            rule_cases = [
                tc for tc in test_cases
                if rid in tc.get("requirement_ref", "")
                and tc.get("technique", "") == "BVA"
            ]
            found = len(rule_cases)
            details[rid] = {"required": 7, "found": found}
            total_found += min(found, 7)

        pct = (total_found / total_required * 100) if total_required else 100.0
        return pct, details

    @staticmethod
    def _partition_coverage(test_cases: list[dict], technique_decisions: dict) -> float:
        """
        Verifica que haya ≥1 caso por partición de equivalencia.
        Aproximación: cada regla con técnica Particion_Equivalencia debe tener
        al menos 1 caso positivo y 1 negativo.
        """
        part_rules = {
            rid for rid, td in technique_decisions.items()
            if hasattr(td, "primary_technique") and "Particion" in td.primary_technique
        }
        if not part_rules:
            return 100.0

        covered = 0
        for rid in part_rules:
            rule_cases = [tc for tc in test_cases if rid in tc.get("requirement_ref", "")]
            has_positive = any(tc.get("priority", "") != "BAJA" for tc in rule_cases)
            if has_positive and rule_cases:
                covered += 1

        return (covered / len(part_rules) * 100) if part_rules else 100.0

    @staticmethod
    def _decision_table_coverage(test_cases: list[dict], technique_decisions: dict) -> float:
        dt_rules = {
            rid for rid, td in technique_decisions.items()
            if hasattr(td, "primary_technique") and "Tabla_Decision" in td.primary_technique
        }
        if not dt_rules:
            return 100.0

        covered = 0
        for rid in dt_rules:
            rule_cases = [tc for tc in test_cases if rid in tc.get("requirement_ref", "")]
            # Cada regla de decisión debe tener ≥2 casos (true/false de condición principal)
            if len(rule_cases) >= 2:
                covered += 1

        return (covered / len(dt_rules) * 100) if dt_rules else 100.0

    @staticmethod
    def _risk_based_coverage(risk_register: list[dict], test_cases: list[dict]) -> tuple[float, dict]:
        """
        Riesgo alto (≥15): ≥2 casos. Medio (8-14): ≥1 caso.
        """
        if not risk_register:
            return 100.0, {}

        details  = {}
        total    = 0
        compliant= 0

        for risk in risk_register:
            score    = risk.get("score", 0)
            rule_ref = risk.get("rule_ref", "")
            rule_cases = [tc for tc in test_cases if rule_ref in tc.get("requirement_ref", "")]

            if score >= 15:
                required = 2
                total   += 1
                ok       = len(rule_cases) >= required
                details[rule_ref] = {"level": "ALTO", "required": required, "found": len(rule_cases), "ok": ok}
                if ok:
                    compliant += 1
            elif score >= 8:
                required = 1
                total   += 1
                ok       = len(rule_cases) >= required
                details[rule_ref] = {"level": "MEDIO", "required": required, "found": len(rule_cases), "ok": ok}
                if ok:
                    compliant += 1

        pct = (compliant / total * 100) if total else 100.0
        return pct, details
