"""
Cliente HTTP para enviar scripts ao Blender e receber feedback rico.

Uso básico:
    from client.send import enviar_script, descrever_cena
    resultado = enviar_script("bpy.ops.mesh.primitive_cube_add()")
    print(resultado.resumo())
    resultado.salvar_screenshots("pasta/capturas")  # salva os 4 PNGs

    descricao = descrever_cena()
    print(descricao)

Uso via linha de comando:
    python -m client.send meu_script.py --screenshots capturas/
    python -m client.send --cena
    python -m client.send --teste
"""

from __future__ import annotations
import http.client
import json
import base64
import os
import sys
from dataclasses import dataclass, field
from typing import Optional

HOST      = "localhost"
PORT      = 19000
TIMEOUT_S = 70


# ---------------------------------------------------------------------------
# Resultado de execução
# ---------------------------------------------------------------------------

@dataclass
class ResultadoBlender:
    sucesso: bool
    erro: Optional[str]
    objetos_criados: list[dict]
    screenshots: dict[str, str]          # chave: "perspectiva"|"frente"|"lado"|"topo"
    tempo_execucao_ms: float
    _raw: dict = field(repr=False, default_factory=dict)

    # Ordem de exibição padrão para salvar arquivos
    _ORDEM_VISTAS = ["perspectiva", "frente", "lado", "topo"]

    def resumo(self) -> str:
        linhas = []
        status = "OK" if self.sucesso else f"ERRO: {self.erro}"
        linhas.append(f"Status        : {status}")
        linhas.append(f"Tempo exec    : {self.tempo_execucao_ms} ms")
        linhas.append(f"Novos objetos : {len(self.objetos_criados)}")

        for obj in self.objetos_criados:
            dims = [round(d * 1000, 1) for d in obj.get("dimensoes", [0, 0, 0])]
            problemas = obj.get("problemas", [])
            tag = ""
            if problemas:
                tag = "  !! " + "; ".join(problemas)
            linhas.append(
                f"  • {obj['nome']}  "
                f"{dims[0]}×{dims[1]}×{dims[2]} mm  "
                f"V:{obj.get('vertices','?')} F:{obj.get('faces','?')}"
                f"{tag}"
            )

        vistas_ok = list(self.screenshots.keys())
        linhas.append(f"Screenshots   : {len(vistas_ok)}/4 — {', '.join(vistas_ok) or 'nenhum'}")
        return "\n".join(linhas)

    def salvar_screenshots(self, prefixo: str) -> list[str]:
        """
        Salva as quatro vistas como arquivos PNG.
        prefixo pode ser:
          - um diretório:  "capturas/"  → salva capturas/perspectiva.png, etc.
          - um prefixo:    "saida/disco" → salva saida/disco_perspectiva.png, etc.
        """
        if not self.screenshots:
            print("[send] Nenhum screenshot disponível.")
            return []

        salvos = []
        eh_dir = prefixo.endswith("/") or prefixo.endswith("\\") or os.path.isdir(prefixo)

        for vista in self._ORDEM_VISTAS:
            if vista not in self.screenshots:
                continue
            if eh_dir:
                os.makedirs(prefixo, exist_ok=True)
                caminho = os.path.join(prefixo, f"{vista}.png")
            else:
                os.makedirs(os.path.dirname(prefixo) or ".", exist_ok=True)
                caminho = f"{prefixo}_{vista}.png"

            dados = base64.b64decode(self.screenshots[vista])
            with open(caminho, "wb") as f:
                f.write(dados)
            print(f"[send] {vista:12s} → {caminho}")
            salvos.append(caminho)

        return salvos

    def tem_problemas(self) -> bool:
        if not self.sucesso:
            return True
        return any(obj.get("problemas") for obj in self.objetos_criados)


# ---------------------------------------------------------------------------
# Funções públicas
# ---------------------------------------------------------------------------

def enviar_script(codigo: str) -> ResultadoBlender:
    """Executa código Python no Blender e retorna resultado com 4 screenshots."""
    dados = _post("/", codigo.encode("utf-8"))
    return ResultadoBlender(
        sucesso=dados.get("sucesso", False),
        erro=dados.get("erro"),
        objetos_criados=dados.get("objetos_criados", []),
        screenshots=dados.get("screenshots", {}),
        tempo_execucao_ms=dados.get("tempo_execucao_ms", 0),
        _raw=dados,
    )


def enviar_arquivo(caminho_py: str) -> ResultadoBlender:
    """Lê um arquivo .py e envia ao Blender."""
    with open(caminho_py, "r", encoding="utf-8") as f:
        return enviar_script(f.read())


def descrever_cena() -> str:
    """Retorna descrição textual dos objetos presentes na cena do Blender."""
    dados = _get("/cena")
    return dados.get("descricao", "(sem resposta)")


def testar_conexao() -> bool:
    try:
        r = enviar_script("pass")
        return r.sucesso
    except Exception:
        return False


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _post(path: str, corpo: bytes) -> dict:
    conn = http.client.HTTPConnection(HOST, PORT, timeout=TIMEOUT_S)
    try:
        conn.request("POST", path, body=corpo,
                     headers={"Content-Type": "text/plain; charset=utf-8",
                               "Content-Length": str(len(corpo))})
        resp = conn.getresponse()
        return json.loads(resp.read().decode("utf-8"))
    finally:
        conn.close()


def _get(path: str) -> dict:
    conn = http.client.HTTPConnection(HOST, PORT, timeout=TIMEOUT_S)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        return json.loads(resp.read().decode("utf-8"))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Linha de comando
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Larperian Bridge Client")
    p.add_argument("script", nargs="?", help="Arquivo .py a enviar")
    p.add_argument("--codigo",      "-c", metavar="CODIGO",   help="Código inline")
    p.add_argument("--screenshots", "-s", metavar="PREFIXO",  help="Salvar screenshots (pasta/ ou prefixo)")
    p.add_argument("--cena",              action="store_true", help="Descrever cena atual")
    p.add_argument("--teste",             action="store_true", help="Testar conexão")
    args = p.parse_args()

    if args.teste:
        ok = testar_conexao()
        print("Bridge ATIVO" if ok else "Bridge INATIVO — abra o Blender e ative o addon.")
        sys.exit(0 if ok else 1)

    if args.cena:
        print(descrever_cena())
        sys.exit(0)

    if args.codigo:
        resultado = enviar_script(args.codigo)
    elif args.script:
        resultado = enviar_arquivo(args.script)
    else:
        p.print_help()
        sys.exit(1)

    print(resultado.resumo())

    if args.screenshots:
        resultado.salvar_screenshots(args.screenshots)

    sys.exit(0 if not resultado.tem_problemas() else 1)
