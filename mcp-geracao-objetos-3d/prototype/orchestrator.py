"""
ORQUESTRADOR — a espinha que amarra as peças num fluxo só.

  spec -> rotear(domínio) -> gerar -> medir -> conferir -> [corrigir -> repetir] -> exportar -> ver

Tudo é plugável:
  - DRIVER por domínio (mecânico=B-rep/build123d, orgânico=SDF/sdf)
  - CORRETOR (numérico burro agora; um LLM entra na mesma interface depois)
  - RENDER (Blender headless, processo à parte)

Rodar:  .venv/Scripts/python.exe prototype/orchestrator.py
"""

import os
import math
import subprocess
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
BLENDER = r"C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe"
RENDER_SCRIPT = os.path.join(AQUI, "render_views.py")


# ===========================================================================
# DRIVERS por domínio — mesma interface: gerar / medir / exportar_stl
# ===========================================================================

class DriverMecanico:
    dominio = "mecanico"

    def gerar(self, params):
        """Despacha pela 'tipo' da peça — cada tipo é uma receita build123d."""
        from build123d import BuildPart, Cylinder, Box, Mode, PolarLocations
        tipo = params.get("tipo", "cilindro_oco")

        with BuildPart() as p:
            if tipo == "cilindro_oco":            # bucha / tubo / arruela
                od, idd, h = params["diametro_ext"], params["diametro_furo"], params["altura"]
                Cylinder(radius=od / 2, height=h)
                Cylinder(radius=idd / 2, height=h, mode=Mode.SUBTRACT)
            elif tipo == "cilindro":              # disco / eixo / cilindro sólido
                Cylinder(radius=params["diametro"] / 2, height=params["altura"])
            elif tipo == "caixa":                 # placa / bloco
                Box(params["largura"], params["profundidade"], params["altura"])
            elif tipo == "disco_furado":          # flange (furos em círculo)
                Cylinder(radius=params["diametro"] / 2, height=params["altura"])
                with PolarLocations(params["raio_furos"], int(params["n_furos"])):
                    Cylinder(radius=params["diametro_furo"] / 2, height=params["altura"], mode=Mode.SUBTRACT)
            else:
                raise ValueError(f"tipo mecânico desconhecido: {tipo}")
        return p.part

    def medir(self, part):
        bb = part.bounding_box()
        medidas = {
            "bbox_x": bb.size.X, "bbox_y": bb.size.Y, "bbox_z": bb.size.Z,
            "volume": part.volume,
            "centro_x": (bb.min.X + bb.max.X) / 2, "centro_y": (bb.min.Y + bb.max.Y) / 2,
            "solido_valido": 1.0 if part.is_valid else 0.0,
        }
        medidas["furos"] = self._contar_furos(part)
        return medidas

    def _contar_furos(self, part):
        """Nº de furos passantes = gênero da peça, provado por topologia (Euler).
        Pra superfície fechada: euler = 2 - 2*genero  =>  furos = (2 - euler)/2."""
        import trimesh
        from build123d import export_stl
        tmp = os.path.join(tempfile.gettempdir(), "larp_mech_topo.stl")
        export_stl(part, tmp)
        m = trimesh.load(tmp)
        if not m.is_watertight or len(m.split(only_watertight=False)) != 1:
            return -1.0
        return float(max(0, (2 - int(m.euler_number)) // 2))

    def exportar_stl(self, part, caminho):
        from build123d import export_stl
        export_stl(part, caminho)


class DriverOrganico:
    dominio = "organico"

    def gerar(self, params):
        from sdf import sphere, capsule, X, Z
        corpo = sphere(params["raio_corpo"])
        cabeca = sphere(params["raio_cabeca"]).translate(tuple(params["pos_cabeca"]))
        membro = capsule(-X * params["membro_dentro"], -X * params["membro_fora"] - Z * 0.2, params["raio_membro"])
        f = corpo.union(cabeca, k=0.25).union(membro, k=0.25)
        tmp = os.path.join(tempfile.gettempdir(), "larp_organic.stl")
        f.save(tmp, step=0.04, verbose=False)   # 0.05 saiu non-watertight; resolução importa
        return tmp

    def medir(self, stl_path):
        import trimesh
        m = trimesh.load(stl_path)
        return {
            "watertight": 1.0 if m.is_watertight else 0.0,
            "componentes": float(len(m.split(only_watertight=False))),
            "euler": float(m.euler_number),
            "volume": float(m.volume) if m.is_volume else -1.0,
        }

    def exportar_stl(self, stl_path, caminho):
        import shutil
        shutil.copyfile(stl_path, caminho)


DRIVERS = {d.dominio: d for d in (DriverMecanico(), DriverOrganico())}


# ===========================================================================
# ROTEAÇÃO em cascata: domínio explícito da spec, senão palavra-chave
# ===========================================================================

PALAVRAS = {
    "mecanico": ["bucha", "flange", "parafuso", "engrenagem", "eixo", "rolamento", "disco"],
    "organico": ["arvore", "árvore", "bicho", "criatura", "blob", "planta", "folha"],
}

def rotear(spec):
    if spec.get("dominio") in DRIVERS:
        return spec["dominio"], "explícito"
    texto = spec.get("identidade", "").lower()
    for dom, kws in PALAVRAS.items():
        if any(k in texto for k in kws):
            return dom, f"palavra-chave ({texto})"
    return None, "indefinido — precisa clarificar"


# ===========================================================================
# CHECAGEM — asserts genéricos sobre as medidas
# ===========================================================================

def conferir(medidas, asserts):
    """Cada assert: {medida, alvo, tol}. Retorna lista (nome, medido, alvo, tol, ok)."""
    res = []
    for a in asserts:
        med = medidas.get(a["medida"])
        if med is None:
            res.append((a["medida"], None, a["alvo"], a.get("tol", 0), False)); continue
        tol = a.get("tol", 0)
        ok = abs(med - a["alvo"]) <= tol
        res.append((a["medida"], round(med, 3), a["alvo"], tol, ok))
    return res


# ===========================================================================
# CORRETORES (plugáveis)
# ===========================================================================

class CorretorBissecao:
    """Numérico, burro: ajusta UM parâmetro por feedback de UMA medida monotônica."""
    def __init__(self, param, medida, lo, hi, decresce=True):
        self.param, self.medida, self.lo, self.hi, self.decresce = param, medida, lo, hi, decresce

    def propor(self, params, medidas, asserts):
        alvo = next(a["alvo"] for a in asserts if a["medida"] == self.medida)
        med = medidas[self.medida]
        cresceu_demais = (med > alvo) if self.decresce else (med < alvo)
        if cresceu_demais:
            self.lo = params[self.param]
        else:
            self.hi = params[self.param]
        novos = dict(params)
        novos[self.param] = (self.lo + self.hi) / 2
        return novos


class CorretorNenhum:
    """Sem correção (pra domínios/casos onde a 1a geração já basta)."""
    def propor(self, params, medidas, asserts):
        return None


# ===========================================================================
# ESPINHA — o laço
# ===========================================================================

def orquestrar(spec, corretor, render=False, max_iters=20):
    print(f"\n{'='*64}\nSPEC: {spec['identidade']}")
    dom, motivo = rotear(spec)
    print(f"roteação -> {dom}  ({motivo})")
    if dom is None:
        print("ABORTA: não soube rotear. (aqui dispararia desambiguação)")
        return False
    driver = DRIVERS[dom]

    params = dict(spec["params"])
    artefato = None
    for i in range(1, max_iters + 1):
        artefato = driver.gerar(params)
        medidas = driver.medir(artefato)
        checks = conferir(medidas, spec["asserts"])
        falhas = [c for c in checks if not c[4]]
        status = "OK" if not falhas else f"{len(falhas)} falha(s)"
        print(f"  iter {i:2d}: {status:>11}  " + "  ".join(
            f"{c[0]}={c[1]}[{'ok' if c[4] else 'X'}]" for c in checks))
        if not falhas:
            print(f"  -> convergiu em {i} iteração(ões)")
            break
        novos = corretor.propor(params, medidas, spec["asserts"])
        if novos is None:
            print("  -> sem corretor capaz; PARA (aqui entraria a correção inteligente)")
            return False
        params = novos
    else:
        print("  -> estourou o limite de iterações")
        return False

    saida = os.path.join(AQUI, f"out_orq_{dom}.stl")
    driver.exportar_stl(artefato, saida)
    print(f"  exportou: {os.path.basename(saida)}")

    if render:
        print("  renderizando 4 vistas no Blender...")
        r = subprocess.run([BLENDER, "--background", "--python", RENDER_SCRIPT, "--", saida],
                           capture_output=True, text=True, timeout=300)
        ok = "LARP: FIM" in r.stdout
        print(f"  render: {'OK' if ok else 'FALHOU'}  -> prototype/views/{os.path.splitext(os.path.basename(saida))[0]}/")
    return True


# ===========================================================================
# DEMO — dois pedidos, dois domínios, mesma espinha
# ===========================================================================

SPEC_MECANICO = {
    "identidade": "bucha por volume-alvo",
    # sem 'dominio' explícito de propósito: a roteação acha pela palavra "bucha"
    "params": {"diametro_ext": 40.0, "diametro_furo": 10.0, "altura": 25.0},
    "asserts": [
        {"medida": "bbox_z", "alvo": 25.0, "tol": 0.3},
        {"medida": "volume", "alvo": math.pi * (20.0**2 - 11.65**2) * 25.0, "tol": 5.0},
        {"medida": "solido_valido", "alvo": 1.0, "tol": 0.0},
    ],
}

SPEC_ORGANICO = {
    "identidade": "blob (criatura simples)",
    "params": {"raio_corpo": 1.0, "raio_cabeca": 0.55, "pos_cabeca": [0.9, 0.0, 0.3],
               "membro_dentro": 0.3, "membro_fora": 1.3, "raio_membro": 0.22},
    "asserts": [
        {"medida": "watertight", "alvo": 1.0, "tol": 0.0},
        {"medida": "componentes", "alvo": 1.0, "tol": 0.0},
        {"medida": "euler", "alvo": 2.0, "tol": 0.0},
    ],
}


def main():
    print("LARPERIAN — orquestrador (uma espinha, dois domínios)")
    # mecânico: precisa do laço (corretor de bisseção no furo, mirando o volume)
    orquestrar(SPEC_MECANICO,
               CorretorBissecao(param="diametro_furo", medida="volume", lo=2.0, hi=38.0, decresce=True),
               render=True)
    # orgânico: já passa de primeira (sem corretor)
    orquestrar(SPEC_ORGANICO, CorretorNenhum(), render=True)


if __name__ == "__main__":
    main()
