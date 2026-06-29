"""Motor de volume: a "forma" reutilizavel do gerador.

Varre uma secao transversal parametrica ao longo de um eixo. A forma e o tamanho
da secao mudam ponto a ponto (interpolados entre "secoes-chave"). Toda peca de
carroceria (corpo, paralama, cabine, nariz...) e um volume desses com config
diferente -- sem codigo proprio por peca.

Entradas: secoes-chave + eixo de varredura + opcoes (vinco, suavizacao, espelho).
Saidas: objeto de malha (nomeado, simetrico, com vincos) + relatorio
(bbox, nº de vertices, manifold, pontos-chave para encaixe posterior).

Coordenadas globais: X = comprimento, Y = largura, Z = altura.
"""

import math


# Campos de uma secao e seus defaults. Cada secao-chave traz 't' (0..1 ao longo
# do eixo) e qualquer subconjunto destes campos; o resto cai no default.
SECTION_DEFAULTS = {
    "hw": 0.5,       # meia-largura (no eixo "right")
    "top": 1.0,      # topo (no eixo "up")
    "bottom": 0.1,   # base (no eixo "up")
    "cy": 0.0,       # deslocamento lateral do centro da secao
    "ny": 2.6,       # cheio das laterais (maior = mais reto)
    "nu": 3.0,       # arredondamento do topo
    "nl": 3.6,       # arredondamento da base
    "tumble": 0.0,   # tumblehome: puxa o topo pra dentro
}


def _smoothstep(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def _interp_section(sections, u):
    """Mistura as secoes-chave na posicao u (0..1) campo a campo."""
    ss = sorted(sections, key=lambda s: s["t"])
    if u <= ss[0]["t"]:
        a = b = ss[0]
        w = 0.0
    elif u >= ss[-1]["t"]:
        a = b = ss[-1]
        w = 0.0
    else:
        a = b = ss[-1]
        w = 0.0
        for i in range(len(ss) - 1):
            if ss[i]["t"] <= u <= ss[i + 1]["t"]:
                a, b = ss[i], ss[i + 1]
                span = b["t"] - a["t"]
                w = _smoothstep((u - a["t"]) / span) if span > 0 else 0.0
                break
    out = {}
    for key, dflt in SECTION_DEFAULTS.items():
        va = a.get(key, dflt)
        vb = b.get(key, dflt)
        out[key] = va + (vb - va) * w
    return out


def _ring_local(sec, k):
    """Anel da secao no plano transversal local: lista de (ry, rz)."""
    hw, tz, bz = sec["hw"], sec["top"], sec["bottom"]
    cy, tumble = sec["cy"], sec["tumble"]
    ny, nu, nl = sec["ny"], sec["nu"], sec["nl"]
    mid = (tz + bz) / 2.0
    up = max(tz - mid, 1e-4)
    lo = max(mid - bz, 1e-4)
    pts = []
    for i in range(k):
        th = 2.0 * math.pi * i / k
        c = math.cos(th)
        s = math.sin(th)
        y = hw * math.copysign(abs(c) ** (2.0 / ny), c)
        if s >= 0.0:
            z = mid + up * (abs(s) ** (2.0 / nu))
            zf = (z - mid) / up
            y *= (1.0 - tumble * (max(0.0, zf) ** 1.5))
        else:
            z = mid - lo * (abs(s) ** (2.0 / nl))
        pts.append((cy + y, z))
    return pts


def build_volume(name, sections, material=None, axis=None, k=24, ring_stations=30,
                 crease_columns=None, crease_value=0.8, subdiv=2,
                 closed_ends=True, mirror_y=False):
    """Constroi um volume varrendo a secao ao longo do eixo.

    sections: lista de dicts (cada um com 't' e campos de SECTION_DEFAULTS).
    axis: {"start": (x,y,z), "end": (x,y,z), "up": (x,y,z)}. Default = eixo X.
    mirror_y: espelha em Y (pecas de um lado so, ex.: paralama).
    Retorna {"object", "report"}.
    """
    import bmesh  # type: ignore
    import bpy  # type: ignore
    from mathutils import Vector  # type: ignore

    axis = axis or {"start": (-1, 0, 0), "end": (1, 0, 0), "up": (0, 0, 1)}
    start = Vector(axis["start"])
    end = Vector(axis["end"])
    up = Vector(axis["up"]).normalized()
    fwd = (end - start)
    if fwd.length < 1e-6:
        fwd = Vector((1, 0, 0))
    fwd = fwd.normalized()
    right = up.cross(fwd).normalized()  # X fwd + Z up -> right = +Y

    n = max(2, ring_stations)
    verts = []
    ring_idx = []
    for j in range(n):
        u = j / (n - 1)
        base = start + (end - start) * u
        sec = _interp_section(sections, u)
        idxs = []
        for (ry, rz) in _ring_local(sec, k):
            p = base + right * ry + up * rz
            idxs.append(len(verts))
            verts.append((p.x, p.y, p.z))
        ring_idx.append(idxs)

    faces = []
    for r in range(len(ring_idx) - 1):
        a, b = ring_idx[r], ring_idx[r + 1]
        for i in range(k):
            jj = (i + 1) % k
            faces.append((a[i], a[jj], b[jj], b[i]))

    if closed_ends:
        def cap(ring, rev):
            cx = sum(verts[i][0] for i in ring) / k
            cyc = sum(verts[i][1] for i in ring) / k
            cz = sum(verts[i][2] for i in ring) / k
            ctr = len(verts)
            verts.append((cx, cyc, cz))
            for i in range(k):
                jj = (i + 1) % k
                faces.append((ctr, ring[jj], ring[i]) if rev else (ctr, ring[i], ring[jj]))
        cap(ring_idx[0], False)
        cap(ring_idx[-1], True)

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    manifold = all(e.is_manifold for e in bm.edges)
    if crease_columns:
        nst = len(ring_idx)
        targets = set()
        for r in range(nst - 1):
            for i in crease_columns:
                targets.add(frozenset((r * k + i, (r + 1) * k + i)))
        cl = bm.edges.layers.float.new("crease_edge")
        bm.verts.ensure_lookup_table()
        for e in bm.edges:
            if frozenset((e.verts[0].index, e.verts[1].index)) in targets:
                e[cl] = crease_value
    bm.to_mesh(mesh)
    bm.free()

    for poly in mesh.polygons:
        poly.use_smooth = True

    obj = bpy.data.objects.new(name, mesh)
    coll = getattr(bpy.context, "collection", None) or bpy.context.scene.collection
    coll.objects.link(obj)
    if material:
        obj.data.materials.append(material)
    if mirror_y:
        mir = obj.modifiers.new("vol_mirror", "MIRROR")
        mir.use_axis = (False, True, False)
    if subdiv and subdiv > 0:
        sd = obj.modifiers.new("vol_subsurf", "SUBSURF")
        sd.levels = subdiv
        sd.render_levels = subdiv
    obj.modifiers.new("vol_weighted_normals", "WEIGHTED_NORMAL")

    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    report = {
        "name": name,
        "n_verts": len(verts),
        "manifold": bool(manifold),
        "bbox_min": [min(xs), min(ys), min(zs)],
        "bbox_max": [max(xs), max(ys), max(zs)],
        "mirror_y": bool(mirror_y),
    }
    return {"object": obj, "report": report}
