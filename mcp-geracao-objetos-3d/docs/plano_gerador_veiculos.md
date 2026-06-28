# Plano de Implementacao - Gerador Procedural de Veiculos

> Data: 2026-06-28.
> Escopo: criar um workspace e um conjunto de ferramentas MCP para gerar veiculos
> com precisao dimensional, boa fidelidade a blueprints/referencias e iteracao
> automatica no Blender/headless. Este plano complementa `plano_mestre.md`.

---

## 1. Objetivo

Construir um gerador procedural de veiculos que permita a uma IA criar, medir,
renderizar, auditar e corrigir modelos de veiculos a partir de:

- um prompt textual;
- um preset/arquetipo, como `supercar`, `sedan`, `suv`, `pickup`, `van`, `truck`;
- uma imagem de referencia;
- um blueprint com vistas ortograficas;
- medidas conhecidas, como comprimento, largura, altura e entre-eixos.

O objetivo nao e apenas "fazer um carro bonito". O objetivo e criar um sistema que
transforma referencias em uma representacao intermediaria verificavel e, a partir
dela, gera geometria de forma automatica.

O sistema deve privilegiar:

- fidelidade de proporcao;
- controle dimensional;
- simetria;
- edicao parametrica;
- iteracao automatica;
- rastreabilidade do erro;
- custo baixo de tokens para a IA orquestradora.

---

## 2. Tese central

A melhor abordagem para veiculos e hibrida:

1. **Blueprint/spec primeiro, malha depois.**
   A IA nao deve escrever Blender Python direto a partir de uma imagem. Primeiro a
   referencia vira `VehicleSpec`, landmarks, curvas, secoes e restricoes.

2. **Rig dimensional como fonte de verdade.**
   Antes de qualquer carroceria, o sistema cria um esqueleto com origem, eixos,
   rodas, bitolas, altura livre do solo, comprimento total, largura e altura.

3. **Carroceria por curvas e loft.**
   A carroceria principal deve nascer de curvas e secoes transversais, nao de uma
   colecao de cubos booleanados. Isso preserva continuidade, silhueta e controle.

4. **Detalhes por grafo de features.**
   Farol, lanterna, splitter, difusor, asa, entradas de ar, vincos, portas e
   para-lamas sao features ancoradas em partes do rig/body, com parametros
   nomeados e verificaveis.

5. **Modificadores nao destrutivos encapsulados.**
   Mirror, Bevel, Subdivision Surface, Shrinkwrap, Solidify, Boolean, Weighted
   Normals e Geometry Nodes devem virar presets/ferramentas internas. A IA escolhe
   intencoes; o sistema aplica stacks seguros.

6. **Loop gerar -> renderizar -> medir -> comparar -> corrigir.**
   O modelo nao e aceito porque "parece bom". Ele passa por auditoria numerica,
   comparacao visual automatica e, opcionalmente, avaliacao visual por Gemini/VLM.

---

## 3. Resultado esperado

No MVP, o sistema deve gerar veiculos com:

- proporcoes gerais corretas;
- rodas no lugar correto;
- altura, comprimento, largura e wheelbase medidos;
- carroceria coerente;
- cabine e vidros posicionados;
- para-lamas alinhados as rodas;
- frente/traseira distintas;
- render ortografico de frente, lado, topo, traseira e perspectiva;
- relatorio de erro dimensional e visual.

Na versao madura, o sistema deve tambem gerar:

- farois e lanternas por contorno;
- entradas de ar por boolean/corte parametricos;
- vincos e linhas de painel por curvas projetadas;
- rodas parametrizadas por padrao radial;
- difusores, splitters, spoilers e asas;
- interior simples;
- variacoes por estilo;
- iteracao automatica contra blueprint.

---

## 4. Estrutura proposta de workspace

Criar a pasta:

```text
mcp-geracao-objetos-3d/
  vehicle_workspace/
    README.md
    specs/
      examples/
        supercar_sv24.json
        suv_generic.json
        pickup_generic.json
    archetypes/
      supercar.json
      sedan.json
      hatch.json
      suv.json
      pickup.json
      van.json
      truck.json
      bus.json
      motorcycle.json
      sci_fi.json
    references/
      blueprints/
      images/
      extracted/
    vehicle/
      __init__.py
      schema.py
      units.py
      coordinate_system.py
      archetypes.py
      spec_normalizer.py
      feature_graph.py
    generators/
      rig.py
      blockout.py
      body_loft.py
      wheels.py
      tires.py
      glass.py
      lights.py
      aero.py
      intakes.py
      panel_lines.py
      mirrors.py
      interior.py
    modifiers/
      mirror_stack.py
      bevel_stack.py
      subdivision_stack.py
      boolean_cutters.py
      shrinkwrap_projectors.py
      geometry_nodes.py
    validation/
      dimensions.py
      symmetry.py
      wheel_fitment.py
      silhouette.py
      clearance.py
      mesh_health.py
      feature_presence.py
    rendering/
      cameras.py
      orthographic_views.py
      diagnostic_materials.py
      overlays.py
    orchestration/
      pipeline.py
      iteration.py
      budgets.py
      reports.py
    outputs/
      blends/
      gltf/
      stl/
      renders/
      reports/
```

