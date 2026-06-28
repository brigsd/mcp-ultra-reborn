# Entrada e geração — spec, roteação, desambiguação, autoria de geradores, B-rep→Blender

> Pesquisa da metade que estava magra (6 frentes + síntese, web). Data: 2026-06-21.

## A jogada central: a spec deixa de ser instrução e vira contrato

O erro que mata o Larperian não é geométrico, é de INTENÇÃO — e nenhum verificador geométrico o pega
(o código é "plausível por construção, não correto por construção"). A inversão que destrava a entrada:
**a spec deixa de ser instrução pro gerador e vira o conjunto de asserções que o gerador tem que
satisfazer E que o verificador roda sem reescrever nada.** Mesma fonte de verdade, ancorada nos
PARÂMETROS do programa (nome estável), nunca em faces de malha. É design-by-contract aplicado a
geometria, convergência de QIF/MBD (CAD/metrologia) + spec→assertion (verificação de hardware) +
spec-driven development.

## 1. Formato de spec recomendado

**Regra dura: o texto cru do usuário NUNCA vai direto pro gerador.** Passa por normalização que produz
uma spec paramétrica auditada. Evidência: ProCAD/CADSmith — spec limpa derruba erro de 86.9%→0.9%, e
spec curta+precisa bate verbosa.

```
spec:
  identidade: "disco de freio ventilado, automotivo esportivo"   # âncora do veto de identidade do VLM
  dominio: mecanico | organico | hibrido     # saída do roteador
  representacao: brep | malha                 # decisão de roteação de 1a classe

  features:                       # PARTE 1 — forma geral
    - id: disco_principal         # ID ESTÁVEL = nome de parâmetro, NUNCA face de malha
      tipo: revolve
      params: { diametro_ext: 320, espessura: 28 }
      origem: especificado | inferido          # contrato-duro vs palpite-revisável
      from_text: "disco de freio 320mm"        # rastreabilidade reversa (nl2spec)

  setup: { workplane: XY, origem: centro, unidade: mm }   # PARTE 2

  build: [ sketch_disco, revolve, sketch_furos, pattern_circular ]   # PARTE 3 = ordem do coder

  asserts:                        # O CHECKLIST — cada item ancorado a um PARÂMETRO
    por_feature:
      - feature: disco_principal
        pos: diametro_ext_medido in [319.6, 320.4]
      - feature: furo_montagem_1
        pos: furos_count == 5 AND concentrico(datum_A)
    invariantes: [ solido_watertight, manifold ]   # Gate 0
    organico:                     # quando dominio=organico: PROPRIEDADE, nunca vértice
      - distribuicao_angulos in <faixa>
      - profundidade_ramificacao == <n>
```

**Regras de ouro:**
1. Texto cru nunca vai direto ao gerador (erro ~87%→~1%).
2. Âncora = nome de parâmetro (estável), nunca face de malha. Pra consultar geometria, consulta
   semântica no B-rep (estilo BRepGround), não índice de face.
3. Spec mínima-suficiente, não exaustiva — só o que muda a forma.
4. Marcar `especificado` vs `inferido` — senão fica válido porém errado de intenção e a asserção passa.
5. As MESMAS asserções são o feedback de correção: devolver discrepância NUMÉRICA (medido vs alvo),
   nunca "está errado". Asserções persistem entre iterações (impede "remover constraint até sumir").
6. Começar few-shot/prompt, saída JSON `{is_misleading, questions[], standardized_prompt=esta_spec}`.

## 2. Roteação de domínio/estilo

**Cascata, não classificador único:** (1) regra/léxico pros óbvios (porca M8→mecânico; árvore→orgânico);
(2) classificador semântico por embedding pro resto; (3) LLM só pros ambíguos. Fallback heurístico
obrigatório. Quatro defesas contra erro de roteação:
- **Custo assimétrico → enviesar pro ramo caro (B-rep).** Mandar mecânico pra malha perde a
  fonte-de-verdade e invalida toda a verificação por asserção; orgânico→B-rep falha cedo e barato
  (OCCT recusa). Exigir mais evidência antes de abandonar o B-rep.
- **Rótulo HÍBRIDO explícito.** Fronteira hard-surface/orgânico é fuzzy; robô com músculo = decompor e
  rotear cada sub-peça. Híbrido é onde clarificar deve disparar, não chutar.
- **Leque pequeno por nível.** Acerto de tool-use despenca com nº de opções (84-95% com ~50, 0-20% com
  ~740). Expor representação-raiz primeiro (B-rep vs malha), revelar operadores só depois.
