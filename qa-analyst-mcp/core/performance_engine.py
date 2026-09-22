"""
performance_engine.py — Motor de Performance (Ley de Little + 4 perfiles de carga).

Activa si: concurrente / simultáneo / SLA / volumen / pico / batch
           o ≥3 integraciones o generación de reportes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------- señales
_PERF_SIGNALS = re.compile(
    r"\b(concurrente|simult[aá]neo|SLA|tiempo de respuesta|volumen|pico|batch|"
    r"tps|throughput|latencia|carga|reporte|generaci[oó]n de informe|"
    r"procesamiento masivo)\b",
    re.I,
)

_SLA_AVG_WARN = re.compile(
    r"\b(promedio|media|tiempo medio|average)\b.*\b(respuesta|latencia|tiempo)\b|"
    r"\b(respuesta|latencia|tiempo)\b.*\b(promedio|media|average)\b",
    re.I,
)

_TPS_PATTERN  = re.compile(r"(\d[\d.,]*)\s*(?:tps|transacciones por segundo|req/s|requests/s)", re.I)
_RT_PATTERN   = re.compile(r"p?95[<\s=]*(\d[\d.,]*)\s*(?:ms|s|seg)", re.I)
_USERS_PATTERN= re.compile(r"(\d[\d.,]*)\s*(?:usuarios? concurrentes?|concurrent users?)", re.I)


@dataclass
class PerformanceProfile:
    name:        str
    description: str
    ramp_up:     str
    steady:      str
    ramp_down:   str
    target_users:int
    notes:       str = ""


@dataclass
class PerformanceCase:
    id:              str
    name:            str
    objective:       str
    precondition:    str
    steps:           list[str]
    test_data:       str
    expected_result: str
    profile:         str
    little_n:        Optional[float] = None
    monitors:        list[str]       = field(default_factory=list)


@dataclass
class PerformancePlan:
    activated:        bool
    activation_reason:str
    concurrent_users: int
    tps:              float
    response_time_s:  float
    peak_factor:      float
    little_n:         float
    sla_warning:      Optional[str]
    profiles:         list[PerformanceProfile]
    test_cases:       list[PerformanceCase]
    tool_recommendation: str
    coordinated_omission_warning: str


class PerformanceEngine:

    PEAK_FACTOR = 3.0  # Factor pico por defecto (Ley de Little)

    def should_activate(self, full_text: str, integration_count: int) -> tuple[bool, str]:
        m = _PERF_SIGNALS.search(full_text)
        if m:
            return True, f"Señal detectada: '{m.group()}'"
        if integration_count >= 3:
            return True, f"{integration_count} integraciones detectadas (≥3)"
        return False, ""

    def generate(
        self,
        full_text: str,
        project: str,
        has_cicd: bool = False,
        peak_factor: float = PEAK_FACTOR,
    ) -> PerformancePlan:
        activated, reason = self.should_activate(full_text, self._count_integrations(full_text))

        if not activated:
            return PerformancePlan(
                activated=False,
                activation_reason="No se detectaron señales de performance.",
                concurrent_users=0, tps=0, response_time_s=0,
                peak_factor=peak_factor, little_n=0,
                sla_warning=None, profiles=[], test_cases=[],
                tool_recommendation="", coordinated_omission_warning="",
            )

        # Extraer parámetros del texto
        concurrent_users = self._extract_users(full_text)
        tps              = self._extract_tps(full_text)
        rt_s             = self._extract_rt(full_text)

        # Advertencia: SLA en promedio
        sla_warn = None
        if _SLA_AVG_WARN.search(full_text):
            sla_warn = (
                "ADVERTENCIA: El SLA detectado usa promedio/media. "
                "Los SLAs deben expresarse en percentiles p95/p99 para ser significativos. "
                "Por favor confirmar con el equipo si el SLA real es p95 o p99."
            )

        # Ley de Little: N = TPS × R(s) × factor_pico
        little_n = tps * rt_s * peak_factor

        profiles = self._build_profiles(concurrent_users, peak_factor)
        cases    = self._build_cases(project, concurrent_users, tps, rt_s, little_n, profiles)

        # Herramienta recomendada
        tool = "k6" if has_cicd else "k6 (si hay pipeline CI/CD) / JMeter (protocolos no-HTTP)"

        return PerformancePlan(
            activated=True,
            activation_reason=reason,
            concurrent_users=concurrent_users,
            tps=tps,
            response_time_s=rt_s,
            peak_factor=peak_factor,
            little_n=little_n,
            sla_warning=sla_warn,
            profiles=profiles,
            test_cases=cases,
            tool_recommendation=tool,
            coordinated_omission_warning=(
                "ADVERTENCIA: Al usar JMeter o herramientas síncronas, verificar "
                "el problema de 'Coordinated Omission': las métricas de latencia pueden "
                "subestimarse si el cliente espera respuesta antes de enviar la siguiente "
                "solicitud. Usar corrección de omisión coordenada o herramientas asíncronas."
            ),
        )

    # ----------------------------------------------------------- builders
    def _build_profiles(self, peak_users: int, factor: float) -> list[PerformanceProfile]:
        stress_users = int(peak_users * 1.5)
        return [
            PerformanceProfile(
                name="Carga (Load)",
                description="Verifica el comportamiento bajo carga esperada sostenida.",
                ramp_up="10 minutos",
                steady="45 minutos",
                ramp_down="5 minutos",
                target_users=peak_users,
                notes="Monitorear CPU, memoria, tiempos de respuesta y errores.",
            ),
            PerformanceProfile(
                name="Estrés (Stress)",
                description="Verifica el comportamiento al 150% de la carga pico.",
                ramp_up="5 minutos",
                steady="30 minutos",
                ramp_down="5 minutos",
                target_users=stress_users,
                notes=f"150% del pico = {stress_users} usuarios. Identificar punto de quiebre.",
            ),
            PerformanceProfile(
                name="Pico (Spike)",
                description="Simula un incremento súbito de carga en menos de 30 segundos.",
                ramp_up="< 30 segundos",
                steady="10 minutos",
                ramp_down="5 minutos",
                target_users=stress_users,
                notes="Verificar recuperación automática tras el pico.",
            ),
            PerformanceProfile(
                name="Resistencia (Soak)",
                description="Verifica estabilidad prolongada y detección de memory leaks.",
                ramp_up="10 minutos",
                steady="4 horas mínimo",
                ramp_down="10 minutos",
                target_users=peak_users,
                notes="Monitorear memoria heap, conexiones BD, file descriptors durante toda la prueba.",
            ),
        ]

    @staticmethod
    def _build_cases(
        project: str,
        users: int,
        tps: float,
        rt_s: float,
        little_n: float,
        profiles: list[PerformanceProfile],
    ) -> list[PerformanceCase]:
        monitors = [
            "Tiempo de respuesta p95 y p99",
            "Tasa de error (< 1%)",
            "CPU del servidor (< 80%)",
            "Memoria del servidor (< 85%)",
            "Conexiones activas a base de datos",
            "Latencia de red",
        ]
        cases = []
        for i, profile in enumerate(profiles, 1):
            cases.append(PerformanceCase(
                id=f"PERF-{i:03d}",
                name=f"Prueba de {profile.name} — {project}",
                objective=(
                    f"Verificar que el sistema mantiene el SLA definido (p95 ≤ {rt_s}s) "
                    f"bajo el perfil {profile.name} con {profile.target_users} usuarios concurrentes."
                ),
                precondition=(
                    f"Ambiente de performance configurado con datos representativos de producción. "
                    f"Herramienta de monitoreo activa. {profile.target_users} usuarios virtuales disponibles."
                ),
                steps=[
                    f"Configurar el perfil '{profile.name}': ramp-up {profile.ramp_up}, "
                    f"steady {profile.steady}, ramp-down {profile.ramp_down}.",
                    f"Iniciar la ejecución con {profile.target_users} usuarios concurrentes.",
                    "Monitorear en tiempo real los indicadores definidos.",
                    "Registrar métricas al finalizar la prueba.",
                    "Comparar resultados contra el SLA objetivo.",
                ],
                test_data=(
                    f"Usuarios concurrentes: {profile.target_users} | "
                    f"TPS objetivo: {tps:.1f} | "
                    f"Tiempo de respuesta objetivo p95: {rt_s}s | "
                    f"Ley de Little N estimado: {little_n:.1f} peticiones en vuelo"
                ),
                expected_result=(
                    f"p95 ≤ {rt_s}s, p99 ≤ {rt_s * 1.5:.2f}s. "
                    f"Tasa de error < 1%. CPU < 80%. Memoria estable sin crecimiento sostenido."
                ),
                profile=profile.name,
                little_n=little_n,
                monitors=monitors,
            ))
        return cases

    # ----------------------------------------------------------- extractors
    @staticmethod
    def _extract_users(text: str) -> int:
        m = _USERS_PATTERN.search(text)
        if m:
            return int(m.group(1).replace(",", "").replace(".", ""))
        return 100  # default

    @staticmethod
    def _extract_tps(text: str) -> float:
        m = _TPS_PATTERN.search(text)
        if m:
            return float(m.group(1).replace(",", ""))
        return 10.0  # default

    @staticmethod
    def _extract_rt(text: str) -> float:
        m = _RT_PATTERN.search(text)
        if m:
            val = float(m.group(1).replace(",", ""))
            # Si está en ms, convertir a segundos
            raw = m.group(0).lower()
            if "ms" in raw:
                val /= 1000
            return val
        return 2.0  # default 2s

    @staticmethod
    def _count_integrations(text: str) -> int:
        matches = re.findall(
            r"\b(api|servicio|pasarela|tercero|webhook|kafka|cola|bus|soap|microservicio)\b",
            text, re.I,
        )
        return len(set(m.lower() for m in matches))
