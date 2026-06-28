from vehicle_workspace.vehicle.coordinate_system import wheel_positions
from vehicle_workspace.vehicle.units import m_to_mm


def audit_wheel_fitment(spec):
    import bpy  # type: ignore

    results = []
    for wheel in wheel_positions(spec["_meters"]):
        obj = bpy.data.objects.get(f"vehicle_wheel_{wheel['id']}_tire")
        if not obj:
            results.append({"wheel": wheel["id"], "pass": False, "error": "missing wheel object"})
            continue
        center_error = max(
            abs(obj.location.x - wheel["x"]),
            abs(obj.location.y - wheel["y"]),
            abs(obj.location.z - wheel["z"]),
        )
        ground_error = abs((obj.location.z - wheel["radius"]) - 0.0)
        results.append({
            "wheel": wheel["id"],
            "center_error_mm": round(m_to_mm(center_error), 4),
            "ground_error_mm": round(m_to_mm(ground_error), 4),
            "pass": m_to_mm(center_error) <= 1.0 and m_to_mm(ground_error) <= 1.0,
        })
    return {
        "wheel_results": results,
        "pass": all(item.get("pass", False) for item in results),
    }

