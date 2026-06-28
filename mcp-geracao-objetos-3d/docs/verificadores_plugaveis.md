# Verificadores de forma 3D plugáveis — bibliotecas concretas

> Caça por ferramentas instaláveis (pip/binding) pra cada camada de verificação, com mantenedor,
> maturidade, e a regra anti-overstacking. 6 frentes + síntese. Data: 2026-06-21.

## Resumo

O conjunto que se complementa sem brigar é pequeno. A pergunta certa não é "quais existem"
(dezenas), é "qual conjunto mínimo cobre modos de falha DISTINTOS sem os verificadores brigarem".
Regra-mestre: **1 verificador por modo de falha** (validade ≠ fidelidade ≠ estrutura ≠ percepção).
Dobrar dentro do mesmo buraco é onde nasce o falso-negativo por veto cruzado.

---

## 1. Ferramentas por camada

**Camada A — Validade topológica (watertight/manifold/Euler). Barata, primeiro filtro.**
- **trimesh** (`pip install trimesh`, MIT) — `is_watertight`, `is_winding_consistent`, `is_volume`,
  componentes conexos (pega peça flutuante), `broken_faces`. O porteiro. NÃO faz auto-interseção
  robusta nem winding generalizado. https://github.com/mikedh/trimesh
- **Open3D** (`pip install open3d`, MIT, Intel ISL) — entra só pelo `is_self_intersecting()` /
  `is_edge_manifold`. Não duplicar com trimesh na mesma checagem.

**Camada B — Validade matemática forte.**
- **libigl** (`pip install libigl`, Jacobson/Panozzo, Toronto/NYU) — quem faz winding number robusto
  (`fast_winding_number`, Barill 2018), dentro/fora mesmo em triangle soup; booleana exata e
  auto-interseção via CGAL. https://github.com/libigl/libigl-python-bindings
- **CGAL PMP** (binding parcial — fronteira). Padrão-ouro, mas usar via libigl, não cru.

**Camada C — Reparo pra sair watertight (heurística, escolha de domínio).**
- **pymeshfix** (`pip install pymeshfix`, algoritmo Attene/PyVista) — force-bruta confiável: assume
  um sólido fechado e devolve uma malha watertight. Grosseiro em CAD tesselado.
- **PyMeshLab** (`pip install pymeshlab`, CNR-ISTI Pisa) — canivete de filtros nomeados
  (`repair_non_manifold_edges`, `meshing_close_holes`). Reparo dirigido. API por strings é o atrito.
- **manifold3d** (`pip install manifold3d`, Emmett Lalish — **é o solver Boolean do Blender 4.5+**) —
  não repara lixo, mas GARANTE saída manifold/watertight em booleanas. Validade-por-construção.

**Camada D — Estrutura: ramificação vs buracos (a correção central).**
Homologia NÃO conta galho. Um "Y" e uma reta têm a mesma homologia. Dois eixos separados:
- *Ramificação → esqueleto+grafo:* **skeletor** (`pip install skeletor`, GPL-3) — mesh → curve
  skeleton → networkx; conta nós de grau ≥3, comprimento de ramo. É o caminho prático pra contar
  bifurcação. https://github.com/navis-org/skeletor — ou **scikit-image `skeletonize` + skan**
  (`pip`, BSD-3) pra voxel → grafo de ramos.
- *Buracos/alças/cavidades reais → TDA:* **GUDHI** (`pip`, INRIA) ou **Ripser** (`pip`). Só quando
  há furo/vazio real. Não desperdiçar em forma ramificada sem buraco.

**Camada E — Fidelidade vs referência (mecânico).**
- **PyMeshLab `get_hausdorff_distance`** (Metro do VCGlib) — min/max/mean/RMS. One-sided, rodar nos
  dois sentidos.
- **point-cloud-utils** (`pip install point-cloud-utils`, MIT, F. Williams) — Chamfer, Hausdorff,
  conectividade, make-watertight numa API numpy. Menor atrito pra check duro num loop.
- **fast-simplification** (`pip`, PyVista) — decimação QEM quando precisar.

**Camada F — Qualidade PERCEBIDA (Hausdorff não correlaciona com olho).**
- **MSDM2 / CMDM** (LIRIS/Lyon, Lavoué/Nehmé, no MEPP2) — perceptual sobre curvatura multiescala
  (SSIM pra malha). Atrito: SEM pip, compilar MEPP2 (C++).
- **Graphics-LPIPS** (Nehmé, ACM TOG 2023) — deep perceptual pra malha texturizada, opera sobre
  RENDERS. Encaixa no Blender (já renderiza). https://github.com/MEPP-team/Graphics-LPIPS

