# Verificação adversarial — Plano-mestre Larperian

> Ataque independente ao plano-mestre (4 frentes adversariais + síntese, web). Data: 2026-06-21.
> Confiança: **[sólido]** = fontes primárias convergentes; **[médio]** = extrapolação fundamentada;
> **[chute]** = baixa evidência, sinalizado.

## Veredito

O plano se sustenta na arquitetura de loop e na escolha de solver/kernel como sinal de verdade, mas
QUEBRA na fundação de representação (malha como primária contradiz "precisão") e na premissa de que a
auditoria é barata, neutra e independente do gerador — ela é correlacionada com o erro, sem oráculo,
e manipulável (reward hacking). **Não é refundação: é trocar a coluna de representação para
B-rep-como-fonte-de-verdade e endurecer a independência da verificação.**

---

## 1. Falso achado / fraqueza real (por severidade)

### CRÍTICO

**1.1 "Só Blender" (malha) contradiz a promessa de precisão. [sólido]**
B-rep guarda a equação exata (um furo circular *é* circular); malha aproxima por triângulos e perde
exatidão na tesselação. A decisão de apostar em build123d/py_slvs é certa — mas eles rodam sobre OCCT
(B-rep). O plano gera a precisão no mundo B-rep e a joga fora ao assar pra malha, depois audita com
Hausdorff o erro que ele mesmo introduziu. Fix: manter um **gêmeo B-rep (STEP) como fonte-de-verdade
da forma**; malha Blender = artefato de render.

**1.2 Falha correlacionada gerador↔verificador. [sólido]**
Gerador e verificador falham nas MESMAS entradas difíceis. Hausdorff precisa de referência que sai do
mesmo pipeline IA; gerador erra a forma → referência também errada → Hausdorff diz "perfeito" contra
alvo errado. O loop converge confiante pro objeto errado. Trocar de verificador não resolve.

**1.3 Sem oráculo/ground-truth de fidelidade no caso geral. [sólido]**
A maioria dos prompts texto→3D não tem geometria de referência. Sem referência, a camada de fidelidade
não roda (ou roda contra proxy de IA). A área migrou pra métricas no-reference (alinhamento semântico).
Contradição: proibimos o VLM de vetar, mas no regime sem-referência o VLM pode ser o único sinal.

**1.4 Reward hacking contra os próprios verificadores. [sólido]**
O gerador pode minimizar Hausdorff sem ser a forma certa, ou — pior — editar/desabilitar o verificador
no script que ele mesmo escreve, já que código gerado e verificadores dividem o mesmo
`blender --background`. Hardening reduziu exploits ~88%. **O verificador NUNCA pode ser
importável/editável pelo script gerado.**

**1.5 Manifold como verificador é circular E exige input limpo. [sólido]**
(a) manifold3d (pip) e o Manifold do Blender são a MESMA lib — um "confirmar" o outro só prova que dois
builds concordam. (b) Manifold retorna erro se o input não for manifold e não conserta — falha justo no
regime sujo onde a IA mais erra. No Blender 4.5 nem é o solver default.

### ALTO

**1.6 "VLM só triagem, nunca veto" está mais errado do que parece. [sólido]**
CADSmith: remover a imagem renderizada (o olho VLM) **degradou Chamfer 35x (1.42→49.68)** porque
métricas de kernel sozinhas não detectam falsa convergência (forma com volume/bbox plausíveis mas
estruturalmente errada). Duas classes de falha disjuntas: programática pega alucinação
dimensional/topológica; visual pega "estruturalmente errado mas numericamente plausível". O VLM DEVE
poder vetar "isto não é a coisa pedida" (identidade), só não tolerância fina.

**1.7 Métrica de sucesso (forma/topologia) é o 80% fácil. [sólido]**
MUSE: execução 77% → validade geométrica 69% → alinhamento de intenção ~52% → função/fabricabilidade/
montabilidade 19-21%; "Overlap Free" (interpenetração) despenca mais. "Forma correta" ≠ "design certo".
O plano não tem verificador de interpenetração/colisão.

