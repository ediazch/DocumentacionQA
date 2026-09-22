"""
istqb_classifier.py — Clasificación ISTQB de 4 dimensiones con señal explícita.

D1 NIVEL: componente | integracion_componentes | sistema | integracion_sistema | aceptacion
D2 TIPO:  funcional | performance | seguridad | usabilidad | compatibilidad | fiabilidad
D3 PERSPECTIVA: black_box | white_box_recomendacion
D4 MOTIVO: primera_ejecucion | candidato_regresion | one_shot
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


# ------------------------------------------------------------------ señales
_D1_SIGNALS: list[tuple[str, str, re.Pattern]] = [
    # (nivel, descripción_señal, regex)
    ("integracion_sistema",    "integración con sistema externo",
     re.compile(r"\b(api|servicio|core|pasarela|tercero|webhook|soap|rest|microservicio|bus|cola|kafka|mq)\b", re.I)),
    ("aceptacion",             "criterio de aceptación / UAT",
     re.compile(r"\b(criterio de aceptaci[oó]n|UAT|user acceptance|prueba de aceptaci[oó]n)\b", re.I)),
    ("componente",             "cálculo / fórmula / redondeo",
     re.compile(r"\b(f[oó]rmula|redondeo|c[aá]lculo|algoritmo|interés|amortizaci[oó]n|comisi[oó]n)\b", re.I)),
]
_D1_DEFAULT = "sistema"

_D2_SIGNALS: list[tuple[str, str, re.Pattern]] = [
    ("performance",    "carga / SLA / concurrencia",
     re.compile(r"\b(concurrente|simult[aá]neo|SLA|tiempo de respuesta|volumen|pico|batch|tps|throughput|latencia)\b", re.I)),
    ("seguridad",      "autenticación / datos sensibles / cifrado",
     re.compile(r"\b(contrase[ñn]a|cifrado|autenticaci[oó]n|datos personales|PCI|PII|rol|permiso|acceso|token|JWT)\b", re.I)),
    ("usabilidad",     "interfaz / accesibilidad / UX",
     re.compile(r"\b(usabilidad|interfaz|accesibilidad|UX|navegaci[oó]n|dise[ñn]o|pantalla|flujo de usuario)\b", re.I)),
    ("compatibilidad", "navegador / dispositivo / SO",
     re.compile(r"\b(navegador|browser|dispositivo|m[oó]vil|SO|sistema operativo|android|ios|chrome|firefox)\b", re.I)),
    ("fiabilidad",     "disponibilidad / backup / recuperación",
     re.compile(r"\b(disponibilidad|backup|recuperaci[oó]n|failover|redundancia|uptime|MTTR|MTBF)\b", re.I)),
]
_D2_DEFAULT = "funcional"

_D3_COMPLEX = re.compile(
    r"\b(f[oó]rmula|c[aá]lculo|algoritmo|interés|redondeo|amortizaci[oó]n|descuento|impuesto|comisi[oó]n)\b",
    re.I,
)

_D4_ONE_SHOT = re.compile(
    r"\b(migraci[oó]n inicial|datafix|conversi[oó]n [uú]nica|one.?shot|[uú]nica ejecuci[oó]n)\b",
    re.I,
)

# Validación cruzada: caja blanca NO aplica en aceptación ni integración_sistema
_WHITEBOX_FORBIDDEN_LEVELS = {"aceptacion", "integracion_sistema"}


@dataclass
class Classification:
    rule_id:     str
    level:       str          # D1
    level_signal: str
    type_:       str          # D2
    type_signal: str
    perspective: str          # D3
    whitebox_recommendation: bool
    motive:      str          # D4
    cross_validation_warning: Optional[str] = None


class ISTQBClassifier:

    def classify(self, rule_id: str, text: str) -> Classification:
        # D1 — Nivel
        level        = _D1_DEFAULT
        level_signal = "default (sin señal detectada)"
        for lvl, signal_desc, pattern in _D1_SIGNALS:
            m = pattern.search(text)
            if m:
                level        = lvl
                level_signal = f"'{m.group()}' → {signal_desc}"
                break

        # D2 — Tipo
        type_        = _D2_DEFAULT
        type_signal  = "default funcional (sin señal no funcional)"
        for t, signal_desc, pattern in _D2_SIGNALS:
            m = pattern.search(text)
            if m:
                type_        = t
                type_signal  = f"'{m.group()}' → {signal_desc}"
                break

        # D3 — Perspectiva
        whitebox_rec = bool(_D3_COMPLEX.search(text))
        perspective  = "black_box"  # QA siempre black_box
        if whitebox_rec:
            perspective = "black_box + recomendacion_white_box"

        # D4 — Motivo
        if _D4_ONE_SHOT.search(text):
            motive = "one_shot"
        else:
            motive = "primera_ejecucion+candidato_regresion"

        # Validación cruzada (caja blanca prohibida en aceptación/integración_sistema)
        cross_warn = None
        if whitebox_rec and level in _WHITEBOX_FORBIDDEN_LEVELS:
            cross_warn = (
                f"[ADVERTENCIA] La recomendación white-box no aplica para nivel '{level}' "
                f"(CTFL §4.3). Rediseñar como black-box exclusivamente."
            )

        return Classification(
            rule_id=rule_id,
            level=level,
            level_signal=level_signal,
            type_=type_,
            type_signal=type_signal,
            perspective=perspective,
            whitebox_recommendation=whitebox_rec,
            motive=motive,
            cross_validation_warning=cross_warn,
        )

    def classify_all(self, rules: dict[str, str]) -> dict[str, Classification]:
        return {rid: self.classify(rid, text) for rid, text in rules.items()}

    @staticmethod
    def level_label(level: str) -> str:
        return {
            "componente":            "Componente (CTFL §2.2.1)",
            "integracion_componentes":"Integración de Componentes (CTFL §2.2.2)",
            "sistema":               "Sistema (CTFL §2.2.3)",
            "integracion_sistema":   "Integración de Sistema (CTFL §2.2.4)",
            "aceptacion":            "Aceptación (CTFL §2.2.5)",
        }.get(level, level)

    @staticmethod
    def type_label(type_: str) -> str:
        return {
            "funcional":       "Funcional (CTFL §2.3.1)",
            "performance":     "No Funcional — Performance (ISO/IEC 25010)",
            "seguridad":       "No Funcional — Seguridad (ISO/IEC 25010)",
            "usabilidad":      "No Funcional — Usabilidad (ISO/IEC 25010)",
            "compatibilidad":  "No Funcional — Compatibilidad (ISO/IEC 25010)",
            "fiabilidad":      "No Funcional — Fiabilidad (ISO/IEC 25010)",
        }.get(type_, type_)
