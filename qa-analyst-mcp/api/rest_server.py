"""
rest_server.py — API REST del QA Intelligence Suite v2.0

Endpoints:
  POST /api/analyze          → analizar documento
  POST /api/generate         → generar casos de prueba
  POST /api/deliverables     → pipeline completo (Word+Excel+CSV)
  GET  /api/documents        → listar documentos procesados
  GET  /api/documents/<hash> → detalle de un documento
  GET  /api/cases/<project>  → casos de prueba de un proyecto
  GET  /api/stats/<project>  → estadisticas del proyecto
  GET  /api/tokens           → estado del monitor de tokens
  GET  /api/health           → estado del sistema
  GET  /api/sessions         → sesiones de trabajo

Uso:
  env\Scripts\python api/rest_server.py
  env\Scripts\python api/rest_server.py --port 8080
"""
from __future__ import annotations

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

from main import (
    read_document, extract_rules, generate_risks,
    generate_test_cases, build_traceability,
    deliverable_name, OUTPUT_DIR,
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
from core.database           import (
    Logger, SessionManager, DocumentRepository,
    TestCaseRepository, TokenRepository, AuditTrail
)
from generators.word_generator  import WordGenerator
from generators.excel_generator import ExcelGenerator

app   = Flask(__name__)
CORS(app)  # Permitir peticiones desde cualquier origen

corpus = CorpusManager(OUTPUT_DIR / "corpus.json")
vm     = VersionManager(corpus)
log    = Logger("REST_API")


# ─────────────────────────────────────── helpers
def _error(msg: str, code: int = 400) -> tuple:
    return jsonify({"status": "error", "message": msg}), code


def _ok(data: dict) -> tuple:
    data["status"] = "ok"
    data["timestamp"] = datetime.utcnow().isoformat()
    return jsonify(data), 200


def _run_pipeline(
    doc_path: str,
    project: str,
    org_mode: int = 2,
    detail_level: int = 3,
    has_cicd: bool = False,
) -> dict:
    """Ejecuta el pipeline completo y retorna el resultado."""
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

    vr = vm.check(project, doc_name, content)

    if vr.decision == VersionDecision.REUSE:
        deliverables = corpus.get_deliverables(project, doc_name)
        return {
            "decision":     "REUSE",
            "message":      "Documento ya procesado. Entregables reutilizados.",
            "deliverables": deliverables,
            "version":      vr.version_number,
        }

    cases = generate_test_cases(
        rules, tds, clss, pw, risks, content,
        org_mode=org_mode, detail_level=detail_level,
    )

    perf  = PerformanceEngine().generate(content, project, has_cicd)
    owasp = OWASPEngine().generate(content)
    abuse = AbuseCaseGenerator().generate(content, project)
    auto  = AutomationEngine().generate(cases, content)
    maint = MaintenanceTesting().analyze(vr.regeneration_plan, rules, cases)

    for ac in abuse:
        cases.append({
            "id": ac.id, "name": ac.name, "objective": ac.objective,
            "precondition": ac.precondition, "steps": ac.steps,
            "test_data": ac.test_data, "expected_result": ac.expected_result,
            "priority": ac.priority, "level": "Sistema", "type": "seguridad",
            "technique": "Abuse_Case", "requirement_ref": "OWASP-" + ac.owasp_ref,
            "risk": "ALTA", "automation_label": "MANUAL",
            "estimated_min": 20, "dimension": "Excepcion",
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

    traz = build_traceability(rules, cases, clss, tds)
    cov  = CoverageMetrics().calculate(rules, cases, tds, risks)
    v    = vr.version_number

    xlsx_path = deliverable_name(project, doc_name, v, "TestCases", "xlsx")
    csv_path  = deliverable_name(project, doc_name, v, "TestCases", "csv")
    docx_path = deliverable_name(project, doc_name, v, "QADeck",    "docx")

    from core.version_manager import VersionResult
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

    corpus.save_document(project, doc_name, content, doc_hash, v, rules,
                         [docx_path, xlsx_path, csv_path])

    # Guardar en SQLite
    doc_id = DocumentRepository.save(
        project, doc_name, doc_hash, v,
        len(rules), len(cases),
        [docx_path, xlsx_path, csv_path],
    )
    TestCaseRepository.save_batch(cases, project, doc_id)

    return {
        "decision":      vr.decision.value,
        "version":       v,
        "rules_count":   len(rules),
        "cases_count":   len(cases),
        "coverage_pct":  cov.requirements_coverage_pct,
        "performance":   perf.activated,
        "security":      owasp.activated,
        "excel_rows":    excel_rows,
        "csv_rows":      csv_rows,
        "deliverables": {
            "word":  str(Path(docx_path).name),
            "excel": str(Path(xlsx_path).name),
            "csv":   str(Path(csv_path).name),
        },
        "paths": {
            "word":  docx_path,
            "excel": xlsx_path,
            "csv":   csv_path,
        },
    }


# ═══════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@app.route("/api/health", methods=["GET"])
def health():
    """Estado del sistema."""
    return _ok({
        "system":  "QA Intelligence Suite v2.0",
        "version": "2.0.0",
        "uptime":  "ok",
        "db":      "ok",
    })


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """
    Analiza un documento y retorna reglas extraidas.
    Body: { "doc_path": "ruta", "project": "nombre" }
    """
    data     = request.get_json() or {}
    doc_path = data.get("doc_path", "")
    project  = data.get("project", "Proyecto")

    if not doc_path or not Path(doc_path).exists():
        return _error(f"Documento no encontrado: {doc_path}")

    try:
        log.info("analyze", f"Analizando: {doc_path}")
        content = read_document(doc_path)
        rules   = extract_rules(content)
        clf     = ISTQBClassifier()
        sel     = TechniqueSelector()
        clss    = clf.classify_all(rules)
        tds     = sel.select_all(rules)
        doc_hash = sha256(content)
        vr       = vm.check(project, Path(doc_path).name, content)

        from collections import Counter
        tecnicas = Counter(td.primary_technique for td in tds.values())

        return _ok({
            "project":    project,
            "doc_name":   Path(doc_path).name,
            "doc_hash":   doc_hash[:16] + "...",
            "version":    vr.version_number,
            "decision":   vr.decision.value,
            "rules_count":len(rules),
            "techniques": dict(tecnicas),
            "rules": {
                rid: {
                    "text":      text[:100],
                    "level":     clss[rid].level if rid in clss else "",
                    "type":      clss[rid].type_ if rid in clss else "",
                    "technique": tds[rid].primary_technique if rid in tds else "",
                }
                for rid, text in list(rules.items())[:10]
            },
        })
    except Exception as e:
        log.error("analyze", str(e))
        return _error(str(e), 500)


@app.route("/api/generate", methods=["POST"])
def generate():
    """
    Genera casos de prueba.
    Body: { "doc_path": "ruta", "project": "nombre",
            "org_mode": 2, "detail_level": 3 }
    """
    data         = request.get_json() or {}
    doc_path     = data.get("doc_path", "")
    project      = data.get("project", "Proyecto")
    org_mode     = int(data.get("org_mode", 2))
    detail_level = int(data.get("detail_level", 3))

    if not doc_path or not Path(doc_path).exists():
        return _error(f"Documento no encontrado: {doc_path}")

    try:
        log.info("generate", f"Generando casos: {doc_path}")
        content = read_document(doc_path)
        rules   = extract_rules(content)
        clf     = ISTQBClassifier()
        sel     = TechniqueSelector()
        clss    = clf.classify_all(rules)
        tds     = sel.select_all(rules)
        risks   = generate_risks(rules, clss, content)
        pw      = PairwiseGenerator()
        cases   = generate_test_cases(
            rules, tds, clss, pw, risks, content,
            org_mode=org_mode, detail_level=detail_level,
        )

        from collections import Counter
        dims = Counter(tc.get("dimension", "?") for tc in cases)

        return _ok({
            "total_cases":  len(cases),
            "org_mode":     org_mode,
            "detail_level": detail_level,
            "by_dimension": dict(dims),
            "by_technique": dict(Counter(tc.get("technique","?") for tc in cases)),
            "sample": [
                {
                    "id":        tc["id"],
                    "dimension": tc.get("dimension", ""),
                    "name":      tc["name"][:80],
                    "technique": tc.get("technique", ""),
                }
                for tc in cases[:5]
            ],
        })
    except Exception as e:
        log.error("generate", str(e))
        return _error(str(e), 500)


@app.route("/api/deliverables", methods=["POST"])
def deliverables():
    """
    Pipeline completo: Word + Excel + CSV.
    Body: { "doc_path": "ruta", "project": "nombre",
            "org_mode": 2, "detail_level": 3, "has_cicd": false }
    """
    data         = request.get_json() or {}
    doc_path     = data.get("doc_path", "")
    project      = data.get("project", "Proyecto")
    org_mode     = int(data.get("org_mode", 2))
    detail_level = int(data.get("detail_level", 3))
    has_cicd     = bool(data.get("has_cicd", False))

    if not doc_path or not Path(doc_path).exists():
        return _error(f"Documento no encontrado: {doc_path}")

    try:
        sid = SessionManager.create(project, Path(doc_path).name,
                                    org_mode, detail_level)
        log.info("pipeline", f"Iniciando pipeline: {doc_path}", {"session": sid})
        AuditTrail.log(sid, "pipeline_start", "document", doc_path)

        result = _run_pipeline(doc_path, project, org_mode, detail_level, has_cicd)

        SessionManager.close(sid, "completed")
        AuditTrail.log(sid, "pipeline_complete", "document", doc_path,
                       new_value=json.dumps(result.get("deliverables", {})))

        result["session_id"] = sid
        return _ok(result)
    except Exception as e:
        log.error("pipeline", str(e))
        return _error(str(e), 500)


@app.route("/api/documents", methods=["GET"])
def list_documents():
    """Lista todos los documentos procesados."""
    project = request.args.get("project")
    try:
        docs = DocumentRepository.list_documents(project)
        return _ok({"total": len(docs), "documents": docs})
    except Exception as e:
        return _error(str(e), 500)


@app.route("/api/cases/<project>", methods=["GET"])
def get_cases(project: str):
    """Casos de prueba de un proyecto."""
    try:
        cases = TestCaseRepository.get_by_project(project)
        stats = TestCaseRepository.stats(project)
        return _ok({
            "project": project,
            "stats":   stats,
            "cases":   cases[:100],  # max 100 en la respuesta
        })
    except Exception as e:
        return _error(str(e), 500)


@app.route("/api/stats/<project>", methods=["GET"])
def get_stats(project: str):
    """Estadisticas del proyecto."""
    try:
        cases  = TestCaseRepository.stats(project)
        docs   = DocumentRepository.list_documents(project)
        tokens = TokenRepository.summary(project)
        return _ok({
            "project":   project,
            "documents": len(docs),
            "cases":     cases,
            "tokens":    tokens,
        })
    except Exception as e:
        return _error(str(e), 500)


@app.route("/api/tokens", methods=["GET"])
def token_status():
    """Estado del monitor de tokens."""
    try:
        summary = TokenRepository.summary()
        return _ok({"tokens": summary})
    except Exception as e:
        return _error(str(e), 500)


@app.route("/api/sessions", methods=["GET"])
def list_sessions():
    """Lista sesiones de trabajo."""
    project = request.args.get("project")
    try:
        sessions = SessionManager.list_sessions(project)
        return _ok({"total": len(sessions), "sessions": sessions})
    except Exception as e:
        return _error(str(e), 500)


@app.route("/api/download/<filename>", methods=["GET"])
def download_file(filename: str):
    """Descarga un entregable generado."""
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        return _error(f"Archivo no encontrado: {filename}", 404)
    return send_file(str(file_path), as_attachment=True)


@app.route("/api/audit", methods=["GET"])
def audit():
    """Historial de auditoria."""
    session_id = request.args.get("session_id")
    try:
        history = AuditTrail.get_history(session_id)
        return _ok({"total": len(history), "history": history})
    except Exception as e:
        return _error(str(e), 500)


# ─────────────────────────── entry point
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QA Suite REST API")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    print(f"\n{'='*50}")
    print(f"  QA Intelligence Suite v2.0 — API REST")
    print(f"  http://localhost:{args.port}/api/health")
    print(f"{'='*50}\n")

    app.run(host=args.host, port=args.port, debug=args.debug)
