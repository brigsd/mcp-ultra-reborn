"""
Validação geométrica — a IA chama isto antes de finalizar uma peça.
Retorna um dict com diagnóstico completo da malha.
"""

import bpy
import bmesh
from mathutils import Vector
import math


def validar_objeto(obj: bpy.types.Object) -> dict:
    """
    Retorna um relatório completo sobre a saúde geométrica do objeto.
    Use antes de enviar uma peça ao montador ou antes de renderizar.
    """
    if obj.type != "MESH" or not obj.data:
        return {"valido": False, "erro": f"Objeto '{obj.name}' não é MESH"}

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()

    relatorio = {
        "nome": obj.name,
        "valido": True,
        "avisos": [],
        "erros": [],
        "metricas": {},
    }

    # --- Métricas básicas ---
    relatorio["metricas"] = {
        "vertices": len(bm.verts),
        "arestas": len(bm.edges),
        "faces": len(bm.faces),
        "triangulos": sum(1 for f in bm.faces if len(f.verts) == 3),
        "quads": sum(1 for f in bm.faces if len(f.verts) == 4),
        "ngons": sum(1 for f in bm.faces if len(f.verts) > 4),
        "dimensoes": list(obj.dimensions),
        "volume": bm.calc_volume(),
        "area_superficie": sum(f.calc_area() for f in bm.faces),
    }

    # --- Erros ---
    verts_nao_manifold = [v.index for v in bm.verts if not v.is_manifold]
    if verts_nao_manifold:
        relatorio["erros"].append({
            "tipo": "non_manifold",
            "descricao": f"{len(verts_nao_manifold)} vértices não-manifold",
            "indices": verts_nao_manifold[:20],
        })
        relatorio["valido"] = False

    # Faces com normais invertidas (detecta por comparação de vizinhos)
    faces_problema = []
    for face in bm.faces:
        centro = face.calc_center_median()
        for aresta in face.edges:
            faces_adj = aresta.link_faces
            for f_adj in faces_adj:
                if f_adj is face:
                    continue
                if face.normal.dot(f_adj.normal) < -0.9:
                    faces_problema.append(face.index)
                    break
    if faces_problema:
        relatorio["avisos"].append({
            "tipo": "normais_suspeitas",
            "descricao": f"{len(set(faces_problema))} faces com normais potencialmente invertidas",
        })

    # --- Avisos ---
    if relatorio["metricas"]["ngons"] > 0:
        relatorio["avisos"].append({
            "tipo": "ngons",
            "descricao": f"{relatorio['metricas']['ngons']} n-gons (podem causar problemas em subdivisão)",
        })

    escala = obj.scale
    if max(abs(s - 1.0) for s in escala) > 0.001:
        relatorio["avisos"].append({
            "tipo": "escala_nao_aplicada",
            "descricao": f"Escala não aplicada: {list(escala)}. Use aplicar_transformacoes().",
        })

    if relatorio["metricas"]["volume"] < 0:
        relatorio["erros"].append({
            "tipo": "volume_negativo",
            "descricao": "Volume negativo — normais provavelmente invertidas globalmente.",
        })
        relatorio["valido"] = False

    # Vértices duplicados
    bm2 = bm.copy()
    bmesh.ops.remove_doubles(bm2, verts=bm2.verts, dist=0.0001)
    delta = len(bm.verts) - len(bm2.verts)
    if delta > 0:
        relatorio["avisos"].append({
            "tipo": "vertices_duplicados",
            "descricao": f"{delta} vértices duplicados detectados. Use remove_doubles.",
        })
    bm2.free()

    bm.free()
    return relatorio


def relatorio_para_texto(relatorio: dict) -> str:
    """Formata o relatório de validação como texto legível."""
    linhas = [f"=== Validação: {relatorio.get('nome', '?')} ==="]
    status = "OK" if relatorio.get("valido") else "FALHOU"
    linhas.append(f"Status: {status}")

    m = relatorio.get("metricas", {})
    if m:
        linhas.append(f"Vértices: {m.get('vertices')}  |  Faces: {m.get('faces')}  |  N-gons: {m.get('ngons')}")
        linhas.append(f"Dimensões (m): {[round(d, 4) for d in m.get('dimensoes', [])]}")
        linhas.append(f"Volume: {round(m.get('volume', 0), 6)} m³")

    for e in relatorio.get("erros", []):
        linhas.append(f"[ERRO] {e['tipo']}: {e['descricao']}")
    for a in relatorio.get("avisos", []):
        linhas.append(f"[AVISO] {a['tipo']}: {a['descricao']}")

    return "\n".join(linhas)
