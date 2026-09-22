# Graph Report - .  (2026-09-21)

## Corpus Check
- Corpus is ~31.739 words - fits in a single context window. You may not need a graph.

## Summary
- 486 nodes · 1419 edges · 20 communities detected
- Extraction: 58% EXTRACTED · 42% INFERRED · 0% AMBIGUOUS · INFERRED: 598 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output
- Edge kinds: uses: 598 · calls: 303 · method: 192 · contains: 156 · rationale_for: 102 · imports_from: 60 · inherits: 8


## Input Scope
- Requested: auto
- Resolved: all (source: default-auto)
- Included files: 37 · Candidates: recursive
- Excluded: 0 untracked · 0 ignored · 0 sensitive · 0 missing committed
## God Nodes (most connected - your core abstractions)
1. `PairwiseGenerator` - 45 edges
2. `CorpusManager` - 44 edges
3. `OWASPEngine` - 43 edges
4. `PerformanceEngine` - 41 edges
5. `AutomationEngine` - 39 edges
6. `CoverageMetrics` - 39 edges
7. `TechniqueSelector` - 39 edges
8. `ISTQBClassifier` - 37 edges
9. `VersionManager` - 36 edges
10. `VersionDecision` - 35 edges

## Surprising Connections (you probably didn't know these)
- `rest_server.py — API REST del QA Intelligence Suite v2.0  Endpoints:   POST /` --uses--> `Logger`  [INFERRED]
  api/rest_server.py → core/database.py
- `rest_server.py — API REST del QA Intelligence Suite v2.0  Endpoints:   POST /` --uses--> `OWASPEngine`  [INFERRED]
  api/rest_server.py → core/owasp_matrix.py
- `rest_server.py — API REST del QA Intelligence Suite v2.0  Endpoints:   POST /` --uses--> `WordGenerator`  [INFERRED]
  api/rest_server.py → generators/word_generator.py
- `Analiza un documento y retorna reglas extraidas.     Body: { "doc_path": "ruta"` --uses--> `Logger`  [INFERRED]
  api/rest_server.py → core/database.py
- `Analiza un documento y retorna reglas extraidas.     Body: { "doc_path": "ruta"` --uses--> `OWASPEngine`  [INFERRED]
  api/rest_server.py → core/owasp_matrix.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.12
