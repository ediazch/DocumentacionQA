"""
logging_skill.py — Skill global de logging.
Registra todas las operaciones en SQLite y consola.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.database import Logger

def get_logger(module: str, session_id: str = None) -> Logger:
    return Logger(module, session_id)
