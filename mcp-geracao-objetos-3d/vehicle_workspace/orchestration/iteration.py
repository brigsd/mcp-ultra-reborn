"""Loop de iteracao automatica (fase 6).

Princípio: a correcao altera a SPEC (bloco `tuning`), nunca a malha. O
controlador le a comparacao de FORMA por regiao (fase 4) e ajusta deltas de
parametro do perfil. O loop gera -> compara -> ajusta -> repete ate o budget.

Para ficar testavel e desacoplado do Blender, `iterate()` recebe um callback
`generate_and_compare(spec) -> (report, compare_report)` que faz a parte pesada
(rodar Blender headless + comparar silhueta). O orquestrador MCP fornece o real.
"""

import copy

from vehicle_workspace.orchestration.budgets import Budget

# regiao da comparacao -> knob de tuning no perfil do deck
_REGION_TO_KNOB = {
    "front_overhang": "nose_delta",
    "hood_cowl": "hood_delta",
    "rear_deck": "rear_deck_delta",
    "rear_overhang": "tail_delta",
    # "cabin" NAO entra: protege o teto (altura travada no spec)
}


def propose_tuning(spec, compare_report, gain=0.45, clamp=0.22):
    """Le shape_regions (erro % vs blueprint, normalizado por altura) e devolve
    um novo dict de tuning. erro negativo = nosso mais baixo -> sobe o perfil."""
    tuning = dict(spec.get("tuning", {}) or {})
    for r in compare_report.get("shape_regions", []):
        knob = _REGION_TO_KNOB.get(r.get("region"))
        if not knob:
            continue
        err = r.get("shape_error_pct", 0.0) / 100.0  # <0 = baixo demais
        cur = tuning.get(knob, 0.0)
        new = cur - gain * err  # sobe onde esta baixo
        tuning[knob] = round(max(-clamp, min(clamp, new)), 4)
    return tuning


def _spec_with_tuning(spec, tuning):
    out = copy.deepcopy(spec)
    out.pop("_meters", None)  # sera recomputado no load_spec
    out["tuning"] = tuning
    return out


def iterate(spec, generate_and_compare, budget=None):
    """Roda o loop. generate_and_compare(spec) -> (report, compare_report).
    compare_report deve conter 'shape_area_iou' e 'shape_regions'."""
    budget = budget or Budget()
    history = []
    best = None
    current = copy.deepcopy(spec)

    for i in range(budget.max_iterations):
        report, comp = generate_and_compare(current)
        iou = float(comp.get("shape_area_iou", 0.0))
        step = {
            "iteration": i,
            "shape_area_iou": iou,
            "shape_mean_abs_error_pct": comp.get("shape_mean_abs_error_pct"),
            "tuning": dict(current.get("tuning", {}) or {}),
            "model_dir": (report or {}).get("paths", {}).get("output_dir"),
        }
        history.append(step)

        if best is None or iou > best["shape_area_iou"]:
            best = step

        # parada por sucesso
        if iou >= budget.target_shape_iou:
            step["stop_reason"] = "target_atingido"
            break
        # parada por plateau
        if i > 0 and (iou - history[-2]["shape_area_iou"]) < budget.min_improvement:
            step["stop_reason"] = "plateau"
            break
        # ultima iteracao do budget
        if i == budget.max_iterations - 1:
            step["stop_reason"] = "budget_esgotado"
            break

        # ajusta a SPEC (nao a malha) e segue
        new_tuning = propose_tuning(current, comp)
        current = _spec_with_tuning(current, new_tuning)

    return {
        "history": history,
        "best": best,
        "iterations": len(history),
        "final_tuning": dict(current.get("tuning", {}) or {}),
        "budget": budget.to_dict(),
    }
