# Rascunho de ideias — Larperian

> Documento vivo. Caderno de anotações, não especificação final. Vai mudando conforme a
> gente decide. Última atualização: 2026-06-20.
>
> **Visão de topo consolidada: [plano_mestre.md](plano_mestre.md)** (mapa conectivo, revisões,
> frentes em aberto). Este rascunho vira o caderno de ideias soltas; o plano-mestre é a referência.
> Outras leituras: [pesquisa_ia_3d.md](pesquisa_ia_3d.md), [panorama_ferramentas_ia_3d.md](panorama_ferramentas_ia_3d.md),
> [pesquisa_prova_forma.md](pesquisa_prova_forma.md), [verificadores_plugaveis.md](verificadores_plugaveis.md).

---

## 0. A grande foto

O objetivo é uma IA que gera objetos 3D no Blender com **precisão geométrica** (forma,
proporção, topologia), não textura/cor. O que faz isso funcionar não é a IA "acertar de
primeira" — é o **loop**: gerar → rodar → ver/medir → corrigir → repetir.

Três peças:
1. **A ponte** — como a IA fala com o Blender, executa, e recebe de volta render + métricas.
2. **Os geradores** — como cada tipo de objeto vira geometria. Modular por domínio.
3. **O verificador (a espinha)** — o que mede se ficou certo e devolve isso pra IA corrigir.

Decisão de fundo: **a espinha (loop + verificação) é compartilhada; os geradores divergem
por domínio.**

---

## 1. A ponte (conexão IA ↔ Blender)

### O que já sabemos
- Blender instalado via Steam: `C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe` (v5.1.2).
- Dirigir por **dado/código (bpy)**, nunca por automação de GUI (clicar/screenshot da tela).
  Confirmado pela própria doutrina do Lente: "tem API? usa a API."
- **blender-mcp** (ahujasid, ~23k stars) — REBAIXADO de "chassi" pra referência. Ele dirige um
  Blender VIVO por socket; como decidimos render headless, a gente chama `blender --background`
  direto e quase não precisa dele. Estudar a superfície de ferramentas, não usar como base.
  (ver [plano_mestre.md](plano_mestre.md) §2)

### A decisão mais urgente: caminho do render-feedback
A IA precisa "ver" o que fez. Tem uma parede técnica aqui:
- **Headless puro (`blender --background`)** → screenshot rápido de viewport **NÃO funciona**
  (precisa de contexto GPU/GL que o headless não tem). EEVEE idem.
- **Render do Cycles pra arquivo** → **funciona** headless (CPU ou GPU). Mais lento, mas confiável.
- **Blender vivo (aberto, com display)** → viewport rápido funciona. É o que os MCPs em produção
  fazem. Custo: precisa do Blender aberto.

→ **DECIDIDO (2026-06-20): começar com Cycles-pra-arquivo** (headless confiável, automático, sem
  janela aberta). A lentidão a gente resolve depois se incomodar. **Caveat do teste de addons:** se
  em algum momento a gente precisar de addon preso à GUI, aí cai pro Blender vivo — mas como o plano
  é escrever nossa própria auditoria (bmesh) e preferir geradores por operador, o headless segue
  viável. Blender vivo fica como plano B.

### Ideias soltas pra ponte
- Render **multi-view** (4 vistas: perspectiva, frente, lado, topo) — já prototipado.
- `descrever_cena()` — devolve estado textual da cena pra IA ler antes de criar. Já prototipado.
- Métricas estruturadas no retorno (vértices, faces, bbox, dimensões, problemas).
- **Injetar pistas visuais no render** (setas de eixo, círculos de clearance, escala) — lição da
  pesquisa: VLM olhando render cru é cego pra detalhe geométrico fino.
- `--python-exit-code` propaga exceção como código de saída (bom pra loop automático).

### Em aberto
- Migrar do nosso addon+HTTP atual pro chassi do blender-mcp?
- `pip install bpy` (embute Blender no processo) vs `blender.exe --background` vs Blender vivo.
- Sandbox de execução: Python arbitrário é poderoso e perigoso.

---

## 2. Motor de geração (geradores por domínio)

