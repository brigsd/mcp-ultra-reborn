"""
CORRETOR INTELIGENTE — pluga na MESMA interface dos corretores burros (propor()).

A "inteligência" vem de um CÉREBRO plugável:
  - brain_anthropic: chamada real a um modelo (autônomo) — precisa de ANTHROPIC_API_KEY + SDK.
  - brain_demo: substituto que carrega MEU raciocínio pra um defeito estrutural específico,
    pra rodar aqui sem chave. NÃO é geral — só prova a fiação e o tipo de conserto.

Diferença pro corretor burro (bisseção): aquele só mexe 1 parâmetro por 1 medida monotônica.
Este recebe o defeito inteiro (quais asserts falharam, por quanto, e os params) e pode mexer
em VÁRIOS parâmetros raciocinando sobre a causa — ex: "peça em 2 pedaços => membro descolou".
"""

import json
import os


def _passa(a, medidas):
    m = medidas.get(a["medida"])
    return m is not None and abs(m - a["alvo"]) <= a.get("tol", 0)


class CorretorInteligente:
    def __init__(self, brain, label="LLM"):
        self.brain = brain
        self.label = label

    def propor(self, params, medidas, asserts):
        falhas = [a for a in asserts if not _passa(a, medidas)]
        contexto = {
            "params_atuais": dict(params),
            "medidas": dict(medidas),
            "asserts_falhos": [
                {"medida": a["medida"], "alvo": a["alvo"], "tol": a.get("tol", 0),
                 "medido": medidas.get(a["medida"])}
                for a in falhas
            ],
        }
        return self.brain(contexto, params)


# ---------------------------------------------------------------------------
# CÉREBRO real (autônomo) — precisa de chave + `pip install anthropic`
# ---------------------------------------------------------------------------
def brain_anthropic(contexto, params, model="claude-sonnet-4-6"):
    import anthropic
    client = anthropic.Anthropic()  # lê ANTHROPIC_API_KEY do ambiente
    prompt = (
        "Você corrige parâmetros de um gerador 3D procedural. A peça falhou na verificação.\n"
        f"Parâmetros atuais: {json.dumps(params)}\n"
        f"Medidas obtidas: {json.dumps(contexto['medidas'])}\n"
        f"Asserções que FALHARAM (medida/alvo/medido): {json.dumps(contexto['asserts_falhos'])}\n\n"
        "Raciocine sobre a CAUSA do defeito e devolva SÓ um JSON com os parâmetros corrigidos "
        "(mesmas chaves dos atuais, valores novos). Sem texto fora do JSON."
    )
    msg = client.messages.create(
        model=model, max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    txt = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    ini, fim = txt.find("{"), txt.rfind("}")
    return json.loads(txt[ini:fim + 1]) if ini >= 0 else None


# ---------------------------------------------------------------------------
# CÉREBRO substituto (roda aqui sem chave) — encoda meu raciocínio p/ "peça partida"
# ---------------------------------------------------------------------------
def brain_demo(contexto, params):
    falhas = {f["medida"] for f in contexto["asserts_falhos"]}
    medidas = contexto["medidas"]
    novos = dict(params)

    # Defeito: peça saiu em N>1 componentes. Num blob, isso acontece quando o
    # membro descola — a ponta de dentro dele (membro_dentro) ficou FORA do corpo.
    # Conserto raciocinado: puxar a ponta pra dentro do corpo + engrossar pra garantir sobreposição.
    if "componentes" in falhas and medidas.get("componentes", 1) > 1:
        if "membro_dentro" in novos and "raio_corpo" in novos:
            novos["membro_dentro"] = round(novos["raio_corpo"] * 0.4, 3)
            if "raio_membro" in novos:
                novos["raio_membro"] = round(novos["raio_membro"] * 1.2, 3)
            return novos
    return None  # não soube corrigir este defeito (cérebro real generalizaria)


def cerebro_padrao():
    """Escolhe o cérebro disponível: real se houver chave, senão o substituto."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            import anthropic  # noqa
            return brain_anthropic, "anthropic(API)"
        except ImportError:
            pass
    return brain_demo, "demo(substituto)"
