"""
PORTA DE ENTRADA — pedido em texto vira a SPEC (a "encomenda") que o orquestrador consome.

Princípios (da pesquisa):
  - texto cru NÃO vai direto pro gerador; passa por normalização.
  - marca o que foi ESPECIFICADO vs INFERIDO (default) — senão fica válido porém errado de intenção.
  - pergunta só quando a lacuna é material (aqui: quando nem sabe que objeto é).

Normalizador atual = regras simples e reproduzíveis. Um normalizador LLM pluga na MESMA
interface (normalizar(texto) -> spec) depois, sem mexer no resto.

Rodar:  .venv/Scripts/python.exe prototype/entrada.py
"""

import os
import re
import sys
import math

AQUI = os.path.dirname(os.path.abspath(__file__))
if AQUI not in sys.path:
    sys.path.insert(0, AQUI)


# ---------------------------------------------------------------------------
# Catálogo de tipos conhecidos (template por objeto)
# ---------------------------------------------------------------------------
# regexes de extração (compartilhadas)
RE_EXT = r"(?:di[aâ]metro\s+externo|externo|ext)\D{0,8}(\d+(?:\.\d+)?)"
RE_FURO = r"(?:furo|interno|int)\D{0,8}(\d+(?:\.\d+)?)"
RE_DIAM = r"di[aâ]metro\D{0,8}(\d+(?:\.\d+)?)"
RE_ALT = r"(?:altura|espessura|comprimento)\D{0,8}(\d+(?:\.\d+)?)"
RE_LARG = r"largura\D{0,8}(\d+(?:\.\d+)?)"
RE_PROF = r"profundidade\D{0,8}(\d+(?:\.\d+)?)"
RE_NFUROS = r"(\d+)\s*furos"

_ORGANICO = {"raio_corpo": 1.0, "raio_cabeca": 0.55, "pos_cabeca": [0.9, 0.0, 0.3],
             "membro_dentro": 0.3, "membro_fora": 1.3, "raio_membro": 0.22}

TEMPLATES = {
    # --- mecânico: cilindro oco ---
    "bucha": {"dominio": "mecanico",
              "params_default": {"tipo": "cilindro_oco", "diametro_ext": 40.0, "diametro_furo": 20.0, "altura": 25.0},
              "extracao": {"diametro_ext": [RE_EXT], "diametro_furo": [RE_FURO], "altura": [RE_ALT]}},
    "tubo": {"dominio": "mecanico",
             "params_default": {"tipo": "cilindro_oco", "diametro_ext": 30.0, "diametro_furo": 24.0, "altura": 80.0},
             "extracao": {"diametro_ext": [RE_EXT], "diametro_furo": [RE_FURO], "altura": [RE_ALT]}},
    "arruela": {"dominio": "mecanico",
                "params_default": {"tipo": "cilindro_oco", "diametro_ext": 30.0, "diametro_furo": 16.0, "altura": 4.0},
                "extracao": {"diametro_ext": [RE_EXT], "diametro_furo": [RE_FURO], "altura": [RE_ALT]}},
    # --- mecânico: cilindro sólido ---
    "disco": {"dominio": "mecanico",
              "params_default": {"tipo": "cilindro", "diametro": 80.0, "altura": 8.0},
              "extracao": {"diametro": [RE_DIAM], "altura": [RE_ALT]}},
    "eixo": {"dominio": "mecanico",
             "params_default": {"tipo": "cilindro", "diametro": 16.0, "altura": 120.0},
             "extracao": {"diametro": [RE_DIAM], "altura": [RE_ALT]}},
    "cilindro": {"dominio": "mecanico",
                 "params_default": {"tipo": "cilindro", "diametro": 40.0, "altura": 40.0},
                 "extracao": {"diametro": [RE_DIAM], "altura": [RE_ALT]}},
    # --- mecânico: caixa ---
    "placa": {"dominio": "mecanico",
              "params_default": {"tipo": "caixa", "largura": 80.0, "profundidade": 60.0, "altura": 8.0},
              "extracao": {"largura": [RE_LARG], "profundidade": [RE_PROF], "altura": [RE_ALT]}},
    # --- mecânico: disco com furos em círculo (flange) ---
    "flange": {"dominio": "mecanico",
               "params_default": {"tipo": "disco_furado", "diametro": 90.0, "altura": 10.0,
                                  "n_furos": 4, "diametro_furo": 9.0, "raio_furos": 35.0},
               "extracao": {"diametro": [RE_DIAM], "altura": [RE_ALT], "diametro_furo": [RE_FURO], "n_furos": [RE_NFUROS]}},
    # --- orgânico (gerador só faz o blob por ora) ---
    "blob": {"dominio": "organico", "params_default": dict(_ORGANICO), "extracao": {}},
}
SINONIMOS = {"criatura": "blob", "bicho": "blob"}


