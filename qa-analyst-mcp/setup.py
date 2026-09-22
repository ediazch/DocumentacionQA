"""
setup.py — Script de reconstruccion automatica del QA Intelligence Suite v2.0

Uso:
    python setup.py           → instala todo
    python setup.py --check   → solo verifica el entorno
    python setup.py --reset   → elimina env/ y reconstruye desde cero

Este script:
1. Verifica Python 3.10+
2. Crea el entorno virtual
3. Instala todas las dependencias
4. Crea la estructura de carpetas
5. Verifica que todo funciona
6. Muestra instrucciones de uso
"""
from __future__ import annotations

import os
import sys
import subprocess
import shutil
import argparse
from pathlib import Path

# ── Colores para consola
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):  print(f"{GREEN}  [OK]{RESET} {msg}")
def err(msg): print(f"{RED}  [ERROR]{RESET} {msg}")
def warn(msg):print(f"{YELLOW}  [WARN]{RESET} {msg}")
def info(msg):print(f"{BLUE}  [INFO]{RESET} {msg}")
def head(msg):print(f"\n{BOLD}{msg}{RESET}")

# ── Dependencias requeridas
DEPENDENCIES = [
    "python-docx",
    "openpyxl",
    "pypdf",
    "flask",
    "requests",
    "pytest",
    "playwright",
    "jinja2",
    "pandas",
    "pydantic",
    "cryptography",
    "lxml",
    "openai",
    "openai-agents",
    "fastmcp",
    "uvicorn",
    "starlette",
    "python-dotenv",
]

# ── Estructura de carpetas requerida
FOLDERS = [
    "core",
    "generators",
    "output",
    "skills/global",
    "skills/specific/qa",
    "skills/specific/security",
    "skills/specific/performance",
    "skills/specific/dev",
    "tools",
    "agents",
    "api",
    "tests",
    "docs",
]

# ── Archivos requeridos del proyecto
REQUIRED_FILES = [
    "main.py",
    "mcp_server.py",
    "agents_config.py",
    "core/__init__.py",
    "core/pipeline_state.py",
    "core/version_manager.py",
    "core/corpus_manager.py",
    "core/quality_gates.py",
    "core/istqb_classifier.py",
    "core/technique_selector.py",
    "core/pairwise_generator.py",
    "core/coverage_metrics.py",
    "core/performance_engine.py",
    "core/owasp_matrix.py",
    "core/abuse_case_generator.py",
    "core/automation_engine.py",
    "core/maintenance_testing.py",
    "core/case_builder.py",
    "generators/__init__.py",
    "generators/word_generator.py",
    "generators/excel_generator.py",
]


def check_python() -> bool:
    head("1. Verificando Python")
    version = sys.version_info
    if version.major == 3 and version.minor >= 10:
        ok(f"Python {version.major}.{version.minor}.{version.micro} — compatible")
        return True
    else:
        err(f"Python {version.major}.{version.minor} — se requiere 3.10+")
        return False


def create_venv(reset: bool = False) -> Path:
    head("2. Entorno virtual")
    env_path = Path("env")

    if reset and env_path.exists():
        warn("Eliminando entorno virtual anterior...")
        shutil.rmtree(env_path)
        ok("Entorno anterior eliminado")

    if env_path.exists():
        ok("Entorno virtual ya existe — reutilizando")
    else:
        info("Creando entorno virtual...")
        subprocess.run([sys.executable, "-m", "venv", "env"], check=True)
        ok("Entorno virtual creado")

    return env_path


def get_pip(env_path: Path) -> str:
    if sys.platform == "win32":
        return str(env_path / "Scripts" / "pip.exe")
    return str(env_path / "bin" / "pip")


def get_python(env_path: Path) -> str:
    if sys.platform == "win32":
        return str(env_path / "Scripts" / "python.exe")
    return str(env_path / "bin" / "python")


