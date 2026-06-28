# gerador_3d — bancada de teste do caminho neural (imagem → 3D)

A pasta `gerador_3d/` é um **estudo pessoal do usuário, à parte do projeto**. Não faz parte do
caminho de desenvolvimento do Larperian e está **fora de cogitação** para a arquitetura dele.
Fica documentada aqui só como registro do que existe na máquina, não como frente do projeto.

Aqui mora a outra metade do problema: gerar 3D por **rede neural** em vez de por script.

> Só os documentos sobem pro repo (`README.md`, `requirements.txt`, `iniciar_comfyui.bat`).
> Modelo, pesos, o clone do TRELLIS.2 e o `Instant Meshes.exe` ficam de fora — são pesados e
> regeneráveis. Os pesos e o ComfyUI moram em `D:\ComfyUI\`, fora do repositório.

## O que tem dentro

- **TRELLIS.2** (Microsoft, via ComfyUI) — pega uma imagem e gera um `.glb` em malha.
  Roda local na RTX 4060 Ti (8 GB), em modo `--lowvram --force-fp16`, backend `sdpa`.
- **Instant Meshes** — retopologia: pega a malha triangular densa que a IA cospe e
  reconstrói numa malha limpa, usável no Unity/Blender.
- `iniciar_comfyui.bat` / `requirements.txt` — como subir o ambiente.
- `README.md` da pasta — passo a passo operacional e o histórico de bugs corrigidos na configuração.

## Por que isso existe ao lado do protótipo

O protótipo (`prototype/`) é o caminho **procedural**: a IA escreve a receita, a geometria sai
exata, e camadas conferem medida, topologia e encaixe. Nada é inventado, mas o vocabulário é
limitado ao que foi codificado — ele não sabe gerar um objeto fora da lista.

O TRELLIS é o **avesso**: qualquer imagem vira 3D, generalidade total, mas a forma é alucinada
pela rede, a malha sai densa e **não há nenhuma garantia** de medida certa nem de topologia
correta. É exatamente o tipo de geração que o projeto nasceu querendo evitar.

Não são rivais — são as duas pontas de um trade-off:

| | procedural (`prototype/`) | neural (`gerador_3d/`) |
|---|---|---|
| Generalidade | baixa (só o vocabulário codificado) | alta (qualquer imagem) |
| Precisão / medida | garantida e verificável | nenhuma garantia |
| Malha | limpa por construção | densa, precisa de retopologia |
| Risco de alucinação | ~zero | alto |

## Decisão: fora do projeto

Já se cogitou plugar a camada de verificação do lado procedural na saída do TRELLIS. **Está
descartado.** O TRELLIS é estudo pessoal do usuário e não entra na arquitetura do Larperian — nem
como gerador, nem como fornecedor de forma para o caminho procedural. O desenvolvimento do projeto
segue só pelo lado procedural (geração por código + verificação por contrato).
