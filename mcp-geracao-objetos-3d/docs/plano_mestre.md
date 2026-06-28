# Plano-mestre Larperian — consolidação conectiva

> Documento de integração. Junta tudo que decidimos e pesquisamos num mapa único, separa o que é
> real do que é falso achado, define o que vira módulo / ferramenta / biblioteca / coisa-a-adotar,
> e levanta as frentes que ainda não tocamos. Supera o [rascunho_ideias.md](rascunho_ideias.md) como
> visão de topo (o rascunho continua sendo o caderno de ideias soltas).
> Data: 2026-06-21.

---

## 1. O mapa conectivo (o que é cada coisa)

Quatro camadas. A regra é: **a espinha e a ponte são únicas; os geradores e os verificadores são
plugáveis.**

### Espinha (única, é o produto central)
O **orquestrador do loop**: gerar → executar → renderizar+medir → auditar em camadas → devolver erro
medido → corrigir → repetir. É aqui que mora o diferencial (loop autônomo + verificação métrica). Não
é MCP tool nem biblioteca de fora — é o coração que a gente escreve.

### Ponte (única, infraestrutura)
Runner headless: `blender --background --python` + render Cycles-pra-arquivo + introspecção de cena +
retorno de métricas estruturadas. **Não é o blender-mcp** (ver revisão na seção 2). Exposta à IA como
um punhado pequeno de **MCP tools**:
- `blender_exec(code)` — roda código do gerador, devolve objetos criados + métricas.
- `render_views(alvo)` — vistas múltiplas em PNG (com opção de pistas visuais).
- `describe_scene()` — estado textual da cena.
- `audit(alvo, dominio, estilo)` — roda a pilha de verificadores, devolve relatório em camadas.
- `fetch_reference(peca)` — puxa referência (mecânico).

### Geradores (módulos plugáveis, divergem por domínio)
Pacotes Python internos, **não** MCP tools — a IA os usa via `blender_exec`. Cada módulo =
gerador + verificadores do domínio + tipo de referência.
- **`generators/mecanico`** — DSL paramétrica (`api/` atual) + catálogo + solver de restrição.
- **`generators/organico`** — **SDF (lib `sdf` do Fogleman)** como motor principal (cobre orgânico
  amplo, não só planta); L-System/fractal vira sub-caso pra ramificação. Verificado 2026-06-21 (ver §7).
- Futuros: arquitetura, criatura/pessoa (Rigify), etc. — abre seção quando chegar.

### Verificadores (bibliotecas plugáveis, 1 por modo de falha)
Não são módulos nossos do zero — são libs de fora que a gente embrulha numa interface única e pluga
no estágio `audit` da espinha. Detalhe completo em [verificadores_plugaveis.md](verificadores_plugaveis.md).
- **Validade:** trimesh (+ nosso bmesh) — watertight/manifold/componentes.
- **Fidelidade (mecânico):** point-cloud-utils ou PyMeshLab Hausdorff vs alvo.
- **Estrutura (orgânico):** skeletor (mesh→grafo, conta ramificação); GUDHI/Ripser só pra furo real.
- **Construção-por-regra:** manifold3d (booleana mecânica, já é o solver do Blender); gramática (orgânico).
- **Percepção:** VLM (eu, ou VLM local) — só triagem, nunca veto.

### Conhecimento (dados/docs)
- `catalog/` (dimensões mecânicas), `references/` (PDFs de patente/catálogo), `protocols/` (manuais
  pra IA — hoje DESATUALIZADOS, ver seção 2).

---

## 2. Revisões ao estado atual (real / falso / desatualizado)

O que mudou de figura conforme aprendemos. Itens que **precisam de correção**:

1. **"Adotar blender-mcp como chassi" → REBAIXADO a referência.** O blender-mcp dirige um Blender
   VIVO por socket. Como decidimos render headless (Cycles-pra-arquivo), a gente quase não precisa
   dele — eu chamo `blender --background` direto. Ele vira inspiração/estudo de superfície de
   ferramenta, não a base. (Contradição interna que estava no rascunho seção 4.)

