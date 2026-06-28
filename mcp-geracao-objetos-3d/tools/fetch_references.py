"""
Ferramenta de referências técnicas do Larperian.

Estratégia de fontes (por ordem de prioridade):
  1. PDFs de patentes USPTO (Google Patents) — seções transversais, vistas explodidas
  2. PDFs de catálogos de fabricantes (SKF, INA, etc.) — dimensões exatas + desenhos
  3. Wikimedia Commons — fallback para componentes padronizados simples

Por que PDFs são a fonte primária:
  - Imagens em resolução vetorial/alta (~2500×3300px a 300 DPI via PyMuPDF)
  - Patentes são documentos públicos imutáveis — nunca mudam de conteúdo
  - Catálogos de fabricantes são documentos de engenharia obrigatoriamente precisos
  - Ambos funcionam sem autenticação e sem rate limit agressivo

Dependência necessária:
  pip install pymupdf

Uso:
  python tools/fetch_references.py brake_disc          # baixa tudo configurado
  python tools/fetch_references.py bearing             # catálogos SKF
  python tools/fetch_references.py --listar            # mostra o que está disponível
"""

from __future__ import annotations
import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import date
from pathlib import Path

ROOT     = Path(__file__).resolve().parent.parent
REFS_DIR = ROOT / "references"

UA = "LarperianProject/1.0 (educational; tiagomarcondechadeck@gmail.com)"


# ---------------------------------------------------------------------------
# CATÁLOGO DE FONTES
#
# Adicione aqui novas peças conforme o projeto cresce.
# Cada entrada tem:
#   - url_pdf:        URL direta do PDF (obrigatório)
#   - nome_arquivo:   como salvar localmente
#   - paginas_ref:    lista de números de página (1-based) que contêm
#                     desenhos técnicos úteis para modelagem
#   - mapa_paginas:   {num_pagina: "descricao"} para nomear as imagens
#   - descricao:      o que esta fonte contém
#   - tipo:           "patente" | "catalogo_fabricante"
#   - fonte_nome:     nome legível da fonte
# ---------------------------------------------------------------------------

FONTES_PDF: dict[str, list[dict]] = {

    "brake_disc": [
        {
            "tipo":         "patente",
            "fonte_nome":   "USPTO — US20090314591A1",
            "descricao":    (
                "Disco de freio mecanicamente ventilado com impeller centrífugo livre. "
                "NOTA: design especializado (impeller livre), não disco padrão — "
                "mas geometria do chapéu (hat profile) e estrutura de duas faces são referência válida."
            ),
            "url_pdf":      "https://patentimages.storage.googleapis.com/b4/a6/52/ea37c207b55111/US20090314591A1.pdf",
            "nome_arquivo": "patent_US20090314591A1.pdf",
            "paginas_ref":  [2, 3, 4],
            "mapa_paginas": {
                2: ("ref_fig1_explodida_isometrica.png",
                    "FIG.1 — Vista isométrica explodida: 4 camadas (disco inboard, anel, impeller, disco outboard)"),
                3: ("ref_fig2_vista_frontal.png",
                    "FIG.2 — Vista frontal montada: slots curvos do impeller, furos de ventilação, linha de corte A-A"),
                4: ("ref_fig3_secao_transversal.png",
                    "FIG.3 — Seção A-A: hat profile do cubo, duas faces de fricção, pastilha (pontilhado), impeller (V)"),
            },
            "licenca":      "Domínio público (patente USPTO)",
            "url_pagina":   "https://patents.google.com/patent/US20090314591A1/en",
        },
    ],

    "bearing": [
        {
            "tipo":         "catalogo_fabricante",
            "fonte_nome":   "SKF — Deep Groove Ball Bearings",
            "descricao":    (
                "Catálogo técnico SKF para rolamentos de esferas de sulco profundo. "
                "Contém: seções transversais detalhadas, variantes (shields, vedações, snap ring), "
                "tabela de folgas internas para todos os tamanhos (2.5mm–240mm), "
                "fatores de carga dinâmica e estática, faixas de temperatura."
            ),
            "url_pdf":      "https://landvelar.is/wp-content/uploads/2016/11/SKF_Deep-groove-ball-bearings.pdf",
            "nome_arquivo": "skf_deep_groove_ball_bearings.pdf",
            "paginas_ref":  [3, 4, 5],
            "mapa_paginas": {
                3: ("ref_p03_secoes_transversais.png",
                    "Seção transversal: rolamento aberto (single row) e com filling slots — pista, esferas, gaiola visíveis"),
                4: ("ref_p04_variacoes_com_vedacao.png",
                    "Variações: shields, vedações de borracha, snap ring — perfis de vedação e montagem"),
                5: ("ref_p05_tabela_folgas_internas.png",
                    "Tabela 1: Folga interna radial para todas as séries — C2, Normal, C3, C4, C5 (2.5mm a 240mm)"),
            },
            "licenca":      "© SKF — uso educacional / referência de engenharia",
            "url_pagina":   "https://www.skf.com/group/products/rolling-bearings/ball-bearings/deep-groove-ball-bearings",
        },
    ],

    "caliper": [
        # A preencher — sugestão: patente US7857111B1 (pinça reforçada)
        # ou patente EP1000083A2 (pinça monobloco Brembo)
    ],

    "coil_spring": [
        # Sugestão: catálogo técnico da Lesjöfors ou Stabilus
        # URL: https://www.lesjofors.com/technical-information/
    ],

    "wheel_hub": [
        # Sugestão: patente US6422358B2 (hub com disco ventilado) ou
        # catálogo FAG/Schaeffler de unidades de cubo
    ],
}


