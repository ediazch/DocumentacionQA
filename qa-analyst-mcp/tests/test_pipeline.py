"""
test_pipeline.py — Suite de pruebas automaticas del pipeline QA.

Ejecutar:
    env\Scripts\pytest tests/ -v
    env\Scripts\pytest tests/ -v --tb=short
    env\Scripts\pytest tests/test_pipeline.py::test_bva -v
"""
from __future__ import annotations

import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.pairwise_generator  import PairwiseGenerator
from core.version_manager     import VersionManager, VersionDecision, sha256
from core.corpus_manager      import CorpusManager
from core.quality_gates       import QualityGates, GateDecision
from core.istqb_classifier    import ISTQBClassifier
from core.technique_selector  import TechniqueSelector
from core.performance_engine  import PerformanceEngine
from core.owasp_matrix        import OWASPEngine
from core.automation_engine   import AutomationEngine
from core.coverage_metrics    import CoverageMetrics
from core.case_builder        import CaseBuilder
from main                     import extract_rules, generate_risks, generate_test_cases


# ═══════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def pw():
    return PairwiseGenerator()


@pytest.fixture
def tmp_corpus(tmp_path):
    return CorpusManager(tmp_path / "corpus.json")


@pytest.fixture
def tmp_vm(tmp_corpus):
    return VersionManager(tmp_corpus)


@pytest.fixture
def sample_brd():
    return """
    RN-001: El sistema debe validar que el monto ingresado este entre 100 y 5000.
    RN-002: Si el usuario tiene rol administrador y el estado es activo, puede aprobar solicitudes.
    RN-003: El sistema debe autenticar al usuario mediante correo electronico y contrasena.
    RN-004: El sistema debe integrarse con la API de pagos externa para procesar transacciones.
    RN-005: La fecha de inicio no puede ser mayor a la fecha fin.
    """


@pytest.fixture
def sample_rules(sample_brd):
    return extract_rules(sample_brd)


# ═══════════════════════════════════════════════════════════════════
# CA1 — BVA: exactamente 7 casos por rango
# ═══════════════════════════════════════════════════════════════════

class TestBVA:

    def test_bva_genera_7_casos(self, pw):
        cases = pw.bva_cases(100, 5000, "TEST")
        assert len(cases) == 7, f"Se esperaban 7 casos BVA, se generaron {len(cases)}"

    def test_bva_valores_correctos(self, pw):
        cases = pw.bva_cases(100, 5000, "TEST")
        values = [float(c["value"]) for c in cases]
        assert 99  in values,  "Falta min-1 (99)"
        assert 100 in values,  "Falta min (100)"
        assert 101 in values,  "Falta min+1 (101)"
        assert 5000 in values, "Falta max (5000)"
        assert 5001 in values, "Falta max+1 (5001)"

    def test_bva_validos_invalidos(self, pw):
        cases = pw.bva_cases(100, 5000, "TEST")
        validos   = [c for c in cases if c["valid"]]
        invalidos = [c for c in cases if not c["valid"]]
        assert len(validos)   == 5, f"Se esperaban 5 casos validos, hay {len(validos)}"
        assert len(invalidos) == 2, f"Se esperaban 2 casos invalidos, hay {len(invalidos)}"

    def test_bva_decimal(self, pw):
        cases = pw.bva_cases(0.0, 1.0, "DEC")
        assert len(cases) == 7
        values = [float(c["value"]) for c in cases]
        # min-1 y max+1 deben estar fuera del rango
        invalidos = [c for c in cases if not c["valid"]]
        assert len(invalidos) == 2, "Debe haber exactamente 2 casos invalidos"
        vals_invalidos = [float(c["value"]) for c in invalidos]
        assert any(v < 0.0 for v in vals_invalidos), "Falta valor menor al minimo"
        assert any(v > 1.0 for v in vals_invalidos), "Falta valor mayor al maximo"


# ═══════════════════════════════════════════════════════════════════
# CA2 — Pairwise: cobertura 2-way 100%
# ═══════════════════════════════════════════════════════════════════

class TestPairwise:

    def test_pairwise_8x3_rango(self, pw):
        params = {f"P{i}": ["v1", "v2", "v3"] for i in range(8)}
        result = pw.generate(params, "PW")
        assert 12 <= len(result.test_cases) <= 30, \
            f"Se esperaban 12-30 casos, se generaron {len(result.test_cases)}"

    def test_pairwise_cobertura_100(self, pw):
        params = {f"P{i}": ["v1", "v2", "v3"] for i in range(8)}
        result = pw.generate(params, "PW")
        assert result.validation_passed, \
            f"Cobertura 2-way no es 100%: {result.coverage_pct:.1f}%"
        assert result.uncovered_pairs == 0

    def test_pairwise_2_params(self, pw):
        params = {"A": ["x", "y"], "B": ["1", "2"]}
        result = pw.generate(params, "PW")
        assert result.validation_passed
        assert result.total_pairs == 4

    def test_pairwise_param_unico(self, pw):
        params = {"A": ["x", "y", "z"]}
        result = pw.generate(params, "PW")
        assert len(result.test_cases) == 3