Separar `vehicle_workspace/` do gerador mecanico atual evita misturar regras de
pecas CAD com regras de design automotivo. O sistema de veiculos ainda pode
reutilizar `catalog/`, `api/`, `prototype/render_views.py` e a ponte headless.

---

## 5. Sistema de coordenadas e unidades

Padrao obrigatorio:

- unidade interna: metros;
- entrada/saida humana: milimetros;
- eixo X: comprimento do veiculo, frente positiva;
- eixo Y: largura, esquerda/direita;
- eixo Z: altura;
- origem: centro do entre-eixos no chao, em `Z=0`;
- frente do veiculo: `+X`;
- lado esquerdo: `+Y`;
- simetria primaria: plano `X/Z`, espelhando `Y`.

Exemplo:

```text
front axle x = +wheelbase / 2
rear axle x  = -wheelbase / 2
ground       = z 0
vehicle mid  = y 0
```

Isso precisa ser imposto por codigo. Nao pode ficar como convencao implicita.

---

## 6. VehicleSpec

O `VehicleSpec` e o contrato principal. Ele deve ser serializavel em JSON e conter
apenas parametros nomeados, unidades explicitas e assercoes verificaveis.

Exemplo inicial:

```json
{
  "schema_version": "0.1",
  "name": "SV-24 inspired supercar",
  "archetype": "supercar",
  "units": "mm",
  "dimensions": {
    "length": 4750,
    "width": 2020,
    "height": 1210,
    "wheelbase": 2680,
    "front_track": 1890,
    "rear_track": 1875,
    "ground_clearance": 110
  },
  "wheels": {
    "count": 4,
    "front_diameter": 720,
    "rear_diameter": 740,
    "front_rim": 20,
    "rear_rim": 21,
    "front_width": 265,
    "rear_width": 325
  },
  "layout": {
    "engine": "mid",
    "doors": 2,
    "seats": 2,
    "cab_forward": 0.48,
    "roof_peak_x_ratio": 0.04
  },
  "style": {
    "silhouette": "low_wedge",
    "front": "aggressive_splitter",
    "rear": "diffuser_wing",
    "surface_language": "sharp_creased",
    "headlights": "thin_angular_led",
    "taillights": "wide_layered_led"
  },
  "features": {
    "active_rear_wing": true,
    "large_rear_diffuser": true,
    "side_intakes": true,
    "front_splitter": true
  },
  "constraints": [
    {"id": "length", "type": "dimension", "target_mm": 4750, "tolerance_mm": 15},
    {"id": "wheelbase", "type": "dimension", "target_mm": 2680, "tolerance_mm": 8},
    {"id": "symmetry_y", "type": "symmetry", "max_error_mm": 2},
    {"id": "wheel_clearance", "type": "clearance", "min_mm": 20}
  ]
}
```

Regras:

- texto cru nunca vai direto para o gerador;
- prompt e imagem sao normalizados para `VehicleSpec`;
- todo numero importante vira constraint;
- toda feature importante tem id estavel;
- parametros devem ser editaveis sem remendar a malha.

---

## 7. Archetypes

O gerador deve ser generico para veiculos, mas especializado por arquetipo.

Arquetipos iniciais:

```text
supercar
sedan
hatch
suv
pickup
van
truck
bus
motorcycle
sci_fi
```

Cada arquetipo define:

- faixa de proporcoes;
- numero de rodas/eixos;
- posicao de cabine;
- relacao capo/cabine/traseira;
- altura livre do solo;
- tamanho tipico das rodas;
- volume principal;
- features comuns;
- validadores especificos;
- presets de estilo.

Exemplo:

```json
{
  "id": "supercar",
  "length_range_mm": [4200, 5200],
  "height_range_mm": [1050, 1300],
  "wheelbase_ratio_range": [0.54, 0.60],
  "cabin_position": "mid_forward",
  "engine_layouts": ["mid", "rear_mid"],
  "required_features": ["low_roof", "wide_track", "large_wheels"],
  "optional_features": ["active_wing", "diffuser", "side_intakes"]
}
```

Para veiculos muito diferentes, como motocicleta, caminhao articulado, tanque ou
trem, o nucleo de `VehicleSpec` ainda serve, mas os geradores mudam bastante. A
arquitetura deve permitir subfamilias sem forcar tudo no mesmo molde de carro.

