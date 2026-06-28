# Provar forma correta em 3D: o que a pesquisa realmente sustenta

> Pesquisa aberta (6 frentes + síntese, 60 achados). Data: 2026-06-21.
> Pergunta: dá pra PROVAR que uma forma 3D está correta, não só válida nem só parecida?

## Resposta direta

Não existe prova absoluta de "forma correta" pra um objeto gerado isolado. Provar *fidelidade*
exige uma referência; sem ela, só dá pra provar **validade interna** (topologia) e **correção
estrutural** (quantos buracos/componentes/partes), não "é geometricamente o X certo". O mais perto
de prova: checagens binárias sem referência (watertight/manifold/Euler) e certificação topológica
com localização (Betti Matching) — mais a ponte CAD-as-code, que valida o PROGRAMA e herda kernel
exato em vez de validar a malha crua.

---

## 1. O mais perto de "prova", por ordem de rigor

**LEI (restrição dura):** "forma correta" no sentido de fidelidade só é provável contra uma
referência. Sem alvo, não há contra o que provar fidelidade — só validade e estrutura. Isso é o que
"correto" significa, não limitação de engenharia. Confiança: alta.

**(a) Prova binária sem referência — validade do sólido.** Watertight/manifold + característica de
Euler (χ = V − E + F) provam que é um sólido bem-definido. Métricas pra saída de IA: Boundary Edge
Ratio, Self-Intersection Ratio, Flux Enclosure Error. Limite: prova validade, não fidelidade (um
cubo perfeito é watertight quando você queria uma esfera).
- https://arxiv.org/html/2505.16761v1

**(b) Prova estrutural — Betti Matching / persistent homology.** O que mais diretamente CERTIFICA
estrutura: número certo de componentes (H0), alças (H1), cavidades (H2), e com localização correta
(os buracos no lugar certo). Já existe como loss differentiable com código 3D. Pega exatamente o
que Chamfer ignora. Limite: prova topologia, não geometria fina.
- https://arxiv.org/abs/2407.04683 (Betti Matching 3D)
- https://proceedings.mlr.press/v202/stucki23a.html (ICML 2023)

**(c) Validar o PROGRAMA, não a malha (CAD-as-code).** Gerar como programa paramétrico e validar a
saída herdando garantias do kernel. CADSmith combina medida exata do OpenCASCADE + juiz visual VLM.
Empilha validade + tolerância + fidelidade + semântica. Confiança média-alta; fronteira, e só vale
se o objeto for expressável como programa/B-rep.
- https://arxiv.org/pdf/2603.26512 (CADSmith)

**Por que Chamfer/IoU NÃO são prova:** há prova formal de que otimizar Chamfer pode PIORAR a forma
(gradiente many-to-one colapsa pontos), chegando a mascarar falha estrutural.
- https://arxiv.org/html/2603.09925v1

**Teto de rigor — verificação formal (Lean/Coq):** prova um ALGORITMO correto pra toda entrada, não
um objeto. Serve pra tornar confiável o nosso VALIDADOR (ex.: o checador de interseção), não pra
certificar uma peça.

## 2. Ranking por alavanca pra PROVAR (não só medir)

1. **Validade topológica** (watertight/manifold/Euler) — prova binária sem referência. Maturidade alta.
2. **Betti Matching / persistent homology** — prova estrutura com localização. Recente, maturando rápido.
3. **CAD-as-code** (validar o programa) — empilha 4 provas; o caminho mais provável de quebrar o teto. Emergente.
4. **GD&T + zona mínima (minimax)** — prova "dentro de tolerância" com veredito OK/NOK auditável. Norma industrial.
5. **Procrustes / morfometria** — único que dá p-VALOR ("não difere da classe-alvo"). Precisa de landmarks + população.
6. **Verificação por partes** (part-aware Chamfer/SeaLion, scene graphs, simetria) — pega "partes certas no arranjo errado". Verificador unificado incipiente.
7. **Descritores espectrais** (Shape-DNA, HKS, Zernike) — fortes pra similaridade, teto duro (isospectralidade: "não dá pra ouvir a forma do tambor"). Não provam igualdade.
8. **Hausdorff + Chamfer juntos** — pior caso + erro médio. Medem fidelidade vs ground-truth, não validade.
9. **Juízes aprendidos** (CLIP-3D, VLM/GPT-4V) — os mais gerais e alinhados a humano em plausibilidade (Kendall τ ~0.71), mas semântica grosseira em 2D, com "2D-cheating" documentado. Não provam geometria.
   - https://arxiv.org/abs/2502.08503 (2D-cheating)

