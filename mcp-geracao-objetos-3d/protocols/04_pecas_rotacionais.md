# Protocolo 04 — Peças Rotacionais

Use este protocolo para: discos, cilindros, anéis, tubos, rolamentos, volantes, engrenagens cilíndricas, molas helicoidais.

**Definição:** qualquer peça cuja geometria pode ser descrita como a rotação de um perfil 2D em torno de um eixo.

---

## Por que peças rotacionais são especiais

São as mais fáceis de acertar **e** as mais fáceis de errar sutilmente.
Fáceis porque têm simetria total que simplifica o código.
Difíceis porque pequenos erros no perfil se propagam 360°, amplificando qualquer desvio.

---

## Abordagem 1 — Primitivo direto (mais simples)

Use quando o perfil é retangular (cilindro, anel, disco plano):

```python
from api.primitives import criar_cilindro_oco
from catalog.dimensions import DISCO_FREIO

dim = DISCO_FREIO["compacto"]
obj = criar_cilindro_oco(
    raio_ext  = dim["raio_ext"],     # 0.140
    raio_int  = dim["raio_int"],     # 0.065
    altura    = dim["espessura"],    # 0.022
    segmentos = 128,
    nome      = "DiscoDFreio",
)
```

Quando usar: disco plano, tubo, aro simples, cubo de roda sem detalhes.

---

## Abordagem 2 — Spin de perfil (mais poderosa)

Use quando o perfil tem forma não-retangular: rolamento, peça com ressaltos, cubo cônico.

```python
import bpy, bmesh
from mathutils import Vector
import math

# 1. Desenhe o perfil 2D no plano XZ (Y=0, X=raio, Z=altura)
#    Cada ponto é (raio, 0, altura_relativa)
perfil_vertices = [
    (0.020, 0, -0.007),   # borda interna inferior
    (0.023, 0, -0.007),   # chanfro interno inferior
    (0.023, 0, -0.005),
    (0.023, 0,  0.005),   # corpo
    (0.023, 0,  0.007),   # chanfro interno superior
    (0.020, 0,  0.007),   # borda interna superior
]

bm = bmesh.new()

# 2. Cria os verts do perfil
verts = [bm.verts.new(Vector(v)) for v in perfil_vertices]

# 3. Conecta em arestas
for i in range(len(verts) - 1):
    bm.edges.new((verts[i], verts[i+1]))

# 4. Faz o spin (revolução 360° em torno do eixo Z)
resultado = bmesh.ops.spin(
    bm,
    geom      = bm.verts[:] + bm.edges[:],
    axis      = Vector((0, 0, 1)),
    cent      = Vector((0, 0, 0)),
    angle     = math.tau,       # 360°
    steps     = 64,             # segmentos
    use_duplicate = False,
)

bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

mesh = bpy.data.meshes.new("Rolamento_PistaInterna")
bm.to_mesh(mesh)
bm.free()
mesh.update()
obj = bpy.data.objects.new("Rolamento_PistaInterna", mesh)
bpy.context.collection.objects.link(obj)
```

---

## Checklist específico para peças rotacionais

### Antes de modelar
- [ ] Identificou o eixo de simetria? (quase sempre Z no Larperian)
- [ ] Tem o perfil completo em mente? Desenhe em papel se necessário
- [ ] Sabe os raios: interno, externo, e raios intermediários se houver ressaltos?

### Durante a modelagem
- [ ] O número de segmentos é adequado para o tamanho da peça? (ver tabela no protocolo 02)
- [ ] Ao usar `spin()`: `remove_doubles` foi aplicado? (o seam do spin cria verts duplicados)
- [ ] Ao usar primitivo: o `raio_int > 0` para criar o furo central?

### Validação específica
Na vista TOPO, a peça deve aparecer como círculos concêntricos perfeitos:
- [ ] Borda externa: círculo uniforme, sem facetamento visível
- [ ] Furo central: círculo interno concêntrico
- [ ] Padrões radiais (furos): espaçamento uniforme visível

Na vista FRENTE:
- [ ] Espessura/altura constante em toda a extensão radial
- [ ] Chanfros visíveis nas quatro arestas externas (topo-ext, topo-int, base-ext, base-int)

---

## Erros típicos em peças rotacionais

**Furo central ausente ou muito pequeno**
```
Causa: raio_int = 0 ou muito próximo de zero
Efeito: parece um disco sólido sem furo
Fix: sempre defina raio_int a partir do catálogo
```

**Disco "torto" (não perpendicular ao eixo Z)**
```
Causa: objeto importado ou criado com rotação não-zero
Fix: aplicar_transformacoes(obj) antes de qualquer operação
```

**Facetamento visível nas bordas circulares**
```
Causa: poucos segmentos (< 32 para peças visíveis)
Fix: aumente segmentos; aplique suavizar_objeto(obj, 60°)
```

**Seam visível após spin()**
```
Causa: verts duplicados na junção do spin (0° = 360°)
Fix: bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
```
