"""Extracao de silhueta a partir de PNG (numpy + Pillow, sem OpenCV).

Estrategia robusta para dois casos:
- render proprio: veiculo claro sobre fundo escuro -> fg = pixel claro;
- blueprint: linhas (claras sobre fundo escuro, ou escuras sobre claro) ->
  detecta o brilho do fundo pelas bordas e inverte o limiar conforme o caso.

Para comparacao usamos o "perfil" da silhueta: por coluna X, a linha mais alta
(topo) e mais baixa (base) marcada como foreground. Isso evita flood-fill e
funciona tanto para massa solida (render) quanto para line-art (blueprint).
"""

import numpy as np
from PIL import Image


def load_gray(path):
    """Carrega PNG como array float HxW em [0,1] (tons de cinza)."""
    img = Image.open(path).convert("L")
    return np.asarray(img, dtype=np.float32) / 255.0


def background_is_dark(gray):
    """Heuristica: media dos pixels da borda. Fundo escuro -> True."""
    border = np.concatenate([gray[0, :], gray[-1, :], gray[:, 0], gray[:, -1]])
    return float(border.mean()) < 0.5


def foreground_mask(gray, kind="auto", thresh=None):
    """Mascara booleana (True = veiculo/tinta).

    kind:
      'render'    -> claro sobre escuro (fg = gray > thr)
      'blueprint' -> auto pelo brilho do fundo
      'auto'      -> igual a 'blueprint'
    """
    if kind == "render":
        thr = 0.20 if thresh is None else thresh
        return gray > thr
    if background_is_dark(gray):
        thr = 0.42 if thresh is None else thresh
        return gray > thr
    thr = 0.55 if thresh is None else thresh
    return gray < thr


def bbox(mask):
    """(x0, y0, x1, y1) inclusivo, ou None se vazio. Linha 0 = topo da imagem."""
    ys, xs = np.where(mask)
    if xs.size == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def profiles(mask):
    """Perfis por coluna (vetorizado).

    Retorna (top, bottom), arrays float de largura W. top[x] = linha mais alta
    (menor indice) com foreground; bottom[x] = linha mais baixa. NaN onde a
    coluna esta vazia.
    """
    h, _ = mask.shape
    any_col = mask.any(axis=0)
    top = np.argmax(mask, axis=0).astype(np.float32)
    bottom = (h - 1 - np.argmax(mask[::-1, :], axis=0)).astype(np.float32)
    top[~any_col] = np.nan
    bottom[~any_col] = np.nan
    return top, bottom


def car_extent(mask, min_col_frac=0.10):
    """Extensao horizontal do CARRO (colunas com 'massa' real), ignorando linhas
    finas (ex.: linha do solo do blueprint) que atravessam o recorte inteiro.

    Uma coluna conta como carro se sua contagem de foreground supera uma fracao
    da coluna mais densa. Retorna (cx0, cx1) inclusivo.
    """
    colmass = mask.sum(axis=0)
    if colmass.max() == 0:
        return None
    thr = max(3.0, colmass.max() * min_col_frac)
    car_cols = np.where(colmass >= thr)[0]
    if car_cols.size < 2:
        return None
    return int(car_cols.min()), int(car_cols.max())


def height_profile_mm(mask, length_mm, samples=240):
    """Perfil de ALTURA acima do solo, em mm, reamostrado em `samples` posicoes
    normalizadas de X (0..1 = nariz..traseira do CARRO, nao do recorte).

    Calibra pelo comprimento do carro: mm_por_px = length_mm / largura_carro_px,
    onde a largura ignora linhas finas (solo). Solo = base da silhueta. Altura
    por coluna = (base - topo) * mm_por_px.
    """
    bb = bbox(mask)
    if bb is None:
        raise ValueError("Mascara vazia: nada para medir.")
    _, _, _, y1 = bb
    ext = car_extent(mask)
    if ext is None:
        raise ValueError("Silhueta insuficiente para perfil.")
    cx0, cx1 = ext
    width_px = max(cx1 - cx0, 1)
    mm_per_px = length_mm / width_px
    top, _ = profiles(mask)
    cols = np.arange(cx0, cx1 + 1)
    top_seg = top[cx0:cx1 + 1]
    height_px = (y1 - top_seg)  # base (solo) menos topo
    valid = ~np.isnan(height_px)
    if valid.sum() < 2:
        raise ValueError("Silhueta insuficiente para perfil.")
    xnorm = (cols - cx0) / width_px
    samp = np.linspace(0.0, 1.0, samples)
    height_mm = np.interp(samp, xnorm[valid], height_px[valid] * mm_per_px)
    return {
        "x_norm": samp,
        "height_mm": height_mm,
        "mm_per_px": mm_per_px,
        "bbox_px": [cx0, bb[1], cx1, y1],
        "car_extent_px": [cx0, cx1],
        "length_mm": length_mm,
    }
