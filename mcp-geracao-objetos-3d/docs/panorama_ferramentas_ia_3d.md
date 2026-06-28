# Larperian: panorama estratégico — estamos reinventando a roda?

> Gerado por workflow de levantamento (5 finders web + síntese, 48 achados).
> Data: 2026-06-20. Claims sobre blender-mcp, SceneCraft e LL3M verificados diretamente;
> preprints de 2026 e o MCP oficial da Blender (403 na verificação) ficam como confiança média.

Resposta curta: **parcialmente, e nas partes erradas se você construir tudo do zero.** O chassi
já existe e é popular; o diferencial que você escolheu (loop autônomo + verificação métrica +
modularidade por domínio) é genuinamente pouco ocupado.

---

## 1. O que JÁ EXISTE pronto, por maturidade

**Produção / popular (dá pra plugar hoje):**

- **blender-mcp (ahujasid)** — ~23k stars, *confirmado*. Conecta qualquer LLM ao Blender por
  socket, expõe o loop: criar/modificar/deletar objetos, materiais, luz, **executar Python
  arbitrário**, ler estado da cena, **capturar screenshot do viewport** pra iterar. Integra
  geração de assets (PolyHaven, Sketchfab, Hyper3D Rodin, Hunyuan3D). O caminho mais direto pra
  um agente modelar 3D de propósito geral. https://github.com/ahujasid/blender-mcp
  - **Mas:** o "ver-e-corrigir" é **parcial e não autônomo** — quem julga a screenshot é o humano.
    Python arbitrário é poderoso e perigoso. Frágil em cenas complexas.
- **BlenderGPT (gd3kr)** — ~4.9k stars. One-shot, sem loop de correção real.
  https://github.com/gd3kr/BlenderGPT
- **MCP oficial da Blender Foundation** — *confiança baixa, 403 na verificação, não-confirmado.*
  Indícios de um MCP oficial experimental pra inspeção de cena, execução de código, render e
  navegação de UI. Se real, sinaliza que o loop agente-Blender está virando infraestrutura de
  primeira classe. https://www.blender.org/lab/mcp-server/

**Harness experimental:**

- **PatrykIti/blender-ai-mcp** — ~36 stars. O único da família MCP que mira auto-verificação
  explícita, mas imaturo. https://github.com/PatrykIti/blender-ai-mcp
- **djeada/blender-mcp-server** — ~22 ferramentas. https://github.com/djeada/blender-mcp-server
- **LL3M (threedle)** — ~539 stars, *confirmado*. Multi-agente que escreve bpy em três fases
  (criação, refinamento automático, refinamento guiado), com auto-crítica por código E visual.
  **Caveat:** servidor descontinuado porque o modelo do paper (Sonnet 3.7) foi aposentado.
  https://github.com/threedle/ll3m

**Harness de CAD em loop fechado (vizinho, não-Blender, mas instrutivo):**

- **text-to-cad (cedrickchee fork)** — MIT, feito pra Claude Code. Loop: edita fonte build123d,
  regenera, renderiza "quick review images", inspeciona, exporta STEP/STL/GLB/URDF.
  https://github.com/cedrickchee/text-to-cad
- **CADSmith / AutoFab (jabarkle)** — *match forte de arquitetura*: cinco agentes, **duas malhas
  de correção aninhadas** (interna = erro de execução; externa = divergência geométrica, até 5
  iterações), validação **exata do kernel OpenCASCADE** (volume, faces, validade) + **3 vistas
  renderizadas pra um VLM Judge** + métricas (Chamfer, IoU). Opus julga, Sonnet gera — pra não
  "corrigir a própria prova". https://github.com/jabarkle/CADSmith

**Comercial fechado:**

- **Moonlake 3D Agent** — technical artist DENTRO do Blender (computer use). *Confiança baixa,
  anúncio sem benchmark.* https://moonlakeai.com/blog/3d-agent

---

## 2. Estamos reinventando a roda?

**Construir em cima (não reinvente):**
- A **ponte agente↔Blender** (socket/MCP, executar bpy, ler cena, capturar render). blender-mcp
  já é padrão de fato.
- A **arquitetura gerador-de-edição + avaliador-de-estado** sobre renders. SceneCraft (ICML24,
  +45% CLIP vs BlenderGPT) e BlenderAlchemy (ECCV24) são a referência canônica, *verificadas*.
- **Geometry Nodes / bmesh / Cycles headless por script** — totalmente programável, com DSLs
  prontas (geometry-script, geonodes, NodeToPython).

