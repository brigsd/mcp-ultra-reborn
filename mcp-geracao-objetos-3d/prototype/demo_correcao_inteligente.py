"""
Demonstra a correção INTELIGENTE num defeito ESTRUTURAL que o corretor burro não resolve.

Defeito: blob com o membro solto -> a peça sai em 2 componentes (watertight não pega isso;
quem pega é a contagem de componentes). O corretor de bisseção não tem o que fazer (não é
relação 1D monotônica). O corretor inteligente raciocina sobre a causa e conserta.

Rodar:  .venv/Scripts/python.exe prototype/demo_correcao_inteligente.py
"""

import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
if AQUI not in sys.path:
    sys.path.insert(0, AQUI)

from orchestrator import orquestrar, CorretorNenhum
from corretor_inteligente import CorretorInteligente, cerebro_padrao

SPEC_DEFEITO = {
    "identidade": "blob com membro solto (defeito estrutural)",
    "dominio": "organico",
    "params": {"raio_corpo": 1.0, "raio_cabeca": 0.55, "pos_cabeca": [0.9, 0.0, 0.3],
               "membro_dentro": 1.6, "membro_fora": 2.4, "raio_membro": 0.18},  # ponta de dentro FORA do corpo
    "asserts": [
        {"medida": "componentes", "alvo": 1.0, "tol": 0.0},
        {"medida": "watertight", "alvo": 1.0, "tol": 0.0},
        {"medida": "euler", "alvo": 2.0, "tol": 0.0},
    ],
}


def main():
    print("########## 1) MESMO defeito, corretor BURRO (nenhum) ##########")
    orquestrar(dict(SPEC_DEFEITO), CorretorNenhum(), render=False)

    brain, nome = cerebro_padrao()
    print(f"\n########## 2) MESMO defeito, corretor INTELIGENTE — cérebro: {nome} ##########")
    orquestrar(dict(SPEC_DEFEITO), CorretorInteligente(brain), render=False)


if __name__ == "__main__":
    main()
