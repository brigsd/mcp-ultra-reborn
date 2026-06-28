from vehicle_workspace.vehicle.units import m_to_mm


def audit_symmetry(spec):
    import bpy  # type: ignore

    pairs = [
        ("vehicle_wheel_front_left_tire", "vehicle_wheel_front_right_tire"),
        ("vehicle_wheel_rear_left_tire", "vehicle_wheel_rear_right_tire"),
    ]
    max_error_mm = 0.0
    pair_results = []
    for left_name, right_name in pairs:
        left = bpy.data.objects.get(left_name)
        right = bpy.data.objects.get(right_name)
        if not left or not right:
            pair_results.append({"pair": [left_name, right_name], "pass": False, "error_mm": None})
            continue
        x_error = abs(left.location.x - right.location.x)
        y_error = abs(left.location.y + right.location.y)
        z_error = abs(left.location.z - right.location.z)
        error_mm = m_to_mm(max(x_error, y_error, z_error))
        max_error_mm = max(max_error_mm, error_mm)
        pair_results.append({
            "pair": [left_name, right_name],
            "error_mm": round(error_mm, 4),
            "pass": error_mm <= 2.0,
        })
    return {
        "pair_results": pair_results,
        "max_error_mm": round(max_error_mm, 4),
        "pass": all(item["pass"] for item in pair_results),
    }

