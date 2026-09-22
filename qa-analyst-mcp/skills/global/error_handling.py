"""
error_handling.py — Skill global de manejo de errores.
Captura excepciones, decide si reintentar o escalar.
"""
from __future__ import annotations
import functools
import traceback
from typing import Callable, Any


def safe_execute(func: Callable, *args, retries: int = 1,
                 default: Any = None, **kwargs) -> Any:
    """Ejecuta una funcion con reintentos y captura de errores."""
    for attempt in range(retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt == retries:
                print(f"[ERROR] {func.__name__}: {e}")
                if default is not None:
                    return default
                raise
            print(f"[WARN] {func.__name__} fallo (intento {attempt+1}): {e}. Reintentando...")
    return default


def handle_errors(retries: int = 0, default: Any = None):
    """Decorador para manejo automatico de errores."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return safe_execute(func, *args, retries=retries,
                                default=default, **kwargs)
        return wrapper
    return decorator
