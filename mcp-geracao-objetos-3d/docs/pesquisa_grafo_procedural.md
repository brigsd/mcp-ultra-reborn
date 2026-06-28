# Família "mapa procedural editável" — veredito (2026-06-21)

> Investigação do Proc3D e parentes, lendo os artigos. Pergunta: algum serve de ferramenta, ou de
> blueprint, pra nós?

## Proc3D — FORA (investigado, não serve agora)

[arXiv 2601.12234](https://arxiv.org/abs/2601.12234). Formato PCG (mapa compacto editável), 4-10× mais
enxuto que código, edição local ~400× mais rápida.
- **Não liberado** (sem código/pesos/dataset público).
- **Domínio estreito**: só 5 categorias de móvel feitas de blocos retangulares; fora disso vira "coisa
  de cubos". Não faz orgânico, não é precisão mecânica → não encaixa em nenhum dos nossos lados.
- **NÃO resolve** o problema de nomeação topológica (não discute identidade estável de nó) — que era o
  que a gente esperava dele.
- Sobrevive só o princípio (parâmetro por parte = edição rápida), que já temos com script de parâmetros
  nomeados. Veredito: baixa prioridade, não voltar.

## ProcGen3D — BAIXA prioridade

[arXiv 2511.07142](https://arxiv.org/abs/2511.07142). Imagem RGB → 3D via grafo procedural neural
(transformer autoregressivo).
- **Entrada é imagem** (não é nosso caminho principal, que é pedido→3D).
- **Domínio estreitíssimo**: cacto, árvore, ponte; treinado só em dado sintético.
- **Não liberado**; precisa do modelo treinado deles (não é "promptar um LLM").
- O conceito (imagem de referência → modelo procedural editável) é interessante pro caminho de
  referência, mas este não é o veículo. Vigiar, não adotar.

## ShapeCraft — PROMISSOR (o blueprint mais próximo do nosso projeto)

[arXiv 2510.17603](https://arxiv.org/abs/2510.17603), NeurIPS 2025. LLM agents pra modelagem 3D
estruturada, com representação GPS (grafo de forma procedural).

**Por que importa pra nós:** é praticamente uma instância funcionando da arquitetura que a gente
desenhou. O fluxo dele: um agente Parser decompõe o pedido hierarquicamente → um Coder gera o trecho de
código de cada parte → executa no **Blender** → um agente Evaluator olha o render e realimenta ajustes
("representation bootstrapping"). É parse → grafo → código por nó → Blender → avaliar → iterar.

**O que ele entrega que a gente queria:**
- **Roda com LLM geral, sem fine-tuning** (usa Qwen3 e Qwen-VL via prompting estruturado). Confirma que
  dá pra fazer isso sem treinar modelo.
- **Partes com identidade estável.** Cada nó tem nome e código próprio que persiste → edição local de
  uma parte sem refazer tudo. Isso é a resposta concreta pra "como editar mantendo a identidade" que o
  Proc3D NÃO deu.
- **Backend é Blender** (executa o código de cada nó no Blender, exporta malha) — mesmo palco que o nosso.
- **Valor além de "LLM escreve código"**: parsing hierárquico reduz o espaço de busca do LLM;
  amostragem multi-caminho + iteração visual com avaliador; representação decomposta permite editar,
  animar e plugar geradores externos.

**Caveats honestos:**
- **Não liberado** (só project page, sem GitHub/pesos). Então a gente adota a ARQUITETURA, não o código.
- **Fraco em orgânico** ("struggles com cauda, asa, topologia complexa") — a MESMA fraqueza de todo
  mundo. E é exatamente o buraco que o nosso lado SDF preenche. São complementares: ShapeCraft dá o
  esqueleto de orquestração (parser/coder/avaliador/grafo editável); o SDF dá o motor orgânico que falta.
- Falha em prompt ambíguo/curto/criativo — reforça nossa decisão de normalizar o pedido antes (spec).

**Conclusão:** ShapeCraft é o prior art mais próximo do Larperian inteiro. Não pra usar (não tem código),
mas pra copiar a arquitetura de orquestração e o truque de nó-com-identidade-estável pra edição. Junto
com nosso SDF (orgânico) e B-rep (mecânico), fecha bem o desenho.
