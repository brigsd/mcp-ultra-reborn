# MCP Geração Objetos 3D (ex-Larperian)

Framework para uma IA gerar objetos 3D no Blender com **precisão geométrica** (forma, proporção, topologia). Agora integrado como um servidor MCP global (`geracao-3d`) usando FastMCP.

O sistema funciona em **loop fechado**:
1. O agente solicita a geração de uma peça pelo MCP.
2. O servidor executa a geração no Blender (via GUI Bridge ou Headless).
3. O Blender exporta o STL e gera 4 renders ortográficos (Perspectiva, Frente, Lado, Topo).
4. O agente analisa o resultado visual e geométrico, podendo iterar ou corrigir parâmetros.

---

## Status da Implementação

* **Servidor FastMCP (`geracao-3d`)**: Totalmente implementado e registrado no Antigravity.
* **Addon Blender atualizado**: Renomeado para *MCP 3D Object Generation Bridge* (evitando conflitos com nomes antigos).
* **Dual Execution Mode**:
  * **Modo Bridge GUI**: Se o Blender estiver aberto com o addon ativo, a geração roda instantaneamente na interface gráfica via requisições HTTP (porta `8007`).
  * **Modo Headless Fallback**: Se o Blender estiver fechado, o servidor inicia um processo em background do Blender, gera o objeto, exporta em STL, renderiza as 4 vistas usando o script de renderização (`render_views.py`) e retorna tudo em segundos.
* **Correções no Windows**: 
  * **Deadlock de buffer (Pipe)**: Corrigido substituindo redirecionamento direto de logs por arquivos temporários e uso seguro de `Popen.communicate()`.
  * **Janelas Fantasmas**: Corrigido utilizando a flag `CREATE_NO_WINDOW` e `stdin=DEVNULL` no Windows, impedindo que o Blender em background aguarde input do terminal de forma invisível.
  * **Blender Context**: Corrigido bug de `NoneType` em `bpy.context.collection` ao rodar em modo silencioso (fallback automático para a coleção principal da cena).

---

## Ferramentas Disponíveis no MCP

### 1. `status_blender_bridge`
Verifica se o Blender GUI está aberto com a bridge ativa ou se a execução será direcionada para o modo Headless.

### 2. `gerar_modelo_3d(peca: str, parametros_json: str = "{}")`
Gera uma peça 3D (ex: `arvore_lowpoly`, `disco_freio`) enviando parâmetros personalizáveis. Retorna os caminhos dos renders gerados e o STL.

### 3. `obter_dimensoes_peca(peca: str)`
Retorna especificações de dimensões, restrições e faixas de valores aceitáveis para os parâmetros de uma peça cadastrada no catálogo.

### 4. `listar_referencias_locais()`
Lista as referências técnicas de peças salvas localmente.

### 5. `baixar_referencia_3d(peca: str, view: str = "perspectiva")`
Faz o download ou localiza a imagem de referência técnica de uma determinada peça para comparação.

---

## Estrutura do Projeto

* [geracao_3d_mcp.py](geracao_3d_mcp.py) — Ponto de entrada do servidor FastMCP. Controla a execução da bridge e o fallback headless.
* [bridge/server.py](bridge/server.py) — Addon do Blender (TCP server local na porta `8007`).
* [parts/](parts/) — Scripts de modelagem de peças individuais.
  * [arvore_lowpoly.py](parts/arvore_lowpoly.py) — Gerador de árvore low-poly paramétrica usando o modificador Skin (pele limpa e facetada + folhagem icosférica).
* [prototype/](prototype/) — Protótipos de geração e renderização rápida.
  * [render_views.py](prototype/render_views.py) — Script chamado em headless para gerar as 4 imagens de câmera.
* [catalog/](catalog/) — Regras geométricas de projeto.
* [references/](references/) — Imagens de referência e renders finais salvos.

---

## Como Usar e Testar

### Modo GUI (Recomendado para Desenvolvimento)
1. Abra o Blender.
2. Vá em **Edit > Preferences > Add-ons**, instale o arquivo [bridge/server.py](bridge/server.py) e ative o addon chamado **MCP 3D Object Generation Bridge**.
3. Na barra lateral (tecla `N`), ative a Bridge (ela ficará verde sinalizando que está ouvindo na porta `8007`).
4. Chame a ferramenta `gerar_modelo_3d(peca="arvore_lowpoly")` no chat. O objeto aparecerá instantaneamente na cena do seu Blender aberto.

### Modo Headless (Automático se o Blender GUI estiver Fechado)
1. Certifique-se de que o executável do Blender está configurado em seu sistema (caminho padrão para Steam/Windows já mapeado).
2. Basta chamar a ferramenta `gerar_modelo_3d(peca="arvore_lowpoly")`. 
3. O servidor cuidará de inicializar o Blender em background, rodar o script de modelagem, exportar, renderizar e disponibilizar os caminhos das imagens.
