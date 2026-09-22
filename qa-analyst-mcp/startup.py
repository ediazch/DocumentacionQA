"""
startup.py — Arranque automatico del QA Intelligence Suite v2.0

Ejecutar desde la raiz del proyecto:
    env\Scripts\python startup.py              → modo completo
    env\Scripts\python startup.py --api        → solo API REST
    env\Scripts\python startup.py --mcp        → solo servidor MCP
    env\Scripts\python startup.py --status     → solo estado del sistema
    env\Scripts\python startup.py --api --mcp  → API + MCP simultaneamente
"""
from __future__ import annotations

import sys
import json
import argparse
import subprocess
import threading
from pathlib import Path
from datetime import datetime

# ── Colores
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"
B = "\033[94m"; W = "\033[0m";  BOLD = "\033[1m"


def ok(m):   print(f"{G}  [OK]{W} {m}")
def err(m):  print(f"{R}  [ERR]{W} {m}")
def warn(m): print(f"{Y}  [WARN]{W} {m}")
def info(m): print(f"{B}  [INFO]{W} {m}")


def load_config() -> dict:
    config_file = Path(".aura-config.json")
    if config_file.exists():
        return json.loads(config_file.read_text(encoding="utf-8"))
    return {
        "project":         "QA Intelligence Suite v2.0",
        "version":         "2.0.0",
        "auto_start":      True,
        "mcp_port":        8000,
        "api_port":        5000,
        "skills_global":   ["logging", "error_handling", "token_monitor", "memory"],
        "skills_specific": ["qa_analysis", "test_case", "performance", "security"],
        "paid_model":      "gpt-4o",
        "free_model":      "gpt-4o-mini",
        "output_dir":      "output",
    }


def check_env() -> bool:
    """Verifica que el entorno virtual existe."""
    env_python = Path("env/Scripts/python.exe")
    if not env_python.exists():
        err("Entorno virtual no encontrado. Ejecutar: python setup.py")
        return False
    ok("Entorno virtual disponible")
    return True


def load_global_skills() -> list[str]:
    """Carga las skills globales."""
    loaded = []
    skills_dir = Path("skills/global")
    if not skills_dir.exists():
        warn("Carpeta skills/global no encontrada")
        return loaded

    for skill_file in skills_dir.glob("*.py"):
        if skill_file.name.startswith("_"):
            continue
        try:
            ok(f"Skill global: {skill_file.stem}")
            loaded.append(skill_file.stem)
        except Exception as e:
            warn(f"Skill {skill_file.stem}: {e}")

    return loaded


def load_specific_skills(project_type: str = "qa") -> list[str]:
    """Carga las skills especificas segun el tipo de proyecto."""
    loaded = []
    skills_dir = Path(f"skills/specific/{project_type}")
    if not skills_dir.exists():
        info(f"No hay skills especificas para: {project_type}")
        return loaded

    for skill_file in skills_dir.glob("*.py"):
        if skill_file.name.startswith("_"):
            continue
        try:
            ok(f"Skill especifica ({project_type}): {skill_file.stem}")
            loaded.append(skill_file.stem)
        except Exception as e:
            warn(f"Skill {skill_file.stem}: {e}")

    return loaded


