# Pesquisa: o que permite a uma IA gerar 3D com precisão e sem alucinação

> Relatório gerado por deep-research (104 agentes, 22 fontes, 21 claims verificadas
> por votação adversarial 3-agentes). Data: 2026-06-20.
> Foco: framework onde um agente (Claude) gera 3D no Blender via Python/bpy.

## Resposta direta

O que mais dá precisão a um LLM gerando 3D é **escolher uma representação simbólica/paramétrica
executável** (código CAD — CadQuery, bpy, ou sequências sketch-and-extrude) em vez de gerar malha
ou nuvem de pontos direto. Código compacto preserva arestas vivas, é auditável, exporta B-Rep/STEP
e roda na hora para validação.

Mas isso **sozinho não fecha o gap**. Na geração single-shot, o melhor GPT-4 acerta só ~17.5%
(benchmark 3D-PreMise) e o erro dominante é justamente "precisão espacial". A maior alavanca
comprovada é o **loop de verificação com feedback de uma fonte de verdade geométrica**:

- Solver de restrição no loop: alinhamento por RL sobe sketches totalmente restritos de 8.9% → 93%.
- Feedback multi-view de VLM: CADCodeVerify e EvoCAD chegam a ~87% de correção topológica.
- Feedback de simulação física (FEA): aprovação de requisitos 38.8% → 60.5%.

Para um sistema LLM+Blender/bpy: gerar código paramétrico, executar/renderizar, e **iterar com
verificação automática** é a arquitetura de maior precisão pela evidência atual. Solvers de
restrição são o componente mais subexplorado e de maior alavanca.

## Ranking das representações (maior → menor alavanca de precisão)

1. **Código paramétrico + solver de restrição** (AIDL/SolveSpace) — o LLM emite estrutura e
   restrições, o solver calcula a geometria. O LLM não calcula coordenadas. Precisão por
   construção/verificação.
2. **Código CAD paramétrico / B-Rep** (CadQuery→OpenCASCADE, Text2CAD sketch-and-extrude, bpy)
   com export STEP.
3. **CSG via código** (sólidos construtivos).
4. **Malha direta.**
5. **Nuvem de pontos / implícitos (NeRF, Gaussian Splatting).**

Quanto mais alto, mais a estrutura impede a alucinação por construção em vez de só medir o erro
depois. Ressalva importante: essa vantagem vale para **geometria mecânica/CAD**. Para formas
**orgânicas/freeform**, malha e implícitos podem ser melhores e o ranking se inverte parcialmente.

## Achados verificados (com fontes)

