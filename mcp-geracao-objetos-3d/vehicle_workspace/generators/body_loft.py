"""Carroceria continua por secoes/loft (Fase 3).

Substitui o blockout facetado por uma superficie continua. Estrutura em dois
volumes, como um carro real:

  1. corpo baixo (lower body): deck na altura da cintura, chato e largo, com
     "cintura de coca-cola" na planta (haunches sobre as rodas);
  2. greenhouse (cabine): bolha separada, mais estreita, com tumblehome, que
     pousa sobre o deck na regiao da cabine.

A malha bruta e suavizada por Subdivision Surface, recebe caixas de roda por
boolean e mantem simetria por construcao (secoes simetricas em Y).

Coordenadas: X = comprimento (frente +), Y = largura, Z = altura. Origem no
centro do entre-eixos, no chao (Z=0). s longitudinal: 0 = traseira, 1 = frente.
"""

import math

from vehicle_workspace.generators.blender_utils import (
    create_cylinder_y,
    make_material,
)
from vehicle_workspace.generators.blockout import _create_supercar_aero
from vehicle_workspace.generators.wheels import generate_wheels
from vehicle_workspace.vehicle.coordinate_system import wheel_positions


# ---------------------------------------------------------------------------
# Helpers matematicos (sem numpy: roda no Python embutido do Blender)
# ---------------------------------------------------------------------------