**Onde você é genuinamente novo:**
- **Loop de auto-correção AUTÔNOMO** (sem humano avaliando screenshot). Em produção o humano
  fecha o loop; o autônomo real só vive em protótipos de pesquisa não plugáveis.
- **Verificação MÉTRICA / por-restrição como espinha**, não só perceptual. Quase todo mundo
  valida com "VLM olha o render". Essa é a alavanca mais subexplorada.
- **Modularidade por domínio** (mecânico paramétrico vs orgânico malha) com verificação distinta
  por domínio. Os trabalhos existentes tendem a um paradigma só.

**Veredito: o motor base existe, o diferencial não.**

---

## 3. O teto real de controle do Blender pra IA

**A camada de DADOS é quase 100% programável; as paredes reais são GPU-context, contexto-de-UI e
ferramentas modais.**

**O que DÁ por script:**
- Todo o modelo de cena via `bpy.data` / `bpy.types` / `bmesh`: objetos, malhas, materiais, node
  trees, modifiers, constraints, animação, partículas, física, compositing. Tudo que se edita
  como **dado** é alcançável headless.
- **Geometry Nodes 100% por código.** *Caveat:* IDs de tipo/socket mudam entre versões — script
  gerado é **frágil por versão**.
- **Headless de verdade:** `blender -b -P script.py`, `--python-exit-code` propaga exceção.
- **Render final pra arquivo:** `bpy.ops.render.render(write_still=True)`. **Cycles roda
  totalmente headless** (CPU ou GPU, sem display). Caminho confiável pra "renderizar pra ver".
- Export de todos os formatos. *Caveat:* IDs de operador mudaram 3.x→4.x.
- **`pip install bpy`** embute o Blender no processo Python. **Um .blend por processo, threads
  Python não suportadas** (paralelismo = multiprocessing).

**O que NÃO dá de forma confiável (as três paredes):**
1. **GPU/GL em puro `--background`.** EEVEE é OpenGL-only e historicamente não renderiza headless
   no Windows/macOS. `gpu.offscreen` + `draw_view3d()` (captura rápida de viewport) precisa de
   contexto GL vivo — que background não tem. **É o limite mais carregante pro loop de feedback.**
2. **Operadores presos a contexto de UI.** `bpy.ops` agem sobre `bpy.context`; `poll()` falha sem
   área/região/seleção certa. **Padrão confiável: data-API primeiro, `temp_override` só quando não
   há equivalente de dado.**
3. **Ferramentas modais/escultura.** Escultura, pintura, transform interativo, knife — esperam
   stroke/evento vivos. **Não há data-API limpa pra esculpir proceduralmente.**

**Implicação direta pro Larperian:**
- Pro feedback visual, **use Cycles-pra-arquivo ou um Blender vivo (com display/GPU)** — não puro
  headless com `gpu.offscreen`. Os MCPs em produção dirigem um Blender **vivo** justamente por isso.
- Pro domínio **orgânico**, gere via Geometry Nodes/bmesh, **não via escultura** (parede dura).

---

## 4. A frente acadêmica IA→3D (malha/cena)

O campo **bifurcou em dois paradigmas com validações diferentes:**

**(A) CÓDIGO-COMO-3D** — agente escreve Python e se auto-corrige por crítico visual + erro de runtime:
- **SceneCraft** (ICML24, *verificado*) — scene graph → restrições numéricas → VLM critica render →
  refina script. A arquitetura-referência. https://arxiv.org/abs/2403.01248
- **LL3M** (2025, *verificado*) — multi-agente com BlenderRAG (grounding na doc da API).
  https://arxiv.org/abs/2508.08228
- **3D-GPT** (2023) — precursor, loop fraco. https://arxiv.org/abs/2310.12945
- **BlenderAlchemy** (ECCV24) — edit-generator + state-evaluator visuais. https://arxiv.org/abs/2404.17672

**(B) GERAÇÃO NATIVA DE MALHA** — LLM emite tokens de malha direto:
- **LLaMA-Mesh** (NVIDIA) — coords como texto. https://arxiv.org/abs/2411.09595
- **MeshAnything v1/v2** (ICLR25) — malhas "de artista". https://arxiv.org/pdf/2406.10163
- **Mesh-RFT** (NeurIPS25) — *o mais relevante pro seu diferencial*: validação geométrica **como
  reward por face** (Boundary Edge Ratio, Topology Score), -24.6% Hausdorff. https://arxiv.org/abs/2505.16761

**Pra CENAS, o padrão é LLM-propõe-restrição → solver resolve:**
- **Holodeck** (CVPR24) — GPT-4 gera restrições, solver otimiza layout. https://arxiv.org/abs/2312.09067
- **LayoutVLM / IL3D** — VLM + otimização diferenciável. https://arxiv.org/html/2510.12095v1