def detectar_tipo(texto):
    t = texto.lower()
    for chave, tipo in SINONIMOS.items():
        if chave in t:
            return tipo
    for tipo in TEMPLATES:
        if tipo in t:
            return tipo
    return None


def extrair_numeros(texto, regras):
    achados = {}
    t = texto.lower()
    for param, padroes in regras.items():
        for p in padroes:
            m = re.search(p, t)
            if m:
                achados[param] = float(m.group(1))
                break
    return achados


def montar_asserts(dominio, params):
    if dominio != "mecanico":
        return [
            {"medida": "watertight", "alvo": 1.0, "tol": 0.0},
            {"medida": "componentes", "alvo": 1.0, "tol": 0.0},
            {"medida": "euler", "alvo": 2.0, "tol": 0.0},
        ]
    valido = {"medida": "solido_valido", "alvo": 1.0, "tol": 0.0}
    t = params.get("tipo")
    if t == "cilindro_oco":
        od, idd, h = params["diametro_ext"], params["diametro_furo"], params["altura"]
        vol = math.pi * ((od / 2) ** 2 - (idd / 2) ** 2) * h
        return [{"medida": "bbox_z", "alvo": h, "tol": 0.3},
                {"medida": "volume", "alvo": vol, "tol": max(5.0, vol * 0.003)},
                {"medida": "furos", "alvo": 1.0, "tol": 0.0}, valido]
    if t == "cilindro":
        return [{"medida": "bbox_x", "alvo": params["diametro"], "tol": 0.6},
                {"medida": "bbox_z", "alvo": params["altura"], "tol": 0.3}, valido]
    if t == "caixa":
        return [{"medida": "bbox_x", "alvo": params["largura"], "tol": 0.3},
                {"medida": "bbox_y", "alvo": params["profundidade"], "tol": 0.3},
                {"medida": "bbox_z", "alvo": params["altura"], "tol": 0.3}, valido]
    if t == "disco_furado":
        return [{"medida": "bbox_x", "alvo": params["diametro"], "tol": 0.6},
                {"medida": "bbox_z", "alvo": params["altura"], "tol": 0.3},
                {"medida": "furos", "alvo": float(params["n_furos"]), "tol": 0.0}, valido]
    return [valido]


def normalizar(texto):
    """texto -> (spec | None, perguntas, origem)."""
    tipo = detectar_tipo(texto)
    if tipo is None:
        tipos = ", ".join(t for t in TEMPLATES) + ", " + ", ".join(SINONIMOS)
        return None, [f"Não entendi QUE objeto criar. Diz o tipo? (ex: {tipos})"], {}

    tpl = TEMPLATES[tipo]
    extraidos = extrair_numeros(texto, tpl.get("extracao", {}))
    params = dict(tpl["params_default"])
    origem = {}
    for k in params:
        if k in extraidos:
            params[k] = extraidos[k]
            origem[k] = "especificado"
        else:
            origem[k] = "inferido"

    spec = {
        "identidade": f"{tipo}: {texto.strip()}",
        "dominio": tpl["dominio"],
        "params": params,
        "asserts": montar_asserts(tpl["dominio"], params),
    }
    return spec, [], origem


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def mostrar(texto):
    print(f"\nPEDIDO: \"{texto}\"")
    spec, perguntas, origem = normalizar(texto)
    if spec is None:
        print(f"  -> PRECISA CLARIFICAR: {perguntas[0]}")
        return None
    print(f"  -> domínio: {spec['dominio']}")
    so_relevantes = {k: v for k, v in spec["params"].items() if not isinstance(v, list)}
    for k, v in so_relevantes.items():
        print(f"     {k} = {v}   [{origem[k]}]")
    return spec


PEDIDOS = [
    "uma bucha de diâmetro externo 50, furo 22 e altura 30",
    "um disco de diâmetro 100 e espessura 6",
    "uma placa de largura 70, profundidade 50 e espessura 10",
    "um flange de diâmetro 90, espessura 12 com 6 furos",
    "um eixo de diâmetro 20 e comprimento 150",
    "um bicho",                          # orgânico (gerador só faz o blob)
    "faça uma coisa legal aí",           # não sabe -> pergunta
]


def main():
    print("LARPERIAN — porta de entrada (texto -> spec)")
    for p in PEDIDOS:
        mostrar(p)

    print("\n" + "=" * 64)
    print("END-TO-END: cada pedido mecânico -> spec -> orquestrador -> verificado")
    from orchestrator import orquestrar, CorretorNenhum
    for p in PEDIDOS:
        spec, perguntas, _ = normalizar(p)
        if spec and spec["dominio"] == "mecanico":
            orquestrar(spec, CorretorNenhum(), render=False)


if __name__ == "__main__":
    main()