def _smoothstep(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def _interp_keys(s, keys):
    """Interpola curva (s, valor) com smoothstep entre pontos adjacentes."""
    if s <= keys[0][0]:
        return keys[0][1]
    if s >= keys[-1][0]:
        return keys[-1][1]
    for i in range(len(keys) - 1):
        s0, v0 = keys[i]
        s1, v1 = keys[i + 1]
        if s0 <= s <= s1:
            t = _smoothstep((s - s0) / (s1 - s0)) if s1 > s0 else 0.0
            return v0 + (v1 - v0) * t
    return keys[-1][1]


def _gauss(s, center, sigma):
    return math.exp(-((s - center) ** 2) / (2.0 * sigma * sigma))


def _linspace(a, b, n):
    if n <= 1:
        return [a]
    return [a + (b - a) * i / (n - 1) for i in range(n)]


# ---------------------------------------------------------------------------
# Perfis longitudinais por arquetipo
# ---------------------------------------------------------------------------

def _profiles(spec):
    dims = spec["_meters"]["dimensions"]
    length = dims["length"]
    width = dims["width"]
    height = dims["height"]
    gc = dims["ground_clearance"]
    wmax = width / 2.0
    archetype = spec.get("archetype", "supercar")

    if archetype == "suv":
        hw_keys = [(0.0, 0.62), (0.14, 0.82), (0.26, 0.99), (0.5, 0.97),
                   (0.74, 0.99), (0.88, 0.84), (1.0, 0.66)]
        deck_keys = [(0.0, 0.50), (0.12, 0.56), (0.26, 0.62), (0.74, 0.64),
                     (0.86, 0.56), (1.0, 0.48)]
        gh_span = (0.18, 0.78)
        gh_top_keys = [(0.18, 0.66), (0.30, 0.96), (0.66, 0.98), (0.78, 0.70)]
        gh_w_ratio, gh_tumble = 0.78, 0.16
        ny, nu, nl = 3.0, 3.4, 4.0
    elif archetype == "pickup":
        hw_keys = [(0.0, 0.74), (0.2, 0.97), (0.4, 0.92), (0.6, 0.95),
                   (0.8, 0.97), (0.92, 0.84), (1.0, 0.68)]
        deck_keys = [(0.0, 0.50), (0.12, 0.56), (0.30, 0.60), (0.42, 0.60),
                     (0.62, 0.46), (0.84, 0.46), (1.0, 0.44)]
        gh_span = (0.42, 0.74)
        gh_top_keys = [(0.42, 0.62), (0.52, 0.95), (0.66, 0.96), (0.74, 0.66)]
        gh_w_ratio, gh_tumble = 0.82, 0.14
        ny, nu, nl = 3.4, 3.6, 4.4
    else:  # supercar
        hw_keys = [(0.00, 0.62), (0.12, 0.82), (0.22, 1.00), (0.34, 0.93),
                   (0.50, 0.87), (0.66, 0.97), (0.78, 1.00), (0.90, 0.74),
                   (1.00, 0.52)]
        # deck = altura da cintura/ombro (NAO o teto): chato, sobe pro deck traseiro
        # ajustado contra blueprint (fase 4): capo e deck traseiro mais cheios,
        # mas deck baixo sob o greenhouse (s 0.44-0.56) p/ nao afundar o vidro
        deck_keys = [(0.00, 0.52), (0.10, 0.60), (0.20, 0.66), (0.30, 0.62),
                     (0.44, 0.53), (0.56, 0.50), (0.70, 0.53), (0.78, 0.55),
                     (0.86, 0.47), (1.00, 0.34)]
        gh_span = (0.30, 0.64)
        gh_top_keys = [(0.30, 0.60), (0.38, 0.86), (0.46, 0.99), (0.54, 1.00),
                       (0.60, 0.84), (0.64, 0.66)]
        gh_w_ratio, gh_tumble = 0.60, 0.42
        ny, nu, nl = 2.6, 3.8, 4.0

    bot_keys = [(0.0, gc + 0.10), (0.06, gc + 0.02), (0.12, gc),
                (0.88, gc), (0.94, gc + 0.03), (1.0, gc + 0.09)]

    return {
        "length": length, "width": width, "height": height, "gc": gc,
        "wmax": wmax,
        "half_width": lambda s: min(wmax, _interp_keys(s, hw_keys) * wmax),
        "deck_z": lambda s: _interp_keys(s, deck_keys) * height,
        "bottom_z": lambda s: _interp_keys(s, bot_keys),
        "gh_span": gh_span,
        "gh_top": lambda s: _interp_keys(s, gh_top_keys) * height,
        "gh_w_ratio": gh_w_ratio,
        "gh_tumble": gh_tumble,
        "ny": ny, "nu": nu, "nl": nl,
    }


# ---------------------------------------------------------------------------
# Construcao de malha (loft de aneis)
# ---------------------------------------------------------------------------

def _link(obj):
    import bpy  # type: ignore

    coll = getattr(bpy.context, "collection", None)
    if coll is None:
        coll = bpy.context.scene.collection
    coll.objects.link(obj)


def _ring(x, hw, tz, bz, tumble, ny, nu, nl, k):
    """Anel transversal simetrico em Y (superelipse com tumblehome no teto)."""
    mid = (tz + bz) / 2.0
    up = max(tz - mid, 1e-4)
    lo = max(mid - bz, 1e-4)
    pts = []
    for i in range(k):
        th = 2.0 * math.pi * i / k
        c = math.cos(th)
        sn = math.sin(th)
        y = hw * math.copysign(abs(c) ** (2.0 / ny), c)
        if sn >= 0.0:
            z = mid + up * (abs(sn) ** (2.0 / nu))
            zf = (z - mid) / up
            y *= (1.0 - tumble * (max(0.0, zf) ** 1.5))
        else:
            z = mid - lo * (abs(sn) ** (2.0 / nl))
        pts.append((x, y, z))
    return pts


def _loft(name, rings, material):
    """Constroi malha-tubo fechada a partir de uma lista de aneis (cada anel =
    lista de pontos de mesmo tamanho k)."""
    import bmesh  # type: ignore
    import bpy  # type: ignore

    k = len(rings[0])
    verts = []
    ring_idx = []
    for ring in rings:
        idxs = []
        for p in ring:
            idxs.append(len(verts))
            verts.append(p)
        ring_idx.append(idxs)

    faces = []
    for r in range(len(ring_idx) - 1):
        a, b = ring_idx[r], ring_idx[r + 1]
        for i in range(k):
            j = (i + 1) % k
            faces.append((a[i], a[j], b[j], b[i]))

    def cap(ring, reverse):
        cx = sum(verts[i][0] for i in ring) / k
        cy = sum(verts[i][1] for i in ring) / k
        cz = sum(verts[i][2] for i in ring) / k
        center = len(verts)
        verts.append((cx, cy, cz))
        for i in range(k):
            j = (i + 1) % k
            faces.append((center, ring[j], ring[i]) if reverse
                         else (center, ring[i], ring[j]))

    cap(ring_idx[0], reverse=False)
    cap(ring_idx[-1], reverse=True)

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()

    for poly in mesh.polygons:
        poly.use_smooth = True

    obj = bpy.data.objects.new(name, mesh)
    _link(obj)
    if material:
        obj.data.materials.append(material)
    return obj


# ---------------------------------------------------------------------------
# Volumes
# ---------------------------------------------------------------------------

def _build_lower_body(prof, material, k=26, stations=33):
    half_l = prof["length"] / 2.0
    ny, nu, nl = prof["ny"], prof["nu"], prof["nl"]
    rings = []
    for s in _linspace(0.0, 1.0, stations):
        x = -half_l + s * prof["length"]
        rings.append(_ring(
            x, prof["half_width"](s), prof["deck_z"](s), prof["bottom_z"](s),
            tumble=0.06, ny=ny, nu=nu, nl=nl, k=k,
        ))
    return _loft("vehicle_body_main", rings, material)


def _build_greenhouse(prof, material, k=20, stations=16):
    half_l = prof["length"] / 2.0
    s0, s1 = prof["gh_span"]
    w_ratio = prof["gh_w_ratio"]
    tumble = prof["gh_tumble"]
    rings = []
    for s in _linspace(s0, s1, stations):
        x = -half_l + s * prof["length"]
        deck = prof["deck_z"](s)
        top = max(prof["gh_top"](s), deck + 0.06)
        bottom = deck - 0.04  # pequena imersao no corpo
        hw = prof["half_width"](s) * w_ratio
        rings.append(_ring(
            x, hw, top, bottom, tumble=tumble,
            ny=2.2, nu=2.4, nl=2.6, k=k,
        ))
    gh = _loft("vehicle_glass_canopy", rings, material)
    sub = gh.modifiers.new(name="vehicle_canopy_subsurf", type="SUBSURF")
    sub.levels = 2
    sub.render_levels = 2
    return gh


# ---------------------------------------------------------------------------
# Caixas de roda (boolean)
# ---------------------------------------------------------------------------

def _wheel_arch_cutters(spec):
    cutters = []
    for wheel in wheel_positions(spec["_meters"]):
        cutter = create_cylinder_y(
            f"cutter_arch_{wheel['id']}",
            (wheel["x"], wheel["y"], wheel["z"] + wheel["radius"] * 0.16),
            wheel["radius"] * 1.15,
            wheel["width"] * 1.9,
            material=None,
            vertices=48,
        )
        cutter.hide_render = True
        cutter.hide_viewport = True
        cutters.append(cutter)
    return cutters


def _apply_body_modifiers(body, cutters):
    sub = body.modifiers.new(name="vehicle_body_subsurf", type="SUBSURF")
    sub.levels = 2
    sub.render_levels = 2
    for cutter in cutters:
        bm = body.modifiers.new(name=f"vehicle_arch_{cutter.name}", type="BOOLEAN")
        bm.operation = "DIFFERENCE"
        bm.object = cutter
        try:
            bm.solver = "EXACT"
        except Exception:
            pass
    body.modifiers.new(name="vehicle_body_weighted_normals", type="WEIGHTED_NORMAL")


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------

def generate_body(spec):
    prof = _profiles(spec)
    mat_body = make_material("vehicle_body_clay", (0.58, 0.62, 0.66, 1.0), roughness=0.5)
    body = _build_lower_body(prof, mat_body)
    cutters = _wheel_arch_cutters(spec)
    _apply_body_modifiers(body, cutters)
    return {"body": body, "cutters": [c.name for c in cutters], "prof": prof}


def generate_model(spec):
    mat_glass = make_material(
        "vehicle_glass_blue", (0.04, 0.07, 0.11, 0.40), roughness=0.05, alpha=0.40
    )
    mat_dark = make_material(
        "vehicle_dark_detail", (0.015, 0.017, 0.018, 1.0), roughness=0.7
    )

    body_data = generate_body(spec)
    prof = body_data["prof"]
    canopy = _build_greenhouse(prof, mat_glass)
    wheels = generate_wheels(spec)
    aero = _create_supercar_aero(spec, mat_dark)

    return {
        "objects": [body_data["body"].name, canopy.name] + wheels["objects"] + aero,
        "body": body_data["body"].name,
        "cabin": canopy.name,
        "wheels": wheels,
        "aero": aero,
        "arch_cutters": body_data["cutters"],
    }
