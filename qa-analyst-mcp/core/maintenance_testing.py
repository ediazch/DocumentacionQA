"""
maintenance_testing.py — Análisis de impacto ante cambios (ISTQB §2.4).

Cuando el diff detecta cambios:
  - Casos directos: de la regla cambiada
  - Casos indirectos: reglas que comparten entidad de negocio (similitud tokens >0.35)
  - Obsoletos: de reglas eliminadas (nunca eliminar, solo marcar)
  - Esfuerzo estimado: 0.25h/caso manual
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Optional


@dataclass
class ImpactEntry:
    case_id:      str
    case_name:    str
    impact_type:  str   # direct / indirect / obsolete
    rule_ref:     str
    reason:       str
    effort_hours: float


@dataclass
class MaintenanceReport:
    triggered:        bool
    total_direct:     int
    total_indirect:   int
    total_obsolete:   int
    total_effort_hours: float
    entries:          list[ImpactEntry]
    regression_suite: list[str]        # IDs de casos candidatos a regresión
    rotation_note:    str

    def summary(self) -> str:
        return (
            f"Impacto: {self.total_direct} directos | "
            f"{self.total_indirect} indirectos | "
            f"{self.total_obsolete} obsoletos | "
            f"Esfuerzo estimado: {self.total_effort_hours:.2f}h"
        )


def _jaccard_tokens(a: str, b: str) -> float:
    ta = set(re.findall(r"\w+", a.lower()))
    tb = set(re.findall(r"\w+", b.lower()))
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


class MaintenanceTesting:

    EFFORT_PER_MANUAL_CASE = 0.25  # horas

    def analyze(
        self,
        regeneration_plan: dict,
        rules: dict[str, str],
        test_cases: list[dict],
    ) -> MaintenanceReport:

        modified_rules = set(regeneration_plan.get("regenerate", []))
        removed_rules  = set(regeneration_plan.get("obsolete", []))
        added_rules    = set(regeneration_plan.get("generate", []))

        if not modified_rules and not removed_rules and not added_rules:
            return MaintenanceReport(
                triggered=False,
                total_direct=0, total_indirect=0, total_obsolete=0,
                total_effort_hours=0,
                entries=[],
                regression_suite=[],
                rotation_note=self._rotation_note(),
            )

        entries: list[ImpactEntry] = []

        # ---- Casos directos (de la regla cambiada)
        for tc in test_cases:
            ref = tc.get("requirement_ref", "")
            for rid in modified_rules:
                if rid in ref:
                    entries.append(ImpactEntry(
                        case_id=tc["id"],
                        case_name=tc.get("name", ""),
                        impact_type="direct",
                        rule_ref=rid,
                        reason=f"La regla {rid} fue modificada (diff MODIFIED).",
                        effort_hours=self.EFFORT_PER_MANUAL_CASE,
                    ))
                    break

        # ---- Casos indirectos (comparten entidad de negocio, similitud >0.35)
        for rid_mod in modified_rules:
            text_mod = rules.get(rid_mod, "")
            for rid_other, text_other in rules.items():
                if rid_other == rid_mod or rid_other in modified_rules:
                    continue
                sim = _jaccard_tokens(text_mod, text_other)
                if sim > 0.35:
                    # Buscar casos de rid_other
                    for tc in test_cases:
                        ref = tc.get("requirement_ref", "")
                        if rid_other in ref:
                            # Evitar duplicados
                            if not any(e.case_id == tc["id"] and e.impact_type == "indirect"
                                       for e in entries):
                                entries.append(ImpactEntry(
                                    case_id=tc["id"],
                                    case_name=tc.get("name", ""),
                                    impact_type="indirect",
                                    rule_ref=rid_other,
                                    reason=(
                                        f"Comparte entidad de negocio con {rid_mod} "
                                        f"(similitud Jaccard: {sim:.2f} > 0.35)."
                                    ),
                                    effort_hours=self.EFFORT_PER_MANUAL_CASE,
                                ))

        # ---- Casos obsoletos (reglas eliminadas)
        for tc in test_cases:
            ref = tc.get("requirement_ref", "")
            for rid in removed_rules:
                if rid in ref:
                    entries.append(ImpactEntry(
                        case_id=tc["id"],
                        case_name=tc.get("name", ""),
                        impact_type="obsolete",
                        rule_ref=rid,
                        reason=f"La regla {rid} fue eliminada (diff REMOVED). Caso marcado OBSOLETO (no eliminado).",
                        effort_hours=0.0,
                    ))
                    break

        direct_entries   = [e for e in entries if e.impact_type == "direct"]
        indirect_entries = [e for e in entries if e.impact_type == "indirect"]
        obsolete_entries = [e for e in entries if e.impact_type == "obsolete"]

        total_effort = sum(e.effort_hours for e in entries)

        # Suite de regresión: todos los casos de alto riesgo no obsoletos
        regression = [
            tc["id"] for tc in test_cases
            if tc.get("risk", "").upper() == "ALTA"
            and tc["id"] not in [e.case_id for e in obsolete_entries]
        ]

        return MaintenanceReport(
            triggered=True,
            total_direct=len(direct_entries),
            total_indirect=len(indirect_entries),
            total_obsolete=len(obsolete_entries),
            total_effort_hours=total_effort,
            entries=entries,
            regression_suite=regression,
            rotation_note=self._rotation_note(),
        )

    @staticmethod
    def _rotation_note() -> str:
        return (
            "Suite de regresión con rotación de datos (anti-paradoja del pesticida, ISTQB P4): "
            "en cada ciclo de regresión, rotar al menos el 20% de los datos de prueba. "
            "Usar datos de producción anonimizados cuando sea posible. "
            "Revisar y actualizar la suite cada 3 sprints o ante cambios funcionales."
        )
