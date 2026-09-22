"""
case_builder.py — Motor de construcción de casos con 3 dimensiones:
  Funcionalidad → Validación → Excepción/Alerta

Soporta dos formas de organización:
  Forma 1 — Por bloques: todos los F, luego todos los V, luego todos los E
  Forma 2 — Por caso completo: cada elemento agota F+V+E antes del siguiente

Cubre todos los tipos de elementos aprendidos:
  - Campos: numérico, alfanumérico, caracteres especiales, texto libre
  - Fechas: formato, rango, fecha inicial/final, 29-feb
  - Botones: funcionalidad, doble clic, deshabilitado, cancelar
  - Menús de navegación: acceso por rol, pantalla correcta
  - Listas desplegables: selección, vacía, dependencia entre listas
  - Checkbox y Radio Button: selección, exclusividad, obligatorio
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------- señales
_NUMERIC_FIELD   = re.compile(r"\b(monto|valor|cantidad|n[uú]mero|precio|importe|edad|c[oó]digo num[eé]rico|entero|decimal)\b", re.I)
_ALPHA_FIELD     = re.compile(r"\b(nombre|descripci[oó]n|texto|comentario|observaci[oó]n|alfanum[eé]rico)\b", re.I)
_EMAIL_FIELD     = re.compile(r"\b(correo|email|e-mail|direcci[oó]n de correo)\b", re.I)
_DATE_FIELD      = re.compile(r"\b(fecha|date|d[ií]a|mes|a[ñn]o|periodo|vigencia)\b", re.I)
_DATE_RANGE      = re.compile(r"\b(fecha inicial|fecha de inicio|fecha final|fecha fin|fecha desde|fecha hasta|rango de fecha)\b", re.I)
_BUTTON          = re.compile(r"\b(bot[oó]n|button|guardar|enviar|confirmar|cancelar|eliminar|buscar|limpiar|aceptar)\b", re.I)
_MENU            = re.compile(r"\b(men[uú]|navegaci[oó]n|opci[oó]n de men[uú]|submenu|barra de navegaci[oó]n)\b", re.I)
_DROPDOWN        = re.compile(r"\b(lista desplegable|dropdown|selector|combo|selecci[oó]n|seleccionar)\b", re.I)
_CHECKBOX        = re.compile(r"\b(checkbox|check box|casilla|marcaci[oó]n|marcar|check)\b", re.I)
_RADIO           = re.compile(r"\b(radio button|radio|opci[oó]n [uú]nica|selecci[oó]n [uú]nica)\b", re.I)
_PASSWORD        = re.compile(r"\b(contrase[ñn]a|password|clave|pin)\b", re.I)
_SPECIAL_CHARS   = re.compile(r"\b(caracter especial|caracteres especiales|s[ií]mbolo|@|#|\$|%)\b", re.I)


# ---------------------------------------------------------------- estructura
@dataclass
class CaseBlock:
    """Un bloque de casos para una regla: Funcionalidad + Validación + Excepción."""
    rule_id:       str
    funcionalidad: list[dict] = field(default_factory=list)
    validacion:    list[dict] = field(default_factory=list)
    excepcion:     list[dict] = field(default_factory=list)

    def all_by_dimension(self) -> list[dict]:
        """Forma 1: todos F, luego todos V, luego todos E."""
        return self.funcionalidad + self.validacion + self.excepcion

    def all_interleaved(self) -> list[dict]:
        """Forma 2: F+V+E por caso completo."""
        result = []
        max_len = max(len(self.funcionalidad), len(self.validacion), len(self.excepcion), 1)
        for i in range(max_len):
            if i < len(self.funcionalidad): result.append(self.funcionalidad[i])
            if i < len(self.validacion):    result.append(self.validacion[i])
            if i < len(self.excepcion):     result.append(self.excepcion[i])
        return result


# ---------------------------------------------------------------- builder principal
class CaseBuilder:

    def __init__(self, org_mode: int = 2, detail_level: int = 3):
        """
        org_mode:    1 = por bloques, 2 = por caso completo
        detail_level:1 = solo F, 2 = F+V, 3 = F+V+E
        """
        self.org_mode    = org_mode
        self.detail_level= detail_level

    def build(
        self,
        rule_id:     str,
        text:        str,
        td,          # TechniqueDecision
        cl,          # Classification
        pw_gen,      # PairwiseGenerator
        priority:    str,
        level_label: str,
        type_label:  str,
        risk_level:  str,
        case_counter: list,  # [int] mutable counter
    ) -> list[dict]:
        """
        Construye los casos de una regla con las 3 dimensiones
        y los organiza según org_mode.
        """
        block = CaseBlock(rule_id=rule_id)

        # Detectar tipo de elemento
        element_type = self._detect_element(text)

        # Construir según técnica principal
        if td.primary_technique == "BVA":
            self._build_bva(block, rule_id, text, td, pw_gen,
                            priority, level_label, type_label, risk_level, case_counter)
        elif td.primary_technique == "Transicion_Estados":
            self._build_transitions(block, rule_id, td,
                                    priority, level_label, type_label, risk_level, case_counter)
        elif td.primary_technique in ("Tabla_Decision", "Pairwise"):
            self._build_decision(block, rule_id, text, td, pw_gen,
                                 priority, level_label, type_label, risk_level, case_counter)
        elif td.primary_technique == "Casos_Uso_Integracion":
            self._build_integration(block, rule_id, text, td,
                                    priority, level_label, type_label, risk_level, case_counter)
        else:
            self._build_partition(block, rule_id, text, element_type,
                                  priority, level_label, type_label, risk_level, case_counter)

        # Agregar validaciones por tipo de elemento
        if self.detail_level >= 2:
            self._add_field_validations(block, rule_id, text, element_type,
                                        level_label, type_label, risk_level, case_counter)

        # Agregar excepciones/alertas
        if self.detail_level >= 3:
            self._add_exceptions(block, rule_id, text, element_type,
                                 level_label, type_label, risk_level, case_counter)

        # Organizar según forma elegida
        if self.org_mode == 1:
            return block.all_by_dimension()
        else:
            return block.all_interleaved()

    # ─────────────────────────── detección de elemento
    @staticmethod
    def _detect_element(text: str) -> str:
        if _DATE_RANGE.search(text):   return "date_range"
        if _DATE_FIELD.search(text):   return "date"
        if _EMAIL_FIELD.search(text):  return "email"
        if _PASSWORD.search(text):     return "password"
        if _NUMERIC_FIELD.search(text):return "numeric"
        if _ALPHA_FIELD.search(text):  return "alpha"
        if _BUTTON.search(text):       return "button"
        if _MENU.search(text):         return "menu"
        if _DROPDOWN.search(text):     return "dropdown"
        if _CHECKBOX.search(text):     return "checkbox"
        if _RADIO.search(text):        return "radio"
        return "generic"

    # ─────────────────────────── helpers
    def _tc(self, case_counter: list, rule_id: str, dimension: str,
            name: str, objective: str, precondition: str,
            steps: list[str], test_data: str, expected_result: str,
            priority: str, level_label: str, type_label: str,
            risk_level: str, technique: str,
            estimated_min: int = 10) -> dict:
        case_counter[0] += 1
        return {
            "id":               f"TC-{case_counter[0]:04d}",
            "name":             name,
            "dimension":        dimension,
            "objective":        objective,
            "precondition":     precondition,
            "steps":            steps,
            "test_data":        test_data,
            "expected_result":  expected_result,
            "priority":         priority,
            "level":            level_label,
            "type":             type_label,
            "technique":        technique,
            "requirement_ref":  rule_id,
            "risk":             risk_level,
            "automation_label": "",
            "estimated_min":    estimated_min,
        }

    # ─────────────────────────── BVA
    def _build_bva(self, block, rule_id, text, td, pw_gen,
                   priority, level_label, type_label, risk_level, counter):
        for rng in td.bva_ranges:
            bva_cases = pw_gen.bva_cases(rng["min"], rng["max"], prefix=f"{rule_id}-BVA")
            for bc in bva_cases:
                dim = "Funcionalidad" if bc["valid"] else "Validacion"
                tc  = self._tc(
                    counter, rule_id, dim,
                    name=f"[BVA-{dim}] {rule_id} — {bc['label']}",
                    objective=f"Verificar que el sistema {'acepta' if bc['valid'] else 'rechaza'} "
                              f"el valor {bc['value']} ({bc['label']}) para {rule_id}.",
                    precondition=f"El usuario tiene acceso al campo o formulario de {rule_id}.",
                    steps=[
                        f"Ingresar el valor {bc['value']} en el campo correspondiente.",
                        "Confirmar o enviar la operación.",
                        "Verificar el resultado del sistema.",
                    ],
                    test_data=f"Valor: {bc['value']} | Tipo: {bc['label']}",
                    expected_result=(
                        f"El sistema acepta el valor y procesa la operación correctamente."
                        if bc["valid"] else
                        f"El sistema rechaza el valor y muestra un mensaje de alerta "
                        f"indicando que el valor está fuera del rango permitido."
                    ),
                    priority=priority, level_label=level_label,
                    type_label=type_label, risk_level=risk_level,
                    technique="BVA", estimated_min=5,
                )
                if bc["valid"]:
                    block.funcionalidad.append(tc)
                else:
                    block.validacion.append(tc)

    # ─────────────────────────── Transición de Estados
    def _build_transitions(self, block, rule_id, td,
                           priority, level_label, type_label, risk_level, counter):
        from core.pairwise_generator import PairwiseGenerator
        trans = PairwiseGenerator.state_transition_cases(td.states_detected, prefix=f"{rule_id}-TE")
        for t in trans:
            dim = "Funcionalidad" if t["valid"] else "Validacion"
            tc  = self._tc(
                counter, rule_id, dim,
                name=f"[Transición-{dim}] {rule_id} — {t['label']}",
                objective=f"Verificar la transición de estado: {t['from']} → {t['to']}.",
                precondition=f"El registro de {rule_id} se encuentra en estado '{t['from']}'.",
                steps=[
                    f"Localizar el registro en estado '{t['from']}'.",
                    f"Ejecutar la acción que lleva al estado '{t['to']}'.",
                    "Verificar el nuevo estado en el sistema.",
                ],
                test_data=f"Estado inicial: {t['from']} | Estado destino: {t['to']}",
                expected_result=(
                    f"El estado cambia correctamente a '{t['to']}'."
                    if t["valid"] else
                    f"El sistema rechaza la transición y mantiene el estado '{t['from']}'. "
                    f"Se muestra un mensaje de alerta indicando que la acción no es permitida."
                ),
                priority=priority, level_label=level_label,
                type_label=type_label, risk_level=risk_level,
                technique="Transicion_Estados", estimated_min=10,
            )
            if t["valid"]:
                block.funcionalidad.append(tc)
            else:
                block.validacion.append(tc)

    # ─────────────────────────── Tabla de Decisión / Pairwise
    def _build_decision(self, block, rule_id, text, td, pw_gen,
                        priority, level_label, type_label, risk_level, counter):
        scenarios = [
            ("Funcionalidad", "Todas las condiciones se cumplen",
             ["Sí"] * min(len(td.conditions), 4), True),
            ("Validacion",    "Condición principal no se cumple",
             ["No"] + ["Sí"] * max(0, min(len(td.conditions), 4) - 1), False),
        ]
        for dim, label, cond_vals, valid in scenarios:
            cond_str = " | ".join(
                f"{c.strip()[:30]}: {v}"
                for c, v in zip(td.conditions[:4], cond_vals)
            )
            tc = self._tc(
                counter, rule_id, dim,
                name=f"[Decisión-{dim}] {rule_id} — {label}",
                objective=f"Verificar el resultado de {rule_id} cuando {label.lower()}.",
                precondition=f"Las condiciones del formulario o proceso de {rule_id} están configuradas.",
                steps=[
                    f"Configurar las condiciones: {cond_str}.",
                    "Ejecutar la operación correspondiente.",
                    "Verificar el resultado obtenido en el sistema.",
                ],
                test_data=cond_str,
                expected_result=(
                    f"El sistema ejecuta la acción principal de {rule_id} correctamente."
                    if valid else
                    f"El sistema no ejecuta la acción principal y muestra un mensaje de alerta "
                    f"indicando que las condiciones requeridas no se cumplen."
                ),
                priority=priority, level_label=level_label,
                type_label=type_label, risk_level=risk_level,
                technique=td.primary_technique, estimated_min=15,
            )
            if valid:
                block.funcionalidad.append(tc)
            else:
                block.validacion.append(tc)

    # ─────────────────────────── Integración
    def _build_integration(self, block, rule_id, text, td,
                           priority, level_label, type_label, risk_level, counter):
        for dim, scenario, expected, prio in [
            ("Funcionalidad",
             "Servicio externo responde correctamente",
             f"El sistema integra correctamente con el servicio externo y completa la operación de {rule_id}.",
             priority),
            ("Validacion",
             "Servicio externo no disponible o con timeout",
             f"El sistema detecta la falla, muestra un mensaje de alerta al usuario y "
             f"no deja la operación en estado inconsistente.",
             "ALTA"),
        ]:
            tc = self._tc(
                counter, rule_id, dim,
                name=f"[Integración-{dim}] {rule_id} — {scenario}",
                objective=f"Verificar el comportamiento de {rule_id} cuando: {scenario}.",
                precondition=f"Servicio externo configurado en el ambiente de prueba.",
                steps=[
                    "Configurar el ambiente con el escenario indicado.",
                    f"Ejecutar la operación de {rule_id} que involucra el servicio externo.",
                    "Verificar la respuesta del sistema.",
                ],
                test_data=scenario,
                expected_result=expected,
                priority=prio, level_label=level_label,
                type_label=type_label, risk_level=risk_level,
                technique="Casos_Uso_Integracion", estimated_min=20,
            )
            if dim == "Funcionalidad":
                block.funcionalidad.append(tc)
            else:
                block.validacion.append(tc)

    # ─────────────────────────── Partición de Equivalencia (default)
    def _build_partition(self, block, rule_id, text, element_type,
                         priority, level_label, type_label, risk_level, counter):
        # Funcionalidad positiva
        block.funcionalidad.append(self._tc(
            counter, rule_id, "Funcionalidad",
            name=f"[Funcionalidad] {rule_id} — Datos válidos — flujo exitoso",
            objective=f"Verificar que el sistema procesa correctamente {rule_id} con datos válidos.",
            precondition=f"El usuario tiene acceso a la funcionalidad de {rule_id}.",
            steps=[
                f"Ingresar datos válidos en todos los campos de {rule_id}.",
                "Confirmar la operación.",
                "Verificar el resultado del sistema.",
            ],
            test_data="Clase de equivalencia válida — datos correctos y completos.",
            expected_result=f"El sistema procesa la operación de {rule_id} correctamente y confirma el resultado al usuario.",
            priority=priority, level_label=level_label,
            type_label=type_label, risk_level=risk_level,
            technique="Particion_Equivalencia", estimated_min=10,
        ))
        # Validación negativa
        block.validacion.append(self._tc(
            counter, rule_id, "Validacion",
            name=f"[Validacion] {rule_id} — Datos inválidos — flujo negativo",
            objective=f"Verificar que el sistema rechaza correctamente {rule_id} con datos inválidos.",
            precondition=f"El usuario tiene acceso a la funcionalidad de {rule_id}.",
            steps=[
                f"Ingresar datos inválidos en los campos de {rule_id}.",
                "Intentar confirmar la operación.",
                "Verificar el comportamiento del sistema.",
            ],
            test_data="Clase de equivalencia inválida — datos incorrectos o incompletos.",
            expected_result=f"El sistema rechaza la operación y muestra un mensaje de alerta indicando los datos ingresados no son correctos.",
            priority="MEDIA", level_label=level_label,
            type_label=type_label, risk_level=risk_level,
            technique="Particion_Equivalencia", estimated_min=10,
        ))

    # ─────────────────────────── Validaciones por tipo de elemento
    def _add_field_validations(self, block, rule_id, text, element_type,
                               level_label, type_label, risk_level, counter):
        priority = "MEDIA"

        # ---- Campo numérico
        if element_type == "numeric":
            for name, data, expected in [
                ("Letras en campo numérico",
                 "Valor: texto alfabético (ej. 'abc')",
                 "El sistema rechaza la entrada y muestra un mensaje de alerta indicando que el campo solo acepta valores numéricos."),
                ("Caracteres especiales en campo numérico",
                 "Valor: caracteres especiales (ej. '@#$')",
                 "El sistema rechaza la entrada y muestra un mensaje de alerta indicando que el campo solo acepta valores numéricos."),
                ("Valor cero en campo numérico",
                 "Valor: 0",
                 "El sistema muestra un mensaje de alerta indicando que el valor no puede ser cero, si así lo define la regla de negocio."),
                ("Valor negativo en campo numérico",
                 "Valor: -1",
                 "El sistema rechaza el valor negativo y muestra un mensaje de alerta indicando que el valor debe ser mayor a cero."),
                ("Separador de miles incorrecto",
                 "Valor: 1.000 vs 1,000 (según formato del sistema)",
                 "El sistema interpreta correctamente el separador de miles o muestra alerta de formato incorrecto."),
            ]:
                block.validacion.append(self._tc(
                    counter, rule_id, "Validacion",
                    name=f"[Validacion-Numerico] {rule_id} — {name}",
                    objective=f"Validar el comportamiento del campo numérico de {rule_id} ante: {name.lower()}.",
                    precondition=f"El usuario tiene acceso al campo numérico de {rule_id}.",
                    steps=["Ingresar en el campo numérico el valor indicado en los datos de prueba.",
                           "Intentar continuar o enviar el formulario.",
                           "Verificar el comportamiento del sistema."],
                    test_data=data, expected_result=expected,
                    priority=priority, level_label=level_label,
                    type_label=type_label, risk_level=risk_level,
                    technique="Particion_Equivalencia", estimated_min=5,
                ))

        # ---- Campo alfanumérico
        elif element_type == "alpha":
            for name, data, expected in [
                ("Solo números en campo de texto",
                 "Valor: solo dígitos (ej. '12345')",
                 "El sistema acepta o rechaza según la regla de negocio del campo."),
                ("Caracteres especiales no permitidos",
                 "Valor: '<script>alert(1)</script>'",
                 "El sistema rechaza los caracteres especiales y muestra un mensaje de alerta indicando que el campo no los acepta."),
                ("Longitud máxima superada",
                 "Valor: texto con N+1 caracteres (superando el límite)",
                 "El sistema no permite ingresar el carácter adicional o muestra un mensaje de alerta indicando el límite máximo."),
                ("Solo espacios en blanco",
                 "Valor: '     ' (solo espacios)",
                 "El sistema rechaza el valor como campo vacío y muestra mensaje de campo obligatorio."),
            ]:
                block.validacion.append(self._tc(
                    counter, rule_id, "Validacion",
                    name=f"[Validacion-Texto] {rule_id} — {name}",
                    objective=f"Validar el comportamiento del campo de texto de {rule_id} ante: {name.lower()}.",
                    precondition=f"El usuario tiene acceso al campo de texto de {rule_id}.",
                    steps=["Ingresar en el campo de texto el valor indicado.",
                           "Intentar continuar o enviar el formulario.",
                           "Verificar el comportamiento del sistema."],
                    test_data=data, expected_result=expected,
                    priority=priority, level_label=level_label,
                    type_label=type_label, risk_level=risk_level,
                    technique="Particion_Equivalencia", estimated_min=5,
                ))

        # ---- Email
        elif element_type == "email":
            for name, data, valid in [
                ("Formato de correo válido",           "correo@dominio.com",       True),
                ("Sin arroba",                         "correodominio.com",         False),
                ("Sin dominio",                        "correo@",                   False),
                ("Sin extensión de dominio",           "correo@dominio",            False),
                ("Con espacios",                       "cor reo@dominio.com",       False),
                ("Con caracteres especiales inválidos","correo#@dominio.com",       False),
            ]:
                block.validacion.append(self._tc(
                    counter, rule_id, "Validacion",
                    name=f"[Validacion-Email] {rule_id} — {name}",
                    objective=f"Validar la estructura del correo electrónico en {rule_id}: {name.lower()}.",
                    precondition=f"El usuario tiene acceso al campo de correo de {rule_id}.",
                    steps=["Ingresar en el campo de correo el valor indicado.",
                           "Intentar continuar o enviar el formulario.",
                           "Verificar el comportamiento del sistema."],
                    test_data=f"Correo: {data}",
                    expected_result=(
                        "El sistema acepta el formato y continúa con la validación de credenciales."
                        if valid else
                        "El sistema rechaza el formato y muestra un mensaje de alerta indicando que el correo electrónico no tiene un formato válido."
                    ),
                    priority=priority, level_label=level_label,
                    type_label=type_label, risk_level=risk_level,
                    technique="Particion_Equivalencia", estimated_min=5,
                ))

        # ---- Fecha simple
        elif element_type == "date":
            for name, data, valid in [
                ("Fecha válida en formato correcto",      "15/06/2025 (DD/MM/YYYY)",               True),
                ("Formato de fecha incorrecto",           "06-15-2025 (MM-DD-YYYY)",               False),
                ("Fecha con texto en lugar de números",   "'quince de junio'",                     False),
                ("29 de febrero en año no bisiesto",      "29/02/2023",                            False),
                ("29 de febrero en año bisiesto",         "29/02/2024",                            True),
                ("Fecha muy antigua fuera del rango",     "01/01/1800",                            False),
                ("Fecha muy futura fuera del rango",      "01/01/2999",                            False),
                ("Campo de fecha vacío",                  "Campo vacío (sin fecha ingresada)",     False),
            ]:
                block.validacion.append(self._tc(
                    counter, rule_id, "Validacion",
                    name=f"[Validacion-Fecha] {rule_id} — {name}",
                    objective=f"Validar el comportamiento del campo de fecha de {rule_id}: {name.lower()}.",
                    precondition=f"El usuario tiene acceso al campo de fecha de {rule_id}.",
                    steps=["Ingresar en el campo de fecha el valor indicado.",
                           "Intentar continuar o enviar el formulario.",
                           "Verificar el comportamiento del sistema."],
                    test_data=f"Fecha: {data}",
                    expected_result=(
                        "El sistema acepta la fecha y continúa con el proceso."
                        if valid else
                        "El sistema rechaza la fecha y muestra un mensaje de alerta indicando que la fecha ingresada no es válida."
                    ),
                    priority=priority, level_label=level_label,
                    type_label=type_label, risk_level=risk_level,
                    technique="BVA", estimated_min=5,
                ))

        # ---- Rango de fechas (inicial / final)
        elif element_type == "date_range":
            for name, data, valid in [
                ("Fecha final mayor que fecha inicial",      "Inicio: 01/01/2025 | Fin: 31/12/2025",  True),
                ("Fecha final igual que fecha inicial",      "Inicio: 15/06/2025 | Fin: 15/06/2025",  None),  # depende del BRD
                ("Fecha final menor que fecha inicial",      "Inicio: 31/12/2025 | Fin: 01/01/2025",  False),
                ("Fecha inicial mayor que fecha final",      "Inicio: 01/12/2025 | Fin: 01/01/2025",  False),
                ("Fecha inicial vacía con fecha final llena","Inicio: vacío | Fin: 31/12/2025",        False),
                ("Fecha final vacía con fecha inicial llena","Inicio: 01/01/2025 | Fin: vacío",        False),
                ("Ambas fechas vacías",                      "Inicio: vacío | Fin: vacío",             False),
            ]:
                expected = (
                    "El sistema acepta el rango de fechas y continúa con el proceso."
                    if valid is True else
                    "El sistema rechaza el rango y muestra un mensaje de alerta indicando que la fecha final no puede ser menor a la fecha inicial."
                    if valid is False else
                    "El sistema acepta o rechaza según lo definido en la regla de negocio para fechas iguales."
                )
                block.validacion.append(self._tc(
                    counter, rule_id, "Validacion",
                    name=f"[Validacion-RangoFecha] {rule_id} — {name}",
                    objective=f"Validar el comportamiento del rango de fechas de {rule_id}: {name.lower()}.",
                    precondition=f"El usuario tiene acceso a los campos de fecha inicial y final de {rule_id}.",
                    steps=["Ingresar los valores de fecha inicial y final indicados.",
                           "Intentar continuar o enviar el formulario.",
                           "Verificar el comportamiento del sistema."],
                    test_data=data, expected_result=expected,
                    priority=priority, level_label=level_label,
                    type_label=type_label, risk_level=risk_level,
                    technique="BVA", estimated_min=8,
                ))

        # ---- Botón
        elif element_type == "button":
            for name, data, expected in [
                ("Clic con formulario diligenciado correctamente",
                 "Todos los campos con datos válidos",
                 "El botón ejecuta la acción esperada y el sistema confirma el resultado."),
                ("Clic sin diligenciar campos obligatorios",
                 "Campos obligatorios vacíos",
                 "El sistema no ejecuta la acción y muestra mensaje de alerta indicando los campos obligatorios pendientes."),
                ("Doble clic rápido en el botón",
                 "Doble clic en menos de 1 segundo",
                 "El sistema procesa la acción una sola vez. No genera duplicados ni errores."),
                ("Botón cancelar con datos sin guardar",
                 "Formulario con datos ingresados sin guardar",
                 "El sistema muestra un mensaje de confirmación preguntando si desea cancelar y perder los cambios."),
            ]:
                block.validacion.append(self._tc(
                    counter, rule_id, "Validacion",
                    name=f"[Validacion-Boton] {rule_id} — {name}",
                    objective=f"Validar el comportamiento del botón de {rule_id}: {name.lower()}.",
                    precondition=f"El usuario tiene acceso al botón de {rule_id}.",
                    steps=["Configurar el escenario indicado en los datos de prueba.",
                           "Ejecutar la acción sobre el botón.",
                           "Verificar el comportamiento del sistema."],
                    test_data=data, expected_result=expected,
                    priority=priority, level_label=level_label,
                    type_label=type_label, risk_level=risk_level,
                    technique="Error_Guessing", estimated_min=5,
                ))

        # ---- Lista desplegable
        elif element_type == "dropdown":
            for name, data, expected in [
                ("Selección válida de la lista",
                 "Opción válida seleccionada de la lista",
                 "El sistema registra la selección y continúa el proceso."),
                ("Envío sin seleccionar ninguna opción",
                 "Campo de lista sin selección (en blanco)",
                 "El sistema muestra un mensaje de alerta indicando que debe seleccionar una opción."),
                ("Lista dependiente sin seleccionar el padre primero",
                 "Lista hija activa sin haber seleccionado la lista padre",
                 "El sistema muestra un mensaje de alerta indicando que debe seleccionar primero la opción del nivel superior."),
            ]:
                block.validacion.append(self._tc(
                    counter, rule_id, "Validacion",
                    name=f"[Validacion-Lista] {rule_id} — {name}",
                    objective=f"Validar el comportamiento de la lista desplegable de {rule_id}: {name.lower()}.",
                    precondition=f"El usuario tiene acceso a la lista desplegable de {rule_id}.",
                    steps=["Configurar el escenario indicado.",
                           "Interactuar con la lista desplegable.",
                           "Verificar el comportamiento del sistema."],
                    test_data=data, expected_result=expected,
                    priority=priority, level_label=level_label,
                    type_label=type_label, risk_level=risk_level,
                    technique="Particion_Equivalencia", estimated_min=5,
                ))

        # ---- Checkbox
        elif element_type == "checkbox":
            for name, data, expected in [
                ("Marcar una opción válida",
                 "Checkbox marcado con una opción",
                 "El sistema registra la selección correctamente."),
                ("Envío sin marcar ninguna opción obligatoria",
                 "Ningún checkbox marcado",
                 "El sistema muestra un mensaje de alerta indicando que debe seleccionar al menos una opción."),
                ("Desmarcar la única opción obligatoria marcada",
                 "Se desmarca la única opción previamente seleccionada",
                 "El sistema muestra un mensaje de alerta indicando que debe mantener al menos una opción seleccionada."),
            ]:
                block.validacion.append(self._tc(
                    counter, rule_id, "Validacion",
                    name=f"[Validacion-Checkbox] {rule_id} — {name}",
                    objective=f"Validar el comportamiento del checkbox de {rule_id}: {name.lower()}.",
                    precondition=f"El usuario tiene acceso al checkbox de {rule_id}.",
                    steps=["Configurar el escenario indicado.",
                           "Interactuar con el checkbox.",
                           "Verificar el comportamiento del sistema."],
                    test_data=data, expected_result=expected,
                    priority=priority, level_label=level_label,
                    type_label=type_label, risk_level=risk_level,
                    technique="Particion_Equivalencia", estimated_min=5,
                ))

        # ---- Radio Button
        elif element_type == "radio":
            for name, data, expected in [
                ("Selección de una opción válida",
                 "Radio button seleccionado",
                 "El sistema registra la selección y deselecciona cualquier opción anterior."),
                ("Envío sin seleccionar ninguna opción",
                 "Ningún radio button seleccionado",
                 "El sistema muestra un mensaje de alerta indicando que debe seleccionar una opción."),
                ("Cambio de selección entre opciones",
                 "Se selecciona opción B habiendo seleccionado opción A previamente",
                 "El sistema deselecciona la opción A y selecciona la opción B correctamente."),
            ]:
                block.validacion.append(self._tc(
                    counter, rule_id, "Validacion",
                    name=f"[Validacion-RadioButton] {rule_id} — {name}",
                    objective=f"Validar el comportamiento del radio button de {rule_id}: {name.lower()}.",
                    precondition=f"El usuario tiene acceso al radio button de {rule_id}.",
                    steps=["Configurar el escenario indicado.",
                           "Interactuar con el radio button.",
                           "Verificar el comportamiento del sistema."],
                    test_data=data, expected_result=expected,
                    priority=priority, level_label=level_label,
                    type_label=type_label, risk_level=risk_level,
                    technique="Particion_Equivalencia", estimated_min=5,
                ))

    # ─────────────────────────── Excepciones / Alertas
    def _add_exceptions(self, block, rule_id, text, element_type,
                        level_label, type_label, risk_level, counter):
        priority = "MEDIA"

        # Excepciones universales siempre presentes
        universal = [
            ("Campo obligatorio vacío al enviar",
             "Todos los campos obligatorios de {rid} vacíos al momento del envío.",
             "El sistema muestra un mensaje de alerta indicando que los datos ingresados no son correctos o que los campos son obligatorios."),
            ("Sesión expirada durante el diligenciamiento",
             "La sesión del usuario expira mientras diligencia el formulario de {rid}.",
             "El sistema muestra un mensaje de alerta indicando que la sesión ha expirado y redirige al inicio de sesión sin perder el contexto si es posible."),
            ("Doble envío del formulario",
             "El usuario hace clic dos veces rápidamente en el botón de envío de {rid}.",
             "El sistema procesa la solicitud una sola vez. No genera registros duplicados ni errores."),
        ]

        # Excepciones específicas por tipo de elemento
        specific = {
            "numeric": [
                ("Valor numérico correcto pero usuario incorrecto",
                 "Campo numérico: valor correcto | Usuario que ingresa: sin permisos",
                 "El sistema muestra un mensaje de alerta indicando que los datos ingresados no son correctos o que no tiene permisos."),
            ],
            "email": [
                ("Correo correcto pero contraseña incorrecta",
                 "Correo: correcto y registrado | Contraseña: incorrecta",
                 "El sistema muestra un mensaje de alerta indicando que los datos ingresados no son correctos. No especifica cuál campo falló."),
                ("Correo incorrecto pero contraseña correcta",
                 "Correo: no registrado | Contraseña: correcta",
                 "El sistema muestra un mensaje de alerta indicando que los datos ingresados no son correctos. No especifica cuál campo falló."),
                ("Correo vacío con contraseña diligenciada",
                 "Correo: vacío | Contraseña: con valor",
                 "El sistema muestra un mensaje de alerta indicando que los datos ingresados no son correctos."),
                ("Correo diligenciado con contraseña vacía",
                 "Correo: con valor | Contraseña: vacía",
                 "El sistema muestra un mensaje de alerta indicando que los datos ingresados no son correctos."),
            ],
            "date": [
                ("Fecha fuera del rango histórico permitido",
                 "Fecha ingresada anterior al límite histórico del sistema.",
                 "El sistema muestra un mensaje de alerta indicando que la fecha ingresada está fuera del rango permitido."),
                ("Formato de fecha no reconocido",
                 "Fecha en formato de texto libre (ej. 'hoy', 'mañana').",
                 "El sistema muestra un mensaje de alerta indicando que el formato de fecha no es válido."),
            ],
            "date_range": [
                ("Fecha final menor a la fecha inicial",
                 "Fecha inicial: 31/12/2025 | Fecha final: 01/01/2025",
                 "El sistema muestra un mensaje de alerta indicando que la fecha final no puede ser menor a la fecha inicial."),
                ("Fecha inicial mayor a la fecha final",
                 "Fecha inicial: 01/12/2025 | Fecha final: 01/01/2025",
                 "El sistema muestra un mensaje de alerta indicando que la fecha inicial no puede ser mayor a la fecha final."),
            ],
            "button": [
                ("Clic en botón sin completar campos obligatorios",
                 "Formulario con campos obligatorios vacíos.",
                 "El sistema muestra un mensaje de alerta indicando que debe completar los campos obligatorios antes de continuar."),
            ],
            "dropdown": [
                ("Lista desplegable sin opciones disponibles",
                 "La lista desplegable se carga vacía (sin opciones).",
                 "El sistema muestra un mensaje de alerta indicando que no hay opciones disponibles para seleccionar."),
            ],
        }

        all_exceptions = universal + specific.get(element_type, [])

        for name, data, expected in all_exceptions:
            data_fmt     = data.replace("{rid}", rule_id)
            block.excepcion.append(self._tc(
                counter, rule_id, "Excepcion",
                name=f"[Excepcion] {rule_id} — {name}",
                objective=f"Verificar el manejo de excepción y mensaje de alerta en {rule_id}: {name.lower()}.",
                precondition=f"El usuario tiene acceso a la funcionalidad de {rule_id}.",
                steps=[
                    "Configurar el escenario indicado en los datos de prueba.",
                    "Ejecutar la acción correspondiente.",
                    "Verificar el mensaje de alerta o comportamiento del sistema.",
                ],
                test_data=data_fmt,
                expected_result=expected,
                priority=priority, level_label=level_label,
                type_label=type_label, risk_level=risk_level,
                technique="Error_Guessing", estimated_min=5,
            ))