### 1. Representação paramétrica > malha/nuvem (confiança ALTA, 3-0)
Código CAD cria modelos totalmente paramétricos com pouco código, exporta STEP/AMF/STL. Malha
importada vira "blob amorfo não-editável"; implícitos perdem arestas vivas na conversão.
Fontes: [EvoCAD](https://arxiv.org/pdf/2510.11631), [Text-to-CadQuery](https://arxiv.org/pdf/2505.06507),
[Don't Mesh with Me](https://arxiv.org/pdf/2411.15279), [Zoo.dev](https://zoo.dev/blog/introducing-text-to-cad),
[3D-PreMise](https://arxiv.org/pdf/2401.06437).

### 2. Single-shot LLM→3D é muito ruim (confiança ALTA, 3-0)
3D-PreMise (57 objetos industriais): GPT-4 one-shot CoT 17.5%, zero-shot 7.0% Pass@1. Erro
dominante = precisão espacial. A representação certa é necessária mas insuficiente sem loop.
Fontes: [3D-PreMise](https://arxiv.org/pdf/2401.06437), [FEA-feedback](https://arxiv.org/html/2605.17448v1).

### 3. Solver de restrição no loop é a maior alavanca (confiança ALTA, 3-0)
Alinhamento por RL (RLOO) leva sketches totalmente restritos de 8.9% (sem) → 34% (SFT) → 93%,
usando o solver do Autodesk Fusion como recompensa verificável.
Ressalva: preprint não revisado, escopo é sketch 2D — transferência ao 3D é analógica.
Fonte: [RL-constraint-alignment](https://arxiv.org/html/2504.13178v1).

### 4. Loop de verificação por visão funciona (confiança ALTA, 3-0)
CADCodeVerify (VLM gera e responde perguntas de validação sobre o render, corrige desvios):
-7.3% point-cloud distance, +5% taxa de sucesso. EvoCAD (loop evolutivo com ranking VLM): 87.2%
correção topológica vs ~80% dos baselines single-pass.
Ressalva: ganhos modestos, auto-reportados; melhora só aparece após a 2ª geração.
Fontes: [CADCodeVerify](https://arxiv.org/pdf/2410.05340), [EvoCAD](https://arxiv.org/pdf/2510.11631).

### 5. Fine-tuning/RL no alvo de código melhora acurácia (confiança ALTA, 3-0)
Text-to-CadQuery: top-1 exact match 58.8% → 69.3%, Chamfer Distance -48.6%. CAD-Coder usa
recompensa geométrica (Chamfer) + formato via GRPO.
Fontes: [Text-to-CadQuery](https://arxiv.org/pdf/2505.06507), [CAD-Coder](https://arxiv.org/pdf/2505.19713).

### 6. Feedback de simulação física (FEA) (confiança MÉDIA, 2-1)
Loop com solver estrutural CalculiX: aprovação de requisitos 38.8% → 60.5%. Caro (~68 min/item),
"work in progress". Relevante quando há requisitos funcionais, não só forma.
Fonte: [FEA-feedback](https://arxiv.org/html/2605.17448v1).

### 7. Maturidade dos sistemas reais (confiança ALTA, 3-0)
- **Produção/comercial:** Zoo.dev Text-to-CAD (gera B-Rep, exporta STEP, ~16% erro, fraco em
  geometria complexa/criativa).
- **Pesquisa madura:** Text2CAD (NeurIPS 2024), CADCodeVerify (ICLR 2025), CAD-Coder (NeurIPS 2025),
  Text-to-CadQuery, EvoCAD (ICTAI 2025), AIDL (Pacific Graphics 2025).
- **Experimental/diagnóstico:** 3D-PreMise, geração bpy single-shot estilo BlenderGPT (precisão
  baixa), FEA-feedback.
- **Onde alucinam:** precisão de coordenadas, geometria orgânica/complexa, primeira tentativa.

## Claims REFUTADAS na verificação (não acreditar nelas)

- Que CadQuery "impede alucinação ilimitada" só por ser auditável — refutada 0-3. A
  representação ajuda mas não é a alavanca decisiva sozinha.
- Que modelos de fronteira (GPT-5.5, Claude Opus 4.7) produzem zero artefatos válidos na
  primeira tentativa — refutada 0-3. Não dá pra afirmar isso.

## Lacunas de evidência (não saíram claims verificadas)

- **Auditoria de malha/topologia** (non-manifold, normais, n-gons) e **retopologia automática**
  (Instant Meshes, QuadriFlow) no loop — não retornaram evidência. É lacuna, não prova de
  irrelevância.
- **Differentiable rendering** como sinal de auto-correção vs VLM multi-view — sem comparação
  verificada.

## Perguntas em aberto

1. Quanto da precisão-por-construção do solver (8.9%→93%, demonstrada em sketch 2D) transfere
   pra um gerador 3D LLM+bpy? SolveSpace/FreeCAD sketcher podem entrar no loop de um agente bpy?
2. Rodar verificadores de malha (Instant Meshes/QuadriFlow) no loop melhora a validade da malha
   gerada? Como usar como sinal de feedback?
3. Differentiable rendering fecha mais ou menos gap que feedback VLM multi-view?
4. Para "objetos em geral" incluindo orgânico/freeform, qual representação híbrida (paramétrico
   pra mecânico + malha/SDF pra orgânico, com roteamento por tipo) maximiza precisão?

## Ressalva geral de tempo

3D-PreMise é da era GPT-4 (jan/2024) — tratar o 17.5% como piso histórico, não estado-da-arte.
O campo move rápido. Vários ganhos de loop são auto-reportados em benchmarks próprios e de
magnitude modesta. O resultado mais forte (solver 8.9%→93%) é preprint 2D.