---

## 8. Referencias e blueprints

O sistema deve aceitar:

- blueprint com multiplas vistas numa unica imagem;
- imagens soltas por vista;
- foto de referencia;
- prompt textual;
- medidas conhecidas pelo usuario.

Pipeline recomendado:

```text
imagem/prompt
  -> detectar vistas
  -> calibrar escala
  -> extrair landmarks
  -> extrair curvas/silhuetas
  -> criar VehicleSpec
  -> gerar rig
  -> gerar blockout/body
  -> renderizar vistas equivalentes
  -> comparar overlay
```

### 8.1 Calibracao de blueprint

Ferramenta:

```text
car_calibrar_blueprint(imagem_path, medidas_json)
```

Entrada:

```json
{
  "known_measurements": [
    {"view": "side", "name": "length", "value_mm": 4750},
    {"view": "side", "name": "wheelbase", "value_mm": 2680},
    {"view": "front", "name": "front_track", "value_mm": 1890},
    {"view": "top", "name": "width", "value_mm": 2020}
  ]
}
```

Saida:

```json
{
  "views": {
    "front": {"bbox_px": [20, 20, 420, 210], "scale_mm_per_px": 4.72},
    "side": {"bbox_px": [20, 250, 520, 520], "scale_mm_per_px": 8.91},
    "top": {"bbox_px": [560, 240, 1010, 520], "scale_mm_per_px": 4.50},
    "rear": {"bbox_px": [560, 20, 980, 210], "scale_mm_per_px": 4.68}
  }
}
```

### 8.2 Landmarks

Ferramenta:

```text
car_extrair_landmarks(imagem_path, calibracao_json)
```

Landmarks importantes:

- eixo dianteiro;
- eixo traseiro;
- contato dos pneus com o solo;
- topo do teto;
- ponta dianteira;
- ponta traseira;
- base do parabrisa;
- base do vidro traseiro;
- linha de cintura;
- centro das rodas;
- arco dos para-lamas;
- contorno do vidro;
- farois;
- lanternas;
- splitter;
- difusor;
- asa/spoiler;
- entradas de ar laterais.

Landmarks podem ser extraidos por visao automatica, por Gemini/VLM ou por marcacao
manual assistida no futuro. O formato deve ser o mesmo em todos os casos.

---

## 9. Representacao intermediaria

A fidelidade a blueprint depende mais da representacao intermediaria do que da
malha final.

Representacoes necessarias:

### 9.1 Curvas de silhueta

Curvas principais:

- `side_roofline`;
- `side_hoodline`;
- `side_beltline`;
- `side_rocker`;
- `side_rear_deck`;
- `top_outer_body`;
- `top_cabin`;
- `front_outer_body`;
- `rear_outer_body`;
- `front_headlight_contours`;
- `rear_taillight_contours`.

Formato:

```json
{
  "id": "side_roofline",
  "view": "side",
  "space": "vehicle_mm",
  "points": [[-900, 0, 980], [-300, 0, 1210], [700, 0, 1110]],
  "degree": 3,
  "closed": false
}
```

### 9.2 Secoes transversais

O corpo principal deve ser gerado por secoes em X:

```text
nose_tip
front_overhang_mid
front_axle
hood_mid
windshield_base
roof_peak
rear_glass
rear_axle
rear_overhang_mid
tail
```

Cada secao define largura, altura, raio/curvatura, linha de cintura e envelope.

### 9.3 Feature graph

O grafo de features preserva identidade estavel:

```json
{
  "nodes": [
    {"id": "body_main", "type": "loft_body"},
    {"id": "front_left_headlight", "type": "light", "anchor": "front_fascia"},
    {"id": "rear_diffuser", "type": "aero_diffuser", "anchor": "rear_lower"},
    {"id": "active_wing", "type": "wing", "anchor": "rear_deck"}
  ],
  "edges": [
    {"from": "body_main", "to": "front_left_headlight", "relation": "supports"},
    {"from": "body_main", "to": "rear_diffuser", "relation": "cuts_into"}
  ]
}
```

Correcoes devem alterar parametros do no, nao editar vertices finais.

---

## 10. Geradores internos

Os geradores internos sao pacotes Python chamados pelo MCP. Nem todos precisam ser
ferramentas MCP publicas.

### 10.1 `rig.py`

Responsavel por criar:

- eixo central;
- planos de referencia;
- bounding box do veiculo;
- posicoes das rodas;
- bitolas;
- ground plane;
- marcas de comprimento/largura/altura;
- cameras ortograficas.

Deve retornar `RigReport`.

### 10.2 `blockout.py`

Gera massas simples:

- corpo principal;
- cabine;
- volumes de capo/traseira;
- rodas temporarias;
- para-lamas simples.

