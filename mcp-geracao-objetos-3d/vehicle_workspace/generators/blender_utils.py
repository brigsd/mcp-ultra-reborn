import math


def require_bpy():
    import bpy  # type: ignore
    return bpy


def make_material(name, color, roughness=0.65, metallic=0.0, alpha=1.0):
    bpy = require_bpy()
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = color
    if alpha < 1.0:
        mat.blend_method = "BLEND"
        mat.use_screen_refraction = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = color
        if "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = alpha
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = roughness
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metallic
    return mat


def assign_material(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return obj


def create_box(name, location, dimensions, material=None, bevel=0.0):
    bpy = require_bpy()
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        assign_material(obj, material)
    if bevel > 0:
        mod = obj.modifiers.new(name="vehicle_bevel", type="BEVEL")
        mod.width = bevel
        mod.segments = 3
        mod.affect = "EDGES"
        obj.modifiers.new(name="vehicle_weighted_normals", type="WEIGHTED_NORMAL")
    return obj


def create_cylinder_y(name, location, radius, width, material=None, vertices=64):
    bpy = require_bpy()
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=radius,
        depth=width,
        location=location,
        rotation=(math.radians(90), 0, 0),
    )
    obj = bpy.context.object
    obj.name = name
    if material:
        assign_material(obj, material)
    obj.modifiers.new(name="vehicle_weighted_normals", type="WEIGHTED_NORMAL")
    return obj


def create_wire_box(name, length, width, height, z_min=0.0):
    bpy = require_bpy()
    lx, wy = length / 2.0, width / 2.0
    z0, z1 = z_min, z_min + height
    verts = [
        (-lx, -wy, z0), (lx, -wy, z0), (lx, wy, z0), (-lx, wy, z0),
        (-lx, -wy, z1), (lx, -wy, z1), (lx, wy, z1), (-lx, wy, z1),
    ]
    edges = [
        (0, 1), (1, 2), (2, 3), (3, 0),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (0, 4), (1, 5), (2, 6), (3, 7),
    ]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, edges, [])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.display_type = "WIRE"
    return obj


def all_vehicle_objects():
    bpy = require_bpy()
    return [obj for obj in bpy.data.objects if obj.name.startswith("vehicle_")]


def bbox_for_objects(objects):
    from mathutils import Vector  # type: ignore

    points = []
    for obj in objects:
        if obj.type not in {"MESH", "CURVE"}:
            continue
        points.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
    if not points:
        zero = Vector((0, 0, 0))
        return zero, zero, zero, zero
    mn = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    mx = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    return mn, mx, (mn + mx) / 2.0, (mx - mn)

