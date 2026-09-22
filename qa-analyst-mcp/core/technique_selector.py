"""
technique_selector.py — Router de técnicas ISTQB por señales del texto.

Detecta:
  - Rango numérico → BVA (7 casos canónicos)
  - Ciclo de vida / estados → Transición de Estados
  - Condiciones combinadas → Tabla de Decisión (>6 condiciones → Pairwise)
  - Integración → caso éxito + falla del tercero
  - Siempre: Error Guessing complementario
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------- patrones
_RANGE_PATTERN = re.compile(
    r"(?:entre|from|de)\s+([\d.,]+)\s*(?:y|a|and|to|-)\s*([\d.,]+)|"
    r"([\d.,]+)\s*(?:<=?|>=?|≤|≥)\s*\w[\w\s]*\s*(?:<=?|>=?|≤|≥)\s*([\d.,]+)|"
    r"(?:m[aá]ximo|m[ií]nimo|l[ií]mite|hasta|mayor que|menor que|no m[aá]s de)\s+([\d.,]+)",
    re.I,
)

_STATE_PATTERN = re.compile(
    r"\b(estado|status|estado de vida|ciclo de vida|flujo|pendiente|activo|inactivo|"
    r"aprobado|rechazado|cancelado|completado|en proceso|borrador|publicado|cerrado|"
    r"creado|enviado|recibido|procesando|fallido|expirado)\b",
    re.I,
)
_TRANSITION_PATTERN = re.compile(
    r"\b(transici[oó]n|pasa a|cambia a|de\s+\w+\s+a\s+\w+|cuando\s+\w+\s+entonces)\b",
    re.I,
)

_CONDITION_PATTERN = re.compile(
    r"\b(si|cuando|en caso de que|dado que|siempre que|a menos que|"
    r"si y solo si|con condici[oó]n)\b",
    re.I,
)
_AND_OR_PATTERN = re.compile(r"\b(y|o|and|or|además|también)\b", re.I)

_INTEGRATION_PATTERN = re.compile(
    r"\b(api|servicio|tercero|pasarela|core|webhook|integraci[oó]n|"
    r"microservicio|cola|kafka|bus|soap|rest)\b",
    re.I,
)

# Checklist de Error Guessing (filtrado por relevancia)
ERROR_GUESSING_CHECKLIST: list[dict] = [
    {"trigger": "campo",      "pattern": re.compile(r"\bcampo|campo de texto|formulario\b", re.I),
     "cases": ["Campo vacío", "Solo espacios en blanco", "Caracteres especiales (!@#$%)", "Longitud máxima + 1"]},
    {"trigger": "numérico",   "pattern": re.compile(r"\bmonto|valor|cantidad|n[uú]mero|precio|importe\b", re.I),
     "cases": ["Valor cero (0)", "Valor negativo (-1)", "Separador de miles (1.000 vs 1,000)", "Decimal con coma vs punto"]},
    {"trigger": "fecha",      "pattern": re.compile(r"\bfecha|d[ií]a|mes|a[ñn]o\b", re.I),
     "cases": ["Fecha 29 de febrero en año no bisiesto", "Día de corte (último del mes)", "Fecha pasada", "Formato de fecha incorrecto"]},
    {"trigger": "sesión",     "pattern": re.compile(r"\bsesi[oó]n|usuario|autenticaci[oó]n|login\b", re.I),
     "cases": ["Sesión expirada durante el proceso", "Doble envío (clic doble en botón)", "Recarga de página tras envío"]},
    {"trigger": "archivo",    "pattern": re.compile(r"\barchivo|documento|adjunto|carga|upload\b", re.I),
     "cases": ["Archivo vacío (0 bytes)", "Tipo de archivo no permitido", "Nombre con caracteres especiales", "Tamaño máximo + 1 byte"]},
    {"trigger": "texto_word", "pattern": re.compile(r"\bnombre|descripci[oó]n|comentario|texto\b", re.I),
     "cases": ["Texto con formato Word (comillas tipográficas, guiones largos, …)", "Texto en mayúsculas", "Texto con saltos de línea"]},
]


@dataclass
class TechniqueDecision:
    primary_technique:   str
    reason:              str
    signal_found:        str
    secondary_techniques:list[str]                    = field(default_factory=list)
    bva_ranges:          list[dict]                   = field(default_factory=list)
    states_detected:     list[str]                    = field(default_factory=list)
    conditions:          list[str]                    = field(default_factory=list)
    condition_count:     int                          = 0
    use_pairwise:        bool                         = False
    error_guessing_cases:list[str]                    = field(default_factory=list)
    extra:               dict[str, Any]               = field(default_factory=dict)


class TechniqueSelector:

    def select(self, rule_id: str, text: str) -> TechniqueDecision:
        """Selecciona la técnica principal y secundarias para una regla."""
        secondary   = []
        eg_cases    = []

        # ------ 1. BVA (rango numérico)
        range_matches = list(_RANGE_PATTERN.finditer(text))
        if range_matches:
            ranges = self._extract_ranges(text)
            eg_cases += self._error_guessing_for(text)
            return TechniqueDecision(
                primary_technique="BVA",
                reason="Rango numérico detectado (CTFL §4.2.3)",
                signal_found=range_matches[0].group(),
                secondary_techniques=["Particion_Equivalencia", "Error_Guessing"],
                bva_ranges=ranges,
                error_guessing_cases=eg_cases,
            )

        # ------ 2. Transición de Estados (ciclo de vida)
        states = self._detect_states(text)
        if states and _TRANSITION_PATTERN.search(text):
            eg_cases += self._error_guessing_for(text)
            return TechniqueDecision(
                primary_technique="Transicion_Estados",
                reason="Ciclo de vida / estados detectados (CTFL §4.2.4)",
                signal_found=_STATE_PATTERN.search(text).group(),
                secondary_techniques=["Error_Guessing"],
                states_detected=states,
                error_guessing_cases=eg_cases,
            )

        # ------ 3. Tabla de Decisión / Pairwise (condiciones combinadas)
        conditions = self._detect_conditions(text)
        if conditions:
            use_pairwise = len(conditions) > 6
            technique    = "Pairwise" if use_pairwise else "Tabla_Decision"
            reason_suffix= " (>6 condiciones → Pairwise, CTFL §4.2.5)" if use_pairwise else " (CTFL §4.2.2)"
            eg_cases    += self._error_guessing_for(text)
            return TechniqueDecision(
                primary_technique=technique,
                reason=f"Condiciones combinadas detectadas{reason_suffix}",
                signal_found=_CONDITION_PATTERN.search(text).group(),
                secondary_techniques=["Error_Guessing"],
                conditions=conditions,
                condition_count=len(conditions),
                use_pairwise=use_pairwise,
                error_guessing_cases=eg_cases,
            )

        # ------ 4. Integración (caso éxito + falla del tercero)
        int_match = _INTEGRATION_PATTERN.search(text)
        if int_match:
            eg_cases += self._error_guessing_for(text)
            return TechniqueDecision(
                primary_technique="Casos_Uso_Integracion",
                reason="Integración con sistema externo detectada (CTFL §4.2.5)",
                signal_found=int_match.group(),
                secondary_techniques=["Error_Guessing"],
                error_guessing_cases=eg_cases,
                extra={"integration_cases": ["Caso de éxito", "Caso de falla del tercero / timeout"]},
            )

        # ------ 5. Default: Partición de Equivalencia + Error Guessing
        eg_cases += self._error_guessing_for(text)
        return TechniqueDecision(
            primary_technique="Particion_Equivalencia",
            reason="Técnica por defecto — sin señales específicas detectadas (CTFL §4.2.1)",
            signal_found="(ninguna señal específica)",
            secondary_techniques=["Error_Guessing"],
            error_guessing_cases=eg_cases,
        )

    # ----------------------------------------------------------- helpers
    @staticmethod
    def _extract_ranges(text: str) -> list[dict]:
        """Extrae rangos numéricos con min y max."""
        ranges = []
        # Patrón "entre X y Y"
        for m in re.finditer(r"(?:entre|de)\s+([\d.,]+)\s*(?:y|a|-)\s*([\d.,]+)", text, re.I):
            try:
                lo = float(m.group(1).replace(",", ""))
                hi = float(m.group(2).replace(",", ""))
                ranges.append({"raw": m.group(), "min": lo, "max": hi})
            except ValueError:
                pass
        # Patrón "hasta X" / "máximo X"
        for m in re.finditer(r"(?:hasta|m[aá]ximo|no m[aá]s de)\s+([\d.,]+)", text, re.I):
            try:
                hi = float(m.group(1).replace(",", ""))
                ranges.append({"raw": m.group(), "min": 0, "max": hi})
            except ValueError:
                pass
        if not ranges:
            ranges.append({"raw": "(rango inferido)", "min": 0, "max": 100})
        return ranges

    @staticmethod
    def _detect_states(text: str) -> list[str]:
        """Extrae estados mencionados en el texto."""
        found = re.findall(
            r"\b(pendiente|activo|inactivo|aprobado|rechazado|cancelado|completado|"
            r"en proceso|borrador|publicado|cerrado|creado|enviado|recibido|"
            r"procesando|fallido|expirado)\b",
            text, re.I,
        )
        return list(dict.fromkeys(s.lower() for s in found))

    @staticmethod
    def _detect_conditions(text: str) -> list[str]:
        """Extrae condiciones lógicas del texto."""
        sentences = re.split(r"[;,\n]", text)
        conditions = []
        for s in sentences:
            if _CONDITION_PATTERN.search(s):
                stripped = s.strip()
                if len(stripped) > 5:
                    conditions.append(stripped)
        return conditions

    @staticmethod
    def _error_guessing_for(text: str) -> list[str]:
        """Filtra el checklist de Error Guessing por relevancia al texto."""
        cases = []
        for item in ERROR_GUESSING_CHECKLIST:
            if item["pattern"].search(text):
                cases.extend(item["cases"])
        # Siempre agregar casos universales
        universal = [
            "Doble envío (clic doble / F5 tras envío)",
            "Sesión expirada a mitad del proceso",
        ]
        for u in universal:
            if u not in cases:
                cases.append(u)
        return cases

    def select_all(self, rules: dict[str, str]) -> dict[str, TechniqueDecision]:
        return {rid: self.select(rid, text) for rid, text in rules.items()}