def check_tools(config: dict) -> dict:
    """Verifica que las herramientas externas esten disponibles."""
    tools_status = {}
    tools = config.get("tools", {})

    # Herramientas del sistema
    system_tools = {
        "java_25": tools.get("java", ""),
        "java_8":  tools.get("java8", ""),
        "soapui":  tools.get("soapui", ""),
    }

    for name, path in system_tools.items():
        if path and Path(path).exists():
            ok(f"Herramienta disponible: {name}")
            tools_status[name] = True
        elif path:
            warn(f"Herramienta no encontrada: {name} ({path})")
            tools_status[name] = False

    # Librerias Python en el entorno virtual
    python = "env/Scripts/python.exe"
    py_tools = ["flask", "pytest", "playwright", "pandas",
                "openai", "fastmcp", "sqlite3"]

    for lib in py_tools:
        result = subprocess.run(
            [python, "-c", f"import {lib}; print('ok')"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            ok(f"Libreria Python: {lib}")
            tools_status[lib] = True
        else:
            warn(f"Libreria Python no disponible: {lib}")
            tools_status[lib] = False

    return tools_status


def init_database() -> bool:
    """Inicializa la base de datos SQLite."""
    try:
        result = subprocess.run(
            ["env/Scripts/python.exe", "-c",
             "from core.database import init_db; init_db()"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            ok("Base de datos SQLite inicializada")
            return True
        else:
            warn(f"Error inicializando BD: {result.stderr[:100]}")
            return False
    except Exception as e:
        warn(f"Error inicializando BD: {e}")
        return False


def start_api(port: int = 5000) -> subprocess.Popen:
    """Inicia el servidor API REST en background."""
    proc = subprocess.Popen(
        ["env/Scripts/python.exe", "api/rest_server.py", "--port", str(port)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    ok(f"API REST iniciada en http://localhost:{port}")
    info(f"  Endpoints disponibles:")
    info(f"  GET  http://localhost:{port}/api/health")
    info(f"  POST http://localhost:{port}/api/deliverables")
    info(f"  GET  http://localhost:{port}/api/documents")
    return proc


def start_mcp(port: int = 8000) -> subprocess.Popen:
    """Inicia el servidor MCP en background."""
    proc = subprocess.Popen(
        ["env/Scripts/python.exe", "mcp_server.py",
         "--http", "--port", str(port)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    ok(f"Servidor MCP iniciado en http://localhost:{port}")
    info(f"  Herramientas MCP disponibles:")
    info(f"  - analyze_document")
    info(f"  - generate_cases")
    info(f"  - generate_deliverables")
    info(f"  - check_version")
    info(f"  - token_status")
    info(f"  - list_processed")
    return proc


def print_status(config: dict, tools: dict,
                 global_skills: list, specific_skills: list) -> None:
    """Muestra el estado completo del sistema."""
    print(f"\n{BOLD}{'='*60}")
    print(f"  QA Intelligence Suite v2.0 — Estado del Sistema")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}{W}")

    print(f"\n{BOLD}SKILLS GLOBALES ({len(global_skills)}):{W}")
    for s in global_skills:
        print(f"  {G}+{W} {s}")

    print(f"\n{BOLD}SKILLS ESPECIFICAS ({len(specific_skills)}):{W}")
    for s in specific_skills:
        print(f"  {G}+{W} {s}")

    avail = sum(1 for v in tools.values() if v)
    total = len(tools)
    print(f"\n{BOLD}HERRAMIENTAS ({avail}/{total} disponibles):{W}")
    for name, status in tools.items():
        symbol = f"{G}OK{W}" if status else f"{Y}NO{W}"
        print(f"  [{symbol}] {name}")

    print(f"\n{BOLD}COMANDOS RAPIDOS:{W}")
    print(f"  Pipeline  : env\\Scripts\\python main.py --doc <ruta> --project <nombre>")
    print(f"  Tests     : env\\Scripts\\python main.py --test")
    print(f"  API REST  : env\\Scripts\\python startup.py --api")
    print(f"  MCP       : env\\Scripts\\python startup.py --mcp")
    print(f"  Ambos     : env\\Scripts\\python startup.py --api --mcp")
    print()


def main():
    parser = argparse.ArgumentParser(description="QA Suite Startup")
    parser.add_argument("--api",    action="store_true", help="Iniciar API REST")
    parser.add_argument("--mcp",    action="store_true", help="Iniciar servidor MCP")
    parser.add_argument("--status", action="store_true", help="Solo mostrar estado")
    args = parser.parse_args()

    print(f"\n{BOLD}{'='*60}")
    print(f"  QA Intelligence Suite v2.0 — Arranque")
    print(f"{'='*60}{W}\n")

    # Cargar configuracion
    config = load_config()
    info(f"Proyecto: {config.get('project')}")

    # Verificar entorno
    if not check_env():
        sys.exit(1)

    # Cargar skills
    print(f"\n{BOLD}Cargando skills globales...{W}")
    global_skills = load_global_skills()

    print(f"\n{BOLD}Cargando skills especificas (QA)...{W}")
    specific_skills = load_specific_skills("qa")

    # Verificar herramientas
    print(f"\n{BOLD}Verificando herramientas...{W}")
    tools = check_tools(config)

    # Inicializar BD
    print(f"\n{BOLD}Inicializando base de datos...{W}")
    init_database()

    # Mostrar estado
    print_status(config, tools, global_skills, specific_skills)

    if args.status:
        return

    # Iniciar servicios
    processes = []

    if args.api:
        print(f"\n{BOLD}Iniciando API REST...{W}")
        api_proc = start_api(config.get("api_port", 5000))
        processes.append(("API REST", api_proc))

    if args.mcp:
        print(f"\n{BOLD}Iniciando servidor MCP...{W}")
        mcp_proc = start_mcp(config.get("mcp_port", 8000))
        processes.append(("MCP Server", mcp_proc))

    if not processes:
        info("Sistema listo. Usa --api o --mcp para iniciar servicios.")
        return

    print(f"\n{G}{BOLD}Sistema iniciado. Presiona Ctrl+C para detener.{W}\n")

    try:
        for name, proc in processes:
            proc.wait()
    except KeyboardInterrupt:
        print(f"\n{Y}Deteniendo servicios...{W}")
        for name, proc in processes:
            proc.terminate()
            ok(f"{name} detenido")
        print(f"{G}Sistema detenido correctamente.{W}\n")


if __name__ == "__main__":
    main()
