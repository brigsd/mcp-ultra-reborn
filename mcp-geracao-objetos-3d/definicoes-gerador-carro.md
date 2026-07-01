# Definições do Sistema Gerador de Carros via IA e Blender

## Problema central

Nenhuma IA generativa de malha (Meshy, Tripo, etc.) entrega topologia game-ready. Elas criam a forma e a topologia juntas, e o resultado é mal otimizado para jogo. O sistema proposto separa essas duas coisas de forma permanente.

---

## Princípio central

**Topologia é autoral. Forma é paramétrica.**

A topologia nunca é gerada pela IA. Malhas base com topologia perfeita de jogo (quads limpos, edge flow correto, polycount controlado, UVs prontas) são criadas uma única vez por humano ou adquiridas como asset. A IA só deforma essas malhas. Como a topologia nunca muda, o resultado é game-ready por construção, sempre.

---

## Arquitetura em 4 camadas

### 1. Rig de proporção
Esqueleto paramétrico do carro: entre-eixos, alturas, larguras, ângulos de coluna e parabrisa. É a única coisa que a IA manipula diretamente. Define também os sockets (pontos de ancoragem de roda, farol, retrovisor, maçaneta).

### 2. Malhas base deformáveis
Carroceria com topologia de jogo autoral, deformada pelo rig. Uma malha base por classe: sedan, SUV, picape, cupê. Forma muda, topologia e UV nunca.

**Estratégia de deformação (ordem de preferência):**
1. **Morph targets / blendshapes** como ponto de partida: N formas extremas autorais por classe, IA define apenas os pesos. Trivial, preserva UV, interpolação bem-comportada, zero rig custom.
2. **Cage SubD** como alternativa: cage low-poly é a própria topologia de jogo, vincos via crease weights de subdivisão, LODs de graça por nível de subdivisão.
3. **Curvas de controle por região + creases** como rig custom: só se os dois anteriores provarem insuficientes para a variedade necessária.

**Nota sobre UV:** deformações grandes (mais de 15-20% de entre-eixos) distorcem densidade de texel. A validação deve checar e normalizar texel density para garantir transferência limpa de normal maps entre variantes.

### 3. Biblioteca de peças parametrizáveis
Rodas, faróis, grades, retrovisores, maçanetas. Cada peça com variações e LODs já prontos. A IA escolhe, posiciona no socket e escala. Ninguém modela roda do zero em cada geração.

### 4. MCP de alto nível com feedback por métricas
Ferramentas de alto nível que expõem operações de design, não geometria. A IA pensa em forma e estilo, o MCP garante execução correta no Blender.

**Avaliação de qualidade:** não depender de VLM julgando renders para qualidade de superfície. Usar métricas geométricas determinísticas: reflection lines/zebra stripes, mapas de curvatura, IoU de silhueta contra referência. O render multiângulo serve para composição geral, as métricas numéricas garantem qualidade de superfície.

---

## Caminho para remover o teto de forma

Malha monolítica deformada por rig tem um teto estrutural: não cria features novas onde o edge flow não suporta (vinco novo, entrada de ar, cupê 2 portas a partir de sedan). Para o longo prazo existem duas rotas:

**Rota A: painéis paramétricos**
Capô, para-lama, porta, teto, colunas como patches procedurais de topologia garantida, costurados com edge flow controlado via Geometry Nodes. Features viram parâmetros, não topologia congelada. Escala variedade muito além do sistema inicial.

**Rota B: shrinkwrap sobre proxy gerado**
Usar IA generativa (Meshy, etc.) ou imagem multi-view apenas como alvo de forma — a malha autoral é projetada sobre o proxy com shrinkwrap, preservando topologia e UV. Topologia continua autoral, mas a fonte de forma vira ilimitada. Essa é a rota que de fato remove o teto sem reconstruir o sistema.

**Decisão:** começar com malha monolítica (mais simples de validar) e desenhar o schema JSON já preparado para evoluir para uma dessas rotas sem quebrar o compilador.

---

## Spec declarativa (JSON)

A IA não chama ferramentas em sequência. Ela produz um arquivo JSON declarativo descrevendo o carro completo (proporções, deformações, peças, materiais). Um compilador determinístico lê esse arquivo e monta o carro no Blender.

**Vantagens:**
- O carro vira dado, não uma sequência de ações
- Versionável e comparável
- Pode misturar dois carros ou regenerar com outro polycount
- Troca de engine no futuro sem mudar a IA
- Cada spec aprovada vira exemplo para melhorar prompts futuros
- Schema extensível para suportar painéis paramétricos ou shrinkwrap no futuro

---

## Agente e skills

**Um agente, múltiplas skills.** Não múltiplos agentes. O problema é execução correta em sequência, não paralelismo de raciocínio.

### Skills do agente

| Skill | Função |
|-------|--------|
| `definir_proporcoes` | Recebe parâmetros e gera o rig do carro |
| `deformar_carroceria` | Aplica proporções na malha base via morph targets ou cage SubD |
| `gerar_socket` | Calcula pontos de ancoragem a partir do rig |
| `selecionar_peca` | Escolhe peça da biblioteca conforme estilo pedido |
| `anexar_peca` | Posiciona e escala a peça no socket certo |
| `aplicar_material` | Cor, pintura, vidro, cromado, borracha (com material IDs e trim sheets) |
| `compilar_spec` | Lê o JSON declarativo e monta tudo em ordem |
| `validar_topologia` | Checa polycount, quads, UV e texel density |
| `renderizar_multiangulo` | Gera preview de vários ângulos para avaliação de composição |
| `medir_qualidade_superficie` | Retorna métricas geométricas: curvatura, zebra stripes, IoU de silhueta |
| `executar_script` | Python no Blender em quarentena (só cria peças novas, nunca toca malha base) |

**Regra do `executar_script`:** opera em quarentena. Só pode criar assets novos que passam por `validar_topologia` antes de qualquer uso. Nunca modifica malha base diretamente. Promoção a skill oficial exige revisão humana.

---

## MCP Tools

Regra de ouro: cada MCP tool devolve algo que a IA consegue interpretar sem saber Blender por dentro (números, status, imagem), nunca erro cru de API.

| Tool | Parâmetros | Retorno |
|------|-----------|---------|
| `set_proportions` | entre_eixos, altura, largura, angulo_parabrisa, classe | rig gerado |
| `deform_body` | regiao, pesos_morphs ou cage_deltas | status da deformação |
| `get_sockets` | — | lista de pontos de ancoragem |
| `list_parts` | categoria, estilo | peças disponíveis na biblioteca |
| `attach_part` | socket_id, part_id, escala | status de encaixe |
| `apply_material` | target, tipo, cor, material_id | status de material |
| `compile_spec` | json | status de compilação |
| `validate_mesh` | — | polycount, quads, UV, texel density |
| `render_views` | angulos | imagens para avaliação de composição |
| `measure_surface` | — | curvatura, zebra stripes, IoU silhueta (números) |
| `run_script` | codigo_python, modo="quarentena" | resultado + status de validação |

---

## Hierarquia de módulos

O módulo de proporção e silhueta global fica acima de todos. Carro bonito é proporção certa, não peças boas isoladas.

1. **Módulo de proporção** — define o esqueleto global
2. **Módulos de superfície** — carroceria, teto, colunas que obedecem o esqueleto
3. **Módulos de peça** — rodas, faróis, maçanetas que se ancoram nos sockets

---

## Riscos técnicos e validação

### Risco principal (validar na semana 1)
Provar que morph targets ou cage SubD entregam variedade suficiente de proporções antes de investir em rig custom. Testar deformar sedan em proporções bem diferentes mantendo vincos e texel density aceitável.

### Loop de feedback
Autonomia real exige que a IA avalie o próprio resultado com dados objetivos. Métricas geométricas determinísticas são a fundação, renders servem só para aprovação visual final ou comunicação com o usuário.

---

## Pontos ainda a definir

1. **Schema do JSON da spec** — campos exatos e seus limites (min/max de entre-eixos, enum de classes), já com campos reservados para painéis e shrinkwrap futuros.
2. **Critério de avaliação** — thresholds aceitáveis para cada métrica geométrica (curvatura máxima, texel density mínima, IoU de silhueta).
3. **Onde o Blender roda** — processo headless local, servidor dedicado ou instância sob demanda. Define latência do loop e capacidade de paralelismo.
4. **Pipeline de export** — formato final (FBX, glTF), estratégia de LOD, pipeline de material IDs e bakes.
5. **Dataset de aprendizado** — guardar cada spec aprovada com métricas para eventualmente treinar a IA a gerar specs melhores com menos iterações.

---

## Resultado esperado

Sistema onde se digita "SUV compacto esportivo, frente agressiva, vermelho" e sai um carro game-ready em minutos: topologia limpa, UV pronta, LODs, material IDs, exportado para engine. Variedade dentro das classes construídas, qualidade consistente por construção e por métricas.

**Teto atual:** variação dentro das classes existentes e do edge flow das malhas base. Features radicalmente novas ou classes totalmente diferentes exigem nova malha base ou evolução para painéis/shrinkwrap.

**Vale a pena quando:** o volume de carros necessários é alto (dezenas, centenas, ou geração sob demanda). O custo é pago uma vez e cada carro depois custa quase zero. O mesmo esqueleto se estende para outros veículos e categorias de asset.

---

## Ordem de construção recomendada

1. Prova de deformação com morph targets ou cage SubD (semana 1) — validar variedade vs complexidade
2. Schema do JSON da spec declarativa (já extensível para painéis/shrinkwrap)
3. Compilador e MCP tools básicas
4. Malha base de sedan + morph targets de proporções extremas
5. Biblioteca mínima de peças (roda, farol) com validação de topologia
6. Loop completo: IA gera spec, compilador monta, métricas retornam para a IA avaliar
7. Expansão de classes e biblioteca de peças
8. Avaliar se shrinkwrap ou painéis paramétricos são necessários para o volume de variedade pretendido