2. **3D-Print Toolbox como "espinha de verificação" → FORA.** O teste empírico mostrou que addon não
   roda confiável em headless, e a pesquisa nova diz pra fazer auditoria com trimesh/bmesh próprios.
   O 3D-Print Toolbox sai como dependência. (Contradiz o que a seção 7 do rascunho ainda elogia.)

3. **`protocols/00–05` estão DESATUALIZADOS.** Foram escritos no começo, assumindo o addon+HTTP e o
   `api/` como caminho único, e usam o brake_disc como exemplo bom. Precisam de reescrita pra nova
   direção (headless, pilha de verificadores em camadas, split por domínio). Marcar como legado até lá.

4. **`parts/brake_disc.py` tem geometria ERRADA** (disco sólido em vez de ventilado). Serve de
   exemplo a corrigir, não de verdade. Já anotado.

5. **Correção já feita (mantida aqui pra registro):** homologia/Betti NÃO conta galho — ramificação é
   esqueleto/grafo (skeletor). Métrica de distância (Chamfer/IoU) NÃO prova forma correta.

**O que se confirmou sólido (não é falso achado):** a DSL paramétrica, o catálogo, o pipeline de
referência por PDF, a ideia de multi-view, o loop como espinha, e a regra "1 verificador por modo de
falha".

---

## 3. O que precisa ser feito, em ordem de alavanca

1. **Runner headless mínimo** — `blender --background --python` que roda um script, renderiza N
   vistas no Cycles e devolve métricas em JSON. (Substitui o `bridge/server.py`.) É o destravador.
2. **Verificador de validade** — embrulhar trimesh + nosso bmesh numa função `audit_validade(obj)`.
   É a camada barata que sempre roda. Reaproveita o conceito do `validators.py`.
3. **Espinha do loop** — orquestrador: gera → render → audita → devolve erro → repete, com condição
   de parada (N iterações / orçamento).
4. **Um gerador de ponta a ponta por domínio** — mecânico: corrigir o brake_disc usando a DSL +
   uma checagem de dimensão vs catálogo. Orgânico: uma árvore L-System + skeletor contando galho.
5. **Solver de restrição (mecânico)** — testar CAD Sketcher (py_slvs) headless; se não rodar, avaliar
   build123d. É a aposta de maior precisão.
6. **Camada de percepção** — render multi-view com pistas visuais; eu como juiz no loop interativo.
7. **Reescrever os protocolos** pra refletir tudo isso.

---

## 4. Frentes que ainda NÃO levantamos (o que você pediu — as perguntas que nem fizemos)

Estas são genuínas lacunas. Nenhuma foi discutida ainda. Marco quais me parecem críticas.

- **[CRÍTICO — agora com design recomendado] Roteação de domínio/estilo.** PESQUISADO: roteador em
  cascata (regra→semântico→LLM), enviesado pro ramo caro-de-reverter (B-rep), com rótulo HÍBRIDO
  explícito e leque pequeno por nível. Ver [pesquisa_spec_e_geracao.md](pesquisa_spec_e_geracao.md) §2.
- **[CRÍTICO] Da onde vem a referência de FORMA no mecânico?** Hausdorff precisa de uma malha-alvo. O
  catálogo tem dimensões (números), não formas. Tem um buraco entre "tenho as medidas" e "tenho contra
  o que comparar a forma". Talvez o próprio programa paramétrico seja o alvo, não uma malha externa.
- **[CRÍTICO — agora com design recomendado] Formato de spec.** PESQUISADO: ver
  [pesquisa_spec_e_geracao.md](pesquisa_spec_e_geracao.md). A virada: a spec não é instrução pro gerador,
  é um CONTRATO — as mesmas asserções que o gerador satisfaz são o checklist que o verificador roda, sem
  ponte entre os dois, ancoradas a PARÂMETROS nomeados (não a faces). Texto cru nunca vai direto ao
  gerador (passa por normalização: erro ~87%→~1%). Esboço concreto do formato no doc.
- **[ALTO] Orçamento de custo/tempo por objeto.** Render Cycles + pilha de verificadores × N iterações
  = tempo real. Sem um teto, o loop autônomo pode rodar pra sempre. Precisa de budget e parada.
- **[ALTO] Recuperação de erro no loop.** O que acontece quando a IA não conserta depois de N
  tentativas? Fallback, escalar pro humano, registrar a falha.
