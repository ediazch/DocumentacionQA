"""
automation_engine.py — Motor de automatización (CTAL-TAE).

AutoScore ponderado:
  frecuencia(0.25) + estabilidad(0.20) + determinismo(0.15)
  + valor_riesgo(0.20) + facilidad(0.20) - valor_manual(0.30)

Umbrales:
  ≥0.70 → AUTOMATE_HIGH (CI/CD)
  0.40-0.69 → AUTOMATE_MEDIUM (backlog)
  <0.40 → MANUAL

Bloqueadores duros → MANUAL: exploratorio, usabilidad subjetiva, ad-hoc, una sola ejecución.
Detecta anti-patrón Ice Cream Cone (>50% automatización en UI).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------- señales
_EXPLORATORY_SIGNAL = re.compile(r"\b(exploratorio|ad.?hoc|heur[ií]stico|basado en experiencia)\b", re.I)
_USABILITY_SIGNAL   = re.compile(r"\b(usabilidad|UX|experiencia de usuario|dise[ñn]o visual|est[eé]tica|intuitivo)\b", re.I)
_ONE_SHOT_SIGNAL    = re.compile(r"\b(migraci[oó]n inicial|datafix|conversi[oó]n [uú]nica|una sola vez)\b", re.I)
_UI_SIGNAL          = re.compile(r"\b(pantalla|bot[oó]n|formulario|interfaz|UI|clic|navegar|men[uú])\b", re.I)
_API_SIGNAL         = re.compile(r"\b(api|servicio|endpoint|rest|soap|integraci[oó]n)\b", re.I)
_REGRESSION_SIGNAL  = re.compile(r"\b(regresi[oó]n|smoke|sanity|repetitivo|frecuente|cada sprint|cada release)\b", re.I)
_STABLE_SIGNAL      = re.compile(r"\b(estable|maduro|sin cambios|consolidado|base)\b", re.I)


@dataclass
class AutomationScore:
    test_case_id:   str
    technique:      str
    frequency:      float   # 0-1
    stability:      float   # 0-1
    determinism:    float   # 0-1
    risk_value:     float   # 0-1
    ease:           float   # 0-1
    manual_value:   float   # 0-1 (penalización)
    raw_score:      float
    final_score:    float
    label:          str     # AUTOMATE_HIGH / AUTOMATE_MEDIUM / MANUAL
    blocker:        Optional[str]
    rationale:      str


@dataclass
class AutomationReport:
    activated:          bool
    scores:             list[AutomationScore]
    ice_cream_cone_warning: Optional[str]
    summary:            dict

    def high(self)   -> list[AutomationScore]: return [s for s in self.scores if s.label == "AUTOMATE_HIGH"]
    def medium(self) -> list[AutomationScore]: return [s for s in self.scores if s.label == "AUTOMATE_MEDIUM"]
    def manual(self) -> list[AutomationScore]: return [s for s in self.scores if s.label == "MANUAL"]


class AutomationEngine:

    def should_activate(self, test_cases: list[dict]) -> bool:
        return len(test_cases) >= 3

    def generate(self, test_cases: list[dict], full_text: str) -> AutomationReport:
        if not self.should_activate(test_cases):
            return AutomationReport(activated=False, scores=[], ice_cream_cone_warning=None,
                                    summary={})

        scores = [self._score_case(tc, full_text) for tc in test_cases]

        # Detección Ice Cream Cone (>50% de automatización en UI)
        total_automatable = [s for s in scores if s.label in ("AUTOMATE_HIGH", "AUTOMATE_MEDIUM")]
        ui_automatable    = [
            s for s in total_automatable
            if _UI_SIGNAL.search(s.technique + " " + s.rationale)
        ]
        ice_cream = None
        if total_automatable and len(ui_automatable) / len(total_automatable) > 0.5:
            ice_cream = (
                f"ANTI-PATRÓN DETECTADO — Ice Cream Cone: "
                f"{len(ui_automatable)}/{len(total_automatable)} casos automatizables "
                f"({len(ui_automatable)/len(total_automatable)*100:.0f}%) están en capa UI. "
                f"Recomendación: balancear automatización hacia API/servicio y componente. "
                f"Pirámide ideal: 70% componente/API, 20% integración, 10% UI end-to-end."
            )

        summary = {
            "total":   len(scores),
            "high":    len([s for s in scores if s.label == "AUTOMATE_HIGH"]),
            "medium":  len([s for s in scores if s.label == "AUTOMATE_MEDIUM"]),
            "manual":  len([s for s in scores if s.label == "MANUAL"]),
        }

        return AutomationReport(
            activated=True,
            scores=scores,
            ice_cream_cone_warning=ice_cream,
            summary=summary,
        )

    # ----------------------------------------------------------- scoring
    def _score_case(self, tc: dict, full_text: str) -> AutomationScore:
        tc_text    = self._tc_text(tc)
        technique  = tc.get("technique", "")
        case_id    = tc.get("id", "?")

        # Bloqueadores duros → MANUAL inmediato
        if _EXPLORATORY_SIGNAL.search(tc_text):
            return self._manual(case_id, technique, "Prueba exploratoria: bloqueador duro (CTAL-TAE)")
        if _USABILITY_SIGNAL.search(tc_text):
            return self._manual(case_id, technique, "Usabilidad subjetiva: bloqueador duro (CTAL-TAE)")
        if _ONE_SHOT_SIGNAL.search(tc_text):
            return self._manual(case_id, technique, "Ejecución única (one-shot): bloqueador duro (CTAL-TAE)")

        # Calcular dimensiones
        frequency   = 0.8 if _REGRESSION_SIGNAL.search(tc_text + full_text) else 0.4
        stability   = 0.9 if _STABLE_SIGNAL.search(tc_text) else 0.5
        determinism = 0.9 if "BVA" in technique or "Tabla_Decision" in technique or "Particion" in technique else 0.6
        risk_value  = self._risk_value(tc)
        ease        = 0.8 if _API_SIGNAL.search(tc_text) else (0.4 if _UI_SIGNAL.search(tc_text) else 0.6)
        manual_val  = 0.7 if _EXPLORATORY_SIGNAL.search(full_text) else 0.2

        raw    = (frequency * 0.25 + stability * 0.20 + determinism * 0.15
                  + risk_value * 0.20 + ease * 0.20)
        final  = max(0.0, min(1.0, raw - manual_val * 0.30))

        if final >= 0.70:
            label    = "AUTOMATE_HIGH"
            rationale= "Alta frecuencia, determinismo y valor de riesgo. Candidato CI/CD."
        elif final >= 0.40:
            label    = "AUTOMATE_MEDIUM"
            rationale= "Automatización recomendada a mediano plazo. Agregar al backlog de automatización."
        else:
            label    = "MANUAL"
            rationale= "Bajo retorno de automatización. Mantener como prueba manual."

        return AutomationScore(
            test_case_id=case_id,
            technique=technique,
            frequency=frequency,
            stability=stability,
            determinism=determinism,
            risk_value=risk_value,
            ease=ease,
            manual_value=manual_val,
            raw_score=raw,
            final_score=final,
            label=label,
            blocker=None,
            rationale=rationale,
        )

    @staticmethod
    def _manual(case_id: str, technique: str, blocker: str) -> AutomationScore:
        return AutomationScore(
            test_case_id=case_id, technique=technique,
            frequency=0, stability=0, determinism=0,
            risk_value=0, ease=0, manual_value=1,
            raw_score=0, final_score=0,
            label="MANUAL", blocker=blocker,
            rationale=f"Bloqueador duro: {blocker}",
        )

    @staticmethod
    def _risk_value(tc: dict) -> float:
        risk = tc.get("risk", "MEDIA").upper()
        return {"ALTA": 0.9, "MEDIA": 0.5, "BAJA": 0.2}.get(risk, 0.5)

    @staticmethod
    def _tc_text(tc: dict) -> str:
        return " ".join([
            tc.get("name", ""),
            tc.get("objective", ""),
            tc.get("technique", ""),
            " ".join(tc.get("steps", [])),
        ])
