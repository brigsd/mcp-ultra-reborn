from vehicle_workspace.generators.blender_utils import create_cylinder_y, make_material
from vehicle_workspace.vehicle.coordinate_system import wheel_positions


def generate_wheels(spec):
    mat_tire = make_material("vehicle_tire_rubber", (0.015, 0.014, 0.013, 1.0), roughness=0.9)
    mat_rim = make_material("vehicle_wheel_rim", (0.72, 0.74, 0.76, 1.0), roughness=0.35, metallic=0.4)
    mat_hub = make_material("vehicle_wheel_hub", (0.12, 0.12, 0.13, 1.0), roughness=0.45, metallic=0.2)

    created = []
    for wheel in wheel_positions(spec["_meters"]):
        tire = create_cylinder_y(
            f"vehicle_wheel_{wheel['id']}_tire",
            (wheel["x"], wheel["y"], wheel["z"]),
            wheel["radius"],
            wheel["width"],
            mat_tire,
            vertices=72,
        )
        rim = create_cylinder_y(
            f"vehicle_wheel_{wheel['id']}_rim",
            (wheel["x"], wheel["y"], wheel["z"]),
            wheel["radius"] * 0.63,
            wheel["width"] * 1.04,
            mat_rim,
            vertices=64,
        )
        hub = create_cylinder_y(
            f"vehicle_wheel_{wheel['id']}_hub",
            (wheel["x"], wheel["y"], wheel["z"]),
            wheel["radius"] * 0.22,
            wheel["width"] * 1.08,
            mat_hub,
            vertices=32,
        )
        created.extend([tire.name, rim.name, hub.name])
    return {"objects": created, "wheel_centers": wheel_positions(spec["_meters"])}