## 3. Procedural autoral como prova-por-construção

A virada: o LLM **não desenha o vértice**, ele **escreve a REGRA**. Quem materializa é o motor
procedural determinístico. Forma válida sai de graça porque é resultado de executar a regra, não
um chute a validar depois. Espectro de força:
- **Generativa pura:** L-systems, CGA shape grammar (CityEngine), Infinigen (ground-truth de graça).
- **Por solver:** Answer Set Programming (generate-and-test: restrições rejeitam solução inválida antes de emitir). Garantia formal mais forte.
- **Neurosimbólico (a tese do projeto, formalizada):** LLM gera a regra/spec (neural, falível), solver simbólico garante e verifica. Mais forte que código de LLM puro.
- https://arxiv.org/abs/2310.12945 (3D-GPT) · https://infinigen.org/ · https://arxiv.org/pdf/2507.16405 (neurosimbólico)

**Contra (LEI):** "válido por construção" garante só o que a gramática CONSEGUE EXPRESSAR.
**Válido ≠ bom** — estética/qualidade continua aberta, exige restrição extra ou avaliação.

## 4. Verificação muda com o estilo

- **Highpoly/realista:** proximidade geométrica/perceptual ao denso. Hausdorff + RMS (Metro), QEM, métrica perceptual (Nehmé TOG 2023, 148k julgamentos humanos).
- **Lowpoly de produção:** silhueta + normais bakeadas. O objeto de verificação INCLUI o normal map. Teste: "lê bem em preto puro". Hausdorff cru é a métrica ERRADA aqui (castiga faceta intencional).
- **Lowpoly estilizado:** a métrica se INVERTE — faceta e aresta viva são o OBJETIVO. Verificação automática quase inexistente, é julgamento artístico.
- **View-dependent (LOD/Nanite):** erro em screen-space abaixo de limiar de pixels, depende da câmera.
- **Animado (riggado):** adiciona edge flow que deforma sem colapsar volume. Forma certa não é só a pose estática.
- **Misto:** esquema próprio — gates por região/intenção, não métrica global.

## 5. Recomendação pro motor Larperian — empilhar gates, não substituir

**Gate 0 — validade (sempre, todo domínio/estilo):** watertight/manifold + Euler + self-intersection. Binário, sem referência, pré-requisito de tudo.

**Mecânico (paramétrico):** gere como programa/B-rep e valide o programa (executa? 1 sólido? medida exata via kernel) + GD&T/tolerância (OK/NOK) + Betti (nº certo de furos/cavidades). Contra: depende de ser expressável como programa; min-zone é caro; CAD-as-code é fronteira.

**Orgânico (gramática/L-System):** a gramática é a prova-por-construção da estrutura + Betti/persistent homology (nº certo de galhos) + simetria/proporção (gate barato) + Procrustes com p-valor SE houver população-referência. Contra: Procrustes precisa de landmarks homólogos; gramática garante válido, não bom.

**Camada estrutural-semântica (ambos):** part-aware Chamfer (se houver rótulos) + scene graph de relações ("assento acima das pernas") pra pegar arranjo errado. Verificador unificado é incipiente, monta-se ad-hoc.

**Juiz final (com ceticismo):** VLM sobre renders multi-view RGB + normais como gate de plausibilidade. O mais geral, MAS opera em 2D, alucina, e há "2D-cheating". Usar como SINAL, nunca prova. Baixo-médio como prova, alto como triagem barata.

**Ajuste por estilo:** modula os gates — highpoly liga Hausdorff/QEM/perceptual; lowpoly produção troca fidelidade por silhueta + normal map; lowpoly estilizado desliga penalização de faceta; animado adiciona edge flow.

**O que precisaria ser verdade pra "prova plena":** uma métrica que (1) opere na geometria 3D nativa, não em projeção 2D, (2) tenha noção de correção estrutural E geométrica, (3) seja calibrada contra humano EM geometria. Hoje não existe pronto — Hi3DEval aponta a direção, é fronteira. A porta não está fechada: "render+VLM é o limite" é estado-da-arte, não lei física.
- https://arxiv.org/abs/2508.05609 (Hi3DEval)