# ---------------------------------------------------------------------------
# Motor de extração PDF → PNG
# ---------------------------------------------------------------------------

def _verificar_pymupdf():
    try:
        import fitz
        return fitz
    except ImportError:
        print("[fetch] PyMuPDF não instalado. Execute: pip install pymupdf")
        sys.exit(1)


def extrair_paginas_pdf(
    pdf_path: Path,
    dest_dir: Path,
    mapa_paginas: dict[int, tuple[str, str]],
    dpi: int = 300,
) -> list[dict]:
    """
    Extrai páginas específicas de um PDF como PNGs de alta resolução.

    mapa_paginas: {num_pagina_1based: (nome_arquivo, descricao)}
    Retorna lista de dicts com info de cada página extraída.
    """
    fitz = _verificar_pymupdf()
    zoom  = dpi / 72.0
    mat   = fitz.__dict__.get("Matrix", None)

    doc = fitz.open(str(pdf_path))
    total = len(doc)
    extraidos = []

    for num_pag, (nome_arquivo, descricao) in sorted(mapa_paginas.items()):
        idx = num_pag - 1  # fitz usa índice 0-based
        if idx >= total:
            print(f"  [aviso] Página {num_pag} não existe no PDF ({total} páginas)")
            continue

        page = doc[idx]
        pix  = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        saida = dest_dir / nome_arquivo
        pix.save(str(saida))

        kb = saida.stat().st_size / 1024
        print(f"  p{num_pag:02d}  {pix.width}×{pix.height}px  {kb:.0f} KB  →  {nome_arquivo}")
        extraidos.append({
            "arquivo":     nome_arquivo,
            "descricao":   descricao,
            "pagina_pdf":  num_pag,
            "resolucao":   f"{pix.width}×{pix.height}",
            "tamanho_kb":  round(kb, 1),
        })

    doc.close()
    return extraidos


# ---------------------------------------------------------------------------
# Download HTTP
# ---------------------------------------------------------------------------

def _baixar(url: str, destino: Path, tentativas: int = 3) -> bool:
    for t in range(tentativas):
        if t:
            espera = 4 * t
            print(f"  [retry {t}] aguardando {espera}s...")
            time.sleep(espera)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                destino.write_bytes(r.read())
            return True
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"  [rate limit] HTTP 429 — aguardando 10s")
                time.sleep(10)
            else:
                print(f"  [HTTP {e.code}] {url}")
                return False
        except Exception as e:
            print(f"  [erro] {e}")
    return False


# ---------------------------------------------------------------------------
# meta.json
# ---------------------------------------------------------------------------

def _carregar_meta(peca: str) -> dict:
    p = REFS_DIR / peca / "meta.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"nome": peca, "referencias": []}


