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
Carroceria com topologia de jogo autoral, deformada pelo rig via curvas de controle por região e creases (não lattice puro, para preservar vincos). Uma malha base por classe: sedan, SUV, picape, cupê. Forma muda, topologia e UV nunca.

### 3. Biblioteca de peças parametrizáveis
Rodas, faróis, grades, retrovisores, maçanetas. Cada peça com variações e LODs já prontos. A IA escolhe, posiciona no socket e escala. Ninguém modela roda do zero em cada geração.

### 4. MCP de alto nível com feedback visual
Ferramentas de alto nível que expõem operações de design, não geometria. A IA pensa em forma e estilo, o MCP garante execução correta no Blender. Inclui ferramenta de escape para casos não previstos.

---

## Spec declarativa (JSON)

A IA não chama ferramentas em sequência. Ela produz um arquivo JSON declarativo descrevendo o carro completo (proporções, deformações, peças, materiais). Um compilador determinístico lê esse arquivo e monta o carro no Blender.

**Vantagens:**
- O carro vira dado, não uma sequência de ações
- Versionável e comparável
- Pode misturar dois carros ou regenerar com outro polycount
- Troca de engine no futuro sem mudar a IA
- Cada spec aprovada vira exemplo para melhorar prompts futuros

---

## Agente e skills

**Um agente, múltiplas skills.** Não múltiplos agentes. O problema é execução correta em sequência, não paralelismo de raciocínio.

### Skills do agente

| Skill | Função |
|-------|--------|
| `definir_proporcoes` | Recebe parâmetros e gera o rig do carro |
| `deformar_carroceria` | Aplica proporções na malha base preservando vincos e topologia |
| `gerar_socket` | Calcula pontos de ancoragem a partir do rig |
| `selecionar_peca` | Escolhe peça da biblioteca conforme estilo pedido |
| `anexar_peca` | Posiciona e escala a peça no socket certo |
| `aplicar_material` | Cor, pintura, vidro, cromado, borracha |
| `compilar_spec` | Lê o JSON declarativo e monta tudo em ordem |
| `validar_topologia` | Checa polycount, quads e UV |
| `renderizar_multiangulo` | Gera preview de vários ângulos para a IA avaliar o próprio resultado |
| `executar_script` | Python livre no Blender para casos não cobertos pelas skills acima |

Quando `executar_script` resolver algo repetido, promove aquilo a skill nova. O sistema cresce assim.

---

## MCP Tools

Regra de ouro: cada MCP tool devolve algo que a IA consegue interpretar sem saber Blender por dentro (números, status, imagem), nunca erro cru de API.

| Tool | Parâmetros | Retorno |
|------|-----------|---------|
| `set_proportions` | entre_eixos, altura, largura, angulo_parabrisa, classe | rig gerado |
| `deform_body` | regiao, intensidade, vinco | status da deformação |
| `get_sockets` | — | lista de pontos de ancoragem |
| `list_parts` | categoria, estilo | peças disponíveis na biblioteca |
| `attach_part` | socket_id, part_id, escala | status de encaixe |
| `apply_material` | target, tipo, cor | status de material |
| `compile_spec` | json | status de compilação |
| `validate_mesh` | — | polycount, checagem de quads, status de UV |
| `render_views` | angulos | imagens para avaliação |
| `run_script` | codigo_python | resultado do script |

---

## Hierarquia de módulos

O módulo de proporção e silhueta global fica acima de todos. Carro bonito é proporção certa, não peças boas isoladas.

1. **Módulo de proporção** — define o esqueleto global
2. **Módulos de superfície** — carroceria, teto, colunas que obedecem o esqueleto
3. **Módulos de peça** — rodas, faróis, maçanetas que se ancoram nos sockets

---

## Riscos técnicos e validação

### Risco principal (validar na semana 1)
Deformação de malha base tende a perder vincos e linhas de caráter. Antes de construir qualquer outra coisa, provar que é possível deformar uma malha base de sedan em proporções diferentes mantendo vincos nítidos. Solução esperada: curvas de controle por região + creases, não lattice puro.

### Loop de feedback visual
Autonomia real exige que a IA veja e julgue o próprio resultado. Investir cedo em renderização de preview multiângulo e critérios objetivos de qualidade. Sem isso nenhuma arquitetura garante resultado.

---

## Pontos ainda a definir

1. **Schema do JSON da spec** — campos exatos e seus limites (min/max de entre-eixos, enum de classes). É o contrato entre IA e compilador.
2. **Critério de avaliação nos renders** — checklist objetiva para a IA julgar o próprio resultado (proporção bate com a classe, vincos visíveis, sem sobreposição de peças).
3. **Onde o Blender roda** — processo headless local, servidor dedicado ou instância sob demanda. Define latência do loop e capacidade de paralelismo.
4. **Pipeline de export** — formato final (FBX, glTF), estratégia de LOD, se malha base já sai com LODs ou é gerado depois.
5. **Dataset de aprendizado** — guardar cada spec aprovada com nota de qualidade para eventualmente treinar a IA a gerar specs melhores com menos iterações.

---

## Resultado esperado

Sistema onde se digita "SUV compacto esportivo, frente agressiva, vermelho" e sai um carro game-ready em minutos: topologia limpa, UV pronta, LODs, exportado para engine. Variedade dentro das classes construídas, qualidade consistente por construção.

**Não é** um designer criativo. Gera variação e recombinação dentro das classes existentes. Invenção radical ainda exige humano.

**Vale a pena quando:** o volume de carros necessários é alto (dezenas, centenas, ou geração sob demanda). O custo é pago uma vez e cada carro depois custa quase zero. O mesmo esqueleto se estende para outros veículos e categorias de asset.

---

## Ordem de construção recomendada

1. Prova de deformação com vincos (1-2 semanas) — validar o risco técnico central
2. Schema do JSON da spec declarativa
3. Compilador e as MCP tools básicas
4. Malha base de sedan + rig de proporção
5. Biblioteca mínima de peças (roda, farol)
6. Loop completo: IA gera spec, compilador monta, render retorna pra IA avaliar
7. Expansão de classes e biblioteca de peças
