"""
mcp_server.py — Servidor MCP del QA Intelligence Suite v2.0

Expone las herramientas del pipeline como un servidor MCP estándar
invocable desde Claude, Cursor, Windsurf u otros agentes compatibles.

Herramientas expuestas:
  - analyze_document       → extrae reglas de un BRD/HU/Requerimiento
  - generate_cases         → genera casos de prueba con 3 dimensiones
  - generate_deliverables  → produce Word, Excel y CSV
  - check_version          → verifica si el documento ya fue procesado
  - token_status           → estado del monitor de tokens
  - list_processed         → lista documentos procesados

Uso:
  env\Scripts\python mcp_server.py          (stdio — para Aura/Claude)
  env\Scripts\python mcp_server.py --http   (HTTP — para otros clientes)
"""
from __future__ import annotations

import sys
import json
import argparse
from pathlib import Path

# Agregar el directorio actual al path
sys.path.insert(0, str(Path(__file__).parent))

from fastmcp import FastMCP
from main import (
    read_document, extract_rules, generate_risks,
    generate_test_cases, build_traceability, deliverable_name, OUTPUT_DIR,
)
from core.istqb_classifier   import ISTQBClassifier
from core.technique_selector import TechniqueSelector
from core.pairwise_generator import PairwiseGenerator
from core.coverage_metrics   import CoverageMetrics
from core.performance_engine import PerformanceEngine
from core.owasp_matrix       import OWASPEngine
from core.abuse_case_generator import AbuseCaseGenerator
from core.automation_engine  import AutomationEngine
from core.maintenance_testing import MaintenanceTesting
from core.corpus_manager     import CorpusManager
from core.version_manager    import VersionManager, VersionDecision, sha256
from core.version_manager    import VersionResult
from generators.word_generator  import WordGenerator
from generators.excel_generator import ExcelGenerator

# ── Instancias compartidas
corpus = CorpusManager(OUTPUT_DIR / "corpus.json")
vm     = VersionManager(corpus)

# ── Servidor MCP
mcp = FastMCP(
    name="qa-analyst-mcp",
    instructions=(
        "Servidor MCP del QA Intelligence Suite v2.0. "
        "Transforma documentos BRD, HU o Requerimientos en casos de prueba "
        "aplicando ISTQB CTFL v4.0, con entregables Word, Excel y CSV."
    ),
)


