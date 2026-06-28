"""
Mostra a verificação de FUROS por topologia (gênero), que os asserts de bbox/volume não pegavam.
Antes: flange com 3 furos em vez de 6 passava. Agora a contagem é provada por Euler.

Rodar:  .venv/Scripts/python.exe prototype/demo_verifica_furos.py
"""

import os
import sys
import copy

AQUI = os.path.dirname(os.path.abspath(__file__))
if AQUI not in sys.path:
    sys.path.insert(0, AQUI)

from entrada import normalizar
from orchestrator import orquestrar, CorretorNenhum


def main():
    spec, _, _ = normalizar("um flange de diametro 90, espessura 12 com 6 furos")

    print("########## 1) flange CERTO — furos conferidos por topologia ##########")
    orquestrar(copy.deepcopy(spec), CorretorNenhum(), render=False)

    print("\n########## 2) flange DEFEITUOSO — gerador faz 5, encomenda pede 6 ##########")
    spec_def = copy.deepcopy(spec)
    spec_def["params"]["n_furos"] = 5         # o gerador vai produzir 5 furos...
    # ...mas os asserts (montados pra 6) continuam pedindo 6 -> tem que PEGAR
    orquestrar(spec_def, CorretorNenhum(), render=False)


if __name__ == "__main__":
    main()
