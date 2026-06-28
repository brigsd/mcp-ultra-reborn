"""
Catálogo de dimensões reais de componentes mecânicos — em metros.
A IA consulta aqui antes de definir qualquer medida para garantir proporções realistas.

Uso:
    from catalog.dimensions import DISCO_FREIO, ROLAMENTO
    raio = DISCO_FREIO["compacto"]["raio_ext"]
"""

# ---------------------------------------------------------------------------
# Discos de freio (veículos de passeio)
# ---------------------------------------------------------------------------
DISCO_FREIO = {
    "compacto": {           # Hatch/Sedan pequeno (Golf, Civic...)
        "raio_ext": 0.140,  # 280mm diâmetro
        "raio_int": 0.065,  # furo central ~130mm
        "espessura": 0.022,
        "espessura_minima": 0.019,
        "raio_orbital_furos": 0.110,
        "qtd_furos": 5,
        "raio_furo_ventilacao": 0.009,
        "qtd_furos_ventilacao": 6,
    },
    "medio": {              # SUV/Sedã médio
        "raio_ext": 0.160,
        "raio_int": 0.075,
        "espessura": 0.026,
        "espessura_minima": 0.023,
        "raio_orbital_furos": 0.120,
        "qtd_furos": 5,
        "raio_furo_ventilacao": 0.010,
        "qtd_furos_ventilacao": 8,
    },
    "esportivo": {          # Esportivo/GT
        "raio_ext": 0.185,
        "raio_int": 0.080,
        "espessura": 0.032,
        "espessura_minima": 0.028,
        "raio_orbital_furos": 0.130,
        "qtd_furos": 5,
        "raio_furo_ventilacao": 0.012,
        "qtd_furos_ventilacao": 10,
    },
}

# ---------------------------------------------------------------------------
# Pinças de freio
# ---------------------------------------------------------------------------
PINCA_FREIO = {
    "simples_2_pistoes": {
        "largura": 0.130,
        "altura": 0.080,
        "profundidade": 0.060,
        "diametro_pistao": 0.040,
        "espessura_parede": 0.012,
    },
    "esportiva_4_pistoes": {
        "largura": 0.180,
        "altura": 0.095,
        "profundidade": 0.075,
        "diametro_pistao_frontal": 0.038,
        "diametro_pistao_traseiro": 0.034,
        "espessura_parede": 0.014,
    },
    "monobloco_6_pistoes": {
        "largura": 0.220,
        "altura": 0.110,
        "profundidade": 0.090,
        "diametro_pistao": 0.032,
        "espessura_parede": 0.016,
    },
}

# ---------------------------------------------------------------------------
# Rolamentos (ISO/DIN)
# ---------------------------------------------------------------------------
ROLAMENTO = {
    "6204": {"d_int": 0.020, "d_ext": 0.047, "largura": 0.014},
    "6205": {"d_int": 0.025, "d_ext": 0.052, "largura": 0.015},
    "6206": {"d_int": 0.030, "d_ext": 0.062, "largura": 0.016},
    "6305": {"d_int": 0.025, "d_ext": 0.062, "largura": 0.017},
    "6306": {"d_int": 0.030, "d_ext": 0.072, "largura": 0.019},
    "6308": {"d_int": 0.040, "d_ext": 0.090, "largura": 0.023},
}

# ---------------------------------------------------------------------------
# Parafusos métricas (ISO)
# ---------------------------------------------------------------------------
PARAFUSO_METRICO = {
    "M6":  {"diametro": 0.006, "passo": 0.001,   "chave_sext": 0.010, "altura_cabeca": 0.004},
    "M8":  {"diametro": 0.008, "passo": 0.00125,  "chave_sext": 0.013, "altura_cabeca": 0.0055},
    "M10": {"diametro": 0.010, "passo": 0.0015,   "chave_sext": 0.017, "altura_cabeca": 0.007},
    "M12": {"diametro": 0.012, "passo": 0.00175,  "chave_sext": 0.019, "altura_cabeca": 0.008},
    "M14": {"diametro": 0.014, "passo": 0.002,    "chave_sext": 0.022, "altura_cabeca": 0.009},
}

# ---------------------------------------------------------------------------
# Rodas (aro de alumínio)
# ---------------------------------------------------------------------------
ARO_RODA = {
    '15"': {
        "diametro_aro": 0.381,
        "largura_tipica": 0.185,
        "raio_bolt_circle": 0.057,  # 4x100 PCD ~= raio 57mm
        "diametro_furo_central": 0.057,
    },
    '17"': {
        "diametro_aro": 0.432,
        "largura_tipica": 0.215,
        "raio_bolt_circle": 0.057,
        "diametro_furo_central": 0.057,
    },
    '18"': {
        "diametro_aro": 0.457,
        "largura_tipica": 0.225,
        "raio_bolt_circle": 0.060,
        "diametro_furo_central": 0.060,
    },
    '20"': {
        "diametro_aro": 0.508,
        "largura_tipica": 0.245,
        "raio_bolt_circle": 0.060,
        "diametro_furo_central": 0.065,
    },
}

# ---------------------------------------------------------------------------
# Molas helicoidais (suspensão)
# ---------------------------------------------------------------------------
MOLA_HELICOIDAL = {
    "dianteira_compacto": {
        "raio_arame": 0.007,
        "raio_mola": 0.038,
        "altura_livre": 0.320,
        "num_espiras": 8,
    },
    "traseira_compacto": {
        "raio_arame": 0.006,
        "raio_mola": 0.032,
        "altura_livre": 0.280,
        "num_espiras": 7,
    },
}
