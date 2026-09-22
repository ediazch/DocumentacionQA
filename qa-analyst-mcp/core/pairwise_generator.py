"""
pairwise_generator.py — Algoritmo greedy 2-way (pairwise) con validación programática.

Garantiza que el 100% de las parejas (parámetro_i × valor_i, parámetro_j × valor_j)
estén cubiertas. Verificación al final: si quedan pares sin cubrir, agrega casos extra.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PairwiseResult:
    test_cases:       list[dict[str, Any]]
    uncovered_pairs:  int
    total_pairs:      int
    coverage_pct:     float
    validation_passed:bool


class PairwiseGenerator:
    """
    Genera casos de prueba con cobertura 2-way (pairwise / OATS).
    Entrada: parameters = {"nombre_param": ["v1", "v2", ...], ...}
    """

    def generate(self, parameters: dict[str, list[Any]], prefix: str = "PW") -> PairwiseResult:
        param_names  = list(parameters.keys())
        param_values = [parameters[p] for p in param_names]
        n_params     = len(param_names)

        if n_params < 2:
            cases = []
            for i, v in enumerate(param_values[0] if param_values else []):
                cases.append({"id": f"{prefix}-{i+1:03d}", "data": {param_names[0]: v}})
            return PairwiseResult(cases, 0, len(cases), 100.0, True)

        # Universo de pares: todas las combinaciones de 2 parámetros × sus valores
        all_pairs: set[tuple] = set()
        for i, j in itertools.combinations(range(n_params), 2):
            for vi in param_values[i]:
                for vj in param_values[j]:
                    all_pairs.add((i, vi, j, vj))

        total_pairs   = len(all_pairs)
        covered_pairs: set[tuple] = set()
        test_cases    = []
        uncovered     = set(all_pairs)
        case_num      = 1

        # Greedy: cada iteración construye un caso que cubre el máximo de pares nuevos
        while uncovered and case_num <= total_pairs + 10:
            case_data: dict[str, Any] = {}
            assigned_params: list[int] = []

            # Asignar parámetros uno a uno, eligiendo el valor que maximiza pares nuevos
            for _ in range(n_params):
                remaining = [p for p in range(n_params) if p not in assigned_params]
                if not remaining:
                    break

                best_param = remaining[0]
                best_val   = param_values[best_param][0]
                best_gain  = -1

                for p in remaining:
                    for v in param_values[p]:
                        gain = 0
                        for ap in assigned_params:
                            pi = min(p, ap)
                            pj = max(p, ap)
                            vi_v = v if pi == p else case_data[param_names[ap]]
                            vj_v = case_data[param_names[ap]] if pi == p else v
                            pair = (pi, vi_v, pj, vj_v)
                            if pair in uncovered:
                                gain += 1
                        # Si no hay asignados aún, contar pares futuros potenciales
                        if not assigned_params:
                            gain = sum(
                                1 for pair in uncovered
                                if pair[0] == p and pair[1] == v
                            )
                        if gain > best_gain:
                            best_gain  = gain
                            best_param = p
                            best_val   = v

                case_data[param_names[best_param]] = best_val
                assigned_params.append(best_param)

            # Completar parámetros no asignados con el primer valor disponible
            for p in range(n_params):
                if param_names[p] not in case_data:
                    # Elegir el valor que cubre más pares nuevos con los ya asignados
                    best_val  = param_values[p][0]
                    best_gain = -1
                    for v in param_values[p]:
                        gain = sum(
                            1 for ap in assigned_params
                            for pair in [
                                (min(p, ap), (v if min(p, ap) == p else case_data[param_names[ap]]),
                                 max(p, ap), (case_data[param_names[ap]] if min(p, ap) == p else v))
                            ]
                            if pair in uncovered
                        )
                        if gain > best_gain:
                            best_gain = gain
                            best_val  = v
                    case_data[param_names[p]] = best_val
                    assigned_params.append(p)

            # Registrar pares cubiertos
            new_pairs_covered = False
            for i, j in itertools.combinations(range(n_params), 2):
                vi = case_data[param_names[i]]
                vj = case_data[param_names[j]]
                pair = (i, vi, j, vj)
                if pair in uncovered:
                    uncovered.discard(pair)
                    covered_pairs.add(pair)
                    new_pairs_covered = True

            # Solo agregar el caso si cubre al menos 1 par nuevo
            if new_pairs_covered:
                test_cases.append({
                    "id":   f"{prefix}-{case_num:03d}",
                    "data": dict(case_data),
                })
                case_num += 1
            else:
                # Fuerza bruta: tomar el primer par sin cubrir y crear un caso mínimo
                if uncovered:
                    pair = next(iter(uncovered))
                    pi, vi_v, pj, vj_v = pair
                    extra = {param_names[k]: param_values[k][0] for k in range(n_params)}
                    extra[param_names[pi]] = vi_v
                    extra[param_names[pj]] = vj_v
                    # Cubrir todos los pares que este caso cubre
                    for i2, j2 in itertools.combinations(range(n_params), 2):
                        p2 = (i2, extra[param_names[i2]], j2, extra[param_names[j2]])
                        if p2 in uncovered:
                            uncovered.discard(p2)
                            covered_pairs.add(p2)
                    test_cases.append({"id": f"{prefix}-{case_num:03d}", "data": extra})
                    case_num += 1

        # Validación final: cubrir cualquier par restante
        for pair in list(all_pairs - covered_pairs):
            pi, vi_v, pj, vj_v = pair
            extra = {param_names[k]: param_values[k][0] for k in range(n_params)}
            extra[param_names[pi]] = vi_v
            extra[param_names[pj]] = vj_v
            for i2, j2 in itertools.combinations(range(n_params), 2):
                p2 = (i2, extra[param_names[i2]], j2, extra[param_names[j2]])
                covered_pairs.add(p2)
            test_cases.append({"id": f"{prefix}-{case_num:03d}", "data": extra, "extra": True})
            case_num += 1

        final_uncovered   = len(all_pairs - covered_pairs)
        coverage_pct      = (len(covered_pairs & all_pairs) / total_pairs * 100) if total_pairs else 100.0
        validation_passed = final_uncovered == 0

        return PairwiseResult(
            test_cases=test_cases,
            uncovered_pairs=final_uncovered,
            total_pairs=total_pairs,
            coverage_pct=coverage_pct,
            validation_passed=validation_passed,
        )


    @staticmethod
    def bva_cases(range_min: float, range_max: float, prefix: str = "BVA") -> list[dict]:
        """
        Genera los 7 casos canónicos de Valores Límite para un rango [min, max].
        Casos: min-1, min, min+1, nominal, max-1, max, max+1
        """
        nominal = round((range_min + range_max) / 2, 2)
        # Detectar si es entero o decimal
        is_int = (range_min == int(range_min)) and (range_max == int(range_max))
        step   = 1 if is_int else 0.01

        def fmt(v: float) -> str:
            return str(int(v)) if is_int else str(round(v, 4))

        cases = [
            {"id": f"{prefix}-1", "label": "min-1 (fuera de rango inferior)",  "value": fmt(range_min - step),  "valid": False},
            {"id": f"{prefix}-2", "label": "min (límite inferior válido)",      "value": fmt(range_min),         "valid": True},
            {"id": f"{prefix}-3", "label": "min+1 (justo dentro del mínimo)",   "value": fmt(range_min + step),  "valid": True},
            {"id": f"{prefix}-4", "label": "nominal (valor central válido)",    "value": fmt(nominal),           "valid": True},
            {"id": f"{prefix}-5", "label": "max-1 (justo dentro del máximo)",   "value": fmt(range_max - step),  "valid": True},
            {"id": f"{prefix}-6", "label": "max (límite superior válido)",      "value": fmt(range_max),         "valid": True},
            {"id": f"{prefix}-7", "label": "max+1 (fuera de rango superior)",   "value": fmt(range_max + step),  "valid": False},
        ]
        return cases

    @staticmethod
    def state_transition_cases(states: list[str], prefix: str = "TE") -> list[dict]:
        """
        Genera casos de transición de estados 0-switch:
        - Todas las transiciones válidas entre estados consecutivos
        - Transiciones inválidas críticas (saltar estados, retroceder)
        """
        cases = []
        n = len(states)
        case_num = 1

        # Válidas: transición lineal
        for i in range(n - 1):
            cases.append({
                "id":     f"{prefix}-{case_num:03d}",
                "label":  f"Transición válida: {states[i]} → {states[i+1]}",
                "from":   states[i],
                "to":     states[i+1],
                "valid":  True,
            })
            case_num += 1

        # Inválidas críticas: salto de estado y retroceso
        if n > 2:
            # Salto de 2 estados
            cases.append({
                "id":    f"{prefix}-{case_num:03d}",
                "label": f"Transición inválida: {states[0]} → {states[2]} (salto de estado)",
                "from":  states[0],
                "to":    states[2],
                "valid": False,
            })
            case_num += 1

        if n > 1:
            # Retroceso
            cases.append({
                "id":    f"{prefix}-{case_num:03d}",
                "label": f"Transición inválida: {states[-1]} → {states[0]} (retroceso al inicio)",
                "from":  states[-1],
                "to":    states[0],
                "valid": False,
            })
            case_num += 1

        return cases
