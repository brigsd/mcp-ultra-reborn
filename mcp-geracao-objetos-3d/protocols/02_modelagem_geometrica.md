# Protocolo 02 — Modelagem Geométrica

Referência para usar durante a escrita do código.
Regras, padrões e armadilhas comuns.

---

## Estrutura padrão de um script de peça

```python
# 1. PATH — sempre primeiro para os imports funcionarem
import sys, os
sys.path.insert(0, r"C:\Users\tiago\Desktop\Larperian")

# 2. IMPORTS do framework
from catalog.dimensions import DISCO_FREIO
from api import (
    criar_cilindro_oco, furar_radial,
    chanfrar_arestas, suavizar_objeto,
    aplicar_transformacoes, validar_objeto, relatorio_para_texto
)

# 3. DIMENSÕES — sempre do catálogo
dim = DISCO_FREIO["compacto"]

# 4. CRIAÇÃO — sequência lógica documentada
obj = criar_cilindro_oco(
    raio_ext  = dim["raio_ext"],
    raio_int  = dim["raio_int"],
    altura    = dim["espessura"],
    segmentos = 128,
    nome      = "DiscoDFreio",
)

# 5. OPERAÇÕES sobre o objeto
obj = furar_radial(obj, ...)
chanfrar_arestas(obj, "circulares_topo", largura=0.0015)

# 6. FINALIZAÇÃO
suavizar_objeto(obj, angulo_graus=60.0)
aplicar_transformacoes(obj)

# 7. VALIDAÇÃO — obrigatória
relatorio = validar_objeto(obj)
print(relatorio_para_texto(relatorio))
```

---

## Regras de modelagem

### Segmentos e resolução

| Tipo de superfície | Segmentos recomendados |
|---|---|
| Cilindro principal (visível) | 64 – 128 |
| Furo de ventilação | 24 – 32 |
| Chanfro | 2 – 3 |
| Torus | 48 maior × 16 menor |

Não use mais segmentos que o necessário — cada booleano multiplica a contagem.
Não use menos que 32 em superfícies circulares principais — facetamento fica visível.

### Ordem das operações (nunca inverta)

```
forma base → furos/subtrações → chanfros → suavização → aplicar transformações → validar
```

Chanfro ANTES de aplicar transformações → as arestas ainda estão em coordenadas locais corretas.
Booleano DEPOIS de ter a forma base completa → mais fácil identificar origem de erros.

### Unidades

Tudo em **metros**. Exemplos:
- 280mm → `0.280`
- 22mm  → `0.022`
- 1.5mm → `0.0015`

### Posicionamento

- A peça principal do conjunto fica na origem `(0, 0, 0)`
- Peças secundárias são posicionadas em relação a ela usando `posicionar(obj, x, y, z)`
- O eixo Z aponta para cima — a face frontal de discos e rodas fica em Z positivo

---

## Armadilhas conhecidas

### booleano que silencia sem erro
```python
# ERRADO — booleano pode não ter intersecção e não avisar
obj = aplicar_booleano(base, cortador)

# CORRETO — verifique contagem de vértices antes e depois
n_antes = len(base.data.vertices)
obj = aplicar_booleano(base, cortador)
n_depois = len(obj.data.vertices)
if abs(n_depois - n_antes) < 10:
    print("AVISO: booleano pode não ter cortado nada")
```

### `exec()` sem path configurado
O bridge executa código com `exec()`. Se o sys.path não estiver configurado,
os imports do framework falham silenciosamente em alguns contextos.
**Sempre inclua no topo do script:**
```python
import sys
sys.path.insert(0, r"C:\Users\tiago\Desktop\Larperian")
```

### Escala não aplicada após join
Depois de `juntar_objetos()`, sempre chame `aplicar_transformacoes()`.
O join pode introduzir escala implícita.

### Normais após booleano
Todo booleano pode inverter normais localmente. A função `aplicar_booleano()`
já faz `recalc_face_normals`, mas verifique sempre no relatório de validação.

---

## Quando a geometria não parece certa

1. Verifique os screenshots das 4 vistas — qual vista mostra o problema?
2. Chame `validar_objeto()` e leia o relatório completo
3. Se há non-manifold: provavelmente booleano com objetos não-coincidentes
4. Se há n-gons inesperados: booleano cortou uma face circular, gerando polígono complexo
5. Se as dimensões no relatório diferem do catálogo em >5%: verifique se `aplicar_transformacoes()` foi chamado