# ═══════════════════════════════════════════════════════════════════
# CA3 — Versionamiento: REUSE si hash identico
# ═══════════════════════════════════════════════════════════════════

class TestVersioning:

    def test_reuse_mismo_documento(self, tmp_vm, tmp_corpus):
        content = "RN-001: El sistema valida el monto entre 100 y 5000."
        h       = sha256(content)
        tmp_corpus.save_document("P", "doc.txt", content, h, 1, {}, [])
        result = tmp_vm.check("P", "doc.txt", content)
        assert result.decision == VersionDecision.REUSE

    def test_new_documento_nuevo(self, tmp_vm):
        content = "RN-001: Nuevo documento nunca procesado."
        result  = tmp_vm.check("P", "nuevo.txt", content)
        assert result.decision == VersionDecision.NEW

    def test_incremental_documento_modificado(self, tmp_vm, tmp_corpus):
        original = "RN-001: Regla original sin cambios. RN-002: Segunda regla."
        h        = sha256(original)
        tmp_corpus.save_document("P", "brd.txt", original, h, 1, {}, [])
        modificado = original + "\nRN-003: Nueva regla agregada."
        result     = tmp_vm.check("P", "brd.txt", modificado)
        assert result.decision == VersionDecision.INCREMENTAL_UPDATE

    def test_diff_1_modificada_de_20(self, tmp_vm, tmp_corpus):
        content_20 = "\n".join(
            f"RN-{i:03d}: Regla de negocio numero {i} sin cambios."
            for i in range(1, 21)
        )
        h = sha256(content_20)
        tmp_corpus.save_document("P2", "brd.txt", content_20, h, 1, {}, [])
        modificado = content_20.replace(
            "RN-010: Regla de negocio numero 10 sin cambios.",
            "RN-010: Regla completamente diferente con nueva logica y monto alto."
        )
        result   = tmp_vm.check("P2", "brd.txt", modificado)
        modified = [d.rule_id for d in result.rule_diffs if d.status.value == "MODIFIED"]
        assert len(modified) >= 1, "Debe detectar al menos 1 regla MODIFIED"


# ═══════════════════════════════════════════════════════════════════
# CA5 — Quality Gates
# ═══════════════════════════════════════════════════════════════════

class TestQualityGates:

    def test_g1_contenido_vacio_block(self):
        g = QualityGates.g1_ingesta("corto", [], "abc123")
        assert g.is_blocked()

    def test_g1_contenido_valido_proceed(self):
        content  = "x" * 100
        sections = ["s1", "s2", "s3"]
        g = QualityGates.g1_ingesta(content, sections, "abc123hash")
        assert g.decision != GateDecision.BLOCK

    def test_g4_lenguaje_tecnico_block(self):
        bad_cases = [{
            "id": "TC-001", "name": "SELECT from tabla",
            "objective": "SELECT * FROM usuarios",
            "precondition": "", "steps": ["ejecutar SELECT"],
            "test_data": "", "expected_result": "resultado",
            "priority": "ALTA", "requirement_ref": "RN-001",
        }]
        g = QualityGates.g4_diseno(True, bad_cases, {"RN-001": "texto"})
        assert g.is_blocked(), "Lenguaje tecnico debe bloquear el gate G4"

    def test_g4_gaps_documentados(self):
        g = QualityGates.g4_diseno(
            True, [],
            {"RN-001": "regla 1", "RN-002": "regla 2"}
        )
        assert not g.is_blocked()
        assert "RN-001" in g.details.get("gaps", [])

    def test_g4_sin_confirmacion_block(self):
        g = QualityGates.g4_diseno(False, [], {})
        assert g.is_blocked()

    def test_g5_cobertura_incompleta_block(self):
        g = QualityGates.g5_cobertura({"requirements_coverage_pct": 80.0})
        assert g.is_blocked()

    def test_g5_cobertura_completa_proceed(self):
        g = QualityGates.g5_cobertura({"requirements_coverage_pct": 100.0})
        assert not g.is_blocked()


# ═══════════════════════════════════════════════════════════════════
# CA7 — Performance
# ═══════════════════════════════════════════════════════════════════