- **[ALTO] Como medir se o Larperian melhora?** Precisa de um conjunto-teste de objetos-alvo + critério
  de sucesso. 3DCodeBench/IR3D-Bench podem servir. Sem isso, "está melhor" é achismo.
- **[MÉDIO] Memória entre sessões.** A IA acumula receitas/parâmetros que funcionaram por classe de
  objeto? (SceneCraft chama de "library learning".) Transforma tentativa-e-erro em conhecimento.
- **[MÉDIO] Convenções de unidade/eixo/origem.** Metros, Z pra cima, onde fica a origem. Mismatch
  disso é fonte clássica de bug. Hoje é implícito (catálogo em metros), não imposto.
- **[MÉDIO] Determinismo / semente.** Geração com aleatoriedade (árvore) precisa de seed control pra
  ser reproduzível e depurável.
- **[MÉDIO] Performance dos verificadores em malha densa.** TDA/esqueleto em malha pesada é lento —
  pode precisar decimar antes de auditar.
- **[MÉDIO] Montagem / cena multi-objeto.** Relações entre peças (a pinça abraça o disco) além do
  assembler atual. Holodeck faz isso com solver de layout — é uma frente inteira.
- **[BAIXO/futuro] Licença/IP.** skeletor é GPL-3 (contamina se virar produto); PDF da SKF é "uso
  educacional", não redistribuível; figuras de patente são domínio público. Importa se comercializar.
- **[BAIXO/futuro] Segurança.** Execução de Python arbitrário no Blender — sandbox se for autônomo.
- **[BAIXO/futuro] Formato de saída e downstream.** O que a IA entrega? `.blend`, glTF, STEP? Liga
  com Unity/Unreal lá na frente.
- **[BAIXO/futuro] Rigging/animação** (Rigify já está instalado) e **material/textura** (fora de
  escopo hoje, mas o realismo total vai pedir em algum momento — marcar a fronteira).

---

## 5. Confiança e contras

- Confiança **alta** no mapa conectivo e nas revisões (são correções de contradições nossas e de
  achados já verificados).
- Confiança **média** no runner headless ser suficiente sozinho — pode ser que o feedback visual
  rápido force o Blender vivo antes do que queremos. Plano B mapeado.
- O **contra** que eu não engulo: a lista de frentes da seção 4 é grande o bastante pra sugerir que
  ainda estamos em arquitetura, não em implementação. A tentação é começar a codar o runner já; o
  risco é codar antes de decidir o formato de spec (seção 4), que é a entrada de tudo. Minha
  recomendação honesta: travar o **formato de spec** e a **roteação de domínio** antes do passo 1.
- Esta consolidação foi atacada por uma verificação adversarial independente. O resultado está na
  seção 6 e em [teardown_plano_mestre.md](teardown_plano_mestre.md). Ele mudou coisa de fundação.

---

## 6. O que a verificação adversarial mudou (2026-06-21)

O plano **se sustenta na direção** (loop gerar-verificar-corrigir, kernel/solver como verdade, modular,
headless), mas levou três correções de fundação. Detalhe e fontes em
[teardown_plano_mestre.md](teardown_plano_mestre.md).

**Rachadura principal — representação.** Eleger malha Blender como objeto primário CONTRADIZ "precisão
geométrica". A precisão nasce em B-rep (build123d/CadQuery rodam sobre OCCT); assar pra malha joga ela
fora, e aí auditar com Hausdorff mede o erro que o próprio pipeline introduziu. **Correção: no
mecânico, o B-rep (STEP) é a fonte-de-verdade da forma; a malha Blender é artefato de render/montagem,
gerada por último.** Isso resolve, de vez, a velha tensão "só Blender é teto?": era, sim, pro mecânico.
O Blender fica pra orgânico + render + cena; a precisão mecânica mora num kernel CAD.

**A verificação não é independente nem neutra.** Gerador e verificador falham nas mesmas entradas
difíceis; sem referência externa o Hausdorff não tem contra o quê medir; e como o código gerado e os
verificadores dividem o mesmo processo Blender, o script pode até desligar o próprio verificador
(reward hacking). **Correções: isolar o verificador num processo separado que lê só o arquivo de saída;
usar verificadores de famílias independentes (Euler/genus, massa/volume B-rep vs malha); e devolver ao
VLM o veto de IDENTIDADE** ("isto não é a coisa pedida") — rebaixá-lo a triagem cega degradou resultado
35x num estudo (CADSmith). VLM não veta tolerância fina, mas veta falsa convergência.

