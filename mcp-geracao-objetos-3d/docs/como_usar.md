# Como usar o Larperian Framework

> ⚠️ **LEGADO / DESATUALIZADO (2026-06-21).** Este guia descreve a ponte antiga (addon + HTTP +
> `client/send.py`), que será substituída pelo runner headless. Não reflete a direção atual.
> Para o estado real do projeto, ver [plano_mestre.md](plano_mestre.md). Mantido só como referência
> da implementação inicial até a reescrita.

## Fluxo de trabalho

```
IA gera código → client/send.py envia para Blender → bridge/server.py executa
→ retorna JSON com métricas + screenshot → IA vê o resultado e itera
```

## 1. Instalar o addon no Blender

1. Abra o Blender → Edit → Preferences → Add-ons → Install
2. Selecione `bridge/server.py`
3. Ative o addon "Larperian Blender Bridge"
4. A ponte inicia automaticamente em `http://localhost:19000`

## 2. Testar a conexão

```bash
python -m client.send --teste
```

## 3. Enviar um script

```bash
# Enviar arquivo
python -m client.send parts/brake_disc.py --screenshot resultado.png

# Enviar código inline
python -m client.send --codigo "import bpy; bpy.ops.mesh.primitive_cube_add()"
```

## 4. Resposta JSON do bridge

```json
{
  "sucesso": true,
  "erro": null,
  "objetos_criados": [
    {
      "nome": "DiscoDFreio",
      "tipo": "MESH",
      "dimensoes": [0.280, 0.280, 0.022],
      "vertices": 4096,
      "faces": 3840,
      "bounding_box": { "min": [-0.14, -0.14, -0.011], "max": [0.14, 0.14, 0.011] },
      "problemas": []
    }
  ],
  "screenshots": {
    "perspectiva": "<PNG base64>",
    "frente":      "<PNG base64>",
    "lado":        "<PNG base64>",
    "topo":        "<PNG base64>"
  },
  "tempo_execucao_ms": 342.5
}
```

## 4b. Descrever a cena atual

```bash
# Via linha de comando
python -m client.send --cena

# Via código
from client.send import descrever_cena
print(descrever_cena())
```

Retorna texto como:
```
CENA: 1 objeto(s) total | 1 MESH

[DiscoDFreio]
  Forma           : cilindro achatado / disco
  Dimensões (mm)  : 280.0 × 280.0 × 22.0  (L × P × A)
  Centro (mm)     : X=0.0  Y=0.0  Z=0.0
  Raio estimado   : 140.0 mm
  Malha           : 4096 vértices  3840 faces
  Volume          : 1352.2 cm³
  Saúde           : ✓ limpa
```

## 5. Padrão de código para a IA

```python
# A IA SEMPRE segue esta estrutura:
import sys; sys.path.insert(0, r"C:\Users\tiago\Desktop\Larperian")

from catalog.dimensions import DISCO_FREIO
from api import criar_cilindro_oco, furar_radial, chanfrar_arestas, validar_objeto

dim = DISCO_FREIO["compacto"]      # 1. Busca dimensões reais
obj = criar_cilindro_oco(...)       # 2. Cria geometria base
obj = furar_radial(obj, ...)        # 3. Aplica operações
relatorio = validar_objeto(obj)     # 4. Valida antes de finalizar
print(relatorio)                    # 5. Reporta problemas
```

## 6. Estrutura de pastas

```
Larperian/
├── bridge/server.py     ← Addon Blender (instale aqui)
├── api/                 ← DSL de geometria (a IA usa isto)
│   ├── primitives.py    ← cilindros, discos, caixas, torus...
│   ├── operations.py    ← booleanos, furos radiais, chanfros...
│   ├── selectors.py     ← seleção semântica de arestas/faces
│   └── validators.py    ← diagnóstico de problemas na malha
├── catalog/
│   └── dimensions.py    ← medidas reais de peças mecânicas
├── parts/               ← peças implementadas (exemplos/testes da api/)
│   └── brake_disc.py
├── client/send.py       ← envia scripts e recebe resultado+screenshot
└── assembler.py         ← monta a cena completa
```

## 7. Adicionar novas peças

Crie `parts/nome_da_peca.py` seguindo o padrão de `brake_disc.py`:
- Importe dimensões do `catalog/`
- Use funções da `api/` (não `bpy.ops` direto)
- Exponha `gerar(variante, nome)` e `gerar_e_validar(variante)`
