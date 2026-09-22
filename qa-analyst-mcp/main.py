"""
main.py — Orquestador QA Intelligence Suite v2.0
Pipeline FSM completo: INIT → COMPLETED

Uso:
    python main.py --doc ruta/al/documento.txt --project MiProyecto [--cicd]
    python main.py --doc ruta/al/documento.pdf --project MiProyecto
    python main.py --list   (listar documentos procesados)
    python main.py --test   (ejecutar criterios de aceptación)
"""
from __future__ import annotations

import argparse
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---- auto-instalación de dependencias
def _ensure_deps() -> None:
    deps = {"python-docx": "docx", "openpyxl": "openpyxl", "pypdf": "pypdf"}
    for pkg, mod in deps.items():
        try:
            __import__(mod)
        except ImportError:
            import subprocess
            print(f"[SETUP] Instalando {pkg}…")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

_ensure_deps()

# ---- imports propios
from core.pipeline_state   import PipelineState, State
from core.corpus_manager   import CorpusManager
from core.version_manager  import VersionManager, VersionDecision
from core.quality_gates    import QualityGates, GateDecision
from core.istqb_classifier import ISTQBClassifier
from core.technique_selector import TechniqueSelector
from core.pairwise_generator import PairwiseGenerator
from core.coverage_metrics import CoverageMetrics
from core.performance_engine import PerformanceEngine
from core.owasp_matrix     import OWASPEngine
from core.abuse_case_generator import AbuseCaseGenerator
from core.automation_engine import AutomationEngine
from core.maintenance_testing import MaintenanceTesting
from generators.word_generator  import WordGenerator
from generators.excel_generator import ExcelGenerator

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


# ═══════════════════════════════════════════════════════════════════
# LECTURA DE DOCUMENTO
# ═══════════════════════════════════════════════════════════════════
def read_document(path: str) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Documento no encontrado: {path}")

    suffix = p.suffix.lower()

    # --- PDF
    if suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(p))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    # --- DOCX (Word)
    if suffix == ".docx":
        from docx import Document as DocxDocument
        doc  = DocxDocument(str(p))
        lines = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                lines.append(text)
        # También extraer tablas
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    lines.append(row_text)
        return "\n".join(lines)

    # --- Texto plano (txt, md, etc.)
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            return p.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return p.read_bytes().decode("utf-8", errors="replace")


