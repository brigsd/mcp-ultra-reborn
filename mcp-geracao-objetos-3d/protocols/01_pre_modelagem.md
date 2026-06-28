# Protocolo 01 — Pré-Modelagem

Execute este checklist completo antes de escrever qualquer código de modelagem.
Pular etapas aqui é a principal causa de retrabalho.

---

## Checklist obrigatório

### A. Entender a peça

- [ ] Qual é a **função mecânica** desta peça? (transmite força? veda? gira? suporta carga?)
- [ ] Quais forças ela sofre em uso? (isso determina onde precisamos de mais material/espessura)
- [ ] Como ela se **conecta** a outras peças? (encaixe, parafuso, prensa, solda?)
- [ ] Leu `references/{peca}/meta.json` e entendeu todas as `notas_geometricas`?

### B. Coletar dimensões

```python
# Sempre começa assim:
from catalog.dimensions import NOME_DO_CATALOGO
dim = NOME_DO_CATALOGO["variante_solicitada"]

# Verifique que você tem:
# - dimensão externa principal (raio ou largura)
# - dimensão interna se for oco
# - espessura/altura
# - parâmetros de furos ou padrões radiais
```

- [ ] Todas as dimensões foram obtidas do catálogo?
- [ ] Há dimensões que o catálogo não tem? → calcule a partir das que tem, documente o cálculo
- [ ] As unidades estão em **metros** (padrão Blender)? — 280mm = 0.280

### C. Entender o contexto da cena

```python
# Execute antes de criar qualquer objeto:
from client.send import descrever_cena
print(descrever_cena())
```

- [ ] A cena está vazia ou tem objetos existentes?
- [ ] Se há objetos existentes: a nova peça precisa se encaixar com eles?
- [ ] Qual deve ser a posição de origem da nova peça? (centro do mundo? encostada em outra peça?)

### D. Escolher a estratégia geométrica

Responda a estas perguntas para escolher a abordagem:

| Pergunta | Sim → |
|---|---|
| A peça tem simetria rotacional (parece um torno)? | Protocolo 04 — Peças Rotacionais |
| Tem furos/elementos dispostos em círculo? | Protocolo 05 — Padrões Radiais |
| É uma extrusão de um perfil 2D? | Use `spin()` ou extrude de curve |
| Tem formas orgânicas sem simetria clara? | Subdivide e sculpt — não é foco deste framework por ora |

### E. Planejar a sequência de operações

Escreva em comentário no topo do script antes de começar:

```python
# PEÇA: brake_disc / variante: compacto
# SEQUÊNCIA:
# 1. Cilindro oco (raio_ext=0.140, raio_int=0.065, h=0.022)
# 2. 6 furos de ventilação radiais (r_orbital=0.110, r_furo=0.009)
# 3. Chanfro topo (0.0015m, 2 seg)
# 4. Chanfro base (0.0015m, 2 seg)
# 5. Suavizar (60°)
# 6. Aplicar transformações
# 7. Validar
```

Só comece a codificar depois de ter este plano escrito.

---

## Sinais de que você não está pronto para modelar

- Você não sabe a dimensão principal da peça de cabeça (ainda não consultou o catálogo)
- Você não sabe como a peça se conecta ao restante do conjunto
- Você planeja usar `bpy.ops` porque "é mais rápido" — não é, é mais frágil
- Você vai "ajustar as proporções depois de ver como ficou" — defina antes
