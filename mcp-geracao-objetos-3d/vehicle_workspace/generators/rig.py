from vehicle_workspace.generators.blender_utils import (
    create_box,
    create_cylinder_y,
    create_wire_box,
    make_material,
)
from vehicle_workspace.vehicle.coordinate_system import wheel_positions


def generate_rig(spec):
    dims = spec["_meters"]["dimensions"]
    wheel_data = wheel_positions(spec["_meters"])

    mat_bbox = make_material("vehicle_rig_bbox", (0.1, 0.45, 1.0, 1.0))
    mat_axle = make_material("vehicle_rig_axle", (1.0, 0.8, 0.1, 1.0))
    mat_marker = make_material("vehicle_rig_marker", (0.1, 0.9, 0.35, 1.0))

    bbox = create_wire_box("vehicle_rig_bounding_box", dims["length"], dims["width"], dims["height"], 0.0)
    bbox.data.materials.append(mat_bbox)

    centerline = create_box(
        "vehicle_rig_centerline",
        (0, 0, 0.025),
        (dims["length"], 0.018, 0.05),
        mat_axle,
        bevel=0.002,
    )

    axle_depth = max(dims["front_track"], dims["rear_track"]) + 0.28
    for axle_name, x in [("front", dims["wheelbase"] / 2.0), ("rear", -dims["wheelbase"] / 2.0)]:
        create_cylinder_y(
            f"vehicle_rig_{axle_name}_axle",
            (x, 0, 0.08),
            0.025,
            axle_depth,
            mat_axle,
            vertices=16,
        )

    markers = []
    for wheel in wheel_data:
        marker = create_cylinder_y(
            f"vehicle_rig_wheel_center_{wheel['id']}",
            (wheel["x"], wheel["y"], wheel["z"]),
            0.055,
            0.035,
            mat_marker,
            vertices=24,
        )
        markers.append(marker)

    return {
        "objects": [bbox.name, centerline.name] + [m.name for m in markers],
        "wheel_centers": wheel_data,
        "dimensions_m": dims,
    }