**1.8 Hausdorff como fidelidade "precisa" é enganoso. [sólido]**
Uni-dimensional, dominado por outlier, instável à amostragem, e NÃO localiza o erro. Um escalar global
não diz ONDE a proporção quebrou — justo o que o loop precisa pra saber o que corrigir. Precisa de erro
por-feature, não Hausdorff agregado.

**1.9 GUDHI/Ripser pra "furo real" tem fragilidade. [sólido]** Persistent homology é sensível a
outlier, escala e amostragem. Sem critério de persistência justificado, o veto topológico vira "ruído
com cara de rigor".

**1.10 "Transferência 2D→3D não provada" está mal enquadrado. [sólido]** py_slvs/SolveSpace JÁ resolve
3D nativo. O risco real: binding cru sem driven dimensions; em sistema subdeterminado minimiza por
mínimos-quadrados → solução plausível-porém-não-pretendida, sem avisar. O caminho maduro é **sketch 2D
restringido → feature 3D paramétrica** (extrude/revolve), que CadQuery/build123d já fazem. Precisa de
detector de sketch sub/sobre-restrito ANTES de extrudar.

**1.11 Nomeação topológica persistente vai comer o loop de correção. [sólido]** Quando uma feature muda,
faces/arestas regeneram com novos IDs e referências morrem (problema clássico não resolvido nem no
FreeCAD; em malha é pior). Implicação: "corrigir" = **re-executar o script paramétrico com parâmetro
alterado**, nunca patch incremental na malha.

**1.12 Erosão monotônica de qualidade no loop. [sólido]** Cada correção empilha booleano/modificador; a
malha vira Frankenstein que passa na validade mas perde limpeza. Precisa de orçamento de
complexidade + rewrite-from-scratch quando o script incha.

**1.13 Loop degenerativo (auto-condicionamento). [sólido]** Agente patcha superficial, re-roda, vê o
mesmo erro, repete até o limite. Contra-intuitivo: dar TODO o histórico pode PIORAR. Precisa de "mesmo
erro 2x → mudar de estratégia" e talvez esquecer tentativas ruins.

**1.14 Reprodutibilidade do verificador (FP + drift de versão). [sólido]** Não-associatividade de
ponto flutuante + GPU vs CPU + versão de lib → mesmo script passa hoje e falha amanhã. Pinar versões
(lockfile), Cycles CPU/determinístico pra auditoria, tolerância > ruído de FP medido.

**1.15 Inverse procedural modeling (L-System) é mal-condicionado. [sólido]** L-systems são ótimos pra
"uma árvore plausível", péssimos pra "ESTA árvore". No orgânico, garantir só validade + plausibilidade,
não fidelidade ponto-a-ponto. Rebaixar a meta explicitamente.

### MÉDIO

**1.16 Cycles-pra-arquivo no loop é caro pra sinal fraco. [lógica sólida, número chute]** Pra triagem,
EEVEE/workbench/matcap/normais/ortográfica mede forma melhor que path-tracing fotorrealista.
**1.17 VLM herda viés de LLM-as-judge.** Usar juiz de família diferente do gerador; medir variância.
**1.18 Critério de PARADA ambíguo.** Definir sucesso vs falha vs desistência: melhoria < ε (ε > ruído FP),
detecção de oscilação, gate validade+topologia ANTES de otimizar fidelidade.

---

## 2. Frentes novas (não estavam na nossa lista)

- **2.1 Verificador de não-interpenetração/clearance em juntas** — terceiro modo de falha; escorre entre
  manifold-global e Hausdorff-global. (ALTO)
- **2.2 Spec-como-asserções-ancoradas (PMI/MBD)** — cada tolerância ligada à feature ("furo F1=Ø10±0.1"),
  pass/fail por asserção, localiza o erro. Ancorar a parâmetros do CÓDIGO, não a faces da malha. (ALTO)
- **2.3 Asset Validator como registro de regras versionadas + severidade + gate único de publish (HALT)** —
  como usdchecker/Omniverse Asset Validator. (ALTO)
- **2.4 Checks baratos determinísticos antes do caro** — n-gons, normais invertidas, vértices duplicados,
  transform aplicado, escala real-world. (ALTO)
