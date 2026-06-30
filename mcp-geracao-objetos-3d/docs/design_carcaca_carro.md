# Design: Modelador de Carcaça de Carro (documento vivo)

> Início: 2026-06-30. Branch: `versao-brasileira-herbert-richers`.
> Status: em definição. Este documento é atualizado conforme as decisões fecham.
> Substitui a tentativa anterior (gerador procedural), encerrada e documentada em
> `docs/postmortem-gerador-veiculos/`.

Este documento registra as definições do novo módulo de modelagem de carro. Ele é
deliberadamente incompleto nas partes ainda em aberto; cada pendência está marcada
de forma explícita na seção 8.

---

## 1. Objetivo desta fase

Modelar **apenas a carcaça** do carro: a casca externa contínua da carroceria.

Fora de escopo nesta fase: porta, roda, vidro, espelho, aerofólio, qualquer recorte
ou peça separada.

A referência mental é a primeira etapa das montadoras, o modelo de superfície
externa (estágio de argila): uma superfície de fora única e contínua, sem painéis
recortados nem aberturas detalhadas.

Consequência prática do escopo: nesta fase o que importa é a **forma da superfície
coincidir com a imagem de referência**, não a organização interna da malha. A
arrumação fina da malha (disposição das faces, definição de arestas) é tema de uma
etapa posterior, quando houver recorte de painel e definição de linhas. Adiantar
isso agora seria trabalho perdido.

---

## 2. Abordagem decidida

A IA constrói a carcaça do zero dentro do Blender.

- Entrada única: a imagem de referência. Não há malha-base pronta. A IA não recebe
  nenhum modelo 3D além da imagem.
- O método é construção guiada pela imagem, dentro de um ciclo de correção visual
  (seção 6).

---

## 3. Caminhos descartados (registrados para não repetir)

- **Motor procedural de varredura de seção.** Descartado: tem teto geométrico real.
  Uma seção fechada e convexa varrida ao longo de um eixo só produz uma cápsula
  lisa. Detalhe completo no post-mortem em `docs/postmortem-gerador-veiculos/`.
- **Malha-base pronta ou baixada.** Descartada: a IA não terá modelo de referência
  além da imagem.
- **Geração automática de 3D a partir da imagem.** Descartada: o resultado vem com a
  malha desorganizada e gera retrabalho de limpeza grande demais.

---

## 4. Imagens de referência

O próprio agente solicita ao Gemini a geração das vistas que considerar necessárias.

Requisitos obrigatórios da imagem gerada:

- Sem marcações, setas, cotas, textos, legendas ou qualquer anotação sobre a imagem.
- Sem ruído visual: fundo limpo, carro isolado.
- O prompt de geração precisa ser detalhado o suficiente para garantir esse padrão
  limpo, sem elementos indesejados.

Observação técnica: a forma 3D só fica determinada com informação de largura, que
vem das vistas de frente e de topo. Apenas a vista lateral obrigaria a IA a inferir
a largura. A definição das vistas necessárias está pendente (seção 8).

---

## 5. O agente (especialista em Blender e modelagem 3D)

O agente é a IA que decide e executa a modelagem. A construção de um agente sólido
é uma etapa própria do projeto, não apenas um detalhe de configuração.

Conhecimento que o agente deve ter:

- Modificadores do Blender e o critério de quando usar cada um.
- Métodos de modelagem de carroceria.
- Topologia (organização da malha) aplicada a carro.
- Catálogo de abordagens de modelagem, para escolher a adequada a cada situação.

O agente não se limita a conhecimento declarativo. Ele opera no ciclo de feedback
visual: gera o render, compara com a imagem de referência, identifica o desvio e
corrige. O julgamento visual no meio do ciclo é parte central da função dele.

Capacidades operacionais já definidas:

- Solicitar ao Gemini imagens de referência limpas, conforme a seção 4.
- Construir a carcaça do zero no Blender.

A detalhar (seção 8): ferramentas concretas que o agente usa, a estrutura do prompt
de sistema do agente, e os limites de atuação.

---

## 6. Ciclo de trabalho

O ciclo de correção visual, repetido até a forma coincidir com a referência:

1. Renderizar a carcaça a partir de vistas fixas.
2. Sobrepor o render à imagem de referência correspondente.
3. Medir o desvio por região.
4. Corrigir a forma da carcaça.
5. Repetir.

---

## 7. Local do módulo

`mcp-geracao-objetos-3d/vehicle_workspace/` (pasta limpa, sem herança do experimento
anterior). As ferramentas serão expostas no mesmo `geracao_3d_mcp.py`, reaproveitando
a ponte com o Blender, o runner headless e o render de vistas que já existem no
projeto.

---

## 8. Pendências (próximas definições)

- Quais vistas de referência o agente vai gerar e usar (lateral, frente, topo,
  traseira), e como ele as alinha dentro do Blender.
- O método inicial concreto de construção da superfície do zero.
- A estrutura técnica do agente: ferramentas, prompt de sistema, limites.
- O alvo de carro desta primeira execução.
