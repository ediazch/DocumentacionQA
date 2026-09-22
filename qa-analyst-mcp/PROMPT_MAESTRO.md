# PROMPT MAESTRO — QA Intelligence Suite v2.0
## Reconstruccion completa del sistema en cualquier entorno

Entregar este archivo a Aura, Claude, ChatGPT o cualquier agente con capacidad
de ejecutar codigo Python y manipular archivos del sistema.

---

## INSTRUCCION PARA EL AGENTE

Eres un agente experto en ingenieria de software y calidad de software (ISTQB).
Tu mision es reconstruir completamente el proyecto **QA Intelligence Suite v2.0**
en el entorno actual, siguiendo exactamente la especificacion de este documento.

**Pasos obligatorios en orden:**
1. Leer este documento completo antes de escribir cualquier codigo
2. Crear la estructura de carpetas
3. Implementar cada modulo en el orden indicado
4. Verificar que los criterios de aceptacion pasan (--test)
5. Confirmar al usuario que el sistema esta listo

---

## 1. DESCRIPCION DEL SISTEMA

Sistema que transforma documentos de requerimientos (BRD, HU, Requerimiento
Funcional) en entregables completos de pruebas de software:
- **Word (.docx)**: analisis completo ISTQB + deck de pruebas
- **Excel (.xlsx)**: casos de prueba formato Jira/Xray (7 columnas)
- **CSV**: derivado del Excel, listo para importar a Jira

### Capacidades principales
- Extrae reglas de negocio automaticamente de .docx, .pdf, .txt, .md
- Clasifica segun ISTQB CTFL v4.0 en 4 dimensiones
- Genera casos en 3 dimensiones: Funcionalidad + Validacion + Excepcion/Alerta
- Detecta elementos de UI: campos, fechas, botones, listas, checkbox, radio
- Motor de seguridad: OWASP Top 10 contextualizado + ASVS
- Motor de performance: Ley de Little + 4 perfiles de carga
- Sistema multi-agente: agente pago + fallback gratuito con monitor de tokens
- Servidor MCP: invocable desde Claude, Aura, Cursor u otros agentes
- Versionamiento: SHA-256 + diff semantico 3 niveles (reutiliza si no cambio)

---

## 2. ESTRUCTURA DE ARCHIVOS

```
qa-analyst-mcp/
├── main.py                        # Orquestador FSM + criterios de aceptacion
├── setup.py                       # Script de instalacion automatica
├── mcp_server.py                  # Servidor MCP (6 herramientas)
├── agents_config.py               # Sistema multi-agente + monitor tokens
├── requirements.txt               # Dependencias
├── .env                           # Variables de entorno (no compartir)
├── .aura-config.json              # Configuracion para Aura
├── PROMPT_MAESTRO.md              # Este archivo
├── core/
│   ├── __init__.py
│   ├── pipeline_state.py          # FSM + write-ahead log idempotente
│   ├── version_manager.py         # SHA-256 + diff semantico 3 niveles
│   ├── corpus_manager.py          # Persistencia corpus.json
│   ├── quality_gates.py           # G1-G7 PROCEED/WARN/BLOCK
│   ├── istqb_classifier.py        # Clasificador 4 dimensiones
│   ├── technique_selector.py      # Router de tecnicas ISTQB
│   ├── pairwise_generator.py      # Pairwise greedy + BVA 7 casos
│   ├── coverage_metrics.py        # Metricas de cobertura
│   ├── performance_engine.py      # Ley de Little + 4 perfiles
│   ├── owasp_matrix.py            # OWASP Top10 + ASVS
│   ├── abuse_case_generator.py    # Casos de seguridad
│   ├── automation_engine.py       # AutoScore + Ice Cream Cone
│   ├── maintenance_testing.py     # Analisis de impacto
│   └── case_builder.py            # Motor 3 dimensiones F+V+E
├── generators/
│   ├── __init__.py
│   ├── word_generator.py          # .docx 5 secciones ISTQB
│   └── excel_generator.py         # .xlsx Xray + CSV derivado
├── output/                        # Entregables generados
├── skills/
│   ├── global/                    # Skills que aplican a todo proyecto
│   └── specific/                  # Skills por modulo
└── env/                           # Entorno virtual (NO incluir en zip)
```

