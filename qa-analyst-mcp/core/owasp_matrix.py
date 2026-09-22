"""
owasp_matrix.py — Matriz OWASP Top 10 2021 contextualizada + niveles ASVS.

Solo incluye categorías que aplican al contexto del documento.
Las excluidas se documentan con razón (auditoría).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------- señales
_AUTH_SIGNAL     = re.compile(r"\b(autenticaci[oó]n|login|usuario|contrase[ñn]a|acceso|rol|permiso|sesi[oó]n)\b", re.I)
_AUTHZ_SIGNAL    = re.compile(r"\b(rol|roles|permiso|permisos|autorizado|no autorizado|privilegio|admin|administrador|perfil|acceso)\b", re.I)
_INJECTION_SIGNAL= re.compile(r"\b(formulario|campo|entrada|texto libre|comentario|b[uú]squeda|filtro)\b", re.I)
_SENSITIVE_SIGNAL= re.compile(r"\b(datos personales|PII|PCI|tarjeta|contrase[ñn]a|cifrado|clave|privado)\b", re.I)
_SECURITY_SIGNAL = re.compile(r"\b(seguridad|autenticaci[oó]n|datos sensibles|API|token|JWT)\b", re.I)
_UPLOAD_SIGNAL   = re.compile(r"\b(archivo|carga|upload|adjunto|documento)\b", re.I)
_EXTERNAL_SIGNAL = re.compile(r"\b(URL|enlace|redirecci[oó]n|link externo|callback)\b", re.I)
_LOG_SIGNAL      = re.compile(r"\b(log|registro|auditor[ií]a|trazabilidad|historial)\b", re.I)
_CRYPTO_SIGNAL   = re.compile(r"\b(cifrado|hash|TLS|SSL|certificado|token|JWT|firma)\b", re.I)

# Nivel ASVS
_L2_SIGNAL = re.compile(r"\b(transacci[oó]n|pago|PII|datos personales|tarjeta|cuenta bancaria|saldo)\b", re.I)
_L3_SIGNAL = re.compile(r"\b(alto valor|cr[ií]tico|banco|financi|pentest|seguridad cr[ií]tica)\b", re.I)


@dataclass
class OWASPCategory:
    code:        str       # A01, A02, etc.
    name:        str
    included:    bool
    reason:      str       # por qué incluida/excluida
    signal:      str       # texto que activó (o vacío si excluida)
    asvs_ref:    str
    test_cases:  list[dict] = field(default_factory=list)


@dataclass
class OWASPMatrix:
    activated:   bool
    asvs_level:  int        # L1, L2, L3
    asvs_reason: str
    categories:  list[OWASPCategory]
    pentest_required: bool
    pentest_note:     Optional[str]

    def included(self) -> list[OWASPCategory]:
        return [c for c in self.categories if c.included]

    def excluded(self) -> list[OWASPCategory]:
        return [c for c in self.categories if not c.included]


class OWASPEngine:

    def should_activate(self, text: str) -> tuple[bool, str]:
        m = _SECURITY_SIGNAL.search(text)
        if m:
            return True, f"Señal: '{m.group()}'"
        return False, ""

    def generate(self, full_text: str) -> OWASPMatrix:
        activated, _ = self.should_activate(full_text)
        if not activated:
            return OWASPMatrix(
                activated=False, asvs_level=1, asvs_reason="Sin señales de seguridad.",
                categories=[], pentest_required=False, pentest_note=None,
            )

        # Nivel ASVS
        if _L3_SIGNAL.search(full_text):
            asvs_level  = 3
            asvs_reason = "Datos de alto valor / sistema crítico detectado → ASVS L3 (requiere pentest)"
            pentest     = True
            pentest_note= (
                "Pentest obligatorio con autorización formal previa. "
                "Metodología recomendada: PTES (Penetration Testing Execution Standard). "
                "Incluir pruebas de caja negra, gris y blanca con alcance delimitado por contrato."
            )
        elif _L2_SIGNAL.search(full_text):
            asvs_level  = 2
            asvs_reason = "Transacciones / PII detectados → ASVS L2"
            pentest     = False
            pentest_note= None
        else:
            asvs_level  = 1
            asvs_reason = "Sistema público sin datos especialmente sensibles → ASVS L1"
            pentest     = False
            pentest_note= None

        categories = self._build_categories(full_text)
        return OWASPMatrix(
            activated=True,
            asvs_level=asvs_level,
            asvs_reason=asvs_reason,
            categories=categories,
            pentest_required=pentest,
            pentest_note=pentest_note,
        )

    # ----------------------------------------------------------- builders
    def _build_categories(self, text: str) -> list[OWASPCategory]:
        cats = []

        # A01 — Control de Acceso Roto
        m = _AUTHZ_SIGNAL.search(text)
        cats.append(OWASPCategory(
            code="A01", name="Control de Acceso Roto",
            included=bool(m),
            reason=f"Señal '{m.group()}' → roles y permisos presentes" if m
                   else "Sin menciones de roles, permisos o autorización en el documento.",
            signal=m.group() if m else "",
            asvs_ref="ASVS V4",
            test_cases=self._a01_cases() if m else [],
        ))

        # A02 — Fallas Criptográficas
        m = _CRYPTO_SIGNAL.search(text)
        cats.append(OWASPCategory(
            code="A02", name="Fallas Criptográficas",
            included=bool(m),
            reason=f"Señal '{m.group()}' → manejo de datos cifrados" if m
                   else "Sin manejo de cifrado, TLS ni tokens detectado.",
            signal=m.group() if m else "",
            asvs_ref="ASVS V6",
            test_cases=self._a02_cases() if m else [],
        ))

        # A03 — Inyección
        m = _INJECTION_SIGNAL.search(text)
        cats.append(OWASPCategory(
            code="A03", name="Inyección",
            included=bool(m),
            reason=f"Señal '{m.group()}' → entradas de texto libre presentes" if m
                   else "Sin campos de entrada libre ni formularios detectados.",
            signal=m.group() if m else "",
            asvs_ref="ASVS V5",
            test_cases=self._a03_cases() if m else [],
        ))

        # A04 — Diseño Inseguro
        cats.append(OWASPCategory(
            code="A04", name="Diseño Inseguro",
            included=False,
            reason="Evaluación de diseño inseguro requiere revisión de arquitectura, fuera del alcance del análisis de requerimientos.",
            signal="",
            asvs_ref="ASVS V1",
            test_cases=[],
        ))

        # A05 — Configuración de Seguridad Incorrecta
        m = _SENSITIVE_SIGNAL.search(text)
        cats.append(OWASPCategory(
            code="A05", name="Configuración de Seguridad Incorrecta",
            included=bool(m),
            reason=f"Señal '{m.group()}' → datos sensibles presentes" if m
                   else "Sin datos sensibles ni configuración de seguridad explícita.",
            signal=m.group() if m else "",
            asvs_ref="ASVS V14",
            test_cases=self._a05_cases() if m else [],
        ))

        # A06 — Componentes Vulnerables y Desactualizados
        cats.append(OWASPCategory(
            code="A06", name="Componentes Vulnerables y Desactualizados",
            included=False,
            reason="Gestión de dependencias y versiones está fuera del alcance del análisis funcional de requerimientos.",
            signal="",
            asvs_ref="ASVS V14",
            test_cases=[],
        ))

        # A07 — Fallas de Autenticación e Identificación
        m = _AUTH_SIGNAL.search(text)
        cats.append(OWASPCategory(
            code="A07", name="Fallas de Autenticación e Identificación",
            included=bool(m),
            reason=f"Señal '{m.group()}' → autenticación presente" if m
                   else "Sin flujos de autenticación detectados.",
            signal=m.group() if m else "",
            asvs_ref="ASVS V2/V3",
            test_cases=self._a07_cases() if m else [],
        ))

        # A08 — Fallas de Integridad de Software y Datos
        cats.append(OWASPCategory(
            code="A08", name="Fallas de Integridad de Software y Datos",
            included=False,
            reason="Verificación de integridad de pipelines CI/CD fuera del alcance funcional.",
            signal="",
            asvs_ref="ASVS V10",
            test_cases=[],
        ))

        # A09 — Registro y Monitoreo de Seguridad Insuficientes
        m = _LOG_SIGNAL.search(text)
        cats.append(OWASPCategory(
            code="A09", name="Registro y Monitoreo de Seguridad Insuficientes",
            included=bool(m),
            reason=f"Señal '{m.group()}' → logs/auditoría mencionados" if m
                   else "Sin requisitos de logging de seguridad detectados.",
            signal=m.group() if m else "",
            asvs_ref="ASVS V7",
            test_cases=self._a09_cases() if m else [],
        ))

        # A10 — SSRF (Server Side Request Forgery)
        m = _EXTERNAL_SIGNAL.search(text)
        cats.append(OWASPCategory(
            code="A10", name="Falsificación de Solicitudes del Lado del Servidor (SSRF)",
            included=bool(m),
            reason=f"Señal '{m.group()}' → URLs externas o redirecciones presentes" if m
                   else "Sin entradas de URL ni redirecciones externas detectadas.",
            signal=m.group() if m else "",
            asvs_ref="ASVS V12",
            test_cases=self._a10_cases() if m else [],
        ))

        return cats

    # -------------------------------------------- abuse cases por categoría
    @staticmethod
    def _a01_cases() -> list[dict]:
        return [
            {"name": "Acceso directo a recurso sin autenticación",
             "steps": ["Intentar acceder a la funcionalidad protegida sin iniciar sesión.",
                       "Verificar que el sistema deniegue el acceso."],
             "expected": "El sistema rechaza la solicitud con mensaje de acceso no autorizado."},
            {"name": "Escalación vertical de privilegios",
             "steps": ["Iniciar sesión con un usuario de rol básico.",
                       "Intentar realizar una acción exclusiva del rol administrador.",
                       "Verificar que el sistema bloquea la acción."],
             "expected": "El sistema niega la acción y no expone funcionalidad restringida."},
            {"name": "IDOR — Acceso a recurso de otro usuario",
             "steps": ["Iniciar sesión como usuario A.",
                       "Modificar el identificador del recurso en la solicitud para apuntar al recurso del usuario B.",
                       "Verificar que el sistema no devuelve datos del usuario B."],
             "expected": "El sistema devuelve error 403/404 sin revelar datos del usuario B."},
        ]

    @staticmethod
    def _a02_cases() -> list[dict]:
        return [
            {"name": "Transmisión de datos sin cifrado",
             "steps": ["Interceptar el tráfico de red durante una operación sensible.",
                       "Verificar que los datos están cifrados (TLS activo)."],
             "expected": "Todo el tráfico sensible viaja cifrado mediante TLS 1.2+."},
        ]

    @staticmethod
    def _a03_cases() -> list[dict]:
        return [
            {"name": "Inyección de caracteres especiales en campo de texto",
             "steps": ["Ingresar en el campo de búsqueda o texto libre: ' OR '1'='1",
                       "Enviar el formulario.",
                       "Verificar que no se devuelven datos no esperados ni errores de BD."],
             "expected": "El sistema sanitiza la entrada y devuelve un error de validación controlado."},
            {"name": "Cross-Site Scripting (XSS) en campo visible",
             "steps": ["Ingresar en un campo de texto: <script>alert('xss')</script>",
                       "Guardar y visualizar el resultado.",
                       "Verificar que el script no se ejecuta."],
             "expected": "El contenido se escapa correctamente y no se ejecuta ningún script."},
        ]

    @staticmethod
    def _a05_cases() -> list[dict]:
        return [
            {"name": "Exposición de datos sensibles en mensajes de error",
             "steps": ["Provocar un error controlado en el sistema.",
                       "Revisar el mensaje de error devuelto al usuario."],
             "expected": "El mensaje de error es genérico y no expone datos internos, trazas ni rutas de servidor."},
        ]

    @staticmethod
    def _a07_cases() -> list[dict]:
        return [
            {"name": "Límite de intentos de autenticación fallidos",
             "steps": ["Intentar iniciar sesión con credenciales incorrectas 5 veces consecutivas.",
                       "Verificar comportamiento del sistema."],
             "expected": "El sistema bloquea temporalmente la cuenta o implementa CAPTCHA tras los intentos fallidos."},
            {"name": "Cierre de sesión real (invalidación de token)",
             "steps": ["Iniciar sesión y copiar el token de sesión.",
                       "Cerrar sesión.",
                       "Usar el token copiado para intentar acceder a un recurso protegido."],
             "expected": "El token queda invalidado en servidor y el acceso es denegado."},
        ]

    @staticmethod
    def _a09_cases() -> list[dict]:
        return [
            {"name": "Registro de eventos de seguridad críticos",
             "steps": ["Realizar una acción de seguridad (inicio de sesión fallido, cambio de contraseña).",
                       "Verificar que el evento queda registrado en el log de auditoría."],
             "expected": "El log contiene: fecha/hora, usuario, acción, resultado y dirección IP."},
        ]

    @staticmethod
    def _a10_cases() -> list[dict]:
        return [
            {"name": "SSRF — URL externa controlada por el usuario",
             "steps": ["Ingresar en el campo de URL: http://169.254.169.254/latest/meta-data/",
                       "Enviar la solicitud.",
                       "Verificar que el sistema no realiza la solicitud a la URL interna."],
             "expected": "El sistema valida y rechaza URLs que apunten a recursos internos o privados."},
        ]
