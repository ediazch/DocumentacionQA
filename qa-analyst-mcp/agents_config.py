"""
agents_config.py — Sistema multi-agente con monitoreo de tokens en tiempo real.

Arquitectura:
  - Agente Principal (pago)   → modelo potente, procesamiento complejo
  - Agente Fallback (gratuito)→ modelo liviano, se activa al agotar tokens
  - TokenMonitor              → monitorea uso en tiempo real y decide handoff
  - MemoryManager             → mantiene contexto entre agentes y sesiones

Skills cargadas:
  - qa_analysis_skill   → análisis de documentos QA (skill global)
  - test_case_skill     → generación de casos de prueba (skill global)
  - webapp_testing_skill→ pruebas de interfaces (skill específica)
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ── OpenAI Agents SDK
from agents import Agent, Runner, handoff
from agents.extensions.handoff_filters import remove_all_tools


# ═══════════════════════════════════════════════════════════════════
# SKILLS — Instrucciones especializadas por dominio
# ═══════════════════════════════════════════════════════════════════

# Skill global 1: Análisis QA
QA_ANALYSIS_SKILL = """
Eres un experto en análisis de calidad de software (ISTQB CTFL v4.0).
Cuando recibes un documento BRD, HU o Requerimiento:
1. Extrae las reglas de negocio y criterios de aceptación
2. Clasifica por nivel (componente/sistema/integración/aceptación)
3. Identifica el tipo (funcional/no funcional)
4. Selecciona la técnica de prueba apropiada (BVA, Tabla de Decisión, etc.)
5. Evalúa riesgos (Probabilidad × Impacto)
Responde siempre en español. Nunca uses lenguaje técnico de BD en los casos.
"""

# Skill global 2: Generación de casos de prueba
TEST_CASE_SKILL = """
Para cada regla de negocio, genera casos de prueba en 3 dimensiones:
  1. Funcionalidad  → flujo positivo y negativo básico
  2. Validación     → tipos de datos, formatos, rangos, fechas, elementos UI
  3. Excepción/Alerta → mensajes de alerta, manejo de errores, casos borde

Para campos:
  - Numérico: letras, cero, negativo, separador de miles
  - Texto: caracteres especiales, longitud máxima, solo espacios
  - Email: sin @, sin dominio, con espacios
  - Fecha: formato incorrecto, 29-feb, rango inválido
  - Fecha inicial/final: final < inicial, ambas vacías

Para elementos UI:
  - Botones: doble clic, sin datos obligatorios, cancelar
  - Listas: sin selección, dependencia entre listas
  - Checkbox/Radio: sin marcar, exclusividad

Forma de organización según preferencia del usuario:
  Forma 1: Todos F → Todos V → Todos E (por bloques)
  Forma 2: F+V+E por cada regla (por caso completo)