---

## 3. DEPENDENCIAS

```
python-docx>=1.0.0
openpyxl>=3.1.0
pypdf>=4.0.0
flask>=3.0.0
requests>=2.31.0
pytest>=7.4.0
playwright>=1.40.0
jinja2>=3.1.0
pandas>=2.0.0
pydantic>=2.0.0
cryptography>=41.0.0
lxml>=4.9.0
openai>=1.0.0
openai-agents>=0.0.1
fastmcp>=0.1.0
uvicorn>=0.24.0
starlette>=0.27.0
python-dotenv>=1.0.0
```

---

## 4. MARCO NORMATIVO (aplicar siempre)

### ISTQB CTFL v4.0
- **Niveles**: componente, integracion_componentes, sistema, integracion_sistema, aceptacion
- **Tipos**: funcional, performance, seguridad, usabilidad, compatibilidad, fiabilidad
- **Tecnicas black-box**: BVA (7 casos por rango), Particion Equivalencia, Tabla Decision, Transicion Estados, Casos Uso
- **Tecnicas experiencia**: Error Guessing, Exploratorio, Checklists
- **Principios P1-P7**: shift-left, risk-based, trazabilidad bidireccional, anti-pesticida

### Cobertura minima
- BVA: exactamente 7 casos por rango (min-1, min, min+, nominal, max-, max, max+1)
- Particiones: 100% con >= 1 caso
- Riesgo alto (>=15): >= 2 casos | Riesgo medio (8-14): >= 1 caso

### 3 Dimensiones de casos (OBLIGATORIO)
1. **Funcionalidad**: flujo positivo y negativo
2. **Validacion**: tipos de datos, formatos, fechas, elementos UI
3. **Excepcion/Alerta**: mensajes de alerta SIEMPRE, aunque el BRD no los especifique

### Elementos UI cubiertos automaticamente
- Numerico: letras, cero, negativo, separador de miles
- Texto: caracteres especiales, longitud maxima, solo espacios
- Email: sin @, sin dominio, sin extension, con espacios
- Fecha: formato incorrecto, 29-feb no bisiesto, fuera de rango
- Rango fechas: final < inicial, inicial > final, ambas vacias, iguales
- Botones: doble clic, sin campos obligatorios, cancelar
- Listas: sin seleccion, lista vacia, dependencia
- Checkbox/Radio: sin marcar, desmarcar obligatorio, exclusividad

### Formas de organizacion
- **Forma 1**: Todos F -> Todos V -> Todos E (por bloques tematicos)
- **Forma 2**: F+V+E por cada regla (por caso completo) — RECOMENDADA

---

## 5. PIPELINE FSM (7 fases)

```
INIT -> INGESTING -> INGESTED -> VERSION_CHECKING -> VERSION_CHECKED ->
ANALYZING -> ANALYZED -> AWAITING_CONFIRMATION -> CONFIRMED ->
DESIGNING -> DESIGNED -> ASSESSING_RISKS -> RISKS_ASSESSED ->
DELIVERING -> DELIVERED -> COMPLETED (o FAILED)
```

### Quality Gates
- G1 Ingesta: contenido >50 chars, hash calculado
- G2 Version: decision REUSE/NEW/INCREMENTAL_UPDATE
- G3 Analisis: >=1 regla extraida, sin contradicciones
- G4 Diseno: usuario confirmo, cero lenguaje tecnico prohibido
- G5 Cobertura: 100% requerimientos cubiertos
- G7 Entregables: archivos validos, CSV == Excel en filas

### Write-ahead log
- Cada transicion se persiste ANTES de ejecutarse (PENDING -> DONE)
- Al reiniciar: detecta operacion PENDING y la reintenta
- Idempotente: se puede ejecutar multiples veces sin efectos secundarios

---

## 6. VERSIONAMIENTO SHA-256 + DIFF SEMANTICO

