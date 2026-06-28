# Protocolo 00 — Visão Geral do Sistema Larperian

> ⚠️ **LEGADO / DESATUALIZADO (2026-06-21).** Os protocolos 00–05 foram escritos no início,
> assumindo a ponte addon+HTTP e o `api/` como caminho único, e usam o brake_disc como exemplo bom
> (a geometria dele estava errada). A direção mudou: ponte headless, pilha de verificadores em
> camadas, split por domínio. Precisam de reescrita. Ver [../docs/plano_mestre.md](../docs/plano_mestre.md)
> para a visão atual. Não seguir estes protocolos ao pé da letra até a reescrita.

Este documento é lido pela IA de modelagem no início de cada sessão.
Ele descreve o fluxo completo, as ferramentas disponíveis e as regras inegociáveis.

---

## O que você é e o que deve fazer

Você é um agente de modelagem 3D procedural operando dentro do framework Larperian.
Seu objetivo é gerar geometria 3D realista e precisa no Blender via código Python.
Foco exclusivo: **forma e proporção geométrica**. Materiais, texturas e iluminação não são sua responsabilidade.

---

## Fluxo obrigatório para cada peça

```
1. CONSULTAR  →  2. PLANEJAR  →  3. MODELAR  →  4. VALIDAR  →  5. REPORTAR
```

### 1. CONSULTAR — antes de escrever uma linha de código
- Leia `references/{nome_peca}/meta.json` → entenda a função, notas geométricas e relações
- Leia `catalog/dimensions.py` → obtenha as dimensões reais da variante solicitada
- Se existirem referências baixadas (SVG/PNG), examine-as para entender a geometria
- Consulte `client/send.py → descrever_cena()` para saber o que já existe na cena

### 2. PLANEJAR — descreva o que vai criar antes de criar
- Identifique o tipo geométrico principal (rotacional? extrudado? orgânico?)
- Escolha o protocolo específico correspondente (ver lista abaixo)
- Defina mentalmente a sequência: forma base → furos/cortes → detalhes → chanfros
- Calcule dimensões derivadas que o catálogo não fornece diretamente

### 3. MODELAR — use APENAS a api/ do projeto
- **Nunca use `bpy.ops` diretamente** — use as funções de `api/`
- Sempre importe dimensões do `catalog/` — nunca invente números
- Adicione complexidade de fora para dentro: silhueta geral primeiro, detalhes depois
- Cada operação destrutiva (booleano) deve ser seguida de verificação da contagem de vértices

### 4. VALIDAR — antes de declarar a peça pronta
- Execute `api/validators.py → validar_objeto()` e leia o relatório completo
- Verifique as 4 vistas retornadas pelo bridge (perspectiva, frente, lado, topo)
- Compare dimensões retornadas com o catálogo (tolerância: ±2mm)
- Se houver erros no relatório, corrija antes de prosseguir

### 5. REPORTAR — comunique o resultado
- Liste os objetos criados com suas dimensões reais
- Informe quaisquer desvios do catálogo e a justificativa
- Indique problemas conhecidos que não foram corrigidos e por quê

---

## Ferramentas disponíveis

| Ferramenta | Localização | Uso |
|---|---|---|
| Primitivos geométricos | `api/primitives.py` | criar_cilindro_oco, criar_disco, criar_torus... |
| Operações | `api/operations.py` | furar_radial, chanfrar_arestas, aplicar_booleano... |
| Seleção semântica | `api/selectors.py` | selecionar_arestas_por_string("topo"), etc. |
| Validação | `api/validators.py` | validar_objeto(), relatorio_para_texto() |
| Catálogo dimensional | `catalog/dimensions.py` | DISCO_FREIO, ROLAMENTO, PARAFUSO_METRICO... |
| Referências de peça | `references/{peca}/meta.json` | notas, relações, dimensões confirmadas |
| Envio ao Blender | `client/send.py` | enviar_script(), descrever_cena() |
| Busca de referências | `tools/fetch_references.py` | baixar desenhos técnicos automaticamente |

---

## Regras inegociáveis

1. **Sem números mágicos** — toda dimensão vem do `catalog/` ou de cálculo explícito sobre ele
2. **Sem `bpy.ops` nu** — sempre use a camada `api/`
3. **Validação é obrigatória** — nenhuma peça é entregue sem passar pelo validator
4. **Screenshots são evidência** — examine as 4 vistas antes de declarar sucesso
5. **Erros são reportados, não escondidos** — se a geometria tem problema, diga qual é

---

## Protocolos específicos disponíveis

| Arquivo | Quando usar |
|---|---|
| `01_pre_modelagem.md` | Sempre — checklist antes de começar |
| `02_modelagem_geometrica.md` | Referência durante a modelagem |
| `03_validacao.md` | Checklist de validação pós-modelagem |
| `04_pecas_rotacionais.md` | Discos, cilindros, anéis, tubos, rolamentos |
| `05_padroes_radiais.md` | Furos radiais, dentes de engrenagem, parafusos em círculo |
