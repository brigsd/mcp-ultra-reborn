bl_info = {
    "name": "MCP 3D Object Generation Bridge",
    "author": "MCP 3D",
    "version": (3, 0),
    "blender": (3, 2, 0),
    "location": "View3D > Sidebar > MCP 3D",
    "description": "Addon de ponte HTTP para o servidor MCP de Geração de Objetos 3D.",
    "category": "Development",
}

import bpy
import http.server
import threading
import queue
import json
import uuid
import time

# Fila: (request_id, tipo, dados)  tipo = "exec" | "descrever"
fila_execucao = queue.Queue()
resultados = {}
eventos = {}
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Inspeção de objeto
# ---------------------------------------------------------------------------

def _inspecionar_objeto(obj):
    bb = obj.bound_box
    coords = [obj.matrix_world @ bpy.mathutils.Vector(v[:]) for v in bb]
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    info = {
        "nome": obj.name,
        "tipo": obj.type,
        "dimensoes": [round(d, 6) for d in obj.dimensions],
        "localizacao": [round(l, 6) for l in obj.location],
        "bounding_box": {
            "min": [round(min(xs), 6), round(min(ys), 6), round(min(zs), 6)],
            "max": [round(max(xs), 6), round(max(ys), 6), round(max(zs), 6)],
        },
    }
    if obj.type == "MESH" and obj.data:
        mesh = obj.data
        info["vertices"] = len(mesh.vertices)
        info["arestas"] = len(mesh.edges)
        info["faces"] = len(mesh.polygons)
        info["problemas"] = _checar_problemas(obj)
    return info


def _checar_problemas(obj):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    problemas = []
    nm = [v.index for v in bm.verts if not v.is_manifold]
    if nm:
        problemas.append(f"non_manifold: {len(nm)} vértices")
    ng = [f.index for f in bm.faces if len(f.verts) > 4]
    if ng:
        problemas.append(f"n_gons: {len(ng)} faces")
    escala = obj.scale
    if max(abs(s - 1.0) for s in escala) > 0.001:
        problemas.append(f"escala_nao_aplicada: [{round(escala.x,3)}, {round(escala.y,3)}, {round(escala.z,3)}]")
    bm.free()
    return problemas


# ---------------------------------------------------------------------------
# Quatro vistas
# ---------------------------------------------------------------------------

# Cada entrada: (chave_resultado, perspectiva, eixo_ou_None)
_VISTAS = [
    ("perspectiva", "PERSP",  None),
    ("frente",      "ORTHO",  "FRONT"),
    ("lado",        "ORTHO",  "RIGHT"),
    ("topo",        "ORTHO",  "TOP"),
]


def _encontrar_viewport():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                return window, area
    return None, None


def _capturar_quatro_vistas():
    import tempfile, os, base64

    window, area = _encontrar_viewport()
    if not area:
        return {}

    space = area.spaces.active
    region3d = space.region_3d

    orig_persp  = region3d.view_perspective
    orig_matrix = region3d.view_matrix.copy()

    scene = bpy.context.scene
    old_path = scene.render.filepath
    old_fmt  = scene.render.image_settings.file_format
    scene.render.image_settings.file_format = "PNG"

    screenshots = {}

    for nome, perspectiva, eixo in _VISTAS:
        caminho = tempfile.mktemp(suffix=f"_{nome}.png")
        scene.render.filepath = caminho
        try:
            with bpy.context.temp_override(window=window, area=area):
                if eixo:
                    bpy.ops.view3d.view_axis(type=eixo, align_active=False)
                else:
                    region3d.view_perspective = "PERSP"
                bpy.ops.view3d.view_all(use_all_regions=False, center=False)
                bpy.ops.render.opengl(write_still=True)
        except Exception as e:
            print(f"[bridge] Vista '{nome}' falhou: {e}")
            continue

        if os.path.exists(caminho):
            with open(caminho, "rb") as f:
                screenshots[nome] = base64.b64encode(f.read()).decode("utf-8")
            os.unlink(caminho)

    # Restaura vista original
    try:
        with bpy.context.temp_override(window=window, area=area):
            region3d.view_perspective = orig_persp
            region3d.view_matrix = orig_matrix
    except Exception:
        pass

    scene.render.filepath = old_path
    scene.render.image_settings.file_format = old_fmt

    return screenshots


# ---------------------------------------------------------------------------
# Descrição textual da cena
# ---------------------------------------------------------------------------