# ═══════════════════════════════════════════════════════════════════
# HERRAMIENTA 1 — Analizar documento
# ═══════════════════════════════════════════════════════════════════
@mcp.tool
def analyze_document(
    doc_path: str,
    project:  str = "Proyecto",
) -> dict:
    """
    Extrae y clasifica las reglas de negocio de un documento BRD, HU o Requerimiento.

    Args:
        doc_path: Ruta al documento (.docx, .pdf, .txt, .md)
        project:  Nombre del proyecto

    Returns:
        Diccionario con reglas extraídas, clasificaciones ISTQB y técnicas detectadas.
    """
    try:
        content = read_document(doc_path)
        rules   = extract_rules(content)
        clf     = ISTQBClassifier()
        sel     = TechniqueSelector()
        clss    = clf.classify_all(rules)
        tds     = sel.select_all(rules)

        # Verificar versión
        doc_name   = Path(doc_path).name
        doc_hash   = sha256(content)
        vr         = vm.check(project, doc_name, content)

        return {
            "status":       "ok",
            "project":      project,
            "doc_name":     doc_name,
            "doc_hash":     doc_hash[:16] + "…",
            "version":      vr.version_number,
            "decision":     vr.decision.value,
            "rules_count":  len(rules),
            "rules":        {
                rid: {
                    "text":      text[:100],
                    "level":     clss[rid].level      if rid in clss else "",
                    "type":      clss[rid].type_      if rid in clss else "",
                    "technique": tds[rid].primary_technique if rid in tds else "",
                }
                for rid, text in list(rules.items())[:20]
            },
            "techniques_summary": {
                td.primary_technique: sum(
                    1 for t in tds.values()
                    if t.primary_technique == td.primary_technique
                )
                for td in tds.values()
            },
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ═══════════════════════════════════════════════════════════════════
# HERRAMIENTA 2 — Generar casos de prueba
# ═══════════════════════════════════════════════════════════════════
@mcp.tool
def generate_cases(
    doc_path:     str,
    project:      str = "Proyecto",
    org_mode:     int = 2,
    detail_level: int = 3,
) -> dict:
    """
    Genera casos de prueba para un documento con las 3 dimensiones ISTQB.

    Args:
        doc_path:     Ruta al documento
        project:      Nombre del proyecto
        org_mode:     1=por bloques, 2=por caso completo (recomendado)
        detail_level: 1=solo funcional, 2=+validación, 3=+excepción (recomendado)

    Returns:
        Resumen de casos generados por dimensión y técnica.
    """
    try:
        content  = read_document(doc_path)
        rules    = extract_rules(content)
        clf      = ISTQBClassifier()
        sel      = TechniqueSelector()
        clss     = clf.classify_all(rules)
        tds      = sel.select_all(rules)
        risks    = generate_risks(rules, clss, content)
        pw       = PairwiseGenerator()
        cases    = generate_test_cases(
            rules, tds, clss, pw, risks, content,
            org_mode=org_mode, detail_level=detail_level,
        )

        from collections import Counter
        dims = Counter(tc.get("dimension", "?") for tc in cases)

        return {
            "status":        "ok",
            "total_cases":   len(cases),
            "org_mode":      org_mode,
            "detail_level":  detail_level,
            "by_dimension":  dict(dims),
            "by_technique":  dict(Counter(tc.get("technique","?") for tc in cases)),
            "sample_cases":  [
                {
                    "id":        tc["id"],
                    "dimension": tc.get("dimension", ""),
                    "name":      tc["name"][:80],
                    "technique": tc.get("technique", ""),
                }
                for tc in cases[:5]
            ],
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ═══════════════════════════════════════════════════════════════════
# HERRAMIENTA 3 — Generar entregables completos
# ═══════════════════════════════════════════════════════════════════
@mcp.tool
def generate_deliverables(
    doc_path:     str,
    project:      str = "Proyecto",
    org_mode:     int = 2,
    detail_level: int = 3,
    has_cicd:     bool = False,
) -> dict:
    """
    Ejecuta el pipeline completo y genera Word, Excel y CSV.

    Args:
        doc_path:     Ruta al documento BRD/HU/Requerimiento
        project:      Nombre del proyecto
        org_mode:     1=por bloques, 2=por caso completo
        detail_level: 1=funcional, 2=+validación, 3=+excepción
        has_cicd:     True si hay pipeline CI/CD (para recomendación k6)

    Returns:
        Rutas de los 3 archivos generados y métricas del proceso.
    """
    try:
        # Leer y analizar
        content  = read_document(doc_path)
        doc_name = Path(doc_path).name
        doc_hash = sha256(content)
        rules    = extract_rules(content)
        clf      = ISTQBClassifier()
        sel      = TechniqueSelector()
        clss     = clf.classify_all(rules)
        tds      = sel.select_all(rules)
        risks    = generate_risks(rules, clss, content)
        pw       = PairwiseGenerator()

        # Versión
        vr = vm.check(project, doc_name, content)
        if vr.decision == VersionDecision.REUSE:
            deliverables = corpus.get_deliverables(project, doc_name)
            return {
                "status":      "reused",
                "message":     "Documento ya procesado. Entregables existentes reutilizados.",
                "deliverables": deliverables,
            }

        # Generar casos
        cases = generate_test_cases(
            rules, tds, clss, pw, risks, content,
            org_mode=org_mode, detail_level=detail_level,
        )

        # Motores de dominio
        perf   = PerformanceEngine().generate(content, project, has_cicd)
        owasp  = OWASPEngine().generate(content)
        abuse  = AbuseCaseGenerator().generate(content, project)
        auto   = AutomationEngine().generate(cases, content)
        maint  = MaintenanceTesting().analyze(vr.regeneration_plan, rules, cases)

        # Agregar abuse + performance
        for ac in abuse:
            cases.append({
                "id": ac.id, "name": ac.name, "objective": ac.objective,
                "precondition": ac.precondition, "steps": ac.steps,
                "test_data": ac.test_data, "expected_result": ac.expected_result,
                "priority": ac.priority, "level": "Sistema", "type": "seguridad",
                "technique": "Abuse_Case", "requirement_ref": "OWASP-" + ac.owasp_ref,
                "risk": "ALTA", "automation_label": "MANUAL", "estimated_min": 20,
                "dimension": "Excepcion",
            })
        if perf.activated:
            for ptc in perf.test_cases:
                cases.append({
                    "id": ptc.id, "name": ptc.name, "objective": ptc.objective,
                    "precondition": ptc.precondition, "steps": ptc.steps,
                    "test_data": ptc.test_data, "expected_result": ptc.expected_result,
                    "priority": "ALTA", "level": "Sistema", "type": "performance",
                    "technique": "Performance", "requirement_ref": "PERF",
                    "risk": "ALTA", "automation_label": "AUTOMATE_HIGH",
                    "estimated_min": 120, "dimension": "Funcionalidad",
                })

        # Cobertura y trazabilidad
        traz = build_traceability(rules, cases, clss, tds)
        cov  = CoverageMetrics().calculate(rules, cases, tds, risks)
        v    = vr.version_number

        # Rutas de salida
        xlsx_path = deliverable_name(project, doc_name, v, "TestCases", "xlsx")
        csv_path  = deliverable_name(project, doc_name, v, "TestCases", "csv")
        docx_path = deliverable_name(project, doc_name, v, "QADeck",    "docx")

        # Generar archivos
        WordGenerator().generate(
            output_path=docx_path, project=project,
            doc_name=doc_name, doc_version=v, doc_hash=doc_hash,
            rules=rules, classifications=clss, technique_decisions=tds,
            test_cases=cases, risks=risks, traceability=traz,
            coverage_report=cov, performance_plan=perf,
            owasp_matrix=owasp, automation_report=auto,
            maintenance_report=maint, version_result=vr,
        )

        eg         = ExcelGenerator()
        excel_rows = eg.generate_xlsx(xlsx_path, cases, risks, traz, cov, project)
        csv_rows   = eg.generate_csv(xlsx_path, csv_path)

        # Persistir
        corpus.save_document(
            project, doc_name, content, doc_hash, v, rules,
            [docx_path, xlsx_path, csv_path],
        )

        return {
            "status":       "ok",
            "project":      project,
            "version":      v,
            "total_cases":  len(cases),
            "coverage_pct": cov.requirements_coverage_pct,
            "deliverables": {
                "word":  docx_path,
                "excel": xlsx_path,
                "csv":   csv_path,
            },
            "metrics": {
                "rules":       len(rules),
                "cases":       len(cases),
                "excel_rows":  excel_rows,
                "csv_rows":    csv_rows,
                "performance": perf.activated,
                "security":    owasp.activated,
            },
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ═══════════════════════════════════════════════════════════════════
# HERRAMIENTA 4 — Verificar versión
# ═══════════════════════════════════════════════════════════════════
@mcp.tool
def check_version(doc_path: str, project: str = "Proyecto") -> dict:
    """
    Verifica si un documento ya fue procesado o si es nuevo/actualizado.

    Args:
        doc_path: Ruta al documento
        project:  Nombre del proyecto

    Returns:
        Decisión de versión: REUSE, NEW o INCREMENTAL_UPDATE
    """
    try:
        content  = read_document(doc_path)
        doc_name = Path(doc_path).name
        vr       = vm.check(project, doc_name, content)
        return {
            "status":   "ok",
            "decision": vr.decision.value,
            "version":  vr.version_number,
            "message":  {
                "REUSE":              "Documento ya procesado. Se reutilizan los entregables existentes.",
                "NEW":                "Documento nuevo. Se ejecutará el pipeline completo.",
                "INCREMENTAL_UPDATE": f"Documento actualizado. Solo se regenerarán las reglas afectadas: {vr.regeneration_plan}",
            }.get(vr.decision.value, ""),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ═══════════════════════════════════════════════════════════════════
# HERRAMIENTA 5 — Estado de tokens
# ═══════════════════════════════════════════════════════════════════
@mcp.tool
def token_status() -> dict:
    """
    Retorna el estado actual del monitor de tokens y el agente activo.
    """
    try:
        from agents_config import TokenMonitor
        monitor = TokenMonitor()
        return {"status": "ok", **monitor.status()}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ═══════════════════════════════════════════════════════════════════
# HERRAMIENTA 6 — Listar documentos procesados
# ═══════════════════════════════════════════════════════════════════
@mcp.tool
def list_processed() -> dict:
    """
    Lista todos los documentos procesados con sus entregables generados.
    """
    try:
        docs = corpus.list_documents()
        return {
            "status": "ok",
            "total":  len(docs),
            "documents": [
                {
                    "key":          d["key"],
                    "version":      d.get("version", 1),
                    "processed_at": d.get("processed_at", "")[:10],
                    "deliverables": d.get("deliverables", []),
                }
                for d in docs
            ],
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ═══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QA Analyst MCP Server")
    parser.add_argument("--http", action="store_true",
                        help="Ejecutar en modo HTTP (puerto 8000)")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.http:
        print(f"[MCP] Servidor HTTP iniciado en http://localhost:{args.port}")
        mcp.run(transport="streamable-http", host="0.0.0.0", port=args.port)
    else:
        print("[MCP] Servidor stdio iniciado (listo para Aura/Claude)")
        mcp.run(transport="stdio")