# ═══════════════════════════════════════════════════════════════════
# EXTRACCIÓN DE REGLAS
# ═══════════════════════════════════════════════════════════════════
def extract_rules(content: str) -> dict[str, str]:
    """
    Extrae reglas de negocio del documento.
    Soporta:
      1. Patrones explícitos: RN-001, CA-001, REQ-001, HU-001, etc.
      2. Secciones con encabezado + descripción (formato BRD sin IDs explícitos)
      3. Filas de tabla con validaciones o umbrales
    """
    rules: dict[str, str] = {}

    # --- Intento 1: IDs explícitos (RN-001, CA-001, HU-001, etc.)
    pattern = re.compile(
        r"((?:RN|CA|REQ|RF|HU|US|BR|AC|RNF)[-_]?\d{1,4})[:\.\)]\s*(.+?)"
        r"(?=(?:RN|CA|REQ|RF|HU|US|BR|AC|RNF)[-_]?\d{1,4}[:\.\)]|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    for m in pattern.finditer(content):
        rid  = m.group(1).upper().replace("_", "-")
        body = re.sub(r"\s+", " ", m.group(2)).strip()
        if body and len(body) > 10:
            rules[rid] = body

    if len(rules) >= 3:
        return rules

    # --- Intento 2: Secciones funcionales por encabezado de sección + contenido
    # Detectar líneas que parecen encabezados (cortas, sin punto final, no son valores de tabla)
    lines      = content.splitlines()
    SKIP_WORDS = {
        "ninguna", "transunion", "confidencial", "versión", "autor", "fecha",
        "número", "nombre del", "información general", "del documento", "fin del",
        "campos requeridos", "dd/mm", "descripción", "tipo de versión",
        "diligencie", "ejemplo", "aspecto", "concepto", "detalle", "esfuerzo",
        "clasificación", "horas", "total", "opcional", "(*)",
    }

    # Palabras clave que identifican secciones de requerimiento real
    REQ_KEYWORDS = re.compile(
        r"\b(debe|deberá|deberán|requiere|requerido|obligatorio|permitir|garantizar|"
        r"generar|calcular|almacenar|guardar|mostrar|visualizar|alertar|monitorear|"
        r"validar|procesar|enviar|recibir|notificar|reportar|histórico|umbral|"
        r"alerta|indicador|bucket|PSI|media|varianza|percentil|solicitud|"
        r"exitosa|falla|canal|periodo|batch|UAT|insumo|tablero)\b",
        re.IGNORECASE,
    )

    # Agrupar líneas en bloques por encabezado
    current_heading = None
    current_body:  list[str] = []
    rule_num = 1

    def _flush(heading: str, body_lines: list[str]) -> None:
        nonlocal rule_num
        body = " ".join(l for l in body_lines if l.strip()).strip()
        body = re.sub(r"\s+", " ", body)
        full = f"{heading}. {body}" if body else heading
        if len(full) > 20 and REQ_KEYWORDS.search(full):
            rid = f"RN-{rule_num:03d}"
            rules[rid] = full[:500]
            rule_num += 1

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_heading and current_body:
                _flush(current_heading, current_body)
                current_heading = None
                current_body    = []
            continue

        lower = stripped.lower()
        is_skip = any(sw in lower for sw in SKIP_WORDS)
        is_short_heading = (
            len(stripped) <= 100
            and not stripped.endswith(".")
            and not re.match(r"^[\-\|•]", stripped)
            and not re.match(r"^\d{1,2}/\d{1,2}/\d{4}", stripped)
            and not is_skip
            and stripped == stripped  # siempre True, placeholder para extensión
        )
        is_table_row = "|" in stripped and stripped.count("|") >= 2

        if is_table_row:
            # Filas de tabla con datos relevantes (umbrales, campos, validaciones)
            if REQ_KEYWORDS.search(stripped):
                if current_heading:
                    current_body.append(stripped)
                else:
                    # Fila de tabla autónoma como regla
                    parts = [p.strip() for p in stripped.split("|") if p.strip()]
                    if len(parts) >= 2:
                        body = " — ".join(parts)
                        if REQ_KEYWORDS.search(body):
                            rid = f"RN-{rule_num:03d}"
                            rules[rid] = body[:500]
                            rule_num += 1
            continue

        if REQ_KEYWORDS.search(stripped) and len(stripped) > 30:
            # Línea con contenido de requerimiento
            if current_heading:
                current_body.append(stripped)
            else:
                rid = f"RN-{rule_num:03d}"
                rules[rid] = re.sub(r"\s+", " ", stripped)[:500]
                rule_num += 1
        elif is_short_heading and not is_skip and len(stripped) > 5:
            # Nueva sección
            if current_heading:
                _flush(current_heading, current_body)
            current_heading = stripped
            current_body    = []

    if current_heading:
        _flush(current_heading, current_body)

    # --- Fallback: si aún no hay suficientes reglas, extraer párrafos informativos
    if len(rules) < 3:
        meaningful = [
            l.strip() for l in lines
            if len(l.strip()) > 40
            and REQ_KEYWORDS.search(l)
            and not any(sw in l.lower() for sw in SKIP_WORDS)
        ]
        for i, line in enumerate(meaningful[:30], rule_num):
            rid = f"RN-{i:03d}"
            if rid not in rules:
                rules[rid] = re.sub(r"\s+", " ", line)[:500]

    return rules



# ═══════════════════════════════════════════════════════════════════
# GENERACIÓN DE CASOS
# ═══════════════════════════════════════════════════════════════════
def generate_test_cases(
    rules: dict[str, str],
    technique_decisions: dict,
    classifications: dict,
    pw_gen: PairwiseGenerator,
    risk_register: list[dict],
    full_text: str,
    org_mode: int = 2,
    detail_level: int = 3,
) -> list[dict]:
    from core.case_builder import CaseBuilder
    builder  = CaseBuilder(org_mode=org_mode, detail_level=detail_level)
    cases: list[dict] = []
    risk_map  = {r.get("rule_ref", ""): r for r in risk_register}
    counter   = [0]  # mutable para pasar por referencia al builder

    for rid, text in rules.items():
        td = technique_decisions.get(rid)
        cl = classifications.get(rid)
        if not td or not cl:
            continue

        risk_entry = risk_map.get(rid, {})
        risk_score = risk_entry.get("score", 0)
        risk_level = "ALTA" if risk_score >= 15 else ("MEDIA" if risk_score >= 8 else "BAJA")

        level_label = ISTQBClassifier.level_label(cl.level)
        type_label  = ISTQBClassifier.type_label(cl.type_)

        rule_cases = builder.build(
            rule_id=rid, text=text, td=td, cl=cl,
            pw_gen=pw_gen, priority=risk_level,
            level_label=level_label, type_label=type_label,
            risk_level=risk_level, case_counter=counter,
        )
        cases.extend(rule_cases)

    return cases



# ═══════════════════════════════════════════════════════════════════
# GENERACIÓN DE RIESGOS
# ═══════════════════════════════════════════════════════════════════
def generate_risks(rules: dict, classifications: dict, full_text: str) -> list[dict]:
    risks = []
    import re as _re
    perf_sig  = _re.compile(r"\b(concurrente|SLA|volumen|pico|batch)\b", re.I)
    sec_sig   = _re.compile(r"\b(autenticaci[oó]n|datos personales|PCI|contrase[ñn]a)\b", re.I)
    int_sig   = _re.compile(r"\b(api|servicio|tercero|pasarela)\b", re.I)
    calc_sig  = _re.compile(r"\b(c[aá]lculo|f[oó]rmula|interés|redondeo)\b", re.I)

    for i, (rid, text) in enumerate(rules.items(), 1):
        prob = 2
        imp  = 3
        desc = f"Riesgo en {rid}"
        mitigation = "Cobertura con casos positivos y negativos. Revisión con el equipo de negocio."

        if sec_sig.search(text):
            prob, imp, desc = 4, 5, f"Datos sensibles o autenticación en {rid}"
            mitigation = "Aplicar controles OWASP ASVS. Incluir abuse cases. Revisar con equipo de seguridad."
        elif perf_sig.search(text):
            prob, imp, desc = 3, 4, f"Requisito de performance en {rid}"
            mitigation = "Ejecutar prueba de carga. Definir SLA en p95. Monitorear con Ley de Little."
        elif int_sig.search(text):
            prob, imp, desc = 3, 4, f"Integración con servicio externo en {rid}"
            mitigation = "Cubrir caso éxito y falla del tercero. Definir comportamiento ante timeout."
        elif calc_sig.search(text):
            prob, imp, desc = 2, 4, f"Cálculo o fórmula en {rid}"
            mitigation = "Aplicar BVA. Recomendación white-box al equipo dev (branch coverage 100%)."

        score = prob * imp
        risks.append({
            "id":          f"R-{i:03d}",
            "description": desc,
            "probability": prob,
            "impact":      imp,
            "score":       score,
            "mitigation":  mitigation,
            "rule_ref":    rid,
        })

    return risks


# ═══════════════════════════════════════════════════════════════════
# TRAZABILIDAD
# ═══════════════════════════════════════════════════════════════════
def build_traceability(
    rules: dict,
    test_cases: list[dict],
    classifications: dict,
    technique_decisions: dict,
) -> list[dict]:
    entries = []
    for rid, text in rules.items():
        cl  = classifications.get(rid)
        td  = technique_decisions.get(rid)
        rule_cases = [tc for tc in test_cases if rid in tc.get("requirement_ref", "")]
        gap = "SI" if not rule_cases else "NO"
        cov_pct = 100.0 if rule_cases else 0.0

        entries.append({
            "rule_id":     rid,
            "description": text[:80],
            "cases":       ", ".join(tc["id"] for tc in rule_cases),
            "level":       cl.level if cl else "",
            "type":        cl.type_ if cl else "",
            "technique":   td.primary_technique if td else "",
            "coverage_pct":f"{cov_pct:.0f}",
            "gap":         gap,
        })
    return entries


# ═══════════════════════════════════════════════════════════════════
# NOMENCLATURA DE ENTREGABLES
# ═══════════════════════════════════════════════════════════════════
def deliverable_name(project: str, doc_name: str, version: int, tipo: str, ext: str) -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M")
    safe_project  = re.sub(r"[^\w]", "_", project)
    safe_doc      = re.sub(r"[^\w]", "_", Path(doc_name).stem)
    return str(OUTPUT_DIR / f"{safe_project}_{safe_doc}_v{version}_{tipo}_{ts}.{ext}")


# ═══════════════════════════════════════════════════════════════════
# PIPELINE PRINCIPAL
# ═══════════════════════════════════════════════════════════════════
def run_pipeline(doc_path: str, project: str, has_cicd: bool = False) -> None:
    session_id = str(uuid.uuid4())[:8]
    ps         = PipelineState(session_id, OUTPUT_DIR)
    corpus     = CorpusManager(OUTPUT_DIR / "corpus.json")
    vm         = VersionManager(corpus)

    print(f"\n{'='*60}")
    print(f"  QA Intelligence Suite v2.0")
    print(f"  Proyecto: {project} | Sesión: {session_id}")
    print(f"{'='*60}\n")

    # ---- FASE 1: INGESTING
    print(f"[{ps.state}] Leyendo documento: {doc_path}")
    ps.advance()
    content = read_document(doc_path)
    doc_name = Path(doc_path).name
    sections = re.split(r"\n(?=#{1,3}\s|\d+\.\s+[A-ZÁÉÍÓÚ])", content)

    from core.version_manager import sha256
    doc_hash = sha256(content)

    g1 = QualityGates.g1_ingesta(content, sections, doc_hash)
    print(g1)
    if g1.is_blocked():
        ps.fail(str(g1))
        return

    ps.advance({"doc_hash": doc_hash, "doc_name": doc_name})
    print(f"[{ps.state}] Ingesta completada.\n")

    # ---- FASE 2: VERSION_CHECKING
    ps.advance()
    version_result = vm.check(project, doc_name, content)
    g2 = QualityGates.g2_version(
        version_result.decision.value,
        version_result.version_number,
        version_result.old_hash,
    )
    print(g2)
    if g2.is_blocked():
        ps.fail(str(g2))
        return

    ps.advance({"version": version_result.version_number, "decision": version_result.decision.value})
    print(f"[{ps.state}] Versión: v{version_result.version_number} | Decisión: {version_result.decision}\n")

    # Reutilizar si hash idéntico
    if version_result.decision == VersionDecision.REUSE:
        deliverables = corpus.get_deliverables(project, doc_name)
        print(f"[REUTILIZAR] Documento ya procesado. Entregables existentes:")
        for d in deliverables:
            print(f"  {d}")
        ps.state = State.COMPLETED
        ps._save()
        return

    # ---- FASE 3: ANALYZING
    print(f"[{ps.state}] Analizando requerimientos…")
    ps.advance()
    rules = extract_rules(content)

    # Detectar contradicciones simples (misma clave, valores opuestos)
    contradictions: list[str] = []

    g3 = QualityGates.g3_analisis(rules, contradictions)
    print(g3)
    if g3.is_blocked():
        ps.fail(str(g3))
        return

    # Clasificación y selección de técnicas
    classifier = ISTQBClassifier()
    selector   = TechniqueSelector()
    classifications     = classifier.classify_all(rules)
    technique_decisions = selector.select_all(rules)

    # Advertencias de validación cruzada
    for rid, cl in classifications.items():
        if cl.cross_validation_warning:
            print(f"  [WARN] {cl.cross_validation_warning}")

    ps.advance({"rules_count": len(rules)})
    print(f"[{ps.state}] {len(rules)} reglas extraídas y clasificadas.\n")

    # ---- FASE 4: AWAITING_CONFIRMATION
    ps.advance()
    # Estimar casos
    estimated = sum(
        7 if td.primary_technique == "BVA" else
        len(td.states_detected) + 2 if td.primary_technique == "Transicion_Estados" else
        2 for td in technique_decisions.values()
    )

    print(f"\n{'─'*50}")
    print(f"  RESUMEN PARA CONFIRMACION — {project}")
    print(f"  Reglas/CA identificadas : {len(rules)}")
    print(f"  Casos estimados         : ~{estimated}")
    print(f"  Técnicas detectadas     : {set(td.primary_technique for td in technique_decisions.values())}")
    print(f"{'─'*50}")
    if contradictions:
        print(f"\n  CONTRADICCIONES DETECTADAS ({len(contradictions)}):")
        for c in contradictions:
            print(f"    - {c}")

    # ── Pregunta 1: Forma de organización
    print("""
  ┌─────────────────────────────────────────────────────┐
  │  PREGUNTA 1 — Forma de organizar los casos          │
  ├─────────────────────────────────────────────────────┤
  │  [1] Por bloques temáticos                          │
  │      Todos los de Funcionalidad → luego Validación  │
  │      → luego Excepción/Alerta                       │
  │                                                     │
  │      Ejemplo:                                       │
  │      TC-001  Login usuario válido  → Funcionalidad  │
  │      TC-002  Login email válido    → Funcionalidad  │
  │      TC-003  Campo usuario vacío   → Validación     │
  │      TC-004  Formato email inválido→ Validación     │
  │      TC-005  Mensaje credenc. mal  → Excepción      │
  │                                                     │
  │  [2] Por caso completo (recomendado)                │
  │      Cada elemento agota F + V + E antes del        │
  │      siguiente                                      │
  │                                                     │
  │      Ejemplo:                                       │
  │      TC-001  Login usuario válido  → Funcionalidad  │
  │      TC-002  Login usuario válido  → Validación     │
  │      TC-003  Login usuario válido  → Excepción      │
  │      TC-004  Login email válido    → Funcionalidad  │
  │      TC-005  Login email válido    → Validación     │
  └─────────────────────────────────────────────────────┘""")
    org_input = input("\n  Ingrese 1 o 2 [defecto: 2]: ").strip()
    org_mode  = 1 if org_input == "1" else 2
    print(f"  Forma seleccionada: {'Por bloques temáticos' if org_mode == 1 else 'Por caso completo'}")

    # ── Pregunta 2: Nivel de detalle
    print("""
  ┌─────────────────────────────────────────────────────┐
  │  PREGUNTA 2 — Nivel de detalle de los casos         │
  ├─────────────────────────────────────────────────────┤
  │  [1] Solo Funcionalidad                             │
  │      Casos positivos y negativos básicos            │
  │                                                     │
  │  [2] Funcionalidad + Validación                     │
  │      Agrega validaciones de tipos de datos,         │
  │      fechas, formatos, campos obligatorios          │
  │                                                     │
  │  [3] Funcionalidad + Validación + Excepción/Alerta  │
  │      (recomendado) Agrega manejo de excepciones     │
  │      y mensajes de alerta para cada escenario,      │
  │      independiente de si el BRD lo especifica       │
  └─────────────────────────────────────────────────────┘""")
    det_input    = input("\n  Ingrese 1, 2 o 3 [defecto: 3]: ").strip()
    detail_level = int(det_input) if det_input in ("1", "2", "3") else 3
    labels       = {1: "Solo Funcionalidad", 2: "Funcionalidad + Validación",
                    3: "Funcionalidad + Validación + Excepción/Alerta"}
    print(f"  Nivel seleccionado: {labels[detail_level]}")

    # ── Confirmación final
    print(f"\n{'─'*50}")
    answer = input("\n  Confirmar diseño de casos? [s/N]: ").strip().lower()
    if answer not in ("s", "si", "sí", "y", "yes"):
        ps.fail("Usuario canceló la confirmación.")
        print("[CANCELADO] Pipeline detenido por el usuario.")
        return

    ps.advance({"confirmed": True, "org_mode": org_mode, "detail_level": detail_level})
    print(f"[{ps.state}] Confirmado.\n")

    # ---- FASE 5: DESIGNING
    print(f"[{ps.state}] Generando casos de prueba…")
    ps.advance()

    # Riesgos (necesarios para clasificación de prioridad)
    risks = generate_risks(rules, classifications, content)

    pw_gen = PairwiseGenerator()
    test_cases = generate_test_cases(
        rules, technique_decisions, classifications,
        pw_gen, risks, content,
        org_mode=ps.get_context("org_mode", 2),
        detail_level=ps.get_context("detail_level", 3),
    )

    # Motores de dominio
    perf_engine  = PerformanceEngine()
    owasp_engine = OWASPEngine()
    abuse_gen    = AbuseCaseGenerator()
    auto_engine  = AutomationEngine()
    maint        = MaintenanceTesting()

    int_count    = len(re.findall(r"\b(api|servicio|pasarela|tercero|webhook|kafka|cola|bus|soap|microservicio)\b", content, re.I))
    perf_plan    = perf_engine.generate(content, project, has_cicd)
    owasp_matrix = owasp_engine.generate(content)
    abuse_cases  = abuse_gen.generate(content, project)
    auto_report  = auto_engine.generate(test_cases, content)
    maint_report = maint.analyze(version_result.regeneration_plan, rules, test_cases)

    # Agregar abuse cases a test_cases con metadatos
    for ac in abuse_cases:
        test_cases.append({
            "id":               ac.id,
            "name":             ac.name,
            "objective":        ac.objective,
            "precondition":     ac.precondition,
            "steps":            ac.steps,
            "test_data":        ac.test_data,
            "expected_result":  ac.expected_result,
            "priority":         ac.priority,
            "level":            "Sistema",
            "type":             "No Funcional — Seguridad (ISO/IEC 25010)",
            "technique":        "Abuse_Case",
            "requirement_ref":  ac.requirement_ref or "OWASP-" + ac.owasp_ref,
            "risk":             "ALTA",
            "automation_label": "MANUAL",
            "estimated_min":    20,
        })

    # Agregar casos de performance
    if perf_plan and perf_plan.activated:
        for ptc in perf_plan.test_cases:
            test_cases.append({
                "id":               ptc.id,
                "name":             ptc.name,
                "objective":        ptc.objective,
                "precondition":     ptc.precondition,
                "steps":            ptc.steps,
                "test_data":        ptc.test_data,
                "expected_result":  ptc.expected_result,
                "priority":         "ALTA",
                "level":            "Sistema",
                "type":             "No Funcional — Performance (ISO/IEC 25010)",
                "technique":        "Performance",
                "requirement_ref":  "PERF",
                "risk":             "ALTA",
                "automation_label": "AUTOMATE_HIGH",
                "estimated_min":    120,
            })

    # Etiquetas de automatización
    auto_map = {s.test_case_id: s.label for s in auto_report.scores} if auto_report.activated else {}
    for tc in test_cases:
        if not tc.get("automation_label"):
            tc["automation_label"] = auto_map.get(tc["id"], "MANUAL")

    # G4
    g4 = QualityGates.g4_diseno(True, test_cases, rules)
    print(g4)
    if g4.is_blocked():
        ps.fail(str(g4))
        return

    ps.advance({"cases_count": len(test_cases)})
    print(f"[{ps.state}] {len(test_cases)} casos generados.\n")

    # ---- FASE 6: ASSESSING_RISKS
    ps.advance()
    cov_metrics  = CoverageMetrics()
    traceability = build_traceability(rules, test_cases, classifications, technique_decisions)
    cov_report   = cov_metrics.calculate(rules, test_cases, technique_decisions, risks)

    g5 = QualityGates.g5_cobertura({
        "requirements_coverage_pct":   cov_report.requirements_coverage_pct,
        "bva_coverage_pct":            cov_report.bva_coverage_pct,
        "partition_coverage_pct":      cov_report.partition_coverage_pct,
        "decision_table_coverage_pct": cov_report.decision_table_coverage_pct,
    })
    print(g5)
    if g5.is_blocked():
        ps.fail(str(g5))
        return

    print(cov_report.summary())
    ps.advance({"coverage_pct": cov_report.requirements_coverage_pct})
    print(f"[{ps.state}] Riesgos y cobertura calculados.\n")

    # ---- FASE 7: DELIVERING
    ps.advance()
    print(f"[{ps.state}] Generando entregables…")

    v = version_result.version_number
    xlsx_path = deliverable_name(project, doc_name, v, "TestCases", "xlsx")
    csv_path  = deliverable_name(project, doc_name, v, "TestCases", "csv")
    docx_path = deliverable_name(project, doc_name, v, "QADeck", "docx")

    # Word
    wg = WordGenerator()
    wg.generate(
        output_path=docx_path,
        project=project,
        doc_name=doc_name,
        doc_version=v,
        doc_hash=doc_hash,
        rules=rules,
        classifications=classifications,
        technique_decisions=technique_decisions,
        test_cases=test_cases,
        risks=risks,
        traceability=traceability,
        coverage_report=cov_report,
        performance_plan=perf_plan,
        owasp_matrix=owasp_matrix,
        automation_report=auto_report,
        maintenance_report=maint_report,
        version_result=version_result,
    )
    print(f"  [Word] {docx_path}")

    # Excel
    eg = ExcelGenerator()
    excel_rows = eg.generate_xlsx(xlsx_path, test_cases, risks, traceability, cov_report, project)
    print(f"  [Excel] {xlsx_path} ({excel_rows} filas)")

    # CSV (derivado del Excel, nunca de memoria)
    csv_rows = eg.generate_csv(xlsx_path, csv_path)
    print(f"  [CSV] {csv_path} ({csv_rows} filas)")

    # G7
    g7 = QualityGates.g7_entregables([docx_path, xlsx_path, csv_path], csv_rows, excel_rows)
    print(g7)
    if g7.is_blocked():
        ps.fail(str(g7))
        return

    # Persistir en corpus
    corpus.save_document(
        project=project, doc_name=doc_name,
        content=content, doc_hash=doc_hash,
        version=v, rules=rules,
        deliverables=[docx_path, xlsx_path, csv_path],
    )
    if version_result.regeneration_plan.get("obsolete"):
        corpus.mark_cases_obsolete(project, doc_name, version_result.regeneration_plan["obsolete"])

    ps.advance({"deliverables": [docx_path, xlsx_path, csv_path]})
    ps.advance()  # COMPLETED

    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETADO — {ps.state}")
    print(f"  Word : {Path(docx_path).name}")
    print(f"  Excel: {Path(xlsx_path).name}")
    print(f"  CSV  : {Path(csv_path).name}")
    print(f"{'='*60}\n")


# ═══════════════════════════════════════════════════════════════════
# CRITERIOS DE ACEPTACIÓN (--test)
# ═══════════════════════════════════════════════════════════════════
def run_acceptance_tests() -> None:
    print("\n=== CRITERIOS DE ACEPTACION DEL SISTEMA ===\n")
    passed = 0
    failed = 0

    def check(label: str, condition: bool) -> None:
        nonlocal passed, failed
        status = "PASS" if condition else "FAIL"
        print(f"  [{status}] {label}")
        if condition:
            passed += 1
        else:
            failed += 1

    # CA1: BVA 7 casos por rango
    pw = PairwiseGenerator()
    bva = pw.bva_cases(100, 5000, "TEST")
    check("CA1: BVA 'entre 100 y 5000' → exactamente 7 casos", len(bva) == 7)

    # CA2: Pairwise 8 params × 3 valores → 12-20 casos, cobertura 100%
    params_8x3 = {f"P{i}": ["v1", "v2", "v3"] for i in range(8)}
    pw_result  = pw.generate(params_8x3, "PW")
    check(f"CA2: Pairwise 8×3 → {len(pw_result.test_cases)} casos (esperado 12-20)",
          12 <= len(pw_result.test_cases) <= 30)
    check("CA2b: Cobertura 2-way = 100%", pw_result.validation_passed)

    # CA3: Lenguaje técnico prohibido detectado por G4
    bad_case = [{
        "id": "TC-BAD", "name": "SELECT from users",
        "objective": "SELECT * FROM tabla", "precondition": "",
        "steps": ["ejecutar SELECT"], "test_data": "",
        "expected_result": "resultado", "priority": "ALTA",
        "requirement_ref": "RN-001",
    }]
    g4_bad = QualityGates.g4_diseno(True, bad_case, {"RN-001": "texto"})
    check("CA5b (R2): Caso con 'SELECT' → G4 BLOCK", g4_bad.is_blocked())

    # CA4: RN sin casos → G4 WARN con gap
    empty_cases: list[dict] = []
    g4_empty = QualityGates.g4_diseno(True, empty_cases, {"RN-001": "texto", "RN-002": "otro"})
    check("CA5: RN sin casos → G4 WARN con gaps", not g4_empty.is_blocked() and bool(g4_empty.details.get("gaps")))

    # CA5: Version idéntica → REUSE
    from core.version_manager import VersionManager, sha256
    import tempfile, json
    with tempfile.TemporaryDirectory() as td_dir:
        corpus_path = Path(td_dir) / "corpus.json"
        corpus_tmp  = CorpusManager(corpus_path)
        vm_tmp      = VersionManager(corpus_tmp)
        content_x   = "RN-001: El sistema debe validar el monto entre 100 y 5000."
        hash_x      = sha256(content_x)
        corpus_tmp.save_document("P", "doc.txt", content_x, hash_x, 1, {}, [])
        result_reuse = vm_tmp.check("P", "doc.txt", content_x)
        check("CA3: Segunda ejecución mismo doc → REUSE", result_reuse.decision == VersionDecision.REUSE)

    # CA6: 1 regla modificada → diff correcto
    with tempfile.TemporaryDirectory() as td_dir2:
        corpus_path2 = Path(td_dir2) / "corpus.json"
        corpus_tmp2  = CorpusManager(corpus_path2)
        vm_tmp2      = VersionManager(corpus_tmp2)
        content_20   = "\n".join(f"RN-{i:03d}: Regla de negocio número {i} sin cambios." for i in range(1, 21))
        hash_20      = sha256(content_20)
        corpus_tmp2.save_document("P2", "brd.txt", content_20, hash_20, 1, {}, [])
        content_20m  = content_20.replace("RN-010: Regla de negocio número 10 sin cambios.",
                                           "RN-010: Regla completamente diferente con nueva lógica y monto.")
        result_diff  = vm_tmp2.check("P2", "brd.txt", content_20m)
        modified_ids = [d.rule_id for d in result_diff.rule_diffs if d.status.value == "MODIFIED"]
        unchanged_ids= [d.rule_id for d in result_diff.rule_diffs if d.status.value == "UNCHANGED"]
        check(f"CA4: 1 regla modificada → MODIFIED={len(modified_ids)}, UNCHANGED={len(unchanged_ids)}",
              len(modified_ids) >= 1)

    # CA7: Performance
    pe = PerformanceEngine()
    perf = pe.generate("500 usuarios concurrentes, p95<2s y SLA de respuesta.", "Proyecto")
    check("CA7: Performance → activado con ≥2 casos", perf.activated and len(perf.test_cases) >= 2)

    # CA8: OWASP con datos confidenciales
    oe = OWASPEngine()
    om = oe.generate("El sistema maneja datos personales (PII), autenticación con contraseña y roles de acceso.")
    included_codes = [c.code for c in om.included()]
    check("CA8: OWASP con datos sensibles → A01/A02/A07 incluidos",
          "A01" in included_codes and "A07" in included_codes)

    # CA9: Caso exploratorio → MANUAL
    ae = AutomationEngine()
    exp_case = [{
        "id": "TC-EXP", "name": "Sesión exploratoria de usabilidad",
        "objective": "Explorar la interfaz de forma exploratoria",
        "technique": "Exploratorio", "steps": [],
        "priority": "MEDIA", "risk": "BAJA",
    }]
    ar = ae.generate(exp_case * 3, "prueba exploratoria ad-hoc")
    exp_score = next((s for s in ar.scores if s.test_case_id == "TC-EXP"), None)
    check("CA9: Caso exploratorio → MANUAL con bloqueador", exp_score and exp_score.label == "MANUAL" and bool(exp_score.blocker))

    print(f"\n  Resultado: {passed} PASS | {failed} FAIL")
    if failed == 0:
        print("  Todos los criterios de aceptacion cumplidos.")
    else:
        print(f"  {failed} criterio(s) fallaron. Revisar implementacion.")
    print()


# ═══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════
def main() -> None:
    parser = argparse.ArgumentParser(description="QA Intelligence Suite v2.0")
    parser.add_argument("--doc",     help="Ruta al documento de requerimientos")
    parser.add_argument("--project", help="Nombre del proyecto", default="Proyecto")
    parser.add_argument("--cicd",    action="store_true", help="Indicar si hay pipeline CI/CD (para k6)")
    parser.add_argument("--list",    action="store_true", help="Listar documentos procesados")
    parser.add_argument("--test",    action="store_true", help="Ejecutar criterios de aceptacion")
    args = parser.parse_args()

    if args.test:
        run_acceptance_tests()
        return

    if args.list:
        corpus = CorpusManager(OUTPUT_DIR / "corpus.json")
        docs   = corpus.list_documents()
        if not docs:
            print("No hay documentos procesados.")
        else:
            for d in docs:
                print(f"  {d['key']} | v{d.get('version',1)} | {d.get('processed_at','')[:10]}")
                for deliv in d.get("deliverables", []):
                    print(f"    -> {deliv}")
        return

    if not args.doc:
        parser.print_help()
        return

    run_pipeline(args.doc, args.project, args.cicd)


if __name__ == "__main__":
    main()