def _descrever_cena():
    import bmesh as _bmesh

    objetos_mesh = [o for o in bpy.data.objects if o.type == "MESH"]

    if not bpy.data.objects:
        return "Cena vazia."

    linhas = [
        f"CENA: {len(bpy.data.objects)} objeto(s) total | {len(objetos_mesh)} MESH",
        "",
    ]

    for obj in objetos_mesh:
        dim = obj.dimensions
        loc = obj.location
        dim_mm = [round(d * 1000, 2) for d in dim]
        loc_mm = [round(l * 1000, 2) for l in loc]
        mesh   = obj.data

        dx, dy, dz = dim.x, dim.y, dim.z
        sim_xy = abs(dx - dy) < max(dx, dy, 0.0001) * 0.03

        if sim_xy and dz < min(dx, dy) * 0.6:
            forma = "cilindro achatado / disco"
        elif sim_xy and abs(dz - dx) < dx * 0.15:
            forma = "cilindro (proporcional)"
        elif abs(dx - dy) < dx * 0.05 and abs(dy - dz) < dy * 0.05:
            forma = "cubo / esfera"
        else:
            forma = "forma assimétrica"

        bm = _bmesh.new()
        bm.from_mesh(mesh)
        bm.normal_update()
        nm  = sum(1 for v in bm.verts if not v.is_manifold)
        ng  = sum(1 for f in bm.faces if len(f.verts) > 4)
        vol = bm.calc_volume()
        bm.free()

        saude = "✓ limpa" if nm == 0 and ng == 0 else \
                "✗ " + ", ".join(filter(None, [
                    f"{nm} non-manifold" if nm else "",
                    f"{ng} n-gons"       if ng else "",
                ]))

        linhas += [
            f"[{obj.name}]",
            f"  Forma           : {forma}",
            f"  Dimensões (mm)  : {dim_mm[0]} × {dim_mm[1]} × {dim_mm[2]}  (L × P × A)",
            f"  Centro (mm)     : X={loc_mm[0]}  Y={loc_mm[1]}  Z={loc_mm[2]}",
        ]
        if sim_xy:
            linhas.append(f"  Raio estimado   : {round(dx / 2 * 1000, 2)} mm")
        linhas += [
            f"  Malha           : {len(mesh.vertices)} vértices  {len(mesh.polygons)} faces",
            f"  Volume          : {round(vol * 1e6, 3)} cm³",
            f"  Saúde           : {saude}",
            "",
        ]

    # Relações espaciais entre pares
    if len(objetos_mesh) > 1:
        linhas.append("RELAÇÕES ESPACIAIS:")
        for i, a in enumerate(objetos_mesh):
            for b in objetos_mesh[i + 1:]:
                dist = (a.location - b.location).length * 1000
                # Sobreposição de bounding box
                def bb_range(o, axis):
                    coords = [o.matrix_world @ bpy.mathutils.Vector(v[:]) for v in o.bound_box]
                    vals = [getattr(c, axis) for c in coords]
                    return min(vals), max(vals)
                overlap = all(
                    bb_range(a, ax)[0] < bb_range(b, ax)[1] and
                    bb_range(b, ax)[0] < bb_range(a, ax)[1]
                    for ax in ("x", "y", "z")
                )
                nota = " [SOBREPOSIÇÃO DETECTADA]" if overlap else ""
                linhas.append(
                    f"  {a.name} ↔ {b.name} : {round(dist, 1)} mm entre centros{nota}"
                )
        linhas.append("")

    # Envelope geral da cena
    if objetos_mesh:
        all_coords = [
            obj.matrix_world @ bpy.mathutils.Vector(v[:])
            for obj in objetos_mesh
            for v in obj.bound_box
        ]
        xs = [c.x * 1000 for c in all_coords]
        ys = [c.y * 1000 for c in all_coords]
        zs = [c.z * 1000 for c in all_coords]
        linhas.append(
            f"ENVELOPE GERAL (mm): "
            f"X[{round(min(xs),1)} .. {round(max(xs),1)}]  "
            f"Y[{round(min(ys),1)} .. {round(max(ys),1)}]  "
            f"Z[{round(min(zs),1)} .. {round(max(zs),1)}]"
        )

    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# Processador da fila (thread principal do Blender)
# ---------------------------------------------------------------------------