```
Nivel 1: hash SHA-256 -> si igual -> REUSE (no regenerar nada)
Nivel 2: diff estructural por secciones
Nivel 3: similitud hibrida = 0.5 x SequenceMatcher + 0.5 x Jaccard
  >= 0.99 -> UNCHANGED
  >= 0.85 -> MODIFIED (si cosmético -> REFINED)
  >= 0.60 -> CANDIDATE (pedir confirmacion)
  < 0.60  -> ADDED / REMOVED
```

### Plan de regeneracion incremental
- ADDED -> generar nuevos casos
- MODIFIED -> regenerar solo esos casos
- REMOVED -> marcar OBSOLETO (NUNCA eliminar)
- UNCHANGED/REFINED -> no tocar

---

## 7. CLASIFICACION ISTQB 4 DIMENSIONES

### D1 — Nivel (por señal regex)
- api, servicio, core, pasarela, tercero -> integracion_sistema
- criterio de aceptacion, UAT -> aceptacion
- formula, calculo, redondeo -> componente
- default -> sistema

### D2 — Tipo (por señal regex)
- concurrente, SLA, volumen, pico -> performance
- contrasena, cifrado, autenticacion, PCI -> seguridad
- usabilidad, UX, accesibilidad -> usabilidad
- disponibilidad, backup, failover -> fiabilidad
- default -> funcional

### D3 — Perspectiva
- QA siempre black-box
- Si hay formula/calculo -> generar recomendacion white-box al equipo dev

### D4 — Motivo
- migracion inicial, datafix -> one_shot
- default -> primera_ejecucion + candidato_regresion

---

## 8. ROUTER DE TECNICAS

```
Rango numerico detectado -> BVA (7 casos canonicos)
Estados detectados + transicion -> Transicion de Estados
Condiciones combinadas (si...y...entonces) -> Tabla Decision
  > 6 condiciones -> Pairwise greedy (validacion programatica 100%)
Integracion detectada -> caso exito + caso falla del tercero
Default -> Particion de Equivalencia
Siempre complementar -> Error Guessing (filtrado por relevancia)
```

---

## 9. FORMATO DE ENTREGABLES

### Word (.docx) — 5 secciones
1. **Portada**: titulo, doc fuente, fecha, version, hash SHA-256, estandares
2. **Analisis del Documento**: contexto, alcance, reglas identificadas con clasificacion
3. **Estrategia ISTQB**: niveles, tipos, tecnicas, criterios entrada/salida, suspension, ambientes
4. **Registro de Riesgos**: tabla con colores (Alta=rojo, Media=amarillo, Baja=verde) + transversales
5. **Deck de Pruebas**: tabla 11 columnas (ID|Nombre|RN|Prioridad|Objetivo|Precondicion|Tiempo|Pasos|Datos|Resultado|Comentario)
6. **Matriz de Trazabilidad**: RN -> Casos, Tipo ISTQB, Riesgo

### Excel (.xlsx) — formato Jira/Xray
**7 columnas exactas**:
Name | Objective | Precondition | Estimated Time | Step | Data | Expected Result