Incluir siempre mensajes de alerta aunque el BRD no los especifique.
"""

# Skill específica: Pruebas de interfaces web
WEBAPP_TESTING_SKILL = """
Para pruebas de interfaces web (basado en anthropics/skills webapp-testing):
- Verificar funcionalidad de cada elemento visible
- Validar navegación entre pantallas
- Verificar mensajes de error y alertas
- Probar en distintos tamaños de pantalla si aplica
- Verificar accesibilidad básica (campos con label, botones descriptivos)
"""

# Skill específica: Construcción de MCP
MCP_BUILDER_SKILL = """
Para construir servidores MCP de calidad (basado en anthropics/skills mcp-builder):
- Usar FastMCP para Python
- Nombrar herramientas con verbos de acción: analyze_document, generate_cases
- Retornar respuestas estructuradas (JSON)
- Manejar errores con mensajes accionables
- Documentar cada herramienta con descripción y parámetros
"""


# ═══════════════════════════════════════════════════════════════════
# MONITOR DE TOKENS
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TokenUsage:
    prompt_tokens:     int = 0
    completion_tokens: int = 0
    total_tokens:      int = 0
    cost_usd:          float = 0.0
    timestamp:         str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TokenMonitor:
    """
    Monitorea el uso de tokens en tiempo real.
    Activa el fallback al agente gratuito cuando se supera el umbral.
    """

    # Límites configurables por entorno
    DEFAULT_PAID_LIMIT   = int(os.getenv("PAID_TOKEN_LIMIT",   "100000"))
    DEFAULT_FREE_LIMIT   = int(os.getenv("FREE_TOKEN_LIMIT",   "50000"))
    WARN_THRESHOLD_PCT   = float(os.getenv("WARN_THRESHOLD",   "0.80"))   # alerta al 80%

    # Costo estimado por token (GPT-4o como referencia)
    COST_PER_1K_INPUT    = 0.0025   # USD
    COST_PER_1K_OUTPUT   = 0.010    # USD

    def __init__(self, log_path: Path = Path("output/token_usage.json")):
        self.log_path       = log_path
        self.paid_used      = 0
        self.free_used      = 0
        self.paid_limit     = self.DEFAULT_PAID_LIMIT
        self.free_limit     = self.DEFAULT_FREE_LIMIT
        self.history: list[dict] = []
        self.using_fallback = False
        self._load()

    def _load(self) -> None:
        if self.log_path.exists():
            with open(self.log_path, encoding="utf-8") as f:
                data = json.load(f)
            self.paid_used      = data.get("paid_used", 0)
            self.free_used      = data.get("free_used", 0)
            self.using_fallback = data.get("using_fallback", False)
            self.history        = data.get("history", [])

    def _save(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "w", encoding="utf-8") as f:
            json.dump({
                "paid_used":      self.paid_used,
                "free_used":      self.free_used,
                "paid_limit":     self.paid_limit,
                "free_limit":     self.free_limit,
                "using_fallback": self.using_fallback,
                "updated_at":     datetime.now(timezone.utc).isoformat(),
                "history":        self.history[-50:],  # últimas 50 entradas
            }, f, indent=2, ensure_ascii=False)

    def record(self, prompt_tokens: int, completion_tokens: int,
               agent_type: str = "paid") -> TokenUsage:
        total = prompt_tokens + completion_tokens
        cost  = (prompt_tokens / 1000 * self.COST_PER_1K_INPUT +
                 completion_tokens / 1000 * self.COST_PER_1K_OUTPUT)

        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            cost_usd=cost,
        )

        if agent_type == "paid":
            self.paid_used += total
        else:
            self.free_used += total

        self.history.append({
            "agent":      agent_type,
            "tokens":     total,
            "cost_usd":   round(cost, 6),
            "timestamp":  usage.timestamp,
        })
        self._save()
        self._print_status(agent_type)
        return usage

    def should_fallback(self) -> bool:
        """Determina si se debe cambiar al agente gratuito."""
        if self.paid_used >= self.paid_limit:
            if not self.using_fallback:
                print(f"\n[TOKEN MONITOR] Límite de agente pago alcanzado "
                      f"({self.paid_used:,}/{self.paid_limit:,} tokens). "
                      f"Activando agente gratuito...")
                self.using_fallback = True
                self._save()
            return True
        return False

    def warn_if_approaching(self) -> None:
        """Avisa cuando se acerca al límite."""
        pct = self.paid_used / self.paid_limit
        if pct >= self.WARN_THRESHOLD_PCT and not self.using_fallback:
            remaining = self.paid_limit - self.paid_used
            print(f"\n[TOKEN MONITOR] AVISO: {pct*100:.0f}% del límite usado. "
                  f"Quedan ~{remaining:,} tokens del agente pago.")

    def _print_status(self, agent_type: str) -> None:
        total_cost = sum(e["cost_usd"] for e in self.history)
        pct_paid   = min(self.paid_used / self.paid_limit * 100, 100)
        agent_label= "PAGO" if agent_type == "paid" else "GRATUITO"
        print(f"[TOKENS] Agente: {agent_label} | "
              f"Pago: {self.paid_used:,}/{self.paid_limit:,} ({pct_paid:.1f}%) | "
              f"Costo acumulado: ${total_cost:.4f} USD")

    def reset_session(self) -> None:
        """Reinicia el contador de sesión (no el histórico)."""
        self.paid_used      = 0
        self.free_used      = 0
        self.using_fallback = False
        self._save()
        print("[TOKEN MONITOR] Sesión reiniciada.")

    def status(self) -> dict:
        return {
            "paid_used":      self.paid_used,
            "paid_limit":     self.paid_limit,
            "free_used":      self.free_used,
            "free_limit":     self.free_limit,
            "using_fallback": self.using_fallback,
            "total_cost_usd": round(sum(e["cost_usd"] for e in self.history), 4),
        }


# ═══════════════════════════════════════════════════════════════════
# MEMORY MANAGER — Contexto persistente entre agentes y sesiones
# ═══════════════════════════════════════════════════════════════════

class MemoryManager:
    """
    Mantiene el contexto de conversación entre:
    - Cambios de agente (pago → gratuito)
    - Reinicios de sesión
    - Múltiples documentos procesados
    """

    def __init__(self, memory_path: Path = Path("output/memory.json")):
        self.memory_path = memory_path
        self.context: dict[str, Any] = {
            "conversation_history": [],
            "current_project":      None,
            "current_doc":          None,
            "rules_extracted":      {},
            "cases_generated":      0,
            "org_mode":             2,
            "detail_level":         3,
            "last_agent":           "paid",
            "session_start":        datetime.now(timezone.utc).isoformat(),
        }
        self._load()

    def _load(self) -> None:
        if self.memory_path.exists():
            with open(self.memory_path, encoding="utf-8") as f:
                saved = json.load(f)
            self.context.update(saved)

    def _save(self) -> None:
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.memory_path, "w", encoding="utf-8") as f:
            json.dump(self.context, f, indent=2, ensure_ascii=False)

    def add_message(self, role: str, content: str, agent: str = "paid") -> None:
        self.context["conversation_history"].append({
            "role":      role,
            "content":   content,
            "agent":     agent,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        # Mantener solo los últimos 50 mensajes en memoria
        self.context["conversation_history"] = \
            self.context["conversation_history"][-50:]
        self._save()

    def set(self, key: str, value: Any) -> None:
        self.context[key] = value
        self._save()

    def get(self, key: str, default: Any = None) -> Any:
        return self.context.get(key, default)

    def get_history_for_agent(self, last_n: int = 10) -> list[dict]:
        """Retorna el historial reciente para pasar contexto al nuevo agente."""
        history = self.context["conversation_history"][-last_n:]
        return [{"role": m["role"], "content": m["content"]} for m in history]

    def summarize_context(self) -> str:
        """Genera un resumen del contexto actual para el agente de fallback."""
        return (
            f"Contexto actual de la sesión QA:\n"
            f"- Proyecto: {self.context.get('current_project', 'No definido')}\n"
            f"- Documento: {self.context.get('current_doc', 'No definido')}\n"
            f"- Reglas extraídas: {len(self.context.get('rules_extracted', {}))}\n"
            f"- Casos generados: {self.context.get('cases_generated', 0)}\n"
            f"- Forma de organización: {self.context.get('org_mode', 2)}\n"
            f"- Nivel de detalle: {self.context.get('detail_level', 3)}\n"
            f"- Último agente activo: {self.context.get('last_agent', 'paid')}\n"
        )


# ═══════════════════════════════════════════════════════════════════
# AGENTES
# ═══════════════════════════════════════════════════════════════════

def build_agents(memory: MemoryManager) -> tuple[Agent, Agent]:
    """
    Construye el agente principal (pago) y el agente de fallback (gratuito).
    Ambos comparten el mismo sistema de instrucciones y contexto de memoria.
    """

    # Instrucciones base compartidas
    base_instructions = f"""
{QA_ANALYSIS_SKILL}