class TestPerformance:

    def test_performance_activado_por_concurrencia(self):
        pe   = PerformanceEngine()
        plan = pe.generate("500 usuarios concurrentes, p95<2s y SLA definido", "P")
        assert plan.activated
        assert len(plan.test_cases) >= 2

    def test_performance_no_activado(self):
        pe   = PerformanceEngine()
        plan = pe.generate("El sistema valida el nombre del usuario.", "P")
        assert not plan.activated

    def test_ley_de_little(self):
        pe   = PerformanceEngine()
        plan = pe.generate("100 usuarios concurrentes con SLA p95<3s, 10 TPS", "P")
        assert plan.little_n > 0

    def test_4_perfiles_de_carga(self):
        pe      = PerformanceEngine()
        plan    = pe.generate("500 usuarios concurrentes batch", "P")
        nombres = [p.name for p in plan.profiles]
        assert any("Load" in n or "Carga" in n    for n in nombres)
        assert any("Stress" in n or "Estr" in n   for n in nombres)
        assert any("Spike" in n or "Pico" in n    for n in nombres)
        assert any("Soak" in n or "Resistencia" in n for n in nombres)


# ═══════════════════════════════════════════════════════════════════
# CA8 — OWASP
# ═══════════════════════════════════════════════════════════════════

class TestOWASP:

    def test_owasp_activado_con_datos_sensibles(self):
        oe = OWASPEngine()
        om = oe.generate("autenticacion con contrasena y datos personales PII")
        assert om.activated

    def test_owasp_incluye_a01_a07(self):
        oe   = OWASPEngine()
        om   = oe.generate(
            "El sistema maneja datos personales PII, autenticacion "
            "con contrasena y roles de acceso."
        )
        codes = [c.code for c in om.included()]
        assert "A01" in codes, "A01 debe estar incluido"
        assert "A07" in codes, "A07 debe estar incluido"

    def test_owasp_exclusiones_documentadas(self):
        oe = OWASPEngine()
        om = oe.generate("autenticacion con contrasena")
        excluidas = om.excluded()
        assert len(excluidas) > 0
        for cat in excluidas:
            assert cat.reason, f"Categoria {cat.code} sin razon de exclusion"

    def test_owasp_no_activado_sin_senales(self):
        oe = OWASPEngine()
        om = oe.generate("El sistema muestra un reporte de ventas mensual.")
        assert not om.activated


# ═══════════════════════════════════════════════════════════════════
# CA9 — Automatizacion
# ═══════════════════════════════════════════════════════════════════

class TestAutomation:

    def test_exploratorio_es_manual(self):
        ae = AutomationEngine()
        cases = [{
            "id": "TC-EXP", "name": "Sesion exploratoria de usabilidad",
            "objective": "Explorar la interfaz de forma exploratoria ad-hoc",
            "technique": "Exploratorio", "steps": [],
            "priority": "MEDIA", "risk": "BAJA",
        }] * 3
        ar = ae.generate(cases, "prueba exploratoria")
        score = next((s for s in ar.scores if s.test_case_id == "TC-EXP"), None)
        assert score is not None
        assert score.label == "MANUAL"
        assert score.blocker is not None

    def test_bva_alto_es_automate_medium_o_high(self):
        ae = AutomationEngine()
        cases = [{
            "id": f"TC-{i:03d}",
            "name": "Validacion de rango numerico BVA",
            "objective": "Verificar limites del campo",
            "technique": "BVA", "steps": ["paso 1", "paso 2"],
            "priority": "ALTA", "risk": "ALTA",
        } for i in range(5)]
        ar = ae.generate(cases, "sistema estable con regresion frecuente")
        automatizables = [s for s in ar.scores
                          if s.label in ("AUTOMATE_HIGH", "AUTOMATE_MEDIUM")]
        assert len(automatizables) > 0, \
            "Casos BVA de alta prioridad deben ser automatizables"


# ═══════════════════════════════════════════════════════════════════
# CASE BUILDER — 3 dimensiones
# ═══════════════════════════════════════════════════════════════════

