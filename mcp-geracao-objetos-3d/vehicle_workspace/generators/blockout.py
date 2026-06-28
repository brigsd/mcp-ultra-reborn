from vehicle_workspace.generators.blender_utils import create_box, make_material
from vehicle_workspace.generators.wheels import generate_wheels


def _section_profile(archetype, length, width, height, ground):
    if archetype == "pickup":
        return [
            (-0.50, 0.82, 0.70, ground, height * 0.55),
            (-0.30, 0.86, 0.72, ground, height * 0.58),
            (-0.10, 0.82, 0.62, ground, height * 0.62),
            (0.12, 0.78, 0.52, ground, height * 0.93),
            (0.32, 0.80, 0.58, ground, height * 0.90),
            (0.50, 0.74, 0.62, ground, height * 0.68),
        ]
    if archetype == "suv":
        return [
            (-0.50, 0.78, 0.70, ground, height * 0.62),
            (-0.32, 0.86, 0.74, ground, height * 0.78),
            (-0.10, 0.84, 0.66, ground, height * 0.96),
            (0.12, 0.82, 0.64, ground, height),
            (0.34, 0.80, 0.68, ground, height * 0.86),
            (0.50, 0.72, 0.64, ground, height * 0.58),
        ]
    return [
        (-0.50, 0.72, 0.58, ground, height * 0.35),
        (-0.36, 0.88, 0.72, ground, height * 0.50),
        (-0.16, 0.86, 0.46, ground, height * 0.84),
        (0.02, 0.72, 0.36, ground, height),
        (0.22, 0.78, 0.50, ground, height * 0.68),
        (0.38, 0.86, 0.68, ground, height * 0.43),
        (0.50, 0.70, 0.54, ground, height * 0.28),
    ]


def _create_loft_mesh(name, sections, length, width, material):
    import bpy  # type: ignore

    verts = []
    faces = []
    for ratio_x, lower_w_ratio, upper_w_ratio, z_low, z_top in sections:
        x = ratio_x * length
        lower_w = lower_w_ratio * width
        upper_w = upper_w_ratio * width
        shoulder_z = z_low + (z_top - z_low) * 0.42
        verts.extend([
            (x, -lower_w / 2.0, z_low),
            (x, lower_w / 2.0, z_low),
            (x, lower_w / 2.0, shoulder_z),
            (x, upper_w / 2.0, z_top),
            (x, -upper_w / 2.0, z_top),
            (x, -lower_w / 2.0, shoulder_z),
        ])

    loop = 6
    for i in range(len(sections) - 1):
        a = i * loop
        b = (i + 1) * loop
        for j in range(loop):
            faces.append((a + j, a + ((j + 1) % loop), b + ((j + 1) % loop), b + j))
    faces.append(tuple(reversed(range(loop))))
    last = (len(sections) - 1) * loop
    faces.append(tuple(last + j for j in range(loop)))

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)

    bevel = obj.modifiers.new(name="vehicle_body_bevel", type="BEVEL")
    bevel.width = min(0.008, max(length, width) * 0.001)
    bevel.segments = 3
    obj.modifiers.new(name="vehicle_body_weighted_normals", type="WEIGHTED_NORMAL")
    return obj


def _create_cabin(spec, material):
    dims = spec["_meters"]["dimensions"]
    layout = spec["layout"]
    archetype = spec["archetype"]
    length = dims["length"]
    width = dims["width"]
    height = dims["height"]

    if archetype == "pickup":
        loc = (length * 0.12, 0, height * 0.67)
        box = (length * 0.28, width * 0.58, height * 0.46)
    elif archetype == "suv":
        loc = (length * 0.02, 0, height * 0.68)
        box = (length * 0.54, width * 0.62, height * 0.46)
    else:
        loc = (length * (layout.get("roof_peak_x_ratio", 0.03)), 0, height * 0.66)
        box = (length * 0.30, width * 0.46, height * 0.38)

    return create_box("vehicle_glass_cabin_blockout", loc, box, material, bevel=0.05)


def _create_supercar_aero(spec, mat_dark):
    dims = spec["_meters"]["dimensions"]
    length = dims["length"]
    width = dims["width"]
    height = dims["height"]
    ground = dims["ground_clearance"]
    created = []

    if spec["features"].get("front_splitter", False):
        splitter = create_box(
            "vehicle_aero_front_splitter",
            (length * 0.47, 0, ground * 0.42),
            (length * 0.06, width * 0.78, max(ground * 0.22, 0.025)),
            mat_dark,
            bevel=0.012,
        )
        created.append(splitter.name)

    if spec["features"].get("large_rear_diffuser", False):
        diffuser = create_box(
            "vehicle_aero_rear_diffuser",
            (-length * 0.47, 0, ground * 0.55),
            (length * 0.06, width * 0.66, max(ground * 0.45, 0.05)),
            mat_dark,
            bevel=0.018,
        )
        created.append(diffuser.name)

    if spec["features"].get("active_rear_wing", False):
        wing = create_box(
            "vehicle_aero_active_rear_wing",
            (-length * 0.36, 0, height * 0.93),
            (length * 0.08, width * 0.70, height * 0.035),
            mat_dark,
            bevel=0.018,
        )
        created.append(wing.name)

    return created


def generate_blockout(spec, include_rig=False):
    dims = spec["_meters"]["dimensions"]
    mat_body = make_material("vehicle_body_clay", (0.58, 0.62, 0.66, 1.0), roughness=0.72)
    mat_glass = make_material("vehicle_glass_blue", (0.08, 0.18, 0.28, 0.45), roughness=0.1, alpha=0.45)
    mat_dark = make_material("vehicle_dark_detail", (0.015, 0.017, 0.018, 1.0), roughness=0.75)

    sections = _section_profile(
        spec["archetype"],
        dims["length"],
        dims["width"],
        dims["height"],
        dims["ground_clearance"],
    )
    body = _create_loft_mesh("vehicle_body_main_blockout", sections, dims["length"], dims["width"], mat_body)
    cabin = _create_cabin(spec, mat_glass)
    wheels = generate_wheels(spec)
    aero = _create_supercar_aero(spec, mat_dark)

    return {
        "objects": [body.name, cabin.name] + wheels["objects"] + aero,
        "body": body.name,
        "cabin": cabin.name,
        "wheels": wheels,
        "aero": aero,
    }