**Achados que valem ouro:**
- **VLM cru critica render geometricamente MAL.** O padrão Scene-VLM descobriu que é preciso
  **injetar pistas visuais** (setas de eixo, círculos de clearance) pro crítico detectar erro de
  orientação/proximidade. **Render + VLM sozinho é frágil pra geometria.**
- **IR3D-Bench** diagnostica: o gargalo é **falta de precisão visual** do agente — quando ele não
  distingue diferenças finas entre render e alvo, **estanca na auto-correção**. Código+dataset
  liberados. https://arxiv.org/abs/2506.23329
- Gyms de RL (RLCAD, ToolCAD, Hephaestus) existem mas são pra treinar política, não pra plugar
  agente de chat. Hephaestus: loop fechado sobe GPT de 38.8% → 60.5%. *Confiança média (preprints 2026).*

**O buraco:** auto-correção **MÉTRICA de geometria orgânica costurada num loop de agente**. O
rigoroso existe solto (manifoldness, watertight, self-intersection, Mesh-RFT) mas **ninguém amarrou
esses checks num loop de agente conversacional pra malha**. A validação de cena via solver
(Holodeck) é métrica, mas pra *layout*, não pra *forma do objeto*. **Esse é exatamente o seu vão.**

---

## 5. Veredito de paradigma

**Confiança alta:** o paradigma central está certo. Ficar no Blender, loop de verificação como
espinha, geração como código interpretável (não malha-token opaca) — alinhado com a linha mais
forte da pesquisa e com o que funciona em produção. Código interpretável dá editabilidade e
debugabilidade que o nativo-de-malha não dá.

**Dois ajustes (confiança alta):**
1. **Não dependa de feedback visual em puro `--background`.** É parede de GPU-context. Use
   Cycles-pra-arquivo ou um Blender vivo. Decida cedo — afeta toda a infra.
2. **Verificação perceptual sozinha é insuficiente.** Scene-VLM e IR3D-Bench provaram que
   VLM-no-render é geometricamente cego pra detalhe fino. O solver de restrição + checks métricos
   não é "feature extra" — é o que tira você do platô onde os outros estancam.

**O contra (onde seu plano pode estar errado):**
- **"Só Blender" pode ser um teto disfarçado de decisão.** Pro mecânico paramétrico, o ecossistema
  CAD (OpenCASCADE/build123d) já tem validação exata de kernel e FEA no loop que o Blender não
  oferece nativamente. Vale considerar Blender como front-end de cena/orgânico e um kernel CAD como
  back-end de verificação mecânica. Tensão real com sua decisão — não engulo o "só Blender" de graça.
- **Modularidade por domínio pode virar dois produtos meio-feitos.** Mitigação: o loop de
  verificação é o componente compartilhado; os geradores divergem, o verificador unifica.
- **Concordância à toa que evito:** seria fácil dizer "vai fundo, é tudo novo". Não é. O chassi é
  commodity. Seu valor está num ponto estreito (verificação métrica autônoma) — se ele não
  funcionar, você vira mais um wrapper de blender-mcp.

---

## 6. Próximos passos, em ordem de alavanca

1. **Estude blender-mcp como chassi, não reescreva a ponte.** Adote o transporte e gaste seu tempo
   no que falta. Maior alavanca por menor custo. https://github.com/ahujasid/blender-mcp
2. **Decida o caminho de render-feedback agora:** Cycles-pra-arquivo (headless confiável) vs Blender
   vivo (viewport rápido, precisa display). Trava sua infra.
3. **Construa o verificador métrico como módulo central** (sua alavanca real). Comece pelos checks
   prontos: manifold/watertight/self-intersection pro orgânico; bbox/volume/validade de sólido pro
   paramétrico. Costure num loop de agente — é o que ninguém empacotou.
4. **Roube a arquitetura gerador+crítico de SceneCraft/LL3M e o juiz-separado de CADSmith** (modelo
   forte julga, gerador propõe). https://github.com/jabarkle/CADSmith
5. **Antecipe a cegueira geométrica do VLM:** injete pistas visuais no render (eixos, clearance,
   multi-ângulo). Lição de Scene-VLM e IR3D-Bench.
6. **Use IR3D-Bench (código+dataset liberados) como benchmark de loop fechado.**
   https://github.com/LiuHengyu321/IR3D-Bench
7. **Reavalie "só Blender" pro mecânico** depois do passo 3: se a verificação métrica mecânica no
   Blender ficar fraca, plugue um kernel CAD como back-end. Mantenha a porta aberta.