class TestCaseBuilder:

    def test_3_dimensiones_email(self):
        clf = ISTQBClassifier()
        sel = TechniqueSelector()
        builder = CaseBuilder(org_mode=2, detail_level=3)
        text = "RN-001: El usuario debe autenticarse con correo electronico y contrasena."
        cl   = clf.classify("RN-001", text)
        td   = sel.select("RN-001", text)
        pw   = PairwiseGenerator()
        counter = [0]
        cases = builder.build(
            "RN-001", text, td, cl, pw,
            "ALTA", "Sistema", "funcional", "ALTA", counter
        )
        dims = {tc.get("dimension") for tc in cases}
        assert "Funcionalidad" in dims, "Debe tener casos de Funcionalidad"
        assert "Validacion"    in dims, "Debe tener casos de Validacion"
        assert "Excepcion"     in dims, "Debe tener casos de Excepcion"

    def test_dimension_solo_funcional(self):
        clf = ISTQBClassifier()
        sel = TechniqueSelector()
        builder = CaseBuilder(org_mode=2, detail_level=1)
        text = "RN-001: El sistema guarda el nombre del usuario."
        cl   = clf.classify("RN-001", text)
        td   = sel.select("RN-001", text)
        pw   = PairwiseGenerator()
        counter = [0]
        cases = builder.build(
            "RN-001", text, td, cl, pw,
            "MEDIA", "Sistema", "funcional", "MEDIA", counter
        )
        dims = {tc.get("dimension") for tc in cases}
        assert "Excepcion" not in dims, "Nivel 1 no debe tener Excepciones"

    def test_forma_1_bloques(self):
        clf = ISTQBClassifier()
        sel = TechniqueSelector()
        builder = CaseBuilder(org_mode=1, detail_level=3)
        text = "RN-001: El campo correo debe tener formato valido."
        cl   = clf.classify("RN-001", text)
        td   = sel.select("RN-001", text)
        pw   = PairwiseGenerator()
        counter = [0]
        cases = builder.build(
            "RN-001", text, td, cl, pw,
            "ALTA", "Sistema", "funcional", "ALTA", counter
        )
        # En forma 1: primero todos los F, luego todos V, luego todos E
        dims = [tc.get("dimension") for tc in cases]
        if "Funcionalidad" in dims and "Validacion" in dims:
            last_f = max(i for i, d in enumerate(dims) if d == "Funcionalidad")
            first_v = min(i for i, d in enumerate(dims) if d == "Validacion")
            assert last_f < first_v, "En Forma 1, Funcionalidad debe ir antes que Validacion"


# ═══════════════════════════════════════════════════════════════════
# EXTRACCION DE REGLAS
# ═══════════════════════════════════════════════════════════════════

class TestRuleExtraction:

    def test_extrae_reglas_con_id(self):
        content = """
        RN-001: El monto debe estar entre 100 y 5000.
        RN-002: El usuario debe autenticarse con correo y contrasena.
        RN-003: La fecha inicio no puede ser mayor a la fecha fin.
        """
        rules = extract_rules(content)
        assert "RN-001" in rules
        assert "RN-002" in rules
        assert "RN-003" in rules

    def test_extrae_reglas_sin_id(self):
        content = """
        El sistema debe validar que el monto sea positivo y mayor a cero.
        El usuario debe autenticarse antes de acceder al tablero.
        La fecha de inicio debe ser menor a la fecha de fin del periodo.
        """
        rules = extract_rules(content)
        assert len(rules) >= 1

    def test_clasificacion_4_dimensiones(self):
        clf = ISTQBClassifier()
        rules = {
            "RN-001": "El sistema debe autenticarse con contrasena y roles.",
            "RN-002": "La formula calcula el interes compuesto diario.",
            "RN-003": "El sistema se integra con la API de pagos externa.",
        }
        classifications = clf.classify_all(rules)
        assert classifications["RN-001"].type_   == "seguridad"
        assert classifications["RN-002"].level   == "componente"
        assert classifications["RN-003"].level   == "integracion_sistema"


# ═══════════════════════════════════════════════════════════════════
# BASE DE DATOS
# ═══════════════════════════════════════════════════════════════════

class TestDatabase:

    def test_init_db(self):
        from core.database import init_db
        init_db()  # No debe lanzar excepcion

    def test_session_create_close(self):
        from core.database import SessionManager
        sid = SessionManager.create("TestProject", "test.docx")
        assert sid is not None
        SessionManager.close(sid, "completed")

    def test_logger_writes(self):
        from core.database import Logger
        log = Logger("TEST_MODULE", "test-session")
        log.info("test_action", "Mensaje de prueba")  # No debe lanzar excepcion

    def test_document_repository(self):
        from core.database import DocumentRepository
        doc_id = DocumentRepository.save(
            "TestProject", "test.docx", "hash123",
            1, 10, 50, ["output/test.xlsx"]
        )
        assert doc_id > 0

    def test_audit_trail(self):
        from core.database import AuditTrail
        AuditTrail.log("test-session", "test_action", "document", "test.docx")
        history = AuditTrail.get_history("test-session")
        assert len(history) >= 1
