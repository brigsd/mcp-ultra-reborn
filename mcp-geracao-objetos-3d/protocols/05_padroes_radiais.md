# Protocolo 05 — Padrões Radiais

Use este protocolo para: furos de ventilação, furos de parafusos, dentes de engrenagem,
nervuras radiais, qualquer elemento repetido N vezes em círculo.

---

## Conceito

Um padrão radial é um elemento geométrico copiado N vezes em torno de um eixo,
com espaçamento angular uniforme de `360° / N`.

O framework tem `furar_radial()` para o caso mais comum (furos cilíndricos).
Para outros padrões, use `padrao_radial()` ou monte manualmente.

---

## Furos radiais (caso mais comum)

```python
from api.operations import furar_radial
from catalog.dimensions import DISCO_FREIO

dim = DISCO_FREIO["compacto"]

obj = furar_radial(
    obj           = disco,
    quantidade    = dim["qtd_furos_ventilacao"],   # 6
    raio_orbital  = dim["raio_orbital_furos"],     # 0.110 — distância do centro
    raio_furo     = dim["raio_furo_ventilacao"],   # 0.009
    profundidade  = dim["espessura"],              # mesma espessura do disco
    angulo_inicial = 0.0,                          # primeiro furo em 0° (eixo X+)
)
```

**Regra de ouro:** `raio_orbital + raio_furo < raio_ext - 2mm`
Ou seja: o furo não pode "vazar" para fora da borda externa.
E: `raio_orbital - raio_furo > raio_int + 2mm`
O furo não pode "vazar" para dentro do furo central.

---

## Padrão de objetos (duplicar em círculo)

Use quando quer o mesmo objeto sólido repetido em volta de um eixo:

```python
from api.operations import padrao_radial

# Cria o elemento original em posição de 0°
parafuso = criar_parafuso(...)
parafuso.location = (dim["raio_orbital_furos"], 0, dim["espessura"] / 2)

# Duplica em padrão radial (6 vezes)
copias = padrao_radial(parafuso, quantidade=6, eixo="Z", manter_original=False)
# Retorna lista com 6 objetos posicionados a 0°, 60°, 120°, 180°, 240°, 300°
```

---

## Verificação de padrão radial na vista TOPO

Na vista ortográfica TOPO, um padrão radial correto parece:

```
        o       ← furo em 90°
    o       o   ← furos em 30° e 150°
  [    anel   ]
    o       o   ← furos em 210° e 330°
        o       ← furo em 270°
```

O que verificar:
- [ ] Todos os furos têm o mesmo tamanho?
- [ ] O espaçamento angular é uniforme? (deve parecer um relógio simétrico)
- [ ] Nenhum furo está cortando a borda externa ou o furo central?

---

## Cálculo manual de posições (quando não usar furar_radial)

```python
import math

quantidade   = 6
raio_orbital = 0.110
angulo_inicial = 0.0

posicoes = []
for i in range(quantidade):
    angulo = angulo_inicial + (math.tau / quantidade) * i
    x = math.cos(angulo) * raio_orbital
    y = math.sin(angulo) * raio_orbital
    posicoes.append((x, y))

# posicoes[0] = ( 0.110,  0.000)  → 0°
# posicoes[1] = ( 0.055,  0.095)  → 60°
# posicoes[2] = (-0.055,  0.095)  → 120°
# etc.
```

---

## Furos de parafuso de roda (PCD)

O PCD (Pitch Circle Diameter) é o diâmetro do círculo em que os parafusos estão dispostos.
Mais comum: 4x100, 5x112, 5x120 (formato: quantidade x PCD em mm)

```python
# 5x112 significa 5 parafusos em círculo de 112mm de diâmetro
pcd_mm    = 112
quantidade = 5
raio_orbital = (pcd_mm / 2) / 1000   # em metros = 0.056

from catalog.dimensions import PARAFUSO_METRICO
raio_furo = PARAFUSO_METRICO["M12"]["diametro"] / 2 + 0.001  # folga de 1mm
```

---

## Checklist para padrões radiais

- [ ] A quantidade de elementos bate com o catálogo ou especificação?
- [ ] O `raio_orbital` foi obtido do catálogo?
- [ ] Verificou que nenhum elemento ultrapassa as bordas da peça base?
- [ ] Na vista TOPO: o padrão parece uniforme e simétrico?
- [ ] Após os furos: chamou `validar_objeto()` e não há nova non-manifold geometry?
