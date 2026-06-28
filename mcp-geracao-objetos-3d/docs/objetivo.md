# Objetivo do Projeto Larperian

> Visão de "por quê / o quê". Para a arquitetura detalhada e atual, ver
> [plano_mestre.md](plano_mestre.md).

## O problema

Assistentes de IA conseguem escrever código Python para o Blender, mas quando fazem isso "de cabeça"
cometem erros previsíveis: usam proporções inventadas, chamam funções que dependem de contexto, e nunca
ficam sabendo se o resultado ficou certo ou errado. O ciclo vira: IA gera → usuário executa → algo
quebra → usuário descreve o erro em texto → IA tenta de novo. É lento, impreciso e não escala.

A raiz é que um modelo de linguagem não tem modelo espacial interno — ele prevê texto. Então o que faz
a precisão aparecer não é a IA "acertar de primeira"; é um **loop fechado**: gerar → executar → medir e
ver → corrigir → repetir.

## O que este projeto faz

Larperian equipa a IA para gerar geometria 3D com **precisão** no Blender de forma autônoma. O foco é
exclusivamente **geometria** — forma, proporção, estrutura — não materiais, textura ou iluminação. E é
3D **em geral**, não só peça mecânica.

Três pilares sustentam isso:

1. **O loop de verificação (a espinha).** A IA não opera às cegas. Cada tentativa é executada,
   renderizada de vários ângulos e medida; os problemas voltam como erro concreto para a IA corrigir. A
   verificação é em camadas, uma para cada tipo de falha distinta (validade ≠ medida ≠ estrutura ≠
   aparência), sem empilhar checadores que brigam entre si.

2. **A representação certa por domínio.** Peça mecânica nasce como geometria exata num núcleo de CAD
   (B-rep), onde a precisão é garantida por construção; só no fim vira malha para render. Objeto orgânico
   (árvore, criatura) nasce de funções de distância (SDF), que cobrem forma livre e saem fechadas.

3. **A spec como contrato.** O pedido em linguagem natural não vai direto para o gerador. Primeiro vira
   uma especificação estruturada — e essa mesma especificação é o checklist que o verificador roda. Não
   há separação entre "o que pedir" e "como conferir": é a mesma fonte de verdade, ancorada nos
   parâmetros nomeados do código.

## O que NÃO é objetivo

- Materiais, texturas ou iluminação — só geometria.
- Animação ou simulação física (por ora).
- Suporte a outros softwares 3D além do Blender (Unity/Unreal ficam para uma camada de visualização
  futura).
- Interface gráfica própria — o Blender já é o palco.

## Estado e visão de longo prazo

O projeto está em transição: a pesquisa de fundação está consolidada (ver os documentos de pesquisa) e a
implementação da nova arquitetura ainda vai começar. O código atual em `bridge/`, `api/`, etc. é da
primeira versão e será revisado.

A meta de longo prazo é a IA modelar **qualquer objeto 3D** a partir de uma descrição em linguagem
natural, com precisão dimensional no mecânico e plausibilidade estrutural no orgânico, se autocorrigindo
no loop sem depender de um humano para consertar geometria quebrada.
