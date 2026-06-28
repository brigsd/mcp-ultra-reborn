# Protocolo 03 — Validação

Execute este checklist após modelar. A peça só está pronta quando todos os itens estiverem OK.

---

## Checklist de validação

### Nível 1 — Automático (via código)

```python
from api.validators import validar_objeto, relatorio_para_texto
import bpy

obj = bpy.data.objects["NomeDaPeca"]
rel = validar_objeto(obj)
print(relatorio_para_texto(rel))
```

- [ ] `rel["valido"]` é `True`?
- [ ] Nenhum erro de `non_manifold`?
- [ ] Nenhum erro de `volume_negativo`?
- [ ] Avisos de `ngons`: aceitável se < 5% do total de faces e não em superfícies curvas principais
- [ ] Aviso de `escala_nao_aplicada`: NUNCA aceitável — sempre corrija com `aplicar_transformacoes()`
- [ ] Aviso de `vertices_duplicados`: corrija com `bmesh.ops.remove_doubles`

### Nível 2 — Visual (via screenshots)

Os 4 screenshots são retornados automaticamente pelo bridge. Examine cada um:

**Vista FRENTE (ortográfica)**
- [ ] A silhueta bate com o esperado para esta peça?
- [ ] Proporções largura × altura parecem corretas para a variante?
- [ ] Não há geometria "vazando" fora do volume esperado?

**Vista LADO (ortográfica)**
- [ ] A profundidade/espessura está correta?
- [ ] A peça não está achatada nem excessivamente espessa?

**Vista TOPO (ortográfica)**
- [ ] A simetria radial está presente onde deveria estar?
- [ ] Os furos/padrões radiais estão uniformemente distribuídos?
- [ ] O furo central tem o diâmetro correto em relação ao diâmetro externo?

**Vista PERSPECTIVA**
- [ ] A peça tem aparência coerente com o objeto real?
- [ ] Chanfros estão visíveis nas bordas onde foram aplicados?
- [ ] A suavização está aplicada (sem facetamento visível em superfícies curvas)?

### Nível 3 — Dimensional

Compare as dimensões retornadas pelo bridge com o catálogo:

```python
# Dimensões retornadas pelo bridge estão em metros
# Tolerância aceitável: ±2mm (0.002m) em dimensões principais

dim_real   = obj.dimensions  # [largura, profundidade, altura]
dim_esperada = [
    dim["raio_ext"] * 2,   # diâmetro externo
    dim["raio_ext"] * 2,   # deve ser igual (simetria)
    dim["espessura"],
]
for i, (r, e) in enumerate(zip(dim_real, dim_esperada)):
    desvio = abs(r - e)
    status = "OK" if desvio < 0.002 else f"DESVIO {round(desvio*1000,1)}mm"
    print(f"  dim[{i}]: real={round(r*1000,1)}mm  esperado={round(e*1000,1)}mm  {status}")
```

- [ ] Dimensão X dentro da tolerância?
- [ ] Dimensão Y dentro da tolerância?
- [ ] Dimensão Z (espessura/altura) dentro da tolerância?

### Nível 4 — Relações com outras peças

Se a peça faz parte de um conjunto:

- [ ] A peça cabe no espaço disponível? (sem sobreposição com peças existentes)
- [ ] As folgas estão respeitadas? (consulte `references/{peca}/meta.json → relacoes_com_outras_pecas`)
- [ ] Os furos de fixação estão alinhados com os da peça correspondente?

---

## O que fazer quando a validação falha

| Problema | Causa mais provável | Solução |
|---|---|---|
| `non_manifold` | Booleano com geometria não fechada | Verifique se o cortador era uma malha fechada (watertight) |
| `volume_negativo` | Normais globalmente invertidas | `bmesh.ops.recalc_face_normals(bm, faces=bm.faces)` |
| `escala_nao_aplicada` | Join ou import sem aplicar | `aplicar_transformacoes(obj)` |
| `vertices_duplicados` | Booleano ou join criou sobreposição | `bmesh.ops.remove_doubles(bm, dist=0.0001)` |
| Dimensão errada (>5%) | Unidade errada (mm em vez de m) | Verifique se todas as entradas estão em metros |
| Silhueta estranha | Booleano não cortou onde devia | Confirme posição do cortador antes do booleano |