**Correções de enquadramento (eu tinha errado):** (a) py_slvs JÁ resolve 3D nativo — o risco não é
"transferência 2D→3D", é solver subdeterminado que dá solução plausível-porém-errada sem avisar; o
caminho maduro é sketch restringido → feature 3D. (b) manifold3d NÃO é verificador (é a mesma lib do
solver do Blender — confirma a si mesmo). (c) "corrigir" tem que ser re-executar o script paramétrico
com parâmetro mudado, NUNCA patch na malha (nomeação topológica + erosão de qualidade).

**Frentes novas que entraram (as mais fortes):** verificador de **não-interpenetração/clearance** em
juntas (forma certa ≠ design certo: função/montabilidade é onde os sistemas despencam); **spec como
asserções ancoradas a parâmetros** (furo F1 = Ø10±0.1, pass/fail por asserção, localiza o erro) em vez
de Hausdorff global; **checks baratos determinísticos antes do caro** (n-gons, normais, duplicados,
transform, escala); **desambiguação de prompt antes do loop**; **determinismo real** (lockfile, Cycles
CPU, tolerância > ruído de ponto flutuante); e **render diagnóstico** (normais/curvatura/ortográfica/
heatmap), não Cycles fotorrealista, pra triagem.

**Revisão da seção 3 deste plano (build order):** o passo 1 deixa de ser "runner headless + malha" e
passa a incluir a decisão de representação (B-rep no mecânico) e o isolamento do verificador. E reforça
o que a seção 5 já dizia: travar **formato de spec** (agora como asserções ancoradas) e **roteação de
domínio** antes de codar.

---

## 7. Atualização: representação orgânica = SDF (2026-06-21)

Verificado contra fontes. O motor do lado orgânico passa a ser **SDF (signed distance functions)** via a
lib `sdf` do Fogleman (Python puro): a IA combina formas com união/subtração/união suave + repetição/
torção/casca, e a malha sai por marching cubes. É **mais geral que a gramática L-System** que a gente
tinha pensado — cobre criatura, blob, coral, músculo, não só planta com galho. L-System/fractal vira
sub-caso pra ramificação.

Correções honestas sobre a ideia (que veio meio exagerada): (a) marching cubes COSTUMA sair watertight
mas NÃO garante malha sem defeito de junção e ARREDONDA canto vivo — então reduz o trabalho do
verificador de validade, não mata; e confirma que SDF é pro orgânico, peça de precisão fica no B-rep;
(b) os números "4-10× mais enxuto / edição 400× mais rápida" NÃO são do SDF — são de outro formato
(Proc3D), investigado abaixo.

Fontes: [fogleman/sdf](https://github.com/fogleman/sdf), [limitações marching cubes](https://arxiv.org/pdf/2005.11621).

### Família "mapa procedural editável" — investigada (ver [pesquisa_grafo_procedural.md](pesquisa_grafo_procedural.md))

- **Proc3D — FORA.** Não liberado, só móvel de cubo, e NÃO resolve identidade estável de parte (o que a
  gente esperava dele). Baixa prioridade.
- **ProcGen3D — baixa.** Imagem→3D, domínio estreitíssimo, não liberado, precisa do modelo treinado deles.
- **ShapeCraft — PROMISSOR, vira prior art de primeira linha.** É quase a arquitetura inteira do Larperian
  já funcionando: parser→grafo→código por nó→**Blender**→avaliador→itera, com **LLM geral (sem fine-tuning)**
  e **nós com identidade estável pra edição local** — a resposta concreta pra edição/correção que o Proc3D
  não deu. Não tem código liberado → adotar a ARQUITETURA, não o código. Fraco em orgânico, que é
  exatamente onde o nosso SDF entra: **complementares** (ShapeCraft dá a orquestração + grafo editável; SDF
  dá o motor orgânico; B-rep dá a precisão mecânica).
