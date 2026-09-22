"""
word_generator.py — Genera el Deck de Pruebas Word (.docx).

Formato calibrado desde: Deck_Pruebas_BRD_Reconstruccion_Base_Endeudamiento_V4.1.docx

Secciones:
  Portada
  1. Analisis del Documento  (1.1 Contexto, 1.2 Campos clave, 1.3 Reglas)
  2. Estrategia de Pruebas ISTQB  (niveles, tipos, criterios entrada/salida, suspension, ambientes)
  3. Registro de Riesgos  (por RN + transversales)
  4. Deck de Pruebas  (tabla 11 cols: ID | Nombre | RN | Prioridad | Objetivo |
                        Precondicion | Tiempo | Pasos | Datos | Resultado | Comentario)
  5. Matriz de Trazabilidad  (RN | Casos | Tipo ISTQB | Riesgo)
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

try:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml     import OxmlElement
    from docx.oxml.ns  import qn
    from docx.shared   import Cm, Pt, RGBColor
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-docx"],
                          stdout=subprocess.DEVNULL)
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml     import OxmlElement
    from docx.oxml.ns  import qn
    from docx.shared   import Cm, Pt, RGBColor


# ─────────────────────────────────────── colores
C_DARK_BLUE = "1F4E79"
C_MED_BLUE  = "2E75B6"
C_LIGHT_BLU = "D6E4F0"
C_RED       = "FF4444"
C_ORANGE    = "FFAA00"
C_GREEN     = "44BB44"
C_WHITE     = "FFFFFF"
C_GRAY_HDR  = "F2F2F2"

# Mapa de prioridad → color de celda
PRIORITY_COLOR = {
    "Alta":  C_RED,
    "ALTA":  C_RED,
    "Media": C_ORANGE,
    "MEDIA": C_ORANGE,
    "Baja":  C_GREEN,
    "BAJA":  C_GREEN,
}
PRIORITY_FONT_COLOR = {
    "Alta":  C_WHITE, "ALTA":  C_WHITE,
    "Media": "000000", "MEDIA": "000000",
    "Baja":  C_WHITE, "BAJA":  C_WHITE,
}
RISK_COLOR = {
    "Alta":  C_RED,    "ALTA":  C_RED,
    "Media": C_ORANGE, "MEDIA": C_ORANGE,
    "Baja":  C_GREEN,  "BAJA":  C_GREEN,
}


# ─────────────────────────────────────── helpers XML
def _set_cell_bg(cell, hex_color: str) -> None:
    tc   = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd  = OxmlElement("w:shd")
    shd.set(qn("w:val"),   "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"),  hex_color)
    tcPr.append(shd)


def _set_cell_valign(cell, align: str = "top") -> None:
    tc   = cell._tc
    tcPr = tc.get_or_add_tcPr()
    vAlign = OxmlElement("w:vAlign")
    vAlign.set(qn("w:val"), align)
    tcPr.append(vAlign)


def _cell_text(cell, text: str, bold: bool = False,
               font_size: int = 9, color: str = "000000",
               wrap: bool = True) -> None:
    cell.text = ""
    para = cell.paragraphs[0]
    para.paragraph_format.space_after  = Pt(0)
    para.paragraph_format.space_before = Pt(0)
    run = para.add_run(str(text) if text else "")
    run.bold           = bold
    run.font.size      = Pt(font_size)
    run.font.color.rgb = RGBColor.from_string(color)
    _set_cell_valign(cell, "top")


def _header_row(table, headers: list[str],
                bg: str = C_DARK_BLUE, fg: str = C_WHITE,
                font_size: int = 9) -> None:
    row = table.rows[0]
    for i, h in enumerate(headers):
        cell = row.cells[i]
        _cell_text(cell, h, bold=True, font_size=font_size, color=fg)
        _set_cell_bg(cell, bg)
        _set_cell_valign(cell, "center")


def _add_row(table, values: list[str], font_size: int = 9) -> Any:
    row = table.add_row()
    for i, v in enumerate(values):
        if i < len(row.cells):
            _cell_text(row.cells[i], str(v) if v is not None else "",
                       font_size=font_size)
    return row


# ─────────────────────────────────────── utilidades de estilo
def _heading(doc, text: str, level: int) -> None:
    doc.add_heading(text, level=level)


def _para(doc, text: str, bold: bool = False,
          size: int = 10, indent: bool = False) -> None:
    p = doc.add_paragraph()
    if indent:
        p.paragraph_format.left_indent = Cm(0.5)
    run = p.add_run(str(text))
    run.bold      = bold
    run.font.size = Pt(size)


def _bullet(doc, text: str, size: int = 9) -> None:
    p = doc.add_paragraph(style="List Bullet")
    run = p.add_run(str(text))
    run.font.size = Pt(size)


def _number(doc, text: str, size: int = 9) -> None:
    p = doc.add_paragraph(style="List Number")
    run = p.add_run(str(text))
    run.font.size = Pt(size)


def _set_margins(doc) -> None:
    for s in doc.sections:
        s.top_margin    = Cm(2.0)
        s.bottom_margin = Cm(2.0)
        s.left_margin   = Cm(2.5)
        s.right_margin  = Cm(2.0)


def _col_widths(table, widths_cm: list[float]) -> None:
    for row in table.rows:
        for i, w in enumerate(widths_cm):
            if i < len(row.cells):
                row.cells[i].width = Cm(w)


# ═══════════════════════════════════════════════════════════════════
class WordGenerator:

    def generate(
        self,
        output_path:      str,
        project:          str,
        doc_name:         str,
        doc_version:      int,
        doc_hash:         str,
        rules:            dict[str, str],
        classifications:  dict,
        technique_decisions: dict,
        test_cases:       list[dict],
        risks:            list[dict],
        traceability:     list[dict],
        coverage_report,
        performance_plan,
        owasp_matrix,
        automation_report,
        maintenance_report,
        version_result,
        standards: str = "ISTQB CTFL v4.0 | CTAL-TTA | OWASP ASVS 4.0",
    ) -> None:

        doc = Document()
        _set_margins(doc)

        self._portada(doc, project, doc_name, doc_version, doc_hash)
        self._seccion1_analisis(doc, doc_name, doc_hash, doc_version,
                                rules, classifications, technique_decisions,
                                version_result)
        self._seccion2_estrategia(doc, rules, classifications,
                                  technique_decisions, coverage_report)
        self._seccion3_riesgos(doc, risks)
        self._seccion4_deck(doc, test_cases, project)
        self._seccion5_trazabilidad(doc, traceability, rules, classifications)

        # Secciones condicionales al final
        if performance_plan and performance_plan.activated:
            self._seccion_performance(doc, performance_plan)
        if owasp_matrix and owasp_matrix.activated:
            self._seccion_seguridad(doc, owasp_matrix)
        if automation_report and automation_report.activated:
            self._seccion_automatizacion(doc, automation_report)
        if maintenance_report and maintenance_report.triggered:
            self._seccion_mantenimiento(doc, maintenance_report)

        doc.save(output_path)

    # ─────────────────────────────────────── PORTADA
    def _portada(self, doc, project, doc_name, version, doc_hash) -> None:
        doc.add_paragraph()
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(f"Deck de Pruebas — {project}")
        run.bold      = True
        run.font.size = Pt(18)
        run.font.color.rgb = RGBColor.from_string(C_DARK_BLUE)

        doc.add_paragraph()
        meta = [
            ("Fuente:", doc_name),
            ("Fecha:", datetime.now().strftime("%Y-%m-%d")),
            ("Version:", f"V{version}.0"),
            ("Hash SHA-256:", doc_hash[:32] + "…"),
            ("Estandares:", "ISTQB CTFL v4.0 | CTAL-TTA | OWASP ASVS 4.0"),
        ]
        for label, value in meta:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r1 = p.add_run(f"{label} ")
            r1.bold = True
            r1.font.size = Pt(11)
            r2 = p.add_run(value)
            r2.font.size = Pt(11)

        doc.add_page_break()

    # ─────────────────────────────────────── SECCION 1 — ANALISIS
    def _seccion1_analisis(self, doc, doc_name, doc_hash, version,
                           rules, classifications, technique_decisions,
                           version_result) -> None:
        _heading(doc, "1. Analisis del Documento", 1)

        # 1.1 Contexto y Alcance
        _heading(doc, "1.1 Contexto y Alcance", 2)
        _para(doc, f"Documento fuente: {doc_name}  |  Version: V{version}.0  |  Hash: {doc_hash[:16]}…")

        if version_result and version_result.rule_diffs:
            unchanged = sum(1 for d in version_result.rule_diffs if d.status.value == "UNCHANGED")
            modified  = sum(1 for d in version_result.rule_diffs if d.status.value == "MODIFIED")
            added     = sum(1 for d in version_result.rule_diffs if d.status.value == "ADDED")
            removed   = sum(1 for d in version_result.rule_diffs if d.status.value == "REMOVED")
            _para(doc, f"Diff respecto a version anterior: {unchanged} sin cambios | "
                       f"{modified} modificadas | {added} nuevas | {removed} eliminadas")

        _heading(doc, "Dentro de alcance", 3)
        tecnicas_usadas = set(td.primary_technique for td in technique_decisions.values())
        for t in sorted(tecnicas_usadas):
            _bullet(doc, t.replace("_", " "))

        _heading(doc, "Fuera de alcance", 3)
        _bullet(doc, "Diseno tecnico de tablas o estructuras de base de datos")
        _bullet(doc, "Procesos de cargue/validacion de fuentes externas (BRDs separados)")
        _bullet(doc, "Logica de presentacion de reportes")
        doc.add_paragraph()

        # 1.2 Campos y Estructuras Clave
        _heading(doc, "1.2 Campos y Estructuras Clave", 2)
        table = doc.add_table(rows=1, cols=2)
        table.style = "Table Grid"
        _header_row(table, ["Regla / CA", "Descripcion (resumen)"])
        _col_widths(table, [3.5, 13.5])
        for rid, text in list(rules.items())[:20]:
            row = _add_row(table, [rid, text[:180]])
        doc.add_paragraph()

        # 1.3 Reglas de Negocio / Criterios Identificados
        _heading(doc, "1.3 Reglas de Negocio / Criterios Identificados", 2)
        table2 = doc.add_table(rows=1, cols=5)
        table2.style = "Table Grid"
        _header_row(table2, ["ID", "Descripcion", "Nivel (D1)", "Tipo (D2)", "Tecnica"])
        _col_widths(table2, [2.0, 7.5, 2.5, 2.5, 2.5])

        for rid, text in rules.items():
            cl = classifications.get(rid)
            td = technique_decisions.get(rid)
            _add_row(table2, [
                rid,
                text[:120] + ("…" if len(text) > 120 else ""),
                cl.level if cl else "",
                cl.type_ if cl else "",
                td.primary_technique.replace("_", " ") if td else "",
            ])
        doc.add_paragraph()

    # ─────────────────────────────────────── SECCION 2 — ESTRATEGIA
    def _seccion2_estrategia(self, doc, rules, classifications,
                             technique_decisions, coverage_report) -> None:
        _heading(doc, "2. Estrategia de Pruebas (ISTQB)", 1)

        # 2.1 Niveles
        _heading(doc, "2.1 Niveles de Prueba Aplicables", 2)
        table = doc.add_table(rows=1, cols=3)
        table.style = "Table Grid"
        _header_row(table, ["Nivel", "Aplica", "Justificacion"])
        _col_widths(table, [4.0, 2.0, 11.0])

        level_map = {}
        for rid, cl in classifications.items():
            level_map.setdefault(cl.level, []).append(rid)

        all_levels = [
            ("componente",             "Componentes / Unitarias"),
            ("integracion_componentes","Integracion de Componentes"),
            ("sistema",                "Sistema"),
            ("integracion_sistema",    "Integracion de Sistema"),
            ("aceptacion",             "Aceptacion (UAT)"),
        ]
        justif_map = {
            "componente":             "Logica de calculo aislada; recomendacion white-box al equipo dev.",
            "integracion_componentes":"Cruce entre modulos internos.",
            "sistema":                "Construccion end-to-end del proceso.",
            "integracion_sistema":    "Integracion con servicios o sistemas externos.",
            "aceptacion":             "Validacion final con usuarios de negocio (UAT).",
        }
        for key, label in all_levels:
            aplica = "Si" if key in level_map else "No"
            rids   = ", ".join(level_map.get(key, []))
            just   = (justif_map.get(key, "") + (f" Reglas: {rids}" if rids else ""))
            _add_row(table, [label, aplica, just[:200]])
        doc.add_paragraph()

        # 2.2 Tipos de Prueba
        _heading(doc, "2.2 Tipos de Prueba ISTQB Aplicados", 2)
        table2 = doc.add_table(rows=1, cols=3)
        table2.style = "Table Grid"
        _header_row(table2, ["Tipo", "Conteo", "Detalle"])
        _col_widths(table2, [5.0, 2.0, 10.0])

        type_map: dict[str, list[str]] = {}
        for rid, cl in classifications.items():
            type_map.setdefault(cl.type_, []).append(rid)

        for tipo, rids in sorted(type_map.items()):
            _add_row(table2, [tipo, str(len(rids)), ", ".join(rids)])
        doc.add_paragraph()

        # 2.3 Criterios de Entrada
        _heading(doc, "2.3 Criterios de Entrada", 2)
        criterios_entrada = [
            "Documento de requerimientos entregado, revisado y con version aprobada.",
            "Ambientes de prueba aprovisionados con datos representativos.",
            "Reglas de negocio sin ambiguedades bloqueantes resueltas con el equipo de negocio.",
            "Insumo de datos para UAT disponible o confirmado.",
            "Matriz de trazabilidad sin reglas huerfanas.",
        ]
        for c in criterios_entrada:
            _number(doc, c)
        doc.add_paragraph()

        # 2.4 Criterios de Salida
        _heading(doc, "2.4 Criterios de Salida", 2)

        # Contar casos por prioridad
        from collections import Counter
        # no importar Counter arriba para no romper estructura
        total   = len([]) # placeholder, se recalcula abajo
        bullets = [
            "100% de los casos de prioridad Alta ejecutados sin defectos criticos/altos abiertos.",
            "100% de casos Media/Baja ejecutados sin defectos criticos abiertos.",
            "0 casos Exploratorios (EX) pendientes al cierre, salvo aceptacion formal de negocio.",
            "Matriz de trazabilidad sin reglas huerfanas (gap = 0).",
        ]
        if coverage_report:
            bullets.append(
                f"Cobertura de requerimientos: {coverage_report.requirements_coverage_pct:.1f}% "
                f"(objetivo 100%)."
            )
        for b in bullets:
            _bullet(doc, b)
        doc.add_paragraph()

        # 2.5 Criterios de Suspension / Reanudacion
        _heading(doc, "2.5 Criterios de Suspension y Reanudacion", 2)
        _para(doc, "Suspender si aparece defecto critico en reglas de prioridad Alta. "
                   "Reanudar tras correccion confirmada y re-ejecucion del caso afectado.")
        doc.add_paragraph()

        # 2.6 Ambientes y Datos de Prueba
        _heading(doc, "2.6 Ambientes y Datos de Prueba", 2)
        _para(doc, "Ambiente de prueba con todas las fuentes de datos provisionadas "
                   "para cada combinacion de jerarquia definida en el documento. "
                   "Datos limite: valores en fronteras de rangos, registros con "
                   "estados criticos y combinaciones de condiciones multiples.")
        doc.add_paragraph()

    # ─────────────────────────────────────── SECCION 3 — RIESGOS
    def _seccion3_riesgos(self, doc, risks: list[dict]) -> None:
        _heading(doc, "3. Registro de Riesgos", 1)

        # 3.1 Riesgos ligados a reglas
        _heading(doc, "3.1 Riesgos Ligados a Reglas", 2)
        table = doc.add_table(rows=1, cols=7)
        table.style = "Table Grid"
        _header_row(table, ["ID", "Tipo(s)", "Tecnica(s)",
                             "Probabilidad", "Impacto", "Riesgo",
                             "Justificacion / Mitigacion"])
        _col_widths(table, [2.0, 2.0, 2.5, 2.0, 2.0, 2.0, 6.5])

        for risk in risks:
            score  = risk.get("score", 0)
            nivel  = "Alta" if score >= 15 else ("Media" if score >= 8 else "Baja")
            prob   = "Alta" if risk.get("probability", 0) >= 4 else \
                     ("Media" if risk.get("probability", 0) >= 2 else "Baja")
            imp    = "Alta" if risk.get("impact", 0) >= 4 else \
                     ("Media" if risk.get("impact", 0) >= 2 else "Baja")

            row = table.add_row()
            values = [
                risk.get("rule_ref", risk.get("id", "")),
                "F",
                "TD, PE",
                prob,
                imp,
                nivel,
                risk.get("mitigation", "")[:150],
            ]
            for i, v in enumerate(values):
                _cell_text(row.cells[i], v, font_size=9)
            # Color en columna Riesgo (col 5)
            color = RISK_COLOR.get(nivel, C_GRAY_HDR)
            fc    = PRIORITY_FONT_COLOR.get(nivel, "000000")
            _set_cell_bg(row.cells[5], color)
            _cell_text(row.cells[5], nivel, bold=True, font_size=9, color=fc)

        doc.add_paragraph()

        # 3.2 Riesgos Transversales
        _heading(doc, "3.2 Riesgos Transversales", 2)
        transversales = [
            ("R-T01", "Ambiguedad en reglas de negocio sin resolver antes del inicio de pruebas.",
             "Alta", "Alta", "Alta",
             "Escalar al equipo de negocio antes de iniciar el diseno de casos."),
            ("R-T02", "Datos de prueba no representativos del ambiente de produccion.",
             "Media", "Alta", "Alta",
             "Validar insumo de datos con el equipo de datos antes de UAT."),
            ("R-T03", "Cambios de ultima hora en requerimientos durante el ciclo de pruebas.",
             "Media", "Alta", "Alta",
             "Congelar requerimientos antes de inicio de pruebas. Control de cambios formal."),
        ]
        table2 = doc.add_table(rows=1, cols=6)
        table2.style = "Table Grid"
        _header_row(table2, ["ID", "Descripcion",
                              "Probabilidad", "Impacto", "Riesgo", "Mitigacion"])
        _col_widths(table2, [1.5, 6.0, 2.0, 2.0, 2.0, 5.5])

        for rid, desc, prob, imp, nivel, mit in transversales:
            row = table2.add_row()
            for i, v in enumerate([rid, desc, prob, imp, nivel, mit]):
                _cell_text(row.cells[i], v, font_size=9)
            color = RISK_COLOR.get(nivel, C_GRAY_HDR)
            fc    = PRIORITY_FONT_COLOR.get(nivel, "000000")
            _set_cell_bg(row.cells[4], color)
            _cell_text(row.cells[4], nivel, bold=True, font_size=9, color=fc)

        doc.add_paragraph()

    # ─────────────────────────────────────── SECCION 4 — DECK DE PRUEBAS
    def _seccion4_deck(self, doc, test_cases: list[dict], project: str) -> None:
        _heading(doc, "4. Deck de Pruebas", 1)
        _para(doc, "Los casos de prueba se redactan en lenguaje natural, sin terminologia "
                   "tecnica de bases de datos, para que puedan ser ejecutados por cualquier "
                   "usuario de negocio.", size=9)
        doc.add_paragraph()

        # Tabla principal del deck — 11 columnas (igual al ejemplo)
        table = doc.add_table(rows=1, cols=11)
        table.style = "Table Grid"
        _header_row(table, [
            "ID Caso", "Nombre", "RN", "Prioridad",
            "Objetivo", "Precondicion", "Tiempo\nEstimado",
            "Pasos", "Datos de Prueba", "Resultado Esperado",
            "Comentario / Riesgo",
        ], font_size=8)
        _col_widths(table, [1.5, 4.5, 1.2, 1.5, 4.5, 4.5, 1.2, 5.0, 4.0, 5.0, 3.0])

        seq_counter: dict[str, int] = {}
        for tc in test_cases:
            rule_ref = tc.get("requirement_ref", "GEN")
            seq_counter[rule_ref] = seq_counter.get(rule_ref, 0) + 1
            seq = seq_counter[rule_ref]

            # Nombre en nomenclatura de la organización
            raw_name = tc.get("name", "")
            scenario = re.sub(r"^\[.*?\]\s*[\w\-]+\s*—\s*", "", raw_name).strip()
            safe_proj = re.sub(r"[^\w]", "_", project).upper()
            safe_ref  = re.sub(r"[^\w]", "_", rule_ref).upper()
            safe_scen = re.sub(r"[^\w\s]", "", scenario).strip()
            safe_scen = re.sub(r"\s+", "_", safe_scen)[:45]
            nombre    = f"{safe_proj}_{safe_ref}_{safe_scen}_{seq:03d}"

            # Formatear pasos
            steps = tc.get("steps", [])
            pasos = "\n".join(f"{i}. {s.strip()}" for i, s in enumerate(steps, 1))

            # Tiempo
            try:
                mins = int(tc.get("estimated_min", 30))
                tiempo = f"{mins // 60:02d}:{mins % 60:02d}"
            except (TypeError, ValueError):
                tiempo = "00:30"

            # Prioridad
            prioridad = tc.get("priority", "Media")
            if prioridad.upper() == "ALTA":   prioridad = "Alta"
            elif prioridad.upper() == "MEDIA": prioridad = "Media"
            elif prioridad.upper() == "BAJA":  prioridad = "Baja"

            # Comentario (riesgo o nota)
            comentario = tc.get("risk", "")
            if tc.get("technique", "") == "Abuse_Case":
                comentario = f"Caso de seguridad — OWASP {tc.get('requirement_ref','')}"

            row = table.add_row()
            values = [
                tc.get("id", ""),
                nombre,
                rule_ref,
                prioridad,
                tc.get("objective", ""),
                tc.get("precondition", ""),
                tiempo,
                pasos,
                tc.get("test_data", ""),
                tc.get("expected_result", ""),
                comentario,
            ]
            for i, v in enumerate(values):
                _cell_text(row.cells[i], str(v) if v else "", font_size=8)

            # Color en columna Prioridad (col 3)
            color = PRIORITY_COLOR.get(prioridad, C_GRAY_HDR)
            fc    = PRIORITY_FONT_COLOR.get(prioridad, "000000")
            _set_cell_bg(row.cells[3], color)
            _cell_text(row.cells[3], prioridad, bold=True, font_size=8, color=fc)

        doc.add_paragraph()

    # ─────────────────────────────────────── SECCION 5 — TRAZABILIDAD
    def _seccion5_trazabilidad(self, doc, traceability: list[dict],
                                rules: dict, classifications: dict) -> None:
        _heading(doc, "5. Matriz de Trazabilidad", 1)

        table = doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        _header_row(table, ["RN", "Caso(s) de Prueba", "Tipo ISTQB", "Riesgo"])
        _col_widths(table, [2.0, 8.0, 3.0, 2.5])

        for entry in traceability:
            nivel = entry.get("level", "")
            tipo  = entry.get("type", "funcional")
            # Abreviar tipo al estilo del ejemplo (F, D, RB, NFV…)
            tipo_abrev = self._abrev_tipo(tipo)
            riesgo = "Alta" if entry.get("gap") == "SI" else entry.get("coverage_pct", "")
            gap_label = " [GAP]" if entry.get("gap") == "SI" else ""

            row = table.add_row()
            values = [
                entry.get("rule_id", ""),
                entry.get("cases", "") + gap_label,
                tipo_abrev,
                entry.get("gap") == "SI" and "Alta" or "—",
            ]
            for i, v in enumerate(values):
                _cell_text(row.cells[i], str(v), font_size=9)
            # Color si hay gap
            if entry.get("gap") == "SI":
                _set_cell_bg(row.cells[1], "FFE0E0")

        doc.add_paragraph()

    # ─────────────────────────────────────── SECCIONES CONDICIONALES
    def _seccion_performance(self, doc, pp) -> None:
        _heading(doc, "6. Plan de Performance", 1)
        _para(doc, f"Activacion: {pp.activation_reason}")
        _para(doc, f"Usuarios concurrentes: {pp.concurrent_users} | "
                   f"TPS: {pp.tps} | RT objetivo p95: {pp.response_time_s}s | "
                   f"Ley de Little N: {pp.little_n:.1f}")
        if pp.sla_warning:
            _para(doc, pp.sla_warning, bold=True)

        for profile in pp.profiles:
            _para(doc, f"{profile.name}: {profile.description}", bold=True)
            _bullet(doc, f"Ramp-up: {profile.ramp_up} | Steady: {profile.steady} | "
                         f"Usuarios: {profile.target_users}")

        for ptc in pp.test_cases:
            _para(doc, f"{ptc.id} — {ptc.name}", bold=True)
            _para(doc, f"Resultado esperado: {ptc.expected_result}", size=9)
        doc.add_paragraph()

    def _seccion_seguridad(self, doc, om) -> None:
        _heading(doc, "7. Seguridad — Matriz OWASP Top 10 2021", 1)
        _para(doc, f"Nivel ASVS: L{om.asvs_level} — {om.asvs_reason}")
        if om.pentest_required and om.pentest_note:
            _para(doc, om.pentest_note, bold=True)

        _heading(doc, "7.1 Categorias Incluidas", 2)
        for cat in om.included():
            _para(doc, f"{cat.code} — {cat.name}", bold=True)
            _bullet(doc, f"Razon: {cat.reason}")
            for tc in cat.test_cases:
                _bullet(doc, f"Caso: {tc['name']}")

        _heading(doc, "7.2 Categorias Excluidas (auditoria)", 2)
        table = doc.add_table(rows=1, cols=3)
        table.style = "Table Grid"
        _header_row(table, ["Codigo", "Categoria", "Razon de exclusion"])
        _col_widths(table, [2.0, 5.0, 10.0])
        for cat in om.excluded():
            _add_row(table, [cat.code, cat.name, cat.reason])
        doc.add_paragraph()

    def _seccion_automatizacion(self, doc, ar) -> None:
        _heading(doc, "8. Estrategia de Automatizacion (CTAL-TAE)", 1)
        _para(doc, f"Total: {ar.summary.get('total',0)} | "
                   f"AUTOMATE_HIGH: {ar.summary.get('high',0)} | "
                   f"AUTOMATE_MEDIUM: {ar.summary.get('medium',0)} | "
                   f"MANUAL: {ar.summary.get('manual',0)}")
        if ar.ice_cream_cone_warning:
            _para(doc, ar.ice_cream_cone_warning, bold=True)

        table = doc.add_table(rows=1, cols=5)
        table.style = "Table Grid"
        _header_row(table, ["Caso ID", "Tecnica", "Score", "Etiqueta", "Razon"])
        _col_widths(table, [2.5, 4.0, 2.0, 4.0, 6.0])
        for s in ar.scores:
            _add_row(table, [s.test_case_id, s.technique,
                              f"{s.final_score:.2f}", s.label, s.rationale])
        doc.add_paragraph()

    def _seccion_mantenimiento(self, doc, mr) -> None:
        _heading(doc, "9. Suite de Regresion y Mantenimiento", 1)
        _para(doc, mr.summary(), bold=True)
        _para(doc, mr.rotation_note, size=9)
        if mr.entries:
            table = doc.add_table(rows=1, cols=5)
            table.style = "Table Grid"
            _header_row(table, ["Caso ID", "Nombre", "Tipo Impacto", "Regla", "Esfuerzo (h)"])
            _col_widths(table, [2.0, 6.0, 3.0, 2.5, 2.5])
            for e in mr.entries:
                _add_row(table, [e.case_id, e.case_name[:50],
                                  e.impact_type, e.rule_ref, str(e.effort_hours)])
        doc.add_paragraph()

    # ─────────────────────────────────────── utils
    @staticmethod
    def _abrev_tipo(tipo: str) -> str:
        return {
            "funcional":      "F",
            "performance":    "NFV",
            "seguridad":      "S",
            "usabilidad":     "NFU",
            "compatibilidad": "CM",
            "fiabilidad":     "NFR",
        }.get(tipo.lower(), "F")