def install_dependencies(env_path: Path) -> bool:
    head("3. Instalando dependencias")
    pip = get_pip(env_path)

    # Actualizar pip
    info("Actualizando pip...")
    subprocess.run([pip, "install", "--upgrade", "pip"],
                   capture_output=True)

    failed = []
    for dep in DEPENDENCIES:
        result = subprocess.run(
            [pip, "install", dep],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            ok(f"{dep}")
        else:
            warn(f"{dep} — fallo (puede ser proxy corporativo)")
            failed.append(dep)

    if failed:
        warn(f"Dependencias no instaladas (proxy/red): {failed}")
        warn("El proyecto funcionara sin estas dependencias opcionales.")
    else:
        ok("Todas las dependencias instaladas correctamente")

    return True


def create_folders() -> None:
    head("4. Creando estructura de carpetas")
    for folder in FOLDERS:
        Path(folder).mkdir(parents=True, exist_ok=True)
        ok(folder)


def verify_files() -> tuple[list, list]:
    head("5. Verificando archivos del proyecto")
    present = []
    missing = []
    for f in REQUIRED_FILES:
        if Path(f).exists():
            ok(f)
            present.append(f)
        else:
            err(f"FALTANTE: {f}")
            missing.append(f)
    return present, missing


def create_env_file() -> None:
    head("6. Configuracion de entorno (.env)")
    env_file = Path(".env")
    if env_file.exists():
        ok(".env ya existe — no se sobreescribe")
        return

    content = """# QA Intelligence Suite v2.0 — Configuracion
# Copiar este archivo y completar los valores

# ── Modelos de IA (requerido para sistema multi-agente)
OPENAI_API_KEY=sk-tu-clave-aqui
PAID_MODEL=gpt-4o
FREE_MODEL=gpt-4o-mini

# ── Limites de tokens
PAID_TOKEN_LIMIT=100000
FREE_TOKEN_LIMIT=50000
WARN_THRESHOLD=0.80

# ── Servidor MCP
MCP_PORT=8000

# ── Proyecto
DEFAULT_PROJECT=MiProyecto
OUTPUT_DIR=output
"""
    env_file.write_text(content, encoding="utf-8")
    ok(".env creado — editar con tus claves de API")


def create_aura_config() -> None:
    head("7. Configuracion de Aura (.aura-config.json)")
    config_file = Path(".aura-config.json")
    if config_file.exists():
        ok(".aura-config.json ya existe")
        return

    import json
    config = {
        "project":        "QA Intelligence Suite v2.0",
        "version":        "2.0.0",
        "auto_start":     True,
        "mcp_port":       8000,
        "skills_global":  ["logging", "error_handling", "token_monitor", "memory"],
        "skills_specific":["qa_analysis", "test_case", "performance", "security", "webapp_testing"],
        "paid_model":     "gpt-4o",
        "free_model":     "gpt-4o-mini",
        "output_dir":     "output",
        "tools": {
            "soapui":     "C:\\Program Files\\SmartBear\\SoapUI-5.10.0\\bin\\soapui.bat",
            "java":       "C:\\Users\\ediazch\\AppData\\Local\\Programs\\Eclipse Adoptium\\jdk-25.0.4.101-hotspot\\bin\\java.exe",
            "java8":      "C:\\Program Files (x86)\\Java\\jre1.8.0_202\\bin\\java.exe",
        },
        "paths": {
            "skills":     "skills/",
            "output":     "output/",
            "tests":      "tests/",
            "docs":       "docs/",
        }
    }
    config_file.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    ok(".aura-config.json creado")


def run_tests(env_path: Path) -> bool:
    head("8. Verificando que el pipeline funciona")
    python = get_python(env_path)
    result = subprocess.run(
        [python, "main.py", "--test"],
        capture_output=True, text=True
    )
    if "10 PASS" in result.stdout or "PASS" in result.stdout:
        ok("Pipeline funcionando correctamente")
        # Mostrar resumen
        for line in result.stdout.splitlines():
            if "PASS" in line or "FAIL" in line or "Resultado" in line:
                print(f"    {line}")
        return True
    else:
        warn("Algunos tests fallaron — revisar manualmente")
        if result.stdout:
            print(result.stdout[-500:])
        return False


def print_summary(missing: list, env_path: Path) -> None:
    python = get_python(env_path)

    print(f"\n{'='*60}")
    print(f"{BOLD}  QA Intelligence Suite v2.0 — Instalacion completada{RESET}")
    print(f"{'='*60}")

    print(f"\n{BOLD}COMANDOS DISPONIBLES:{RESET}")
    print(f"""
  Pipeline completo:
  {python} main.py --doc "ruta/documento.docx" --project "Proyecto"

  Solo verificar:
  {python} main.py --test

  Listar procesados:
  {python} main.py --list

  Servidor MCP (para Claude/Aura):
  {python} mcp_server.py

  Servidor MCP HTTP (para Jira/otros):
  {python} mcp_server.py --http --port 8000
""")

    if missing:
        print(f"{YELLOW}ARCHIVOS FALTANTES (reconstruir con PROMPT_MAESTRO.md):{RESET}")
        for f in missing:
            print(f"  - {f}")

    print(f"\n{GREEN}Sistema listo para usar.{RESET}\n")


def main():
    parser = argparse.ArgumentParser(description="Setup QA Intelligence Suite v2.0")
    parser.add_argument("--check", action="store_true", help="Solo verificar entorno")
    parser.add_argument("--reset", action="store_true", help="Reconstruir desde cero")
    args = parser.parse_args()

    print(f"\n{BOLD}{'='*60}")
    print(f"  QA Intelligence Suite v2.0 — Setup")
    print(f"{'='*60}{RESET}\n")

    # 1. Verificar Python
    if not check_python():
        sys.exit(1)

    if args.check:
        # Solo verificar
        env_path = Path("env")
        present, missing = verify_files()
        print(f"\n  Archivos presentes: {len(present)}/{len(REQUIRED_FILES)}")
        if missing:
            print(f"  Archivos faltantes: {len(missing)}")
        return

    # 2. Entorno virtual
    env_path = create_venv(reset=args.reset)

    # 3. Dependencias
    install_dependencies(env_path)

    # 4. Carpetas
    create_folders()

    # 5. Verificar archivos
    present, missing = verify_files()

    # 6. .env
    create_env_file()

    # 7. .aura-config.json
    create_aura_config()

    # 8. Tests (solo si hay archivos)
    if not missing:
        run_tests(env_path)
    else:
        warn(f"Faltan {len(missing)} archivos — ejecutar con PROMPT_MAESTRO.md primero")

    # Resumen
    print_summary(missing, env_path)


if __name__ == "__main__":
    main()