- **Monitorar colapso de distribuição** (roteador treinado tende a sempre escolher o ramo que "quase
  sempre roda"). O ramo rule-based é a âncora anti-colapso.

## 3. Desambiguação

**Quando:** só quando a lacuna muda a geometria MATERIALMENTE (ProCAD: só perguntam quando a ambiguidade
degrada Chamfer ≥10x). Não virar questionário.
**Sonda quase de graça:** já vamos gerar código, então gerar 2-3 programas pro mesmo pedido e ver se os
PARÂMETROS divergem (um faz disco 280, outro 320). Divergiu = subespecificado (ClarifyGPT: Pass@1
70.96%→80.80%). Distinguir LACUNA (dimensão faltando→perguntar) de CONFLITO (dois valores→sinalizar).
**Como perguntar:** gate de uma rodada (batch de perguntas) quando há lacunas independentes; sequencial
quando uma resposta muda as próximas. Quando a ambiguidade muda a FORMA, gerar 2-4 hipóteses, renderizar
e deixar o usuário apontar (feedback visual > verbal). Ligar cada asserção ao fragmento do texto que a
originou (rastreabilidade reversa).

## 4. Autoria de geradores

**Código Python nos dois domínios** (LLM é bom em Python; executa sem dependência externa).
Contraintuitivo: alimentar IMAGEM no gerador piora a geometria — a imagem serve pro VLM AUDITAR, não pro
coder INFERIR.

**Mecânico (build123d):**
- **Planner separado do Coder.** Planner→JSON estruturado (componentes, bbox mm, restrições); Coder→
  build123d. O plano é o contrato de interface.
- O 9%→93% é "alinhar o gerador com feedback de solver no loop", NÃO "solver resolve coordenadas".
  "Design intent" vira 3 asserções: tudo restringido, sem sobre-restrição, sem distorção — gate no sketch
  ANTES do render.
- Style guide: params como variáveis nomeadas no topo (âncoras das asserções); subconjunto compacto de
  operações (vocabulário menor = menos falha); estrutura canônica init→sketch→extrude→transform→export.
- RAG sobre a doc (erro→solução) em vez de fine-tuning.
- **Atenção honesta:** a massa de treino do LLM está em CadQuery, não build123d. build123d é mais limpo,
  mas o gerador erra menos em CadQuery por volume. Medir os dois antes de cravar.

**Orgânico (L-System + problema inverso):**
- O inverso (alvo→regra) é mal-posto por lei matemática — NÃO tentar inferir "a" gramática certa.
- Workarounds: parcimônia como regularizador (menos regras = mais robusto); gerar várias candidatas e
  ranquear por fit+simplicidade; ancorar verificação em PROPRIEDADE estatística (ângulos, profundidade,
  contagem), nunca em vértice.
- **Eixo subestimado:** preencher PARÂMETROS de gerador pronto (3D-GPT preenche Infinigen) é muito mais
  confiável que escrever o gerador inteiro. Caminho seguro = LLM preenche params de geradores curados;
  expressivo = LLM escreve o gerador só quando o curado não cobre. Começar pelo seguro.

## 5. B-rep → Blender (prático)

- **No mecânico, o gêmeo B-rep carrega o próprio checklist:** exportar STEP AP242 com PMI SEMÂNTICA
  embutida → o verificador lê o STEP e tem as asserções de graça. Separar PMI apresentacional (texto pro
  VLM) de PMI semântica (máquina executa).
- **Tesselação como passo explícito e versionado.** B-rep é a fonte; malha é artefato derivado pra
  render. Correção sempre re-executa o script e re-exporta, nunca patch na malha.
- **Ponteiro de topologia estável = consulta semântica** (FutureCAD/BRepGround: "a face superior do furo
  F1" resolvido no B-rep em runtime), não índice de face frágil. Mitiga a nomeação topológica. (Confiança
  média — recente, não bala de prata.)
- **No orgânico, direto em bpy/geometry-nodes** — não há B-rep; a fonte é o script+params.

## 6. Pronto vs fronteira

**Pronto (confiança alta):** loop Planner/Coder/Executor-isolado/Juiz/Refiner (CADSmith: Chamfer 38x
melhor); **juiz mais forte E de família diferente do gerador** (mata auto-confirmação); kernel-metrics +
VLM são complementares (tirar o visual estoura Chamfer 1.42→49.68); RAG > fine-tuning; edição dirigida do
código, não regeneração; normalização de entrada + sonda de divergência (peer-reviewed).

**Fronteira / contra honesto:**
- **Precisão espacial fina é o teto real** (SOTA ~17.5% pass@1). Por isso o loop de correção é
  OBRIGATÓRIO — ele substitui o cálculo que o LLM não faz.
- **Mas o loop LONGO rende menos do que se espera:** em vários sistemas o ganho some após ~1 iteração. A
  alavanca real é gerar certo + asserção bem ancorada, não iterar muito. Orçar 2-4 iters, não apostar que
  iteração conserta erro geométrico sutil.
- **Cada camada de restrição que protege a fidelidade DERRUBA a taxa bruta na 1a tentativa** (AIDL: 64%
  com constraints vs 94% sem, mas as sem produzem peça solta ao escalar). O loop existe pra recuperar a
  taxa que a estrutura custou.
- **Reward hacking:** "remover constraint até o erro sumir". O auditor não pode aceitar "erro sumiu";
  asserções são contrato persistente + feedback sempre numérico.
- **JSON rígido demais piora o raciocínio geométrico 10-30%** — deixar o LLM raciocinar em prosa antes de
  destilar pra spec.
- **Calcanhar de aquiles:** todo o esquema spec=checklist pressupõe ID de feature estável. Nomeação
  topológica continua aberta; só se mantém ancorando ao PARÂMETRO, nunca à face regenerada.