> Nome adotado: **"motor de geração"**. O nosso é bem diferente dos geradores 3D comerciais
> (ver seção 8) — não é difusão nem malha-token opaca, é IA escrevendo regra/código interpretável
> que o Blender executa, com o loop de verificação por cima.

### 2A. Mecânico (peças, robôs, carros...)

**Representação:** código paramétrico (primitivos + operações + restrições), **não malha crua**.
A pesquisa confirma: código preserva aresta viva, é auditável, exporta STEP.

**Ideias / mecanismos:**
- DSL de geometria em cima de bmesh (já começado em `api/`): criar_cilindro_oco, furar_radial,
  chanfrar, etc. A IA escreve **intenção geométrica**, não bpy.ops frágil.
- **Catálogo de dimensões reais** (`catalog/`) — a IA consulta antes de inventar número.
- **Solver de restrição** (a alavanca mais subexplorada): a IA diz "furo concêntrico, face
  paralela", o solver calcula as coordenadas. A IA não chuta número. Levou geometria bem-formada
  de 9% → 93% num estudo (em 2D; transferência pra 3D é aposta, não provada).
- **Reusar addons prontos:** BoltFactory (parafusos métricos, já vem no Blender). Verificar caso
  a caso se é scriptável em background.
- Possível **kernel CAD por trás** (build123d/OpenCASCADE) como back-end de verificação exata —
  ver seção de tensões.

**Verificação (métrica DURA):**
- Dimensões vs catálogo (tolerância ±Xmm).
- Manifold, watertight, normais, n-gons, volume, validade de sólido.
- Folga/interferência entre peças que encaixam.
- Padrão juiz-separado (CADSmith): um modelo forte julga, outro gera — não deixar o gerador
  "corrigir a própria prova".

### 2B. Orgânico (árvores, plantas... depois: criaturas, pessoas)

