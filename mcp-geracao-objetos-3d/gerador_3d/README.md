# 🛠️ Gerador 3D - Workspace

Este diretório contém as ferramentas e os repositórios configurados para a geração e otimização de modelos 3D locais utilizando Inteligência Artificial (TRELLIS.2 via ComfyUI) e retopologia (Instant Meshes).

---

## 📁 Estrutura de Pastas

| Pasta / Arquivo | Descrição |
|---|---|
| `InstantMeshes/` | Executável standalone `Instant Meshes.exe` para retopologia de malhas 3D |
| `TRELLIS.2/` | Cópia local do repositório oficial da Microsoft (código-fonte de referência) |
| `iniciar_comfyui.bat` | Script de inicialização rápida do ComfyUI com flags para baixo VRAM |
| `requirements.txt` | Referência dos pacotes principais do ambiente virtual |

O ComfyUI e todos os modelos ficam em **`D:\ComfyUI\`**.

---

## 🚀 Como Executar o Fluxo de Trabalho

### 1. Gerar o Modelo 3D (ComfyUI + TRELLIS.2)

> **Hardware:** RTX 4060 Ti (8GB VRAM) — configurado para rodar com `--lowvram --force-fp16`.

1. Dê dois cliques no arquivo **`iniciar_comfyui.bat`**.
2. Aguarde o terminal mostrar a linha `To see the GUI go to: http://127.0.0.1:8188`.
3. Abra o navegador em **`http://127.0.0.1:8188`**.
4. Carregue um dos workflows de `D:\ComfyUI\custom_nodes\ComfyUI-Trellis2\example_workflows\`.
5. Suba uma imagem (JPG ou PNG, com ou sem fundo transparente) e clique em **Queue Prompt**.
6. O modelo gerado (`.glb`) será salvo em `D:\ComfyUI\output\`.

> **Primeira execução:** o ComfyUI baixará automaticamente os pesos do modelo (~8–10 GB). Isso pode demorar bastante dependendo da sua internet.

#### Configurações recomendadas no nó `Trellis2LoadModel`

| Parâmetro | Valor recomendado |
|---|---|
| `modelname` | `microsoft/TRELLIS.2-4B` |
| `backend` | `sdpa` *(não mudar — flash_attn não está instalado)* |
| `sparse_backend` | `sdpa` *(idem)* |
| `low_vram` | `True` |
| `pipeline_type` | `512` *(mais seguro para 8GB)* ou `1024` *(pode dar OOM no cascade)* |

#### Qual workflow usar com 8GB de VRAM

| Workflow | VRAM estimada | Qualidade | Recomendação |
|---|---|---|---|
| `MeshOnly.json` | ~4–5 GB | Boa (512) | ✅ Mais seguro, sempre funciona |
| `MeshOnly_HighQuality_NoCascade.json` | ~6–7 GB | Alta (1024 sem cascade) | ✅ Melhor custo-benefício |
| `MeshOnly_HighQuality.json` | ~8+ GB | Máxima (1024 cascade) | ⚠️ Pode dar OOM |
| `MeshOnly_LowPoly.json` | ~3–4 GB | Menor | ✅ Para testes rápidos |

> Carregue qualquer workflow pelo menu **Load** do ComfyUI ou arrastando o arquivo `.json` para a janela.

---

### 2. Otimizar o Mesh (Instant Meshes)

Os modelos gerados por IA têm malha triangular densa. Para fazer retopologia:

1. Abra `InstantMeshes\Instant Meshes.exe`.
2. Clique em **Open Mesh** → selecione o `.obj` ou `.ply` do seu modelo.
3. Ajuste o número de vértices desejado com o slider.
4. Clique em **Solve** → depois em **Extract Mesh**.
5. Exporte o modelo limpo para usar no Unity, Blender, etc.

---

## 🛠️ Ambiente Técnico

| Item | Detalhes |
|---|---|
| **ComfyUI** | `D:\ComfyUI\` |
| **Python** | 3.12.10 |
| **PyTorch** | 2.8.0+cu126 (CUDA 12.6) |
| **Custom Node** | `ComfyUI-Trellis2` em `D:\ComfyUI\custom_nodes\ComfyUI-Trellis2\` |
| **Modelos** | `D:\ComfyUI\models\` |
| **TRELLIS.2-4B** | `D:\ComfyUI\models\microsoft\TRELLIS.2-4B\` |
| **DINOv3** | `D:\ComfyUI\models\facebook\dinov3-vitl16-pretrain-lvd1689m\` |

---

## 🐛 Bugs Corrigidos (histórico)

Durante a configuração inicial, foram encontrados e corrigidos os seguintes problemas:

### 1. `TypeError: Cannot handle this data type: (1, 1, 640), |u1`
- **Arquivo:** `D:\ComfyUI\custom_nodes\ComfyUI-Trellis2\nodes.py` — classe `Trellis2PreProcessImage`
- **Causa:** O nó assumia que toda imagem de entrada era RGBA (4 canais). Imagens JPG/PNG normais são RGB (3 canais), causando falha ao acessar o canal alpha.
- **Fix:** Conversão explícita para RGBA antes do processamento; lógica de crop adaptada para imagens sem transparência real.

### 2. `ValueError: Paths don't have the same drive`
- **Arquivo:** `D:\ComfyUI\server.py` — rotas `/view` e `/upload/mask`
- **Causa:** Bug do próprio ComfyUI no Windows — `os.path.commonpath()` lança `ValueError` quando os caminhos pertencem a drives diferentes (ex: `C:\` vs `D:\`).
- **Fix:** Adicionado `try/except ValueError` nos dois pontos do `server.py`, retornando status 403 de forma segura.

### 3. `RuntimeError: ignore_mismatched_sizes`
- **Arquivo:** `D:\ComfyUI\models\facebook\dinov3-vitl16-pretrain-lvd1689m\`
- **Causa:** O diretório do modelo DINOv3 tinha apenas o `model.safetensors` (ViT-Large, dim=1024) sem o `config.json`. O `transformers` criava a arquitetura com valores padrão (dim=384), causando mismatch total de pesos.
- **Fix:** Criação manual do `config.json` com os parâmetros corretos do ViT-Large (24 layers, hidden_size=1024, 16 heads, 4 register tokens).

### 4. `ModuleNotFoundError: No module named 'flash_attn'`
- **Arquivos:** `trellis2/modules/attention/config.py` e `trellis2/modules/sparse/config.py`
- **Causa:** `flash_attn` e `xformers` não estão disponíveis no Windows sem compilação especial. O workflow estava configurado para usá-los por padrão.
- **Fix:** Backend padrão alterado para `sdpa` (PyTorch nativo, sempre disponível). Adicionada detecção automática com fallback: se o backend solicitado não estiver instalado, usa `sdpa` automaticamente. Impacto de performance: ~10–20% mais lento que `flash_attn`, imperceptível na prática.

### 5. `torch.OutOfMemoryError` no nó `Trellis2ShapeCascadeGenerator`
- **Arquivo:** `D:\ComfyUI\custom_nodes\ComfyUI-Trellis2\nodes.py` — método `sample()` da classe `Trellis2ShapeCascadeGenerator`
- **Causa:** O decoder do cascade realiza `upsample(slat, upsample_times=4)` — 4 etapas de upsampling da malha esparsa que elevam o pico de VRAM para >8GB. O OOM ocorre no bloco `SparseResBlockC2S3d.conv1` dentro do `flex_gemm` ao tentar alocar o tensor de saída.
- **Fix aplicado em `nodes.py`:**
  - Limpeza agressiva de VRAM (`gc.collect()` + `torch.cuda.empty_cache()` + `synchronize()`) imediatamente antes de carregar o decoder
  - Ativação de **gradient checkpointing** (`use_checkpoint=True`) em todos os blocos do decoder para trocar recompute por memória
  - Redução do `chunk_size` de `65536` → `32768` para diminuir o pico de alocação por operação
- **Alternativa garantida:** Usar os workflows `MeshOnly.json` (512) ou `MeshOnly_HighQuality_NoCascade.json` (1024 sem cascade) em vez de `MeshOnly_HighQuality.json`.