{TEST_CASE_SKILL}

{WEBAPP_TESTING_SKILL}

Contexto de sesión actual:
{memory.summarize_context()}

IMPORTANTE:
- Responde siempre en español
- Nunca uses lenguaje técnico de bases de datos en los casos de prueba
- Siempre incluye mensajes de alerta aunque el BRD no los especifique
- Mantén la coherencia con el contexto de sesión anterior
"""

    # Agente gratuito (fallback) — sin herramientas pesadas
    fallback_agent = Agent(
        name="QA_Analyst_Free",
        model=os.getenv("FREE_MODEL", "gpt-4o-mini"),
        instructions=base_instructions + "\nModo: Agente gratuito activo. "
                     "Responde de forma concisa optimizando el uso de tokens.",
    )

    # Agente principal (pago) — con handoff al gratuito
    paid_agent = Agent(
        name="QA_Analyst_Pro",
        model=os.getenv("PAID_MODEL", "gpt-4o"),
        instructions=base_instructions + "\nModo: Agente principal activo.",
        handoffs=[
            handoff(
                agent=fallback_agent,
                input_filter=remove_all_tools,
                tool_name_override="switch_to_free_agent",
                tool_description_override=(
                    "Transfiere la conversación al agente gratuito cuando se "
                    "agotan los tokens del agente pago. El contexto se preserva."
                ),
            )
        ],
    )

    return paid_agent, fallback_agent


# ═══════════════════════════════════════════════════════════════════
# ORQUESTADOR PRINCIPAL
# ═══════════════════════════════════════════════════════════════════

class QAAgentOrchestrator:
    """
    Orquestador que:
    1. Selecciona el agente correcto (pago o gratuito)
    2. Monitorea tokens en tiempo real
    3. Hace handoff automático al agotarse tokens
    4. Mantiene contexto de memoria entre cambios de agente
    """

    def __init__(self):
        self.memory  = MemoryManager()
        self.monitor = TokenMonitor()
        self.paid_agent, self.fallback_agent = build_agents(self.memory)

    def run(self, user_message: str) -> str:
        """Procesa un mensaje del usuario con el agente correcto."""

        # Determinar qué agente usar
        if self.monitor.should_fallback():
            agent      = self.fallback_agent
            agent_type = "free"
        else:
            agent      = self.paid_agent
            agent_type = "paid"
            self.monitor.warn_if_approaching()

        # Construir historial de conversación para contexto
        history = self.memory.get_history_for_agent(last_n=10)

        # Si hubo cambio de agente, inyectar resumen de contexto
        if agent_type != self.memory.get("last_agent"):
            context_summary = self.memory.summarize_context()
            history.insert(0, {
                "role":    "system",
                "content": f"CONTEXTO TRANSFERIDO DEL AGENTE ANTERIOR:\n{context_summary}",
            })
            print(f"\n[HANDOFF] Contexto transferido al agente {agent_type.upper()}.")

        # Agregar mensaje del usuario al historial
        history.append({"role": "user", "content": user_message})

        # Ejecutar agente
        print(f"\n[AGENTE] Procesando con: {agent.name}...")
        start = time.time()

        result = Runner.run_sync(
            agent,
            history,
        )

        elapsed = time.time() - start
        response = result.final_output

        # Registrar uso de tokens (estimado si no viene en result)
        prompt_tokens     = getattr(result, "input_token_count",  len(str(history)) // 4)
        completion_tokens = getattr(result, "output_token_count", len(str(response)) // 4)
        self.monitor.record(prompt_tokens, completion_tokens, agent_type)

        # Actualizar memoria
        self.memory.add_message("user",      user_message, agent_type)
        self.memory.add_message("assistant", response,     agent_type)
        self.memory.set("last_agent", agent_type)

        print(f"[TIEMPO] Respuesta en {elapsed:.1f}s")
        return response

    def status(self) -> None:
        """Muestra el estado actual del sistema."""
        s = self.monitor.status()
        print(f"""
╔══════════════════════════════════════════╗
║   QA Intelligence Suite — Estado        ║
╠══════════════════════════════════════════╣
║ Agente activo : {'GRATUITO' if s['using_fallback'] else 'PAGO (Principal)':25s}║
║ Tokens pago   : {s['paid_used']:>8,} / {s['paid_limit']:>8,}        ║
║ Tokens free   : {s['free_used']:>8,} / {s['free_limit']:>8,}        ║
║ Costo total   : ${s['total_cost_usd']:>8.4f} USD               ║
║ Proyecto      : {str(self.memory.get('current_project','—'))[:25]:25s}║
║ Casos gen.    : {self.memory.get('cases_generated', 0):>8,}                    ║
╚══════════════════════════════════════════╝""")

    def reset_tokens(self) -> None:
        """Reinicia los contadores de tokens para nueva sesión."""
        self.monitor.reset_session()
        self.memory.set("last_agent", "paid")
        # Reconstruir agentes con contexto actualizado
        self.paid_agent, self.fallback_agent = build_agents(self.memory)