- Una fila por caso (NO una fila por paso)
- Step: pasos numerados en una celda con saltos de linea (1. ... 2. ... 3. ...)
- Estimated Time: formato HH:MM
- Hojas adicionales: Risks, Traceability, Coverage
- Encabezado: fondo azul oscuro (#1F4E79) fuente blanca

### Name — nomenclatura de la organizacion
```
PROYECTO_RuleRef_Escenario_NNN
Ejemplo: MONITOREO_RN001_ValorLimiteInferior_001
```

### CSV
- Derivado EXCLUSIVAMENTE del Excel ya generado (leer el archivo, no desde memoria)
- UTF-8 con BOM (utf-8-sig)
- Delimitado por comas
- Listo para importar a Jira

---

## 10. MOTORES DE DOMINIO

### Performance (activar si: concurrente/SLA/volumen/pico/batch o >=3 integraciones)
- Ley de Little: N = TPS x R(s) x factor_pico (3.0 por defecto)
- SLA siempre en p95/p99 (advertir si es promedio)
- 4 perfiles: load (ramp 10min, steady 45min), stress (150%), spike (<30s), soak (>=4h)
- Herramienta: k6 si CI/CD, JMeter si no-HTTP

### Seguridad (activar si: autenticacion/datos sensibles/APIs)
- OWASP Top 10 2021 contextualizado (solo categorias que aplican)
- Nivel ASVS: publico->L1, PII/transacciones->L2, alto valor->L3 + pentest
- Abuse cases: IDOR, escalacion vertical, sin sesion, inyeccion, archivos disfrazados,
  manipulacion montos, doble envio, limite intentos, cierre sesion real

### Automatizacion (CTAL-TAE)
- AutoScore: frecuencia(0.25) + estabilidad(0.20) + determinismo(0.15) + riesgo(0.20) + facilidad(0.20) - manual(0.30)
- >= 0.70 -> AUTOMATE_HIGH | 0.40-0.69 -> AUTOMATE_MEDIUM | < 0.40 -> MANUAL
- Bloqueadores duros: exploratorio, usabilidad subjetiva, one-shot
- Detectar Ice Cream Cone (>50% UI) y advertir

---

## 11. SISTEMA MULTI-AGENTE

### Skills Globales (siempre activas)
```python
QA_ANALYSIS_SKILL = """
Experto en ISTQB CTFL v4.0. Extrae reglas, clasifica por nivel/tipo,
selecciona tecnicas, evalua riesgos. Responde en espanol.
Nunca uses lenguaje tecnico de BD en los casos.
"""

TEST_CASE_SKILL = """
3 dimensiones: Funcionalidad + Validacion + Excepcion/Alerta.
Mensajes de alerta SIEMPRE aunque el BRD no los especifique.
2 formas: bloques o por caso completo.
"""
```

### Skills Especificas
```python
WEBAPP_TESTING_SKILL  # pruebas de interfaces web
MCP_BUILDER_SKILL     # construccion de servidores MCP
SECURITY_SKILL        # OWASP, pentest, abuse cases
PERFORMANCE_SKILL     # JMeter, Ley de Little, SLAs
```

### Monitor de Tokens
- Registra en SQLite: timestamp, agente, tokens_entrada, tokens_salida, costo_usd
- Alerta al 80% del limite
- Fallback automatico al 100%: handoff con contexto completo preservado

### Memoria 3 capas
- Capa 1: ultimos 10 mensajes (RAM)
- Capa 2: estado del proyecto (JSON)
- Capa 3: historico completo (SQLite)

---

## 12. SERVIDOR MCP — 6 HERRAMIENTAS

```python
analyze_document(doc_path, project)
  -> Extrae y clasifica reglas ISTQB

generate_cases(doc_path, project, org_mode, detail_level)
  -> Genera casos con 3 dimensiones

generate_deliverables(doc_path, project, org_mode, detail_level, has_cicd)
  -> Pipeline completo: Word + Excel + CSV

check_version(doc_path, project)
  -> REUSE / NEW / INCREMENTAL_UPDATE

token_status()
  -> Estado del monitor de tokens

list_processed()
  -> Lista documentos procesados con entregables
```

---

## 13. LENGUAJE PROHIBIDO EN CASOS (gate bloqueante)

NUNCA usar en casos de prueba:
- SQL: SELECT, INSERT, UPDATE, DELETE, FROM, WHERE, JOIN
- Nombres de campos de BD: campo_, tbl_, col_
- Endpoints, payloads, requests, responses
- JSON, XML, HTTP, REST, API (en el texto de los pasos)
- localhost, 127.0.0.1, uuid, token, jwt, bearer

SIEMPRE usar:
- Pantallas, botones, campos visibles
- Datos en terminos de negocio
- Lenguaje natural comprensible por usuario de negocio

---

## 14. CRITERIOS DE ACEPTACION (verificar con --test)

```
CA1: BRD "entre 100 y 5000" -> exactamente 7 casos BVA
CA2: 8 params x 3 valores -> pairwise 12-30 casos, cobertura 2-way 100%
CA3: Segunda ejecucion mismo doc -> REUSE sin regenerar
CA4: 1 regla modificada de 20 -> MODIFIED=1, UNCHANGED=19
CA5: RN sin casos -> G4 WARN con lista de gaps
CA5b: Caso con "SELECT" -> G4 BLOCK (violacion R2)
CA7: "500 usuarios concurrentes p95<2s" -> performance activado >= 2 casos
CA8: Datos confidenciales -> OWASP A01/A07 incluidos
CA9: Caso exploratorio -> MANUAL con bloqueador citado
CA10: Proceso interrumpido en DELIVERING -> reanuda solo esa fase
```

---

## 15. REGLAS DE COMPORTAMIENTO INVIOLABLES

R1: Entregable generado NUNCA se modifica (inmutabilidad)
R2: Cero lenguaje tecnico en casos (gate bloqueante)
R3: Ambiguedad -> preguntar antes de disenar (nunca resolver en silencio)
R4: Toda RN con >=1 caso o documentado como gap
R5: Documento cambiado -> solo regenerar lo afectado
R6: HU simple -> funcional | BRD medio -> +riesgos | BRD grande -> +performance+seguridad
R7: Antes de disenar -> presentar resumen y pedir confirmacion
R8: Generar en el idioma del documento fuente (espanol por defecto)

---

## 16. PREGUNTAS OBLIGATORIAS ANTES DE GENERAR

El sistema debe preguntar al usuario antes de disenar los casos:

**Pregunta 1 — Forma de organizacion:**
```
[1] Por bloques: Todos F -> Todos V -> Todos E
[2] Por caso completo: F+V+E por cada regla (RECOMENDADO)
```

**Pregunta 2 — Nivel de detalle:**
```
[1] Solo Funcionalidad
[2] Funcionalidad + Validacion
[3] Funcionalidad + Validacion + Excepcion/Alerta (RECOMENDADO)
```

**Pregunta 3 — Confirmar:**
```
Confirmar diseno de casos? [s/N]:
```

---

## 17. CONFIGURACION INICIAL (.aura-config.json)

```json
{
  "project": "QA Intelligence Suite v2.0",
  "version": "2.0.0",
  "auto_start": true,
  "mcp_port": 8000,
  "skills_global": ["logging", "error_handling", "token_monitor", "memory"],
  "skills_specific": ["qa_analysis", "test_case", "performance", "security"],
  "paid_model": "gpt-4o",
  "free_model": "gpt-4o-mini",
  "output_dir": "output"
}
```

---

## 18. COMANDOS DE USO

```powershell
# Instalar todo
python setup.py

# Verificar entorno
python setup.py --check

# Reconstruir desde cero
python setup.py --reset

# Ejecutar pipeline
env\Scripts\python main.py --doc "ruta\documento.docx" --project "MiProyecto"

# Verificar criterios de aceptacion
env\Scripts\python main.py --test

# Listar procesados
env\Scripts\python main.py --list

# Servidor MCP para Aura/Claude
env\Scripts\python mcp_server.py

# Servidor MCP HTTP para Jira/otros
env\Scripts\python mcp_server.py --http --port 8000
```

---

## 19. INSTRUCCIONES FINALES PARA EL AGENTE

1. Implementar TODOS los archivos listados en la seccion 2
2. Respetar EXACTAMENTE el formato de Excel (7 columnas, una fila por caso)
3. Respetar EXACTAMENTE la nomenclatura de entregables
4. Verificar que `python main.py --test` pasa 10/10 antes de reportar completado
5. Si algun criterio falla, corregir antes de reportar
6. NO crear archivos .md de resumen o documentacion adicional
7. NO hardcodear datos de prueba
8. TODO el codigo debe ser funcional, no prototipos

**El sistema esta listo cuando:**
- `env\Scripts\python main.py --test` reporta: "Todos los criterios de aceptacion cumplidos"
- Los 3 entregables se generan correctamente con un documento de prueba
- El servidor MCP inicia sin errores
