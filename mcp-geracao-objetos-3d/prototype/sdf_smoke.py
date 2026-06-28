"""
Primeira fatia vertical do Larperian (prova de conceito do lado orgânico).
Fluxo: a IA "escreve" um SDF -> marching cubes vira malha -> checagem de validade.
Sem Blender ainda; só prova que geração orgânica + verificação de validade rodam.

Rodar:  .venv/Scripts/python.exe prototype/sdf_smoke.py
"""

import os
from sdf import sphere, capsule, X, Y, Z   # se isto falhar, o pacote 'sdf' é o errado (usar fogleman/sdf)

OUT = os.path.join(os.path.dirname(__file__), "out_blob.stl")


def gerar_blob():
    """Um 'blob' orgânico: corpo + duas protuberâncias fundidas com união suave."""
    corpo = sphere(1.0)
    cabeca = sphere(0.55).translate((0.9, 0.0, 0.3))
    # membro começa DENTRO do corpo (-X*0.3) e sai pra fora (-X*1.3) — garante sobreposição
    membro = capsule(-X * 0.3, -X * 1.3 - Z * 0.2, 0.22)
    # união suave (k) = transição orgânica, sem aresta dura — o que dá "cara de bicho"
    f = corpo.union(cabeca, k=0.25).union(membro, k=0.25)
    return f


def main():
    f = gerar_blob()
    # marching cubes -> malha -> STL. step = tamanho do voxel (menor = mais fino/lento)
    f.save(OUT, step=0.04)
    print(f"[gerou] {OUT}")

    import trimesh
    m = trimesh.load(OUT)
    print("=== checagem de validade (camada 0) ===")
    print(f"vertices            : {len(m.vertices)}")
    print(f"faces               : {len(m.faces)}")
    print(f"watertight (fechada): {m.is_watertight}")
    print(f"winding consistente : {m.is_winding_consistent}")
    print(f"is_volume (solido ok): {m.is_volume}")
    print(f"euler number        : {m.euler_number}")
    print(f"volume              : {round(float(m.volume), 4)}")
    print(f"componentes (split) : {len(m.split(only_watertight=False))}")


if __name__ == "__main__":
    main()
