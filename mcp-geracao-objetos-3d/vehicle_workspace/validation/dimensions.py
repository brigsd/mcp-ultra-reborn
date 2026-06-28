from vehicle_workspace.generators.blender_utils import all_vehicle_objects, bbox_for_objects
from vehicle_workspace.vehicle.units import m_to_mm


# Apendices fora do envelope dimensional homologado (largura exclui retrovisor,
# altura nao conta asa, etc.). O envelope e corpo + vidro + rodas.
_APPENDAGE_MARKERS = ("_rig_", "_mirror_", "_aero_", "_light_", "_intake_")


def audit_dimensions(spec):
    dims = spec["dimensions"]
    objects = [
        obj for obj in all_vehicle_objects()
        if not any(m in obj.name for m in _APPENDAGE_MARKERS)
    ]
    mn, mx, center, actual = bbox_for_objects(objects)
    actual_mm = {
        "length": m_to_mm(actual.x),
        "width": m_to_mm(actual.y),
        "height": m_to_mm(actual.z),
    }

    constraints = {c.get("id"): c for c in spec.get("constraints", []) if c.get("type") == "dimension"}
    results = {}
    for key in ["length", "width", "height"]:
        target = float(dims[key])
        tolerance = float(constraints.get(key, {}).get("tolerance_mm", 25))
        error = actual_mm[key] - target
        results[key] = {
            "target_mm": round(target, 3),
            "actual_mm": round(actual_mm[key], 3),
            "error_mm": round(error, 3),
            "tolerance_mm": tolerance,
            "pass": abs(error) <= tolerance,
        }

    # Wheelbase is generated from named wheel centers rather than bbox.
    wheelbase_target = float(dims["wheelbase"])
    wheelbase_actual = None
    import bpy  # type: ignore
    front = bpy.data.objects.get("vehicle_wheel_front_left_tire")
    rear = bpy.data.objects.get("vehicle_wheel_rear_left_tire")
    if front and rear:
        wheelbase_actual = m_to_mm(abs(front.location.x - rear.location.x))
    if wheelbase_actual is not None:
        tolerance = float(constraints.get("wheelbase", {}).get("tolerance_mm", 10))
        error = wheelbase_actual - wheelbase_target
        results["wheelbase"] = {
            "target_mm": round(wheelbase_target, 3),
            "actual_mm": round(wheelbase_actual, 3),
            "error_mm": round(error, 3),
            "tolerance_mm": tolerance,
            "pass": abs(error) <= tolerance,
        }

    return {
        "dimension_results": results,
        "bbox_min_m": [mn.x, mn.y, mn.z],
        "bbox_max_m": [mx.x, mx.y, mx.z],
        "pass": all(item["pass"] for item in results.values()),
    }