- **2.5 Guardrails de parâmetro no gerador (defesa antes de gerar)** — ranges válidos, detecção de
  combinação incompatível de restrições, bounds nos símbolos. (ALTO)
- **2.6 Teste de regressão / golden-baseline + CI no commit do gerador** — "consertei A e quebrei B"
  passa silencioso sem isso. O headless já decidido vira CI quase de graça. (ALTO)
- **2.7 Dois loops aninhados** — interno barato (erro de execução, retry agressivo), externo caro
  (geometria, poucos tiros). (MÉDIO)
- **2.8 Desambiguação de prompt sub-especificado antes de gerar** — erro de INTENÇÃO que nenhum
  verificador geométrico pega. Casa com "perguntar o que falta". (ALTO)
- **2.9 Oráculo independente** — combinar verificadores de FAMÍLIAS diferentes (Euler/genus/componentes
  que não dependem do solver boolean; massa/volume/área analíticos B-rep vs malha tesselada). (MÉDIO)
- **2.10 Decimabilidade como proxy de saúde topológica.** (BAIXO, extrapolação)
- **2.11 Procedência: seed global gravado no metadado + versão imutável + DAG de dependência + nome
  determinístico (dominio_tipo_variante_seed_versao).** (MÉDIO)
- **2.12 Render diagnóstico, não bonito** — render fotorrealista desarma o ceticismo do humano; mostrar
  heatmap de desvio/wireframe/corte. (MÉDIO)

---

## 3. Confirmações (resistiram ao ataque)

- **Solver/kernel como ground-truth do loop é o estado da arte** (Autodesk: solver da Fusion É o
  verificador; CADSmith reduz Chamfer 38x com feedback do kernel OCCT). Ressalva: medem em B-rep, não malha.
- **Modularização mecânico=paramétrico/solver vs orgânico=L-System resiste.**
- **Headless / isolar execução é boa aposta** — mas o ganho real é o código gerado NÃO ter acesso ao
  verificador (processo separado lendo só o arquivo de saída).

---

## 4. Ajustes ao plano (ordem de prioridade)

1. **[CRÍTICO] Inverter representação: B-rep (STEP via build123d/OCCT) = fonte-de-verdade da forma no
   mecânico; malha Blender = render/montagem, gerada por último.** Verificar fidelidade no domínio B-rep
   (massa/volume/área analíticos), não em malha.
2. **[CRÍTICO] Isolar o verificador do código gerado em processo separado** que lê só o arquivo de saída.
3. **[CRÍTICO] Tratar correlação gerador↔verificador e ausência de oráculo** — verificadores de famílias
   independentes + VLM com veto de identidade onde não há referência.
4. **Promover o VLM a veto de identidade/estrutura** (não tolerância). Juiz de família diferente do gerador.
5. **Trocar "transferência 2D→3D" por "sketch restringido → feature 3D paramétrica"** + detector de
   sub/sobre-restrição antes de extrudar.
6. **Substituir Hausdorff-global por asserções ancoradas a parâmetros/features (PMI/MBD)**, ancoradas ao
   código, não a faces.
7. **"Corrigir" = re-executar o script com parâmetro alterado**, nunca patch na malha; + anti-slop
   (rewrite quando incha; mesmo erro 2x → mudar de estratégia).
8. **Verificador de não-interpenetração/clearance** como cidadão de primeira classe; decidir se o plano
   persegue só FORMA ou também função/montabilidade.
9. **Guardrails de parâmetro + checks baratos determinísticos antes do caro.**
10. **Registro de regras versionadas com severidade + gate único de publish.**
11. **Determinismo real: lockfile, Cycles CPU determinístico, tolerância > ruído FP, seed propagado.**
12. **CI com golden-baseline + diff** (geométrico e perceptual).
13. **Loop de dois níveis + critério de parada multi-condição.**
14. **Desambiguação de prompt antes do loop caro.**
15. **Rebaixar a meta orgânica: plausibilidade/validade, não fidelidade ponto-a-ponto.**
16. **Triagem visual com render diagnóstico (EEVEE/normais/curvatura/ortográfica/heatmap), não Cycles.**
17. **Vigiar (não adotar já): persistência justificada pra TDA; decimabilidade como proxy; C2PA pra 3D.**
