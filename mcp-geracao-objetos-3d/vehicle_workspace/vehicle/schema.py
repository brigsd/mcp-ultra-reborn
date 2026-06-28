import copy
import json
from pathlib import Path

from .units import dimensions_mm_to_m, mm_to_m

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
ARCHETYPE_DIR = WORKSPACE_ROOT / "archetypes"


class VehicleSpecError(ValueError):
    pass


def _load_archetype(archetype):
    key = (archetype or "supercar").strip().lower()
    path = ARCHETYPE_DIR / f"{key}.json"
    if not path.exists():
        available = sorted(p.stem for p in ARCHETYPE_DIR.glob("*.json"))
        raise VehicleSpecError(f"Arquetipo '{archetype}' nao encontrado. Disponiveis: {available}")
    return json.loads(path.read_text(encoding="utf-8"))


def _deep_merge(base, override):
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _infer_archetype(prompt):
    text = (prompt or "").lower()
    if any(word in text for word in ["pickup", "caminhonete", "cacamba"]):
        return "pickup"
    if any(word in text for word in ["suv", "utilitario"]):
        return "suv"
    if any(word in text for word in ["van", "furgao"]):
        return "suv"
    return "supercar"


def _default_wheels(archetype_id, dimensions):
    if archetype_id == "supercar":
        return {
            "count": 4,
            "front_diameter": 720,
            "rear_diameter": 740,
            "front_rim": 20,
            "rear_rim": 21,
            "front_width": 265,
            "rear_width": 325,
        }
    if archetype_id == "pickup":
        return {
            "count": 4,
            "front_diameter": 820,
            "rear_diameter": 820,
            "front_rim": 18,
            "rear_rim": 18,
            "front_width": 275,
            "rear_width": 275,
        }
    return {
        "count": 4,
        "front_diameter": 760,
        "rear_diameter": 760,
        "front_rim": 19,
        "rear_rim": 19,
        "front_width": 245,
        "rear_width": 245,
    }


def _constraints_from_dimensions(dimensions):
    constraints = []
    for key in ["length", "width", "height", "wheelbase"]:
        constraints.append({
            "id": key,
            "type": "dimension",
            "target_mm": dimensions[key],
            "tolerance_mm": 15 if key != "wheelbase" else 8,
        })
    constraints.append({"id": "symmetry_y", "type": "symmetry", "max_error_mm": 2})
    constraints.append({"id": "wheel_clearance", "type": "clearance", "min_mm": 20})
    return constraints


def create_spec(prompt="", referencia_path="", medidas=None, overrides=None):
    medidas = medidas or {}
    overrides = overrides or {}
    archetype_id = overrides.get("archetype") or medidas.get("archetype") or _infer_archetype(prompt)
    archetype = _load_archetype(archetype_id)

    dimensions = copy.deepcopy(archetype["default_dimensions_mm"])
    dimensions.update({k: v for k, v in medidas.items() if k in dimensions})

    spec = {
        "schema_version": "0.1",
        "name": overrides.get("name") or archetype.get("label", archetype_id),
        "prompt": prompt,
        "reference_path": referencia_path,
        "archetype": archetype["id"],
        "units": "mm",
        "dimensions": dimensions,
        "wheels": _default_wheels(archetype["id"], dimensions),
        "layout": archetype.get("layout", {}),
        "style": archetype.get("style", {}),
        "features": archetype.get("features", {}),
        "constraints": _constraints_from_dimensions(dimensions),
    }
    return normalize_spec(_deep_merge(spec, overrides))


def load_spec(spec_json):
    if isinstance(spec_json, dict):
        raw = spec_json
    else:
        raw = json.loads(spec_json) if spec_json else {}
    return normalize_spec(raw)


def normalize_spec(raw):
    spec = copy.deepcopy(raw or {})
    archetype = _load_archetype(spec.get("archetype", "supercar"))
    spec.setdefault("schema_version", "0.1")
    spec.setdefault("name", archetype.get("label", archetype["id"]))
    spec.setdefault("archetype", archetype["id"])
    spec.setdefault("units", "mm")
    spec.setdefault("dimensions", copy.deepcopy(archetype["default_dimensions_mm"]))
    spec["dimensions"] = _deep_merge(archetype["default_dimensions_mm"], spec["dimensions"])
    spec.setdefault("wheels", _default_wheels(archetype["id"], spec["dimensions"]))
    spec.setdefault("layout", copy.deepcopy(archetype.get("layout", {})))
    spec["layout"] = _deep_merge(archetype.get("layout", {}), spec["layout"])
    spec.setdefault("style", copy.deepcopy(archetype.get("style", {})))
    spec["style"] = _deep_merge(archetype.get("style", {}), spec["style"])
    spec.setdefault("features", copy.deepcopy(archetype.get("features", {})))
    spec["features"] = _deep_merge(archetype.get("features", {}), spec["features"])
    spec.setdefault("constraints", _constraints_from_dimensions(spec["dimensions"]))
    _validate_required(spec)
    spec["_meters"] = _to_meters(spec)
    return spec


def _validate_required(spec):
    dims = spec.get("dimensions", {})
    required_dims = ["length", "width", "height", "wheelbase", "front_track", "rear_track", "ground_clearance"]
    missing = [key for key in required_dims if key not in dims]
    if missing:
        raise VehicleSpecError(f"Dimensoes obrigatorias ausentes: {missing}")
    for key in required_dims:
        if float(dims[key]) <= 0:
            raise VehicleSpecError(f"Dimensao '{key}' precisa ser positiva.")
    if dims["wheelbase"] >= dims["length"]:
        raise VehicleSpecError("Wheelbase precisa ser menor que o comprimento total.")
    wheels = spec.get("wheels", {})
    for key in ["front_diameter", "rear_diameter", "front_width", "rear_width"]:
        if key not in wheels or float(wheels[key]) <= 0:
            raise VehicleSpecError(f"Parametro de roda invalido: {key}")


def _to_meters(spec):
    wheels = spec["wheels"]
    return {
        "dimensions": dimensions_mm_to_m(spec["dimensions"]),
        "wheels": {
            **wheels,
            "front_diameter": mm_to_m(wheels["front_diameter"]),
            "rear_diameter": mm_to_m(wheels["rear_diameter"]),
            "front_width": mm_to_m(wheels["front_width"]),
            "rear_width": mm_to_m(wheels["rear_width"]),
        },
    }