**Representação:** **SDF (signed distance functions) como motor principal** — biblioteca `sdf` do
Fogleman, Python puro ([github.com/fogleman/sdf](https://github.com/fogleman/sdf)). A IA combina formas
com união/subtração/**união suave** + repetição/torção/casca, e a malha sai por marching cubes. Cobre
orgânico amplo (criatura, blob, coral, músculo), não só planta. **L-System/fractal vira sub-caso** pra
estrutura ramificada (árvore). Tudo é regra interpretável que a IA escreve, não malha crua.

> **Caveats verificados (2026-06-21):** marching cubes COSTUMA sair fechado mas NÃO garante malha sem
> defeito (casos ambíguos) — manter a checagem de validade, ela só fica mais barata. E ele ARREDONDA
> canto vivo → SDF é pro orgânico, não pra peça de precisão (essa fica no B-rep). Verificação orgânica
> ancora em PROPRIEDADE estatística (ângulos, profundidade, contagem), nunca em vértice — o que casa com
> SDF, já que os vértices da malha são não-únicos por construção.

**Ideias / mecanismos:**
- **L-System** (Lindenmayer): gramática que substitui símbolos por comandos de desenho de forma
  recursiva. É a ferramenta canônica pra crescimento de planta.
- **Árvore fractal / autossimilaridade:** galho menor ≈ árvore inteira em escala.
- **Reusar addon Sapling** (gerador de árvore L-System que já vem no Blender). Verificar
  scriptabilidade.
- Geometria orgânica via **Geometry Nodes / bmesh, NÃO escultura** — escultura é parede dura
  (sem data-API, precisa de stroke vivo).
- **Esqueleto + pele contínua (testado) — o jeito certo de ramificar low-poly.** Em vez de colar
  primitivos soltos, a recursão emite um **esqueleto** (vértices+arestas) onde tronco e galhos
  **compartilham o vértice do nó**; uma única pele costura tudo. No Blender headless isso é o
  **modificador Skin**: malha só de arestas → casca poligonal contínua, que escoa do tronco pro
  galho sem emenda. Mantém low-poly sem Subsurf (`branch_smoothing=0`, shade flat); congela via
  depsgraph e exporta STL que o `render_views.py` já consome. Código: `prototype/arvore_skin.py`.

> **Achado verificado (2026-06-21) — o MÉTODO é style-aware, não só a métrica.** Pelo mesmo
> objetivo "árvore ramificada" saíram **geradores diferentes conforme o estilo**: SDF recursivo
> (`arvore.py`) dá superfície lisa e densa (~12k faces); colar cilindros facetados
> (`arvore_lowpoly.py`) fica low-poly mas tem **dois defeitos reais** — emenda/degrau visível no
> nó (as peças não compartilham topologia) e galho com cara de **graveto reto**. O conserto NÃO
> foi ajuste de número: foi trocar o método. Esqueleto de vértice compartilhado + Skin **solda o
> nó** (emenda some) e o raio caindo por nível **afina o tubo** (graveto some). Resultado: 809
> faces no tronco+galhos (vs 1900 da versão colada), contínuo e ainda facetado. Lição: o estilo
> escolhe o **gerador e a representação**, não só o peso da verificação — eco do "lowpoly
> estilizado: a faceta é o objetivo" em [pesquisa_prova_forma.md](pesquisa_prova_forma.md).

**Verificação (métrica de PROPORÇÃO NATURAL — mais mole + visual):**
- **Ângulo de ouro ~137,5°** entre folhas/elementos (filotaxia).
- **Razão de afinamento** galho-pai → galho-filho dentro de faixa realista.
- **Equilíbrio físico:** nenhum galho comprido/pesado demais a ponto de "quebrar" — análogo ao
  que o mecanismo de atenção de um Transformer aprende sobre balanço.
- **Autossimilaridade** consistente entre níveis.
- Camada visual por cima (parecer natural não é 100% reduzível a número).

**Referência:** aqui imagem gerada por IA (Qwen, mais tarde) **é referência legítima**, porque não
há verdade dimensional exata — vale como forma/silhueta. Pedir múltiplas vistas coerentes.

---

## 3. A espinha compartilhada (loop de verificação)

```
gerar (código) → executar no Blender → render multi-view + extrair métricas
   → auditar (métrica + visual) → se errado: devolver o ERRO MEDIDO → corrigir → repetir
```

- **Métrica primeiro, visual depois.** VLM no render sozinho é geometricamente cego pra detalhe
  fino (Scene-VLM, IR3D-Bench). A medição dura é o que tira do platô.
- A verificação **muda por domínio** (dura no mecânico, proporção natural no orgânico), mas a
  **interface do verificador é única** — é o que costura os módulos e evita virar dois produtos
  meio-feitos.
- Esse loop autônomo + verificação métrica é **onde a gente é genuinamente novo** (ninguém
  empacotou ainda).

### Validade ≠ forma correta (correção honesta — 2026-06-20)

A verificação tem **camadas**, e elas medem coisas diferentes:
1. **Validade** (métrica de saneamento): malha fechada, manifold, normais, n-gons, volume > 0.
   Calculada do dado via bmesh, sem render. Diz se a malha é *bem-formada*.
2. **Dimensão** (métrica de requisito): furo = 65mm, espessura, folga. Só aritmética na malha,
   **não precisa de addon**. Só existe onde há especificação → praticamente só no **mecânico**.
3. **Forma correta** (a difícil): "está com cara de árvore / é a peça certa?" — **nenhuma das
   duas acima cobre isso.** Uma massa amorfa passa em validade e volume e continua errada.

**Não existe juiz algorítmico limpo de "forma certa".** Métricas de distância de forma (Chamfer,
Hausdorff, IoU) comparam com uma referência, mas:
- precisam de uma referência (no orgânico não há uma "árvore canônica");
- deixam passar formas estruturalmente erradas — cadeira sem perna, carro com roda chata —
  porque o erro mexe pouco no número ([1905.03678](https://arxiv.org/pdf/1905.03678),
  [Structural Failure of Chamfer Distance](https://arxiv.org/html/2603.09925v1));
- se enganam com outlier e ignoram detalhe fino.

→ **Consequência:** o juiz visual (render + modelo de visão) **é necessário** pra forma correta,
não dá pra terceirizar tudo pra número. Onde o número ajuda na forma é parcial: **assinaturas
estruturais por classe** (ângulo de ouro, razão de ramificação, simetria) e **forma por
construção** (gramática L-System correta → já nasce com a forma certa, igual ao solver no
mecânico). A imagem cobre o resto.

**Peso por domínio:** mecânico = validade + dimensão resolvem quase tudo (forma sai da construção
paramétrica). Orgânico = construção-por-gramática + assinaturas estruturais + **imagem** como juiz
final.

---

## 4. Decisões já tomadas

- **Só Blender** por enquanto (Unity/Unreal ficam pra camada de visualização/simulação depois).
- **Modular por domínio** (mecânico paramétrico vs orgânico gramática).
- **Loop de verificação como espinha**, verificação métrica como alavanca central.
- **Qwen (gerar imagem de referência) adiado** — só pro orgânico, mais tarde, via MCP.
- **Ponte própria headless** (`blender --background`), não blender-mcp como chassi (rebaixado a referência).
- **Render-feedback: Cycles-pra-arquivo** (headless) pra começar. Blender vivo é plano B.
- **Auditoria própria com bmesh**, não via addon de GUI (decisão do teste de addons).

## 5. Tensões e perguntas em aberto

- ~~Render-feedback: Cycles-pra-arquivo vs Blender vivo.~~ **RESOLVIDO:** Cycles-pra-arquivo pra
  começar (ver seção 1 e 4).
- **"Só Blender" é teto pro mecânico?** O mundo CAD tem verificação exata de kernel e FEA que o
  Blender não tem nativo. Talvez Blender = front-end de cena/orgânico + kernel CAD = back-end de
  verificação mecânica. Não engolir "só Blender" de graça.
- Transferência do solver de restrição 2D→3D não está provada — é aposta forte, não fato.
- **Família "mapa procedural editável" — INVESTIGADA** (ver [pesquisa_grafo_procedural.md](pesquisa_grafo_procedural.md)):
  - **Proc3D — FORA.** Não liberado, só faz móvel de cubo, e NÃO resolve identidade estável de parte. Baixa prioridade.
  - **ProcGen3D — baixa.** Imagem→3D, domínio estreitíssimo (cacto/árvore/ponte), não liberado, precisa do modelo deles.
  - **ShapeCraft — PROMISSOR (o achado).** É quase a nossa arquitetura funcionando: parser→grafo→código por nó→Blender→
    avaliador→itera, com LLM geral (sem fine-tuning) e **nós com identidade estável pra edição** (a resposta que o Proc3D
    não deu). Não tem código liberado → copiar a ARQUITETURA, não usar. Fraco em orgânico = exatamente onde o nosso SDF
    entra. Complementares.
- Paralelismo: `bpy` é um .blend por processo, sem threads Python (multiprocessing se precisar).
- Fragilidade por versão: IDs de Geometry Nodes e de operadores mudam entre versões do Blender.

## 6. Prior art pra roubar (não reinventar)

- **blender-mcp** (ahujasid) — chassi da ponte. github.com/ahujasid/blender-mcp
- **SceneCraft** (ICML24), **LL3M** (threedle) — arquitetura gerador + crítico visual.
- **CADSmith** (jabarkle) — padrão juiz-separado + malhas de correção aninhadas.
- **IR3D-Bench** — benchmark de loop fechado (código+dataset liberados).
- **Mesh-RFT** — validação geométrica como reward por face (pro orgânico).
- **Sapling / BoltFactory** — addons Blender prontos (árvore / parafuso).
- **ShapeCraft** (arXiv 2510.17603) — **o blueprint mais próximo do projeto inteiro**: parser→grafo→código
  por nó→Blender→avaliador→itera, LLM geral, nó com identidade estável pra edição. Copiar a arquitetura
  (não tem código). Ver [pesquisa_grafo_procedural.md](pesquisa_grafo_procedural.md).

---

## 7. Addons úteis (a explorar/verificar)

> **TESTE EMPÍRICO no Blender 5.1.2 da máquina (2026-06-20) — correção importante:**
> 1. **Esses addons NÃO vêm mais embutidos.** Desde a 4.2 viraram *extensões* que se instala do
>    repositório oficial (grátis, mas instala). Esse Blender veio só com um mínimo: Rigify,
>    Node Wrangler, io glTF/FBX/SVG/BVH, Cycles, Pose Library. (Rigify = rig de humano/criatura,
>    útil pro domínio futuro de pessoas/robôs.)
> 2. **Instalar headless FUNCIONA:** num script `--background` deu pra ligar o acesso online
>    (`preferences.system.use_online_access=True`), sincronizar o repo, `package_install` e ativar
>    — tudo sem interface. Então provisionar addon automaticamente é viável.
> 3. **MAS usar o addon headless é instável.** Instalei o 3D-Print Toolbox e, em sessão limpa
>    `--background`, o `addon_utils.enable` "passou" mas o addon NÃO ficou de fato ativo e os
>    operadores dele não apareceram. Confirma a regra: **addon instala headless ≠ ferramentas do
>    addon utilizáveis headless.** Muitos são feitos pra GUI.
>
> **Implicações pro projeto:**
> - Pra AUDITORIA, **não depender de addon** — os checks do 3D-Print Toolbox (manifold, watertight,
>   espessura, interseção) a gente faz direto com bmesh no nosso `validators.py`, que é mais
>   confiável que um addon de GUI. Escrever nosso é o caminho.
> - Addons que são gerador puro por operador (BoltFactory `mesh.bolt_add`, Sapling `curve.tree_add`)
>   *podem* funcionar headless — testar caso a caso, ou rodar num **Blender vivo** (reforça o lado
>   "Blender vivo" na decisão de render).
> - Scriptabilidade headless tem que ser verificada **por addon**, não assumida.

> Confiança: a existência dos addons abaixo é alta (são populares e gratuitos). A
> **scriptabilidade em modo background** é o que decide se reaproveitamos — e pelo teste acima,
> não dá pra assumir. Interativos (escultura, retopo manual) tendem a NÃO funcionar headless.

### Auditoria / saneamento de malha (alimentam o verificador — alta prioridade)
- **3D-Print Toolbox** — ~~candidato à espinha~~ **FORA como dependência.** O teste empírico mostrou
  que addon não roda confiável em headless, e a pesquisa nova manda fazer auditoria com
  **trimesh/bmesh próprios** (ver [verificadores_plugaveis.md](verificadores_plugaveis.md)). Os checks
  dele (manifold, watertight, espessura, interseção) a gente reimplementa, não importa o addon.
- **LoopTools** (vem com o Blender) — relaxar, achatar, regularizar malha (limpeza).
- **QuadriFlow remesh** (já embutido no Blender) — retopologia automática em quads.
- **MeasureIt** (vem com o Blender) — medição/cotas dimensionais. Útil pra auditar dimensão.

### Solver de restrição DENTRO do Blender (muda a tensão "só Blender")
- **CAD Sketcher** (gratuito, popular) — traz **restrição geométrica com solver** (usa o solver
  do SolveSpace, py_slvs) pra dentro do Blender: sketch 2D com restrições resolvidas por solver.
  **Importante:** isso pode dar o "solver de restrição" do módulo mecânico SEM precisar sair pro
  ecossistema CAD externo — suaviza a tensão da seção 5. Verificar scriptabilidade headless.

### Geradores paramétricos / procedurais
- **Sverchok** (gratuito) — modelagem node-based paramétrica estilo Grasshopper. Scriptável,
  poderoso pros dois domínios.
- **Extra Objects (Add Mesh)** (vem com o Blender) — inclui **engrenagens** e superfícies
  matemáticas — relevante pro mecânico.
- **Geometry Nodes** (nativo) — já é o motor procedural; DSLs prontas (geometry-script, geonodes).

### Geradores de domínio prontos
- **BoltFactory** (vem com o Blender) — parafusos/porcas métricos (mecânico).
- **Sapling Tree Gen** (vem com o Blender) — árvores por L-System (orgânico).
- **The Grove** (pago) — crescimento de árvore botanicamente preciso. Referência de proporção
  natural mesmo que não usemos direto.
- **Archimesh / Archipack** — geração procedural de arquitetura (domínio futuro).

### A verificar numa varredura mais funda (não levantado ainda)
- Addons novos/AI-específicos pós-2024, ferramentas de retopo scriptáveis, addons de
  measurement/tolerância de engenharia, exportadores STEP pra Blender.

---

## 8. O que roubamos dos geradores 3D genéricos (Meshy, Tripo, Rodin, point-e, MeshAnything...)

**Como eles geram (conceito):** texto/imagem → imaginam o objeto de vários ângulos (vistas
coerentes) → reconstroem uma malha que bate com todas as vistas. Variações: difusão em nuvem de
pontos/campo implícito (point-e, shap-e); ou escrever a malha como tokens, vértice a vértice
(MeshAnything, LLaMA-Mesh). Resultado em todos: uma **"massa"** com silhueta boa mas topologia
suja, sem aresta viva, sem medida exata, não editável. **Otimizam aparência, não correção
geométrica.**

**Veredito como MOTOR:** rejeitado pro nosso objetivo. Eles são *appearance-first*; nós somos
*precision-first* (código interpretável). Pro mecânico, inúteis (silhueta certa, medida errada).
Pro orgânico, no máximo **referência visual** (massa inicial pra olhar), nunca geometria final.

**Conceitos que VALEM (roubar):**
- **Multivista fixa a forma 3D.** Eles usam pra *construir*; nós usamos pra *verificar*. Reforça
  nossa verificação multi-view — uma vista só não prende o 3D, várias prendem.
- **Topologia como número mensurável** (Mesh-RFT: Boundary Edge Ratio, Topology Score) → alimenta
  o verificador do lado orgânico.
- **Retopologia pra limpar malha suja** (QuadriFlow já no Blender; Instant Meshes externo) →
  sanear qualquer malha, nossa ou importada de fora.

---

## 9. Nosso MCP de visão (o "Lente", clonado em `vision_mcp_ref/`)

É uma camada de automação de GUI do Windows (lê árvore de acessibilidade, clica, digita). Foi
feito pra OUTRO problema — operar programas como EPLAN —, não pra entender geometria 3D. Os modelos
de visão dele (OmniParser, GUI-Owl) acham elementos clicáveis, não julgam se uma peça está correta.

**O que vale reaproveitar:**
- **`vision_server/`** — servidor de VLM local com API OpenAI-compatível. Trocando o GUI-Owl por um
  VLM geral (Qwen3-VL), vira um **"juiz visual" local** pro modo **autônomo/offline** (quando o
  Claude não está no loop). Enquanto EU estou no loop, não precisa — eu já vejo os renders e sou
  avaliador visual mais forte que um modelo 4B.
- **Contrato `VisionBackend`** (motor de visão plugável) — bom padrão de abstração pra copiar.
- **A doutrina dele confirma a nossa:** "tem API? usa a API, não automatize a GUI." Por isso
  dirigimos o Blender por bpy, não por clique/screenshot da tela.

---

## 10. Estado atual do projeto (o que já existe e o que sobrevive à nova direção)

- **`bridge/server.py`** (addon + HTTP, com 4 vistas + `descrever_cena`) → **será substituído** pelo
  chassi do blender-mcp + runner headless. O conceito de 4 vistas e descrição de cena sobrevive.
- **`api/`** (primitives, operations, selectors, **validators**) → **conceito sobrevive.** A DSL é o
  caminho certo; `validators.py` é a semente da nossa auditoria própria por bmesh.
- **`catalog/dimensions.py`** → **sobrevive** (dimensões reais do lado mecânico).
- **`references/` + `fetch_references.py` + PDFs** → **sobrevive** (pipeline de referência mecânica
  via PDF de patente/catálogo, em alta resolução).
- **`parts/brake_disc.py` + `assembler.py`** → exemplo/teste. A geometria do disco estava ERRADA
  (sólido em vez de ventilado) — manter como exemplo a corrigir, não como verdade.
- **`tools/probe_addons.py`** → sonda de descoberta de addon (já usada).
- **`docs/`** → objetivo, como_usar, pesquisa_ia_3d, panorama_ferramentas_ia_3d, este rascunho.

> Resumo: o que muda é a PONTE (vira chassi blender-mcp + headless) e a AUDITORIA (vira bmesh
> próprio, não addon). O que fica é a DSL, o catálogo, o pipeline de referência e a ideia de
> multi-view + descrição de cena.