Nodes (57): rest_server.py — API REST del QA Intelligence Suite v2.0  Endpoints:   POST /, Analiza un documento y retorna reglas extraidas.     Body: { "doc_path": "ruta", Genera casos de prueba.     Body: { "doc_path": "ruta", "project": "nombre",, Pipeline completo: Word + Excel + CSV.     Body: { "doc_path": "ruta", "project, Lista todos los documentos procesados., Casos de prueba de un proyecto., Estadisticas del proyecto., Estado del monitor de tokens. (+49 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (46): analyze(), audit(), deliverables(), download_file(), _error(), generate(), get_cases(), get_stats() (+38 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (14): PipelineState, pipeline_state.py — FSM con write-ahead log e idempotencia. Estados: INIT → ING, Avanza al siguiente estado válido con write-ahead log., Gestiona el estado del pipeline con write-ahead log persistido en JSON.     Cad, State, GateDecision, GateResult, QualityGates (+6 more)

### Community 3 - "Community 3"
Cohesion: 0.07
Nodes (18): build_agents(), MemoryManager, QAAgentOrchestrator, agents_config.py — Sistema multi-agente con monitoreo de tokens en tiempo real., Monitorea el uso de tokens en tiempo real.     Activa el fallback al agente gra, Determina si se debe cambiar al agente gratuito., Avisa cuando se acerca al límite., Reinicia el contador de sesión (no el histórico). (+10 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (6): get_connection(), init_db(), Logger, Logger que escribe en SQLite y en consola simultaneamente., Crea todas las tablas si no existen., logging_skill.py — Skill global de logging. Registra todas las operaciones en S

### Community 5 - "Community 5"
Cohesion: 0.28
Nodes (13): _add_row(), _bullet(), _cell_text(), _col_widths(), _header_row(), _heading(), _number(), _para() (+5 more)

### Community 6 - "Community 6"
Cohesion: 0.18
Nodes (23): check_env(), check_tools(), err(), info(), init_database(), load_config(), load_global_skills(), load_specific_skills() (+15 more)

### Community 7 - "Community 7"
Cohesion: 0.17
Nodes (8): CaseBlock, CaseBuilder, case_builder.py — Motor de construcción de casos con 3 dimensiones:   Funcional, Un bloque de casos para una regla: Funcionalidad + Validación + Excepción., Forma 1: todos F, luego todos V, luego todos E., Forma 2: F+V+E por caso completo., org_mode:    1 = por bloques, 2 = por caso completo         detail_level:1 = so, Construye los casos de una regla con las 3 dimensiones         y los organiza s

### Community 8 - "Community 8"
Cohesion: 0.14
Nodes (13): _apply_header(), _build_name(), _fmt_precondition(), _fmt_steps(), _fmt_time(), excel_generator.py — Genera .xlsx y .csv en el formato exacto de la organización, Genera el Excel con el formato exacto de la organización.         Hoja principa, Convierte minutos a HH:MM. (+5 more)

### Community 9 - "Community 9"
Cohesion: 0.32
Nodes (18): check_python(), create_aura_config(), create_env_file(), create_folders(), create_venv(), err(), get_pip(), get_python() (+10 more)

### Community 10 - "Community 10"
Cohesion: 0.24
Nodes (2): OWASPEngine, OWASPMatrix

### Community 11 - "Community 11"
Cohesion: 0.22
Nodes (12): _extract_rules(), _extract_sections(), hybrid_similarity(), _is_cosmetic(), _jaccard(), version_manager.py — Versionamiento SHA-256 + diff semántico 3 niveles.  Nivel, Detecta cambios cosméticos: mismos números, montos y condiciones semánticas., Divide el documento en secciones por encabezados. (+4 more)

### Community 12 - "Community 12"
Cohesion: 0.18
Nodes (4): PerformanceCase, PerformancePlan, PerformanceProfile, performance_engine.py — Motor de Performance (Ley de Little + 4 perfiles de carg

### Community 13 - "Community 13"
Cohesion: 0.20
Nodes (2): AutomationReport, AutomationScore

### Community 14 - "Community 14"
Cohesion: 0.18
Nodes (4): CoverageReport, Verifica que por cada regla con BVA haya exactamente 7 casos., Verifica que haya ≥1 caso por partición de equivalencia.         Aproximación:, Riesgo alto (≥15): ≥2 casos. Medio (8-14): ≥1 caso.

### Community 15 - "Community 15"
Cohesion: 0.18
Nodes (5): Extrae rangos numéricos con min y max., Extrae estados mencionados en el texto., Extrae condiciones lógicas del texto., Filtra el checklist de Error Guessing por relevancia al texto., Selecciona la técnica principal y secundarias para una regla.

### Community 17 - "Community 17"
Cohesion: 0.33
Nodes (5): handle_errors(), error_handling.py — Skill global de manejo de errores. Captura excepciones, dec, Ejecuta una funcion con reintentos y captura de errores., Decorador para manejo automatico de errores., safe_execute()

### Community 18 - "Community 18"
Cohesion: 1.00
Nodes (1): Genera los 7 casos canónicos de Valores Límite para un rango [min, max].

### Community 19 - "Community 19"
Cohesion: 1.00
Nodes (1): Genera casos de transición de estados 0-switch:         - Todas las transicione

### Community 20 - "Community 20"
Cohesion: 1.00
Nodes (1): Genera el CSV EXCLUSIVAMENTE desde el Excel ya generado (nunca desde memoria).

## Knowledge Gaps
- **73 isolated node(s):** `agents_config.py — Sistema multi-agente con monitoreo de tokens en tiempo real.`, `Monitorea el uso de tokens en tiempo real.     Activa el fallback al agente gra`, `Determina si se debe cambiar al agente gratuito.`, `Avisa cuando se acerca al límite.`, `Reinicia el contador de sesión (no el histórico).` (+68 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 10`** (2 nodes): `OWASPEngine`, `OWASPMatrix`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 13`** (2 nodes): `AutomationReport`, `AutomationScore`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 18`** (1 nodes): `Genera los 7 casos canónicos de Valores Límite para un rango [min, max].`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (1 nodes): `Genera casos de transición de estados 0-switch:         - Todas las transicione`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 20`** (1 nodes): `Genera el CSV EXCLUSIVAMENTE desde el Excel ya generado (nunca desde memoria).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TokenMonitor` connect `Community 3` to `Community 0`?**
  _High betweenness centrality (0.132) - this node is a cross-community bridge._
- **Why does `PairwiseGenerator` connect `Community 0` to `Community 7`, `Community 1`, `Community 18`, `Community 19`, `Community 2`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._
- **Why does `WordGenerator` connect `Community 5` to `Community 0`?**
  _High betweenness centrality (0.070) - this node is a cross-community bridge._
- **Are the 40 inferred relationships involving `PairwiseGenerator` (e.g. with `rest_server.py — API REST del QA Intelligence Suite v2.0  Endpoints:   POST /` and `Analiza un documento y retorna reglas extraidas.     Body: { "doc_path": "ruta"`) actually correct?**
  _`PairwiseGenerator` has 40 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `CorpusManager` (e.g. with `rest_server.py — API REST del QA Intelligence Suite v2.0  Endpoints:   POST /` and `Analiza un documento y retorna reglas extraidas.     Body: { "doc_path": "ruta"`) actually correct?**
  _`CorpusManager` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `OWASPEngine` (e.g. with `rest_server.py — API REST del QA Intelligence Suite v2.0  Endpoints:   POST /` and `Analiza un documento y retorna reglas extraidas.     Body: { "doc_path": "ruta"`) actually correct?**
  _`OWASPEngine` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `PerformanceEngine` (e.g. with `rest_server.py — API REST del QA Intelligence Suite v2.0  Endpoints:   POST /` and `Analiza un documento y retorna reglas extraidas.     Body: { "doc_path": "ruta"`) actually correct?**
  _`PerformanceEngine` has 32 INFERRED edges - model-reasoned connections that need verification._