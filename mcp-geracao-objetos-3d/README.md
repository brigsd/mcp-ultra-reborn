# Larperian

Framework para uma IA gerar objetos 3D no Blender com **precisão geométrica** (forma, proporção,
topologia — não textura). A ideia central não é a IA "acertar de primeira", e sim um **loop fechado**:
gerar → executar no Blender → renderizar e medir → auditar em camadas → corrigir → repetir.

> **Status: fase de planejamento/arquitetura.** A pesquisa de fundação está feita e consolidada;
> a implementação da nova arquitetura (runner headless, B-rep no mecânico, verificador isolado) ainda
> não começou. O código atual em `bridge/`, `api/`, etc. é da primeira versão e será revisado.

## Por onde começar

1. **[docs/plano_mestre.md](docs/plano_mestre.md)** — a visão de topo consolidada: o mapa conectivo
   (espinha, ponte, geradores, verificadores), as decisões, o que é falso achado, e as frentes abertas.
   **Comece por aqui.**
2. **[docs/teardown_plano_mestre.md](docs/teardown_plano_mestre.md)** — a verificação adversarial que
   atacou o plano e mudou coisa de fundação (B-rep como fonte-de-verdade no mecânico, verificador isolado).

## A ideia em uma frase

Mecânico = código paramétrico/B-rep (precisão por construção, verificada por kernel e asserções
ancoradas). Orgânico = SDF (signed distance functions, lib `sdf` do Fogleman; L-System como sub-caso),
verificado por validade + estrutura + plausibilidade. Os dois penduram numa espinha única: o loop de
verificação em camadas, com 1 verificador por modo de falha (validade ≠ fidelidade ≠ estrutura ≠
percepção).

## Mapa dos documentos

| Documento | Para quê |
|---|---|
| [plano_mestre.md](docs/plano_mestre.md) | **Entrada.** Visão de topo, mapa conectivo, decisões, frentes abertas. |
| [teardown_plano_mestre.md](docs/teardown_plano_mestre.md) | Verificação adversarial do plano (o que quebra e os ajustes). |
| [rascunho_ideias.md](docs/rascunho_ideias.md) | Caderno de ideias soltas por frente (ponte, motor, verificação). |
| [pesquisa_ia_3d.md](docs/pesquisa_ia_3d.md) | Como uma IA gera 3D com precisão (representações, loop, papers). |
| [panorama_ferramentas_ia_3d.md](docs/panorama_ferramentas_ia_3d.md) | O que já existe pronto (frameworks/MCPs/sandboxes). |
| [pesquisa_prova_forma.md](docs/pesquisa_prova_forma.md) | Dá pra PROVAR que uma forma está correta? |
| [verificadores_plugaveis.md](docs/verificadores_plugaveis.md) | Bibliotecas concretas de verificação (pip), por camada. |
| [pesquisa_spec_e_geracao.md](docs/pesquisa_spec_e_geracao.md) | A entrada: spec-como-contrato, roteação, desambiguação, autoria de geradores, B-rep→Blender. |
| [pesquisa_grafo_procedural.md](docs/pesquisa_grafo_procedural.md) | Família mapa-procedural-editável: Proc3D (fora), ProcGen3D (baixa), ShapeCraft (blueprint promissor). |
| [gerador_3d_neural.md](docs/gerador_3d_neural.md) | Estudo pessoal do usuário (imagem→3D via TRELLIS.2), **à parte e fora do projeto**. Só registro. |
| [objetivo.md](docs/objetivo.md) | Objetivo e escopo do projeto. |
| [como_usar.md](docs/como_usar.md) | ⚠️ Legado — descreve a ponte antiga. |
| [protocols/](protocols/) | ⚠️ Legado — protocolos da v1, a reescrever. |

## Estrutura do código (v1, em revisão)

- `bridge/` — ponte addon+HTTP (será substituída por runner headless).
- `api/` — DSL de geometria sobre bmesh (conceito sobrevive).
- `catalog/` — dimensões mecânicas reais.
- `references/` — referências técnicas (figuras de patente em domínio público; metadados).
- `parts/`, `assembler.py` — exemplos (o brake_disc tem geometria a corrigir).
- `client/`, `tools/` — cliente HTTP e utilitários.
- `gerador_3d/` — estudo pessoal do usuário, **à parte e fora do projeto** (caminho neural; só os docs versionados). Ver [docs/gerador_3d_neural.md](docs/gerador_3d_neural.md).
