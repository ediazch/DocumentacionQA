# QA Intelligence Suite v2.0

Transforma documentos BRD, HU o Requerimientos en entregables completos
de pruebas de software aplicando ISTQB CTFL v4.0, CTAL-TTA y OWASP ASVS 4.0.

---

## Estructura del proyecto

```
qa-analyst-mcp/
├── core/                          # Motores del pipeline ISTQB
│   ├── pipeline_state.py          # FSM + write-ahead log
│   ├── version_manager.py         # SHA-256 + diff semantico 3 niveles
│   ├── corpus_manager.py          # Persistencia de documentos
│   ├── quality_gates.py           # Gates G1-G7 PROCEED/WARN/BLOCK
│   ├── istqb_classifier.py        # Clasificador 4 dimensiones
│   ├── technique_selector.py      # Router de tecnicas ISTQB
│   ├── pairwise_generator.py      # Pairwise greedy + BVA 7 casos
│   ├── coverage_metrics.py        # Metricas de cobertura
│   ├── performance_engine.py      # Ley de Little + 4 perfiles
│   ├── owasp_matrix.py            # OWASP Top10 + ASVS
│   ├── abuse_case_generator.py    # Casos de seguridad
│   ├── automation_engine.py       # AutoScore + Ice Cream Cone
│   ├── maintenance_testing.py     # Analisis de impacto
│   ├── case_builder.py            # Motor 3 dimensiones F+V+E
│   └── database.py                # SQLite - logging y auditoria
├── generators/
│   ├── word_generator.py          # .docx 5 secciones ISTQB
│   └── excel_generator.py         # .xlsx Xray + CSV derivado
├── api/
│   └── rest_server.py             # API REST Flask (10 endpoints)
├── skills/
│   ├── global/                    # Skills globales del proyecto
│   └── specific/                  # Skills por dominio (qa, security, performance)
├── tests/
│   └── test_pipeline.py           # 40 pruebas automaticas
├── .agents/skills/                # 82 skills del ecosistema skills.sh
├── main.py                        # Orquestador FSM del pipeline
├── mcp_server.py                  # Servidor MCP (6 herramientas)
├── agents_config.py               # Sistema multi-agente + monitor tokens
├── startup.py                     # Arranque automatico
├── setup.py                       # Instalacion automatica
├── PROMPT_MAESTRO.md              # Documento de replicacion completa
└── requirements.txt               # Dependencias Python
```

---

## Instalacion rapida

```powershell
python setup.py
```

El script instala todas las dependencias, crea la estructura de carpetas
y verifica que el sistema funciona correctamente.

---

## Uso

```powershell
# Procesar un documento BRD, HU o Requerimiento
env\Scripts\python main.py --doc "ruta\documento.docx" --project "MiProyecto"

# Verificar que todo funciona (10 criterios de aceptacion)
env\Scripts\python main.py --test

# Listar documentos ya procesados
env\Scripts\python main.py --list

# Iniciar servidor MCP (para Aura / Claude)
env\Scripts\python mcp_server.py

# Iniciar API REST (para integraciones externas)
env\Scripts\python startup.py --api

# Iniciar API REST + MCP simultaneamente
env\Scripts\python startup.py --api --mcp

# Ver estado del sistema
env\Scripts\python startup.py --status
```

---

## Entregables generados

| Archivo | Contenido | Audiencia |
|---|---|---|
| `*_QADeck_*.docx` | Analisis completo ISTQB (5 secciones) | QA / Lideres / Negocio |
| `*_TestCases_*.xlsx` | Casos de prueba formato Jira/Xray | Testers / UAT |
| `*_TestCases_*.csv` | Derivado del Excel, listo para Jira | Herramienta de gestion |

Nomenclatura de archivos:
```
{proyecto}_{documento}_v{N}_{tipo}_{YYYYMMDD}-{HHMM}.{ext}
```

---

## Pipeline — 7 fases

```
INIT → INGESTING → INGESTED → VERSION_CHECKING → VERSION_CHECKED →
ANALYZING → ANALYZED → AWAITING_CONFIRMATION → CONFIRMED →
DESIGNING → DESIGNED → ASSESSING_RISKS → RISKS_ASSESSED →
DELIVERING → DELIVERED → COMPLETED
```

