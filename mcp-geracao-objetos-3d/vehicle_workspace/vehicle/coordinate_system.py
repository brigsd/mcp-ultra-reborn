AXIS_LENGTH = "X"
AXIS_WIDTH = "Y"
AXIS_HEIGHT = "Z"
FRONT_SIGN = 1
SYMMETRY_PLANE = "XZ"


def axle_positions(wheelbase_m):
    half = float(wheelbase_m) / 2.0
    return {"front_x": half, "rear_x": -half}


def wheel_positions(spec_m):
    dims = spec_m["dimensions"]
    wheels = spec_m["wheels"]
    axles = axle_positions(dims["wheelbase"])
    front_assembly_width = wheels["front_width"] * 1.10
    rear_assembly_width = wheels["rear_width"] * 1.10
    front_y = min(dims["front_track"] / 2.0, max(0.0, (dims["width"] - front_assembly_width) / 2.0))
    rear_y = min(dims["rear_track"] / 2.0, max(0.0, (dims["width"] - rear_assembly_width) / 2.0))
    front_r = wheels["front_diameter"] / 2.0
    rear_r = wheels["rear_diameter"] / 2.0
    return [
        {"id": "front_left", "x": axles["front_x"], "y": front_y, "z": front_r, "radius": front_r, "width": wheels["front_width"]},
        {"id": "front_right", "x": axles["front_x"], "y": -front_y, "z": front_r, "radius": front_r, "width": wheels["front_width"]},
        {"id": "rear_left", "x": axles["rear_x"], "y": rear_y, "z": rear_r, "radius": rear_r, "width": wheels["rear_width"]},
        {"id": "rear_right", "x": axles["rear_x"], "y": -rear_y, "z": rear_r, "radius": rear_r, "width": wheels["rear_width"]},
    ]