def _processar_fila():
    while not fila_execucao.empty():
        request_id, tipo, dados = fila_execucao.get()

        if tipo == "descrever":
            resultado = {"descricao": _descrever_cena()}
        else:
            resultado = {
                "sucesso": False,
                "erro": None,
                "objetos_criados": [],
                "screenshots": {},
                "tempo_execucao_ms": 0,
            }
            antes = set(bpy.data.objects.keys())
            t0 = time.perf_counter()
            try:
                ns = {"bpy": bpy}
                exec(dados, ns)
                resultado["sucesso"] = True
            except Exception as e:
                resultado["erro"] = str(e)
            resultado["tempo_execucao_ms"] = round((time.perf_counter() - t0) * 1000, 2)

            depois = set(bpy.data.objects.keys())
            for nome in depois - antes:
                if nome in bpy.data.objects:
                    resultado["objetos_criados"].append(_inspecionar_objeto(bpy.data.objects[nome]))

            resultado["screenshots"] = _capturar_quatro_vistas()

        with _lock:
            resultados[request_id] = resultado
        eventos[request_id].set()

    return 0.1


# ---------------------------------------------------------------------------
# Servidor HTTP
# ---------------------------------------------------------------------------

class _Handler(http.server.BaseHTTPRequestHandler):
    TIMEOUT_S = 60  # mais tempo para 4 renders

    def log_message(self, format, *args):
        return

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path.rstrip("/") == "/cena":
            self._enfileirar_e_responder("descrever", None)
        else:
            self._responder({"erro": f"Rota GET desconhecida: {self.path}"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        corpo  = self.rfile.read(length).decode("utf-8")

        if self.path.rstrip("/") == "/cena":
            self._enfileirar_e_responder("descrever", None)
        else:
            self._enfileirar_e_responder("exec", corpo)

    def _enfileirar_e_responder(self, tipo, dados):
        try:
            request_id = str(uuid.uuid4())
            event = threading.Event()
            with _lock:
                eventos[request_id] = event
            fila_execucao.put((request_id, tipo, dados))

            if not event.wait(timeout=self.TIMEOUT_S):
                self._responder({"sucesso": False, "erro": f"Timeout após {self.TIMEOUT_S}s"})
                return

            with _lock:
                resultado = resultados.pop(request_id, None)
                eventos.pop(request_id, None)

            self._responder(resultado or {"sucesso": False, "erro": "Resultado não encontrado"})
        except Exception as e:
            self._responder({"sucesso": False, "erro": f"Erro no servidor: {e}"})

    def _responder(self, dados):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self._cors()
        self.end_headers()
        self.wfile.write(corpo)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "http://localhost")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


_instancia_servidor = None
_thread_servidor    = None


def iniciar_servidor():
    global _instancia_servidor, _thread_servidor
    if _instancia_servidor is not None:
        return
    _instancia_servidor = http.server.HTTPServer(("localhost", 19000), _Handler)
    _thread_servidor = threading.Thread(target=_instancia_servidor.serve_forever, daemon=True)
    _thread_servidor.start()
    if not bpy.app.timers.is_registered(_processar_fila):
        bpy.app.timers.register(_processar_fila)
    print("MCP 3D Bridge: ativo em http://localhost:19000")
    print("  POST /       → executa script  (retorna métricas + 4 screenshots)")
    print("  GET  /cena   → descreve cena   (retorna texto)")


def parar_servidor():
    global _instancia_servidor
    if _instancia_servidor:
        _instancia_servidor.shutdown()
        _instancia_servidor.server_close()
        _instancia_servidor = None
    if bpy.app.timers.is_registered(_processar_fila):
        bpy.app.timers.unregister(_processar_fila)
    print("Larperian Bridge: parado.")


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

class LARPERIAN_OT_Start(bpy.types.Operator):
    bl_idname  = "larperian.start_bridge"
    bl_label   = "Iniciar Ponte"
    def execute(self, context):
        iniciar_servidor()
        return {"FINISHED"}


class LARPERIAN_OT_Stop(bpy.types.Operator):
    bl_idname  = "larperian.stop_bridge"
    bl_label   = "Parar Ponte"
    def execute(self, context):
        parar_servidor()
        return {"FINISHED"}


class LARPERIAN_PT_Panel(bpy.types.Panel):
    bl_label       = "MCP 3D Bridge"
    bl_idname      = "LARPERIAN_PT_Panel"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "MCP 3D"

    def draw(self, context):
        box = self.layout.box()
        if _instancia_servidor is not None:
            box.label(text="ATIVO  |  localhost:19000", icon="CHECKMARK")
            box.label(text="POST /  →  exec + 4 vistas", icon="IMAGE_DATA")
            box.label(text="GET /cena  →  descreve cena", icon="INFO")
            box.operator("larperian.stop_bridge", text="Desativar", icon="CANCEL")
        else:
            box.label(text="INATIVO", icon="CANCEL")
            box.operator("larperian.start_bridge", text="Ativar", icon="PLAY")


classes = (LARPERIAN_OT_Start, LARPERIAN_OT_Stop, LARPERIAN_PT_Panel)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    iniciar_servidor()


def unregister():
    parar_servidor()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