El pipeline pregunta antes de generar:
1. Forma de organizacion: `1` (por bloques) o `2` (por caso completo — recomendado)
2. Nivel de detalle: `1` (funcional) / `2` (+validacion) / `3` (+excepcion/alerta — recomendado)
3. Confirmar: `s`

---

## API REST — endpoints disponibles

| Metodo | Endpoint | Descripcion |
|---|---|---|
| GET | `/api/health` | Estado del sistema |
| POST | `/api/analyze` | Analizar documento |
| POST | `/api/generate` | Generar casos de prueba |
| POST | `/api/deliverables` | Pipeline completo |
| GET | `/api/documents` | Listar documentos procesados |
| GET | `/api/cases/<project>` | Casos de un proyecto |
| GET | `/api/stats/<project>` | Estadisticas |
| GET | `/api/tokens` | Monitor de tokens |
| GET | `/api/sessions` | Sesiones de trabajo |
| GET | `/api/download/<file>` | Descargar entregable |

---

## Servidor MCP — herramientas disponibles

| Herramienta | Descripcion |
|---|---|
| `analyze_document` | Extrae y clasifica reglas ISTQB |
| `generate_cases` | Genera casos con 3 dimensiones F+V+E |
| `generate_deliverables` | Pipeline completo Word+Excel+CSV |
| `check_version` | Detecta si el documento ya fue procesado |
| `token_status` | Estado del monitor de tokens |
| `list_processed` | Lista documentos procesados |

---

## Skills instaladas (82)

| Repositorio | Skills | Descripcion |
|---|---|---|
| `addyosmani/agent-skills` | 25 | Ciclo completo de ingenieria de software |
| `mattpocock/skills` | 38 | Skills para ingenieros reales |
| `obra/superpowers` | 15 | brainstorming, debugging, writing-plans |
| `vercel-labs/skills` | 1 | find-skills |
| `vercel-labs/agent-browser` | 1 | agent-browser |
| `anthropics/skills` | 1 | skill-creator |
| `Graphify-Labs/graphify` | 1 | knowledge graph |

---

## Estandares aplicados

- ISTQB CTFL v4.0
- ISTQB CTAL-TTA
- ISTQB CTAL-TAE
- OWASP Top 10 2021
- OWASP ASVS 4.0
- ISO/IEC 25010

---

## Seguridad

Los siguientes archivos contienen informacion sensible y NO se incluyen
en el repositorio. Deben configurarse manualmente en cada entorno:

| Archivo | Contenido | Reemplazado por |
|---|---|---|
| `.env` | API keys y configuracion de modelos | `*****************` |
| `output/corpus.json` | Documentos procesados y hashes | `*****************` |
| `output/qa_suite.db` | Base de datos SQLite con historial | `*****************` |
| `output/memory.json` | Contexto de sesiones | `*****************` |
| `output/token_usage.json` | Historial de uso de tokens | `*****************` |
| `output/wal_*.json` | Write-ahead logs del pipeline | `*****************` |
| `output/*.docx` | Entregables Word generados | `*****************` |
| `output/*.xlsx` | Entregables Excel generados | `*****************` |
| `output/*.csv` | Entregables CSV generados | `*****************` |

Para configurar el entorno, crear el archivo `.env` con:

```
OPENAI_API_KEY=*****************
PAID_MODEL=gpt-4o
FREE_MODEL=gpt-4o-mini
PAID_TOKEN_LIMIT=100000
FREE_TOKEN_LIMIT=50000
WARN_THRESHOLD=0.80
MCP_PORT=8000
```

---

## Reconstruir en otro entorno

```powershell
# Opcion 1: Clonar y configurar
git clone https://github.com/ediazch/DocumentacionQA.git
cd DocumentacionQA\qa-analyst-mcp
python setup.py

# Opcion 2: Solo con el Prompt Maestro
# Entregar PROMPT_MAESTRO.md a Aura o Claude
# El agente reconstruye todo el codigo desde cero
```

---

## Criterios de aceptacion del sistema

```powershell
env\Scripts\python main.py --test
# Resultado esperado: 10 PASS | 0 FAIL

env\Scripts\pytest tests/ -v
# Resultado esperado: 40 passed
```