Serve para validar proporcao antes da carroceria refinada.

### 10.3 `body_loft.py`

Motor principal da carroceria.

Entrada:

- `VehicleSpec`;
- curvas laterais/topo/frente/traseira;
- secoes transversais.

Saida:

- mesh de carroceria;
- curvas de controle;
- relatorio de dimensoes;
- anchors para features.

Implementacao sugerida:

- construir metade do carro em `Y >= 0`;
- gerar secoes como curvas Bezier/NURBS;
- interpolar secoes ao longo de X;
- criar surface/mesh por loft;
- aplicar Mirror;
- aplicar Subdivision Surface controlado;
- aplicar Weighted Normals.

### 10.4 `wheels.py` e `tires.py`

Rodas devem ser parametrizadas e precisas:

- pneu como torus ou perfil revolvido;
- aro por cilindros/aneis;
- raios via padrao radial;
- cubo central;
- parafusos/porcas opcionais;
- disco de freio e pinca reutilizando catalogo mecanico.

Para rodas, Geometry Nodes ou gerador radial dedicado sao mais eficientes que
malha manual.

### 10.5 `glass.py`

Gera:

- parabrisa;
- vidro lateral;
- vidro traseiro;
- teto de vidro opcional.

Abordagem:

- contorno por curva;
- superficie levemente deslocada da carroceria;
- material transparente;
- espessura via Solidify leve;
- Shrinkwrap opcional sobre body.

### 10.6 `lights.py`

Farois e lanternas devem ser gerados por contorno:

- detectar/receber curva do farol;
- criar lente por superficie;
- adicionar tiras LED;
- usar emissive material;
- opcionalmente booleanar recesso na carroceria.

MVP: farois por presets.
Versao madura: farois por mascara/contorno extraido do blueprint.

### 10.7 `aero.py`

Gera:

- splitter dianteiro;
- canards;
- difusor traseiro;
- asa fixa/ativa;
- spoiler;
- aletas de difusor.

Essas features sao boas candidatas a B-rep/mesh parametricas, pois exigem arestas
limpas e medidas controladas.

### 10.8 `intakes.py`

Entradas de ar:

- lateral;
- frontal;
- capô;
- teto;
- traseira.

Abordagem:

- curva de contorno;
- cutter boolean;
- moldura chanfrada;
- malha interna/grade via Geometry Nodes;
- validacao de existencia e posicao.

### 10.9 `panel_lines.py`

Linhas de painel sao essenciais para fidelidade visual.

Abordagens:

- curvas projetadas na carroceria;
- sulcos por bevel/boolean raso;
- material escuro em curvas finas;
- decals/curves no MVP, geometria real depois.

Itens:

- portas;
- capo;
- tampa traseira;
- para-choques;
- para-lamas;
- linha de cintura;
- molduras de vidro.

---

## 11. Modificadores e addons a encapsular

O sistema deve expor intencoes, nao detalhes crus do Blender.

### 11.1 Mirror

Uso:

- gerar apenas metade do veiculo;
- preservar simetria;
- reduzir custo de modelagem.

Ferramenta interna:

```text
apply_vehicle_mirror(obj, axis="Y", merge_tolerance_mm=1)
```

### 11.2 Bevel

Uso:

- acabamento de bordas;
- farois;
- entradas de ar;
- difusor;
- splitter;
- vincos.

Presets:

```text
body_soft_edge
panel_gap
aero_sharp
wheel_metal
glass_edge
```

### 11.3 Subdivision Surface

Uso:

- suavizar carroceria;
- preservar hard edges por crease/bevel auxiliar.

Regra:

- body recebe SubD controlado;
- pecas mecanicas/aero podem ficar com bevel + weighted normals.

### 11.4 Shrinkwrap

Uso:

- colar vidro, curvas de painel e detalhes sobre carroceria;
- projetar feature em superficie complexa.

### 11.5 Solidify

Uso:

- espessura de splitter;
- vidro;
- paineis finos;
- asas.

### 11.6 Boolean

Uso:

- entradas de ar;
- cavidades de farol;
- difusor;
- caixas de roda.

Regra:

- cutters devem ter id;
- booleans devem ser auditaveis;
- nunca destruir sem salvar parametro/cutter.

### 11.7 Weighted Normals

Uso:

- melhorar shading sem aumentar densidade;
- essencial para partes hard-surface.

### 11.8 Geometry Nodes

Uso:

- grade;
- repeticao de LEDs;
- raios de roda;
- difusor;
- padroes de ventilacao;
- parafusos;
- malhas/colmeias.

Encapsular como presets parametrizados, nao como node tree manual escrita pela IA.

### 11.9 Addons candidatos

Prioridade:

- Blender nativo primeiro;
- Geometry Nodes para repeticao;
- BMesh para controle de malha;
- curvas Bezier/NURBS para silhueta;
- bibliotecas externas somente se trouxerem ganho real.

Possiveis investigacoes futuras:

- CAD Sketcher/build123d para subconjuntos mecanicos;
- Sverchok/Geometry Nodes para grafos procedurais;
- OpenCV/scikit-image para extracao de contorno;
- trimesh para auditoria de malha fora do Blender.

---

## 12. Ferramentas MCP propostas

As ferramentas MCP devem ser poucas, de alto nivel e compostas. As funcoes
pequenas vivem dentro do workspace.

### 12.1 `vehicle_criar_spec`

```text
vehicle_criar_spec(prompt: str, referencia_path: str = "", medidas_json: str = "{}") -> str
```

Cria um `VehicleSpec` normalizado.

Fontes:

- prompt;
- medidas fornecidas;
- arquetipo;
- imagem/blueprint opcional;
- Gemini/VLM opcional para interpretacao semantica.

### 12.2 `vehicle_calibrar_blueprint`

```text
vehicle_calibrar_blueprint(imagem_path: str, medidas_json: str) -> str
```

Detecta vistas, escala em mm/pixel e regioes relevantes.

### 12.3 `vehicle_extrair_landmarks`

```text
vehicle_extrair_landmarks(imagem_path: str, calibracao_json: str) -> str
```

Extrai landmarks e curvas iniciais. No MVP pode devolver landmarks aproximados
por heuristica/manual assistido; depois evolui para CV/VLM.

### 12.4 `vehicle_gerar_rig`

```text
vehicle_gerar_rig(spec_json: str) -> str
```

Gera rig dimensional no Blender/headless e salva `.blend`/renders diagnosticos.

### 12.5 `vehicle_gerar_blockout`

```text
vehicle_gerar_blockout(spec_json: str) -> str
```

Gera forma bruta para validar proporcoes.

### 12.6 `vehicle_gerar_modelo`

```text
vehicle_gerar_modelo(spec_json: str, landmarks_json: str = "{}", qualidade: str = "draft") -> str
```

Gera veiculo completo ou semi-completo.

Qualidades:

- `draft`: rapido, blockout refinado;
- `standard`: body loft + rodas + vidro + features principais;
- `high`: detalhes, panel lines, aero, luzes, auditoria completa.

### 12.7 `vehicle_renderizar_vistas`

```text
vehicle_renderizar_vistas(modelo_id: str, modo: str = "diagnostic") -> str
```

Renderiza:

- frente;
- lado;
- topo;
- traseira;
- perspectiva;
- wire/normal/curvature opcional.

### 12.8 `vehicle_auditar`

```text
vehicle_auditar(modelo_id: str, spec_json: str, blueprint_json: str = "{}") -> str
```

Roda verificadores:

- dimensoes;
- simetria;
- wheel fitment;
- clearance;
- mesh health;
- feature presence;
- silhouette overlay se houver blueprint.

### 12.9 `vehicle_comparar_blueprint`

```text
vehicle_comparar_blueprint(renders_json: str, blueprint_json: str) -> str
```

Compara render ortografico com blueprint calibrado e devolve erro por regiao.

### 12.10 `vehicle_iterar`

```text
vehicle_iterar(spec_json: str, audit_json: str, limite_json: str = "{}") -> str
```

Gera uma nova spec corrigida. Importante: corrige parametros, nao mesh final.

### 12.11 `vehicle_pipeline`

```text
vehicle_pipeline(prompt: str, referencia_path: str = "", medidas_json: str = "{}", budget_json: str = "{}") -> str
```

Ferramenta composta:

```text
criar_spec
  -> calibrar/extrair se houver imagem
  -> gerar_rig
  -> gerar_blockout
  -> gerar_modelo
  -> renderizar
  -> auditar
  -> iterar ate budget
```

Essa e a ferramenta que a IA usaria na maior parte do tempo.

---

## 13. Validadores

Validadores devem rodar fora do processo que gera a geometria sempre que possivel.
O gerador nao deve conseguir "enganar" o verificador.

### 13.1 Dimensoes

Mede:

- comprimento total;
- largura total;
- altura total;
- wheelbase;
- track dianteira/traseira;
- diametro das rodas;
- ground clearance.

Saida:

```json
{
  "dimension_errors": {
    "length": {"target_mm": 4750, "actual_mm": 4741, "error_mm": -9, "pass": true},
    "height": {"target_mm": 1210, "actual_mm": 1268, "error_mm": 58, "pass": false}
  }
}
```

### 13.2 Simetria

Compara lado esquerdo/direito:

- bounding boxes;
- vertices espelhados se possivel;
- features duplicadas;
- rodas e luzes.

### 13.3 Wheel fitment

Checa:

- rodas tocam o solo;
- rodas nao invadem demais a carroceria;
- arcos cobrem as rodas;
- centro da roda bate com eixo;
- diametro bate com spec;
- pneus tem folga minima.

### 13.4 Mesh health

Checa:

- objetos vazios;
- normais invertidas;
- non-manifold;
- faces degeneradas;
- escala nao aplicada;
- objetos duplicados;
- densidade exagerada.

### 13.5 Silhouette overlay

Compara cada vista com blueprint:

- render ortografico em branco/preto;
- extracao de contorno;
- alinhamento por escala calibrada;
- erro por regiao;
- heatmap.

Saida recomendada:

```json
{
  "view": "side",
  "overall_iou": 0.82,
  "regions": {
    "front_overhang": {"error_px": 18, "direction": "too_short"},
    "roof": {"error_px": 24, "direction": "too_high"},
    "rear_deck": {"error_px": 31, "direction": "too_low"}
  }
}
```

### 13.6 Feature presence

Checa se as features pedidas existem:

- active wing;
- diffuser;
- splitter;
- side intakes;
- headlights;
- taillights;
- mirrors;
- doors/panel lines.

No MVP, pode ser baseado em objetos nomeados. Depois, pode cruzar com analise
visual.

---

## 14. Uso do Gemini/VLM

Gemini ou outro VLM deve ser usado como avaliador visual e interpretador
semantico, nao como fonte unica de geometria.

Usos bons:

- identificar arquetipo e estilo da imagem;
- extrair lista de features;
- sugerir landmarks em blueprint;
- criticar renders;
- apontar problemas de identidade visual;
- gerar texto estruturado para ajustes.

Usos ruins:

- inventar medidas finais sem calibracao;
- decidir tolerancia dimensional;
- substituir validadores numericos;
- escrever malha diretamente.

Resposta esperada do VLM:

```json
{
  "identity_score": 78,
  "visual_issues": [
    {"region": "roof", "issue": "roof appears too tall", "severity": "high"},
    {"region": "front", "issue": "headlights are not angular enough", "severity": "medium"}
  ],
  "suggested_parameter_changes": {
    "roof_height_delta_mm": -45,
    "cabin_x_delta_mm": -80,
    "front_headlight_preset": "thin_angular"
  }
}
```

A decisao final de alterar parametros fica com o orquestrador.

---

## 15. Pipeline de implementacao

### Fase 0 - Preparacao

Objetivo: criar base sem gerar veiculo ainda.

Entregas:

- `vehicle_workspace/README.md`;
- `vehicle/schema.py`;
- `vehicle/units.py`;
- `vehicle/coordinate_system.py`;
- exemplos de `VehicleSpec`;
- arquetipos iniciais.

Criterio de pronto:

- carregar spec JSON;
- validar schema;
- normalizar mm -> metros;
- recusar spec incompleta com erro claro.

### Fase 1 - Rig dimensional

Objetivo: provar que medidas e cameras funcionam.

Entregas:

- `generators/rig.py`;
- MCP tool `vehicle_gerar_rig`;
- render diagnostico do rig;
- relatorio dimensional.

Criterio de pronto:

- eixos das rodas na posicao correta;
- bounding box bate com spec;
- cameras ortograficas enquadram corretamente;
- relatorio retorna comprimento/largura/altura/wheelbase.

### Fase 2 - Blockout veicular

Objetivo: gerar massa bruta por arquetipo.

Entregas:

- `generators/blockout.py`;
- `generators/wheels.py` simples;
- `validation/dimensions.py`;
- `validation/wheel_fitment.py`;
- MCP tool `vehicle_gerar_blockout`.

Criterio de pronto:

- supercar, SUV e pickup geram silhuetas diferentes;
- rodas estao posicionadas e escaladas;
- dimensoes principais passam com tolerancia;
- renders de 4/5 vistas sao gerados.

### Fase 3 - Body loft

Objetivo: substituir bloco por carroceria continua.

Entregas:

- `generators/body_loft.py`;
- secoes transversais parametrizadas;
- curvas de controle;
- Mirror/SubD/Weighted Normals encapsulados;
- anchors para features.

Criterio de pronto:

- carroceria e gerada a partir de secoes;
- teto, capo, traseira e laterais respondem a parametros;
- modelo continua simetrico;
- wheel arches ficam coerentes.

### Fase 4 - Blueprint calibration e silhouette compare

Objetivo: fechar o primeiro loop de fidelidade.

Entregas:

- `vehicle_calibrar_blueprint`;
- `vehicle_extrair_landmarks` MVP;
- `validation/silhouette.py`;
- `rendering/overlays.py`;
- relatorio de erro visual por vista.

Criterio de pronto:

- blueprint com medidas conhecidas vira escala;
- render lateral compara contra side view;
- sistema aponta regioes divergentes;
- pelo menos uma correcao parametrica reduz erro.

### Fase 5 - Features principais

Objetivo: dar identidade visual reconhecivel.

Entregas:

- `generators/glass.py`;
- `generators/lights.py`;
- `generators/aero.py`;
- `generators/intakes.py`;
- `generators/panel_lines.py`;
- `validation/feature_presence.py`.

Criterio de pronto:

- supercar com farois, vidros, splitter, difusor e asa;
- features tem ids estaveis;
- features aparecem nos renders;
- auditoria confirma presenca.

### Fase 6 - Iteracao automatica

Objetivo: reduzir trabalho da IA cerebro.

Entregas:

- `orchestration/pipeline.py`;
- `orchestration/iteration.py`;
- `orchestration/budgets.py`;
- MCP tool `vehicle_pipeline`;
- MCP tool `vehicle_iterar`.

Criterio de pronto:

- pipeline roda com budget de tempo/iteracoes;
- ajustes alteram spec, nao mesh;
- cada iteracao salva spec, renders, relatorio e diff;
- loop para com sucesso, budget ou falha explicada.

### Fase 7 - Qualidade e generalizacao

Objetivo: expandir arquetipos e robustez.

Entregas:

- presets para sedan, hatch, van, truck, bus;
- suporte inicial a motorcycle/sci-fi;
- biblioteca de rodas;
- biblioteca de farois/lanternas;
- estilos de superficie;
- benchmark de blueprints.

Criterio de pronto:

- cinco arquetipos geram modelos distinguiveis;
- validadores detectam erros comuns;
- custos e tempos estao medidos;
- documentacao de uso esta pronta.

---

## 16. Ordem recomendada das ferramentas MCP

Nao criar todas de uma vez. Ordem:

1. `vehicle_gerar_rig`
2. `vehicle_gerar_blockout`
3. `vehicle_renderizar_vistas`
4. `vehicle_auditar`
5. `vehicle_gerar_modelo`
6. `vehicle_calibrar_blueprint`
7. `vehicle_comparar_blueprint`
8. `vehicle_iterar`
9. `vehicle_pipeline`
10. `vehicle_criar_spec`

Motivo: gerar e medir vem antes de interpretar imagem. Se o sistema nao consegue
fazer um rig e um blockout corretos, blueprint/Gemini so adicionam complexidade.

---

## 17. Exemplo de fluxo para o blueprint do supercarro

Entrada humana:

```text
Gere um supercarro inspirado neste blueprint.
Medidas: comprimento 4750 mm, largura 2020 mm, altura 1210 mm,
wheelbase 2680 mm, front track 1890 mm, rear track 1875 mm.
```

Fluxo:

```text
vehicle_criar_spec
  -> archetype supercar
  -> VehicleSpec SV-24

vehicle_calibrar_blueprint
  -> front/rear/side/top views
  -> escalas por vista

vehicle_extrair_landmarks
  -> wheel centers
  -> roofline
  -> beltline
  -> front/rear overhang
  -> splitter/diffuser/wing

vehicle_gerar_rig
  -> eixos, rodas, bbox, cameras

vehicle_gerar_blockout
  -> massa principal

vehicle_gerar_modelo(qualidade="standard")
  -> body loft
  -> wheels
  -> glass
  -> headlights
  -> aero

vehicle_renderizar_vistas
  -> front/side/top/rear/perspective

vehicle_auditar + vehicle_comparar_blueprint
  -> erros dimensionais e visuais

vehicle_iterar
  -> ajusta spec
  -> nova geracao
```

Resultado esperado na primeira versao:

- carro baixo de motor central;
- cabine curta;
- rodas grandes;
- frente em cunha;
- traseira larga;
- splitter, difusor e asa presentes;
- proporcoes principais fiéis.

Resultado esperado apos iteracoes:

- silhueta lateral mais proxima;
- teto e cabine ajustados;
- overhangs corrigidos;
- farois/lanternas mais proximos do blueprint;
- erro visual por vista reduzido.

---

## 18. Custo de tokens

Sem ferramentas encapsuladas, gerar um veiculo completo exige muitos tokens porque
a IA precisa:

- interpretar referencia;
- planejar geometria;
- escrever codigo Blender;
- depurar;
- comparar renders;
- corrigir;
- repetir.

Com o workspace proposto, o custo cai porque a IA passa a enviar comandos curtos:

```text
vehicle_pipeline(prompt, referencia, medidas, budget)
vehicle_iterar(spec, audit)
```

A maior parte do trabalho fica em:

- codigo local;
- JSON estruturado;
- validadores;
- renders;
- relatorios.

Meta:

- iteracao simples: poucos milhares de tokens;
- iteracao com Gemini/VLM: custo maior, mas ainda controlado;
- geracao completa: limitada por budget de iteracoes, nao por improviso textual.

---

## 19. Riscos

### Risco 1 - Tentar gerar detalhe cedo demais

Mitigacao:

- rig e blockout antes de farois/entradas/vincos;
- fidelidade de proporcao antes de acabamento.

### Risco 2 - Blueprint ruim ou perspectiva falsa

Mitigacao:

- exigir calibracao;
- detectar vista ortografica;
- permitir marcacao manual assistida;
- usar medidas conhecidas como autoridade.

### Risco 3 - VLM alucinar medidas/features

Mitigacao:

- VLM so sugere;
- validadores numericos decidem dimensoes;
- constraints da spec sao fonte de verdade.

### Risco 4 - Malha bonita mas impossivel de editar

Mitigacao:

- feature graph;
- parametros nomeados;
- cutters preservados;
- corrigir spec e regenerar.

### Risco 5 - Loop infinito de correcao

Mitigacao:

- budget de tempo;
- budget de iteracoes;
- parada por melhoria minima;
- relatorio de falha com ultima spec.

### Risco 6 - Um gerador generico virar mediocre em tudo

Mitigacao:

- nucleo comum;
- arquetipos especializados;
- geradores por subfamilia;
- benchmarks por tipo de veiculo.

---

## 20. Benchmark minimo

Criar conjunto de teste:

```text
benchmarks/
  supercar_blueprint/
  suv_side_front/
  pickup_blueprint/
  van_dimensions_only/
  sci_fi_prompt_only/
```

Metricas:

- erro de comprimento;
- erro de largura;
- erro de altura;
- erro de wheelbase;
- IoU de silhueta por vista;
- score de simetria;
- presenca de features;
- tempo de geracao;
- numero de iteracoes;
- custo aproximado de tokens.

Um modelo so deve ser considerado melhor se melhorar essas metricas, nao apenas
parecer melhor em uma render.

---

## 21. Definicao do MVP

MVP recomendado:

```text
VehicleSpec
  + archetype supercar/suv/pickup
  + rig dimensional
  + blockout
  + rodas/pneus
  + body loft simples
  + vidro simples
  + splitter/difusor/asa simples
  + render 5 vistas
  + auditoria dimensional
  + auditoria de simetria
```

Nao incluir no MVP:

- farois por mascara complexa;
- interior detalhado;
- materiais realistas;
- simulacao fisica;
- rigging;
- deformacao/animacao;
- suporte perfeito a motocicletas.

Primeiro alvo de qualidade:

> Gerar um supercarro baixo e proporcional a partir de spec numerica, com body
> coerente e renders ortograficos auditaveis.

Segundo alvo:

> Usar blueprint calibrado para reduzir erro de silhueta lateral/top/front.

Terceiro alvo:

> Gerar features visuais reconheciveis e iterar com avaliacao visual.

---

## 22. Arquivos iniciais a criar

Primeiro commit de implementacao deve criar:

```text
vehicle_workspace/README.md
vehicle_workspace/specs/examples/supercar_sv24.json
vehicle_workspace/archetypes/supercar.json
vehicle_workspace/archetypes/suv.json
vehicle_workspace/archetypes/pickup.json
vehicle_workspace/vehicle/schema.py
vehicle_workspace/vehicle/units.py
vehicle_workspace/vehicle/coordinate_system.py
vehicle_workspace/generators/rig.py
vehicle_workspace/generators/blockout.py
vehicle_workspace/generators/wheels.py
vehicle_workspace/rendering/orthographic_views.py
vehicle_workspace/validation/dimensions.py
vehicle_workspace/validation/symmetry.py
vehicle_workspace/validation/wheel_fitment.py
```

Depois, expor as primeiras MCP tools em `geracao_3d_mcp.py`:

```text
vehicle_gerar_rig
vehicle_gerar_blockout
vehicle_renderizar_vistas
vehicle_auditar
```

---

## 23. Criterio de sucesso do projeto

O projeto sera bem-sucedido quando uma IA conseguir pedir:

```text
Gere um supercarro inspirado neste blueprint, com comprimento 4750 mm,
largura 2020 mm, altura 1210 mm e entre-eixos 2680 mm.
```

E o sistema retornar:

- spec normalizada;
- modelo gerado;
- renders de vistas ortograficas;
- relatorio dimensional;
- relatorio de simetria;
- comparacao com blueprint;
- recomendacoes de ajuste;
- arquivos finais salvos.

O sinal de qualidade nao e uma imagem bonita isolada. O sinal de qualidade e um
loop que sabe explicar:

- o que tentou gerar;
- quais parametros usou;
- onde errou;
- quanto errou;
- como corrigiu;
- qual versao melhorou.

