"""
abuse_case_generator.py — Generador de abuse cases de seguridad.

Genera casos tipo: IDOR, escalación vertical, acceso sin sesión, inyección,
archivos disfrazados, manipulación de montos, doble envío, límite de intentos,
cierre de sesión real.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


_AMOUNT_SIGNAL  = re.compile(r"\b(monto|importe|precio|valor|saldo|pago|cobro)\b", re.I)
_FILE_SIGNAL    = re.compile(r"\b(archivo|carga|upload|adjunto|documento|imagen)\b", re.I)
_SESSION_SIGNAL = re.compile(r"\b(sesi[oó]n|autenticaci[oó]n|login|token|JWT)\b", re.I)
_ROLE_SIGNAL    = re.compile(r"\b(rol|perfil|permiso|administrador|admin)\b", re.I)
_SUBMIT_SIGNAL  = re.compile(r"\b(enviar|submit|confirmar|pagar|registrar|guardar)\b", re.I)


@dataclass
class AbuseCase:
    id:              str
    name:            str
    category:        str
    objective:       str
    precondition:    str
    steps:           list[str]
    test_data:       str
    expected_result: str
    owasp_ref:       str
    priority:        str = "ALTA"
    requirement_ref: str = ""


class AbuseCaseGenerator:

    def generate(self, full_text: str, project: str) -> list[AbuseCase]:
        cases  = []
        num    = 1

        def _id() -> str:
            nonlocal num
            aid = f"SEC-{num:03d}"
            num += 1
            return aid

        # Siempre: acceso sin sesión
        cases.append(AbuseCase(
            id=_id(), name="Acceso directo sin autenticación",
            category="Acceso sin sesión",
            objective="Verificar que ninguna funcionalidad protegida es accesible sin autenticación previa.",
            precondition="Usuario no autenticado.",
            steps=[
                "Obtener la URL directa de una pantalla o función protegida.",
                "Acceder a esa URL sin haber iniciado sesión.",
                "Verificar la respuesta del sistema.",
            ],
            test_data="URL de recurso protegido sin token/cookie de sesión.",
            expected_result="El sistema redirige al login o devuelve error 401/403. No muestra datos protegidos.",
            owasp_ref="A07",
        ))

        # IDOR (siempre aplica en sistemas con recursos por usuario)
        cases.append(AbuseCase(
            id=_id(), name="IDOR — Acceso al recurso de otro usuario modificando el identificador",
            category="IDOR",
            objective="Verificar que el sistema valida la propiedad del recurso solicitado.",
            precondition="Dos usuarios registrados: Usuario A y Usuario B con recursos propios.",
            steps=[
                "Iniciar sesión como Usuario A.",
                "Identificar el identificador de un recurso propio (ej. número de solicitud, pedido).",
                "Cambiar ese identificador por el del recurso del Usuario B.",
                "Verificar la respuesta.",
            ],
            test_data="ID de recurso del Usuario B (obtenido por otro medio o incrementando el valor).",
            expected_result="El sistema devuelve error y no expone datos del Usuario B.",
            owasp_ref="A01",
        ))

        # Escalación vertical si hay roles
        if _ROLE_SIGNAL.search(full_text):
            cases.append(AbuseCase(
                id=_id(), name="Escalación vertical de privilegios",
                category="Escalación vertical",
                objective="Verificar que un usuario con rol básico no puede ejecutar funciones de administrador.",
                precondition="Usuario autenticado con rol de usuario estándar.",
                steps=[
                    "Iniciar sesión con un usuario de rol básico.",
                    "Intentar invocar una acción restringida al rol administrador.",
                    "Verificar que el sistema bloquea la acción.",
                ],
                test_data="Usuario: rol_basico / Acción: administrar_usuarios (o equivalente en el sistema).",
                expected_result="El sistema deniega la acción y no ejecuta ninguna operación privilegiada.",
                owasp_ref="A01",
            ))

        # Inyección en campos
        cases.append(AbuseCase(
            id=_id(), name="Inyección de caracteres maliciosos en campos de entrada",
            category="Inyección",
            objective="Verificar que el sistema sanitiza correctamente todas las entradas de texto.",
            precondition="Usuario autenticado con acceso a formularios de entrada.",
            steps=[
                "Ingresar en un campo de texto libre: ' OR '1'='1; DROP TABLE--",
                "Ingresar en otro campo: <script>alert('XSS')</script>",
                "Enviar el formulario.",
                "Verificar el resultado.",
            ],
            test_data="Payloads: SQLi: `' OR '1'='1`, XSS: `<img src=x onerror=alert(1)>`",
            expected_result="El sistema rechaza o escapa la entrada. No ejecuta código. No devuelve datos de BD.",
            owasp_ref="A03",
        ))

        # Archivos disfrazados
        if _FILE_SIGNAL.search(full_text):
            cases.append(AbuseCase(
                id=_id(), name="Carga de archivo con extensión disfrazada",
                category="Archivos disfrazados",
                objective="Verificar que el sistema valida el tipo real del archivo, no solo la extensión.",
                precondition="Usuario autenticado con permiso de carga de archivos.",
                steps=[
                    "Renombrar un archivo ejecutable (.exe, .php, .sh) con extensión .pdf o .jpg.",
                    "Intentar cargar el archivo renombrado.",
                    "Verificar la respuesta del sistema.",
                ],
                test_data="Archivo: script_malicioso.exe renombrado a documento.pdf",
                expected_result="El sistema rechaza el archivo al detectar que el tipo MIME no corresponde a la extensión.",
                owasp_ref="A03",
            ))

        # Manipulación de montos
        if _AMOUNT_SIGNAL.search(full_text):
            cases.append(AbuseCase(
                id=_id(), name="Manipulación de monto en la solicitud",
                category="Manipulación de parámetros",
                objective="Verificar que el monto de una transacción no puede ser alterado por el usuario.",
                precondition="Usuario autenticado. Interceptar el tráfico (proxy).",
                steps=[
                    "Iniciar una operación con monto legítimo (ej. 100).",
                    "Interceptar la solicitud antes de enviarla al servidor.",
                    "Modificar el parámetro de monto a un valor menor o negativo (ej. 0.01 o -100).",
                    "Enviar la solicitud modificada.",
                ],
                test_data="Monto original: 100 → Monto modificado: 0.01 o -100",
                expected_result="El sistema valida el monto en el servidor. No procesa el monto manipulado.",
                owasp_ref="A01",
            ))

        # Doble envío
        if _SUBMIT_SIGNAL.search(full_text):
            cases.append(AbuseCase(
                id=_id(), name="Doble envío — idempotencia de la operación",
                category="Doble envío",
                objective="Verificar que enviar la misma solicitud dos veces no genera duplicados.",
                precondition="Usuario autenticado. Formulario de envío disponible.",
                steps=[
                    "Completar el formulario con datos válidos.",
                    "Hacer clic en 'Enviar' dos veces rápidamente (o reenviar la solicitud HTTP).",
                    "Verificar el resultado en el sistema.",
                ],
                test_data="Solicitud idéntica enviada dos veces dentro de 1 segundo.",
                expected_result="El sistema procesa solo una operación. La segunda es ignorada o devuelve un error de operación duplicada.",
                owasp_ref="A04",
            ))

        # Límite de intentos
        if _SESSION_SIGNAL.search(full_text):
            cases.append(AbuseCase(
                id=_id(), name="Fuerza bruta — límite de intentos de autenticación",
                category="Límite de intentos",
                objective="Verificar que el sistema bloquea intentos de fuerza bruta en el inicio de sesión.",
                precondition="Página de inicio de sesión accesible.",
                steps=[
                    "Ingresar credenciales incorrectas 5 veces consecutivas.",
                    "Verificar el comportamiento del sistema tras cada intento.",
                    "Verificar el comportamiento tras superar el límite.",
                ],
                test_data="Usuario: usuario_valido / Contraseña: incorrecta (repetida 5+ veces)",
                expected_result="Tras N intentos fallidos (N configurable), el sistema bloquea temporalmente el acceso y/o activa CAPTCHA.",
                owasp_ref="A07",
            ))

            cases.append(AbuseCase(
                id=_id(), name="Cierre de sesión real — invalidación del token en servidor",
                category="Cierre de sesión real",
                objective="Verificar que al cerrar sesión el token queda inválido en el servidor.",
                precondition="Usuario autenticado.",
                steps=[
                    "Iniciar sesión y obtener el token de sesión activo.",
                    "Realizar una petición válida con ese token (verificar que funciona).",
                    "Cerrar sesión.",
                    "Reutilizar el mismo token para intentar acceder a un recurso protegido.",
                ],
                test_data="Token de sesión válido antes del cierre de sesión.",
                expected_result="El token queda invalidado en el servidor. El acceso posterior con ese token es denegado (401).",
                owasp_ref="A07",
            ))

        return cases
