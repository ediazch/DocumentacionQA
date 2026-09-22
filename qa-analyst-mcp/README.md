# QA Intelligence Suite v2.0

Transforma documentos BRD, HU o Requerimientos en entregables
completos de pruebas de software aplicando ISTQB CTFL v4.0.

## Instalacion rapida

```powershell
python setup.py
```

## Uso

```powershell
# Procesar un documento
env\Scripts\python main.py --doc "ruta\documento.docx" --project "MiProyecto"

# Verificar que todo funciona
env\Scripts\python main.py --test

# Servidor MCP para Aura/Claude
env\Scripts\python mcp_server.py
```

## Reconstruir en otro entorno

1. Copiar estos archivos al nuevo entorno:
   - PROMPT_MAESTRO.md
   - setup.py
   - requirements.txt
   - Todos los .py del proyecto

2. Ejecutar:
   ```powershell
   python setup.py
   ```

3. Si faltan archivos .py, entregar PROMPT_MAESTRO.md
   a Aura o Claude para reconstruirlos automaticamente.

## Entregables generados

| Archivo | Contenido | Audiencia |
|---------|-----------|-----------|
| *_QADeck_*.docx | Analisis completo ISTQB | QA / Lideres / Negocio |
| *_TestCases_*.xlsx | Solo casos de prueba | Testers / UAT |
| *_TestCases_*.csv | Casos para Jira | Herramienta de gestion |

## Estandares aplicados

- ISTQB CTFL v4.0
- ISTQB CTAL-TTA
- ISTQB CTAL-TAE
- OWASP Top 10 2021
- OWASP ASVS 4.0
- ISO/IEC 25010
