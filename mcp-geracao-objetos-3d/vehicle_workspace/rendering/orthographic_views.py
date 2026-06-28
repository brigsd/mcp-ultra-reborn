import math
import os

from vehicle_workspace.generators.blender_utils import all_vehicle_objects, bbox_for_objects


def _look_at(camera, target):
    direction = target - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _setup_scene(resolution=900):
    import bpy  # type: ignore

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 32
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.image_settings.file_format = "PNG"
    try:
        scene.view_settings.view_transform = "Standard"
    except Exception:
        pass

    if scene.world and scene.world.node_tree:
        bg = scene.world.node_tree.nodes.get("Background")
        if bg:
            bg.inputs[0].default_value = (0.045, 0.05, 0.058, 1)
            bg.inputs[1].default_value = 0.55

    if "vehicle_sun" not in bpy.data.objects:
        sun = bpy.data.lights.new("vehicle_sun", "SUN")
        sun.energy = 3.0
        sun_obj = bpy.data.objects.new("vehicle_sun", sun)
        bpy.context.collection.objects.link(sun_obj)
        sun_obj.rotation_euler = (math.radians(45), math.radians(0), math.radians(35))


def render_views(output_dir, resolution=900):
    import bpy  # type: ignore
    from mathutils import Vector  # type: ignore

    os.makedirs(output_dir, exist_ok=True)
    _setup_scene(resolution=resolution)

    objects = all_vehicle_objects()
    mn, mx, center, dim = bbox_for_objects(objects)
    maxd = max(dim.x, dim.y, dim.z, 1.0)
    distance = maxd * 3.0

    cam_data = bpy.data.cameras.new("vehicle_render_camera")
    cam = bpy.data.objects.new("vehicle_render_camera", cam_data)
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam

    views = {
        "perspectiva": {"loc": center + Vector((distance, -distance, distance * 0.55)), "persp": True},
        "frente": {"loc": center + Vector((distance, 0, 0)), "persp": False},
        "traseira": {"loc": center + Vector((-distance, 0, 0)), "persp": False},
        "lado": {"loc": center + Vector((0, -distance, 0)), "persp": False},
        "topo": {"loc": center + Vector((0, 0, distance)), "persp": False},
    }

    rendered = {}
    errors = {}
    for name, cfg in views.items():
        cam.location = cfg["loc"]
        if cfg["persp"]:
            cam.data.type = "PERSP"
            cam.data.lens = 55
        else:
            cam.data.type = "ORTHO"
            cam.data.ortho_scale = maxd * 1.22
        _look_at(cam, center)
        path = os.path.join(output_dir, f"{name}.png")
        bpy.context.scene.render.filepath = path
        try:
            bpy.ops.render.render(write_still=True)
            rendered[name] = path
        except Exception as exc:
            errors[name] = str(exc)
            break

    return {
        "renders": rendered,
        "errors": errors,
        "bbox_min_m": [mn.x, mn.y, mn.z],
        "bbox_max_m": [mx.x, mx.y, mx.z],
        "bbox_dim_m": [dim.x, dim.y, dim.z],
    }


def render_silhouette(output_dir, view="lado", resolution=1100):
    """Render de silhueta limpa: todos os objetos com emissao branca opaca sobre
    fundo preto. Saida ideal para extrair contorno (validation/vision).

    Override de materiais e restauro ao final para nao sujar a cena.
    """
    import bpy  # type: ignore
    from mathutils import Vector  # type: ignore

    os.makedirs(output_dir, exist_ok=True)

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 1
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.image_settings.file_format = "PNG"
    try:
        scene.view_settings.view_transform = "Standard"
    except Exception:
        pass

    # fundo preto
    saved_world_inputs = None
    if scene.world and scene.world.node_tree:
        bg = scene.world.node_tree.nodes.get("Background")
        if bg:
            saved_world_inputs = (bg.inputs[0].default_value[:], bg.inputs[1].default_value)
            bg.inputs[0].default_value = (0, 0, 0, 1)
            bg.inputs[1].default_value = 0.0

    white = bpy.data.materials.get("vehicle_silhouette_white")
    if white is None:
        white = bpy.data.materials.new("vehicle_silhouette_white")
        white.use_nodes = True
        nt = white.node_tree
        nt.nodes.clear()
        emit = nt.nodes.new("ShaderNodeEmission")
        emit.inputs[0].default_value = (1, 1, 1, 1)
        emit.inputs[1].default_value = 1.0
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(emit.outputs[0], out.inputs[0])

    objects = all_vehicle_objects()
    saved = []
    for obj in objects:
        if obj.type != "MESH":
            continue
        saved.append((obj, list(obj.data.materials)))
        obj.data.materials.clear()
        obj.data.materials.append(white)

    mn, mx, center, dim = bbox_for_objects(objects)
    maxd = max(dim.x, dim.y, dim.z, 1.0)
    distance = maxd * 3.0

    cam_data = bpy.data.cameras.new("vehicle_sil_camera")
    cam = bpy.data.objects.new("vehicle_sil_camera", cam_data)
    bpy.context.collection.objects.link(cam)
    scene.camera = cam
    locs = {
        "lado": center + Vector((0, -distance, 0)),
        "frente": center + Vector((distance, 0, 0)),
        "topo": center + Vector((0, 0, distance)),
    }
    cam.location = locs.get(view, locs["lado"])
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = maxd * 1.22
    _look_at(cam, center)

    path = os.path.join(output_dir, f"silhouette_{view}.png")
    scene.render.filepath = path
    result = {"path": path}
    try:
        bpy.ops.render.render(write_still=True)
    except Exception as exc:
        result["error"] = str(exc)

    # restaura materiais e mundo
    for obj, mats in saved:
        obj.data.materials.clear()
        for m in mats:
            obj.data.materials.append(m)
    if saved_world_inputs is not None:
        bg = scene.world.node_tree.nodes.get("Background")
        if bg:
            bg.inputs[0].default_value = saved_world_inputs[0]
            bg.inputs[1].default_value = saved_world_inputs[1]

    return result