def _salvar_meta(peca: str, meta: dict):
    p = REFS_DIR / peca / "meta.json"
    p.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _ja_registrado(meta: dict, arquivo: str) -> bool:
    return any(r.get("arquivo") == arquivo for r in meta.get("referencias", []))


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def processar_peca(peca: str, forcar: bool = False) -> int:
    """
    Baixa PDFs e extrai páginas de referência para a peça indicada.
    Retorna número de imagens extraídas.
    """
    fontes = FONTES_PDF.get(peca)
    if not fontes:
        print(f"[fetch] Sem fontes configuradas para '{peca}'.")
        print(f"  Adicione uma entrada em FONTES_PDF em tools/fetch_references.py")
        return 0

    dest_dir = REFS_DIR / peca
    dest_dir.mkdir(parents=True, exist_ok=True)
    meta    = _carregar_meta(peca)
    total   = 0

    for fonte in fontes:
        print(f"\n[fonte] {fonte['fonte_nome']}")
        print(f"  Tipo : {fonte['tipo']}")
        print(f"  Info : {fonte['descricao'][:80]}...")

        pdf_path = dest_dir / fonte["nome_arquivo"]

        # Baixar PDF se necessário
        if not pdf_path.exists() or forcar:
            print(f"  ↓ Baixando PDF: {fonte['nome_arquivo']}")
            ok = _baixar(fonte["url_pdf"], pdf_path)
            if not ok:
                print(f"  FALHOU — pulando esta fonte")
                continue
            mb = pdf_path.stat().st_size / (1024 * 1024)
            print(f"  OK  ({mb:.2f} MB)")
        else:
            mb = pdf_path.stat().st_size / (1024 * 1024)
            print(f"  PDF já existe ({mb:.2f} MB) — usando cache")

        # Filtrar páginas já extraídas (a menos que --force)
        mapa_pendente = {}
        for num_pag, (nome_arq, desc) in fonte["mapa_paginas"].items():
            saida = dest_dir / nome_arq
            if saida.exists() and not forcar:
                print(f"  SKIP (já existe): {nome_arq}")
            else:
                mapa_pendente[num_pag] = (nome_arq, desc)

        if not mapa_pendente:
            continue

        # Extrair páginas
        print(f"  Extraindo {len(mapa_pendente)} página(s) a 300 DPI...")
        extraidos = extrair_paginas_pdf(pdf_path, dest_dir, mapa_pendente)

        # Registrar no meta.json
        for info in extraidos:
            if not _ja_registrado(meta, info["arquivo"]):
                meta.setdefault("referencias", []).append({
                    "arquivo":             info["arquivo"],
                    "descricao":           info["descricao"],
                    "tipo":                fonte["tipo"],
                    "fonte_nome":          fonte["fonte_nome"],
                    "pagina_no_pdf":       info["pagina_pdf"],
                    "resolucao":           info["resolucao"],
                    "pdf_origem":          fonte["nome_arquivo"],
                    "url_pagina_original": fonte.get("url_pagina", ""),
                    "licenca":             fonte.get("licenca", ""),
                    "baixado_em":          date.today().isoformat(),
                })
        _salvar_meta(peca, meta)
        total += len(extraidos)

    print(f"\n[fetch] Concluído: {total} imagem(ns) extraída(s) para references/{peca}/")
    return total


# ---------------------------------------------------------------------------
# Linha de comando
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Larperian — baixa e extrai referências técnicas em alta resolução"
    )
    p.add_argument("peca",    nargs="?", help="Nome da peça (ex: brake_disc, bearing)")
    p.add_argument("--todas", "-a", action="store_true", help="Processar todas as peças configuradas")
    p.add_argument("--force", "-f", action="store_true", help="Re-baixar e re-extrair mesmo se já existir")
    p.add_argument("--listar","-l", action="store_true", help="Listar fontes configuradas por peça")
    p.add_argument("--dpi",        type=int, default=300, help="Resolução de extração (padrão: 300)")
    args = p.parse_args()

    if args.listar:
        print("\nFontes configuradas:\n")
        for nome, fontes in FONTES_PDF.items():
            pasta  = REFS_DIR / nome
            n_imgs = len([f for f in pasta.glob("ref_*.png")]) if pasta.exists() else 0
            pdfs   = [f["nome_arquivo"] for f in fontes] if fontes else ["(nenhuma)"]
            print(f"  {nome:<20} {len(fontes)} fonte(s)  {n_imgs} imagem(ns) extraída(s)")
            for f in fontes:
                pags = list(f["mapa_paginas"].keys())
                print(f"    · {f['fonte_nome']}  —  páginas {pags}")
        print()
        sys.exit(0)

    if args.todas:
        total = sum(processar_peca(peca, forcar=args.force) for peca in FONTES_PDF)
        print(f"\nTotal geral: {total} imagem(ns)")
        sys.exit(0 if total > 0 else 1)

    if not args.peca:
        p.print_help()
        sys.exit(1)

    n = processar_peca(args.peca, forcar=args.force)
    sys.exit(0 if n >= 0 else 1)