**Camada G — VLM/juiz aprendido (só triagem, nunca veto).**
- **GPTEval3D** (3DTopia, CVPR24) — juiz GPT-4V pareado, ELO. https://github.com/3DTopia/GPTEval3D
- **3DCodeBench** (pip+Blender, **traz wrapper nativo pra Claude Code/Codex**; pega geometria
  flutuante/desconectada) e **BlenderGym** — harnesses agênticos se já estamos em loop Blender.

---

## 2. O que agrega de novo (não redundante)

1. **point-cloud-utils** — camada dura de menor atrito (Chamfer+Hausdorff+conectividade+watertight
   numa API numpy). Pronto, confiança alta.
2. **3DCodeBench** — harness que já expõe estado+feedback iterativo com wrapper pra agente de
   código; seu achado (falha dominante = geometria flutuante) é exatamente o defeito que queremos
   pegar. Confiança alta no design, média no esforço (GPU pros scorers).
3. **skeletor/skan** — a correção esqueleto-vs-homologia já operacionalizada: caminho pip direto
   mesh→networkx pra contar ramificação.
4. **Literatura do "quando somar piora"** (Condorcet, calibração) — não é lib, é o critério que
   protege o princípio anti-overstacking: ensemble só ajuda se os erros forem pouco correlacionados.

---

## 3. Stack mínimo recomendado

**MECÂNICO paramétrico:** trimesh (porteiro) + manifold3d (validade-por-construção nas booleanas,
alinha com o Blender) + libigl SÓ pra winding/auto-interseção em casos sujos + PyMeshLab Hausdorff
ou point-cloud-utils (fidelidade vs alvo). **Fora:** TDA (o programa já prova estrutura), juiz
perceptual como veto, CGAL cru.

**ORGÂNICO gramática:** trimesh (validade) + skeletor (mesh→grafo, conta bifurcação — coração do
domínio) ou scikit-image+skan (voxel) + GUDHI/Ripser SÓ quando há furo/alça real. **Fora:**
homologia como contador de galho (não conta), Hausdorff vs referência (raramente há canônica).

**ESTILO/percepção (transversal, opcional, peso baixo):** Graphics-LPIPS se há textura, senão MSDM2;
VLM (GPTEval3D) só triagem. **Fora:** rodar dois/três perceptuais como votos iguais (erros
correlacionados = viés amplificado).

**Regra-mestre:** cada verificador novo tem que cobrir um modo de falha que nenhum outro cobre.

---

## 4. Labs/empresas fora dos EUA (reusável)

- **China (avaliar 3D gerado):** 3DTopia (GPTEval3D, 3DGen-Bench, Hi3DEval — único com avaliação de
  material), SJTU, Tsinghua T3Bench. Código rodável. https://github.com/3DTopia
- **França (QA perceptual de mesh):** LIRIS/Lyon (Lavoué, Nehmé) — MSDM2/CMDM/Graphics-LPIPS +
  datasets. O mais relevante pro eixo qualidade-percebida.
- **Alemanha:** Fraunhofer (OptoInspect3D, industrial não-pip); TU Munich/Nießner (Scan2CAD,
  protocolo Chamfer/F-score); RWTH (OpenMesh).
- **Suíça:** ETH (TetraDiffusion). **Coreia:** KAIST/POSTECH (fortes em geração, fracos em métrica).
- **Japão:** lacuna honesta — não achei benchmark japonês de referência pra validação de forma.

---

## 5. Pronto vs fronteira

**Pronto (pip, confiança alta):** trimesh, Open3D, libigl, pymeshfix, PyMeshLab, manifold3d,
point-cloud-utils, skeletor, scikit-image+skan, GUDHI, Ripser, fast-simplification, GPTEval3D.

**Fronteira (build/conda/checkpoints):** CGAL Python, MSDM2/CMDM (compilar MEPP2), Graphics-LPIPS
(render+pesos), 3DCodeBench/BlenderGym (GPU). DreamReward (pesos não confirmados).

**O contra:** "1 verificador por buraco" é limpo no papel mas alguns se sobrepõem (is_volume já
mistura watertight+winding+orientação) — não forçar pureza onde uma lib cobre dois de graça. E
medir correlação de erros entre os NOSSOS verificadores exige um conjunto de validação real; antes
disso, "escolha por modo de falha distinto" é a melhor heurística, não prova. O teto que pode cair:
quase todo repo não-pip vira plugável com wrapper fino se a gente emitir render+mesh em formato
padrão (glTF/obj + cameras).
