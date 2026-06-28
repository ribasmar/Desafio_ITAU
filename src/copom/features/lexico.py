# Módulo do baseline léxico hawkish/dovish
# Task #5 — Elder Nunes — Sprint 0

# Lista de palavras que indicam postura hawkish (preocupado, aperto)
PALAVRAS_HAWKISH = [
    "elevação",
    "alta",
    "pressão",
    "pressões",
    "vigilância",
    "deterioração",
    "aceleração",
    "aperto",
    "contracionista",
    "restritiva",
    "cautela",
    "cauteloso",
    "incerteza",
    "riscos",
    "desancoragem",
    "persistência",
    "persistente",
    "resiliente",
    "aquecimento",
    "desequilíbrio",
]

# Lista de palavras que indicam postura dovish (tranquilo, afrouxamento)
PALAVRAS_DOVISH = [
    "redução",
    "queda",
    "moderação",
    "arrefecimento",
    "convergência",
    "flexibilização",
    "afrouxamento",
    "acomodação",
    "desaceleração",
    "recuo",
    "melhora",
    "benigno",
    "estabilização",
    "ancoragem",
    "desinflação",
    "benignidade",
    "normalização",
    "alívio",
    "cedendo",
    "recuando",
]

def calcular_lexico(texto: str) -> dict:
    """
    Recebe o texto de uma ata do Copom e retorna
    um score hawkish/dovish por contagem de palavras.

    Parâmetros:
        texto: string com o conteúdo da ata

    Retorna:
        dicionário com score, contagens e palavras encontradas
    """

    texto_lower = texto.lower()

    encontradas_hawkish = [
        palavra for palavra in PALAVRAS_HAWKISH
        if palavra in texto_lower
    ]

    encontradas_dovish = [
        palavra for palavra in PALAVRAS_DOVISH
        if palavra in texto_lower
    ]

    n_hawkish = len(encontradas_hawkish)
    n_dovish  = len(encontradas_dovish)
    total     = n_hawkish + n_dovish

    if total == 0:
        score = 0.0
    else:
        score = (n_hawkish - n_dovish) / total

    return {
        "score":               round(score, 4),
        "n_hawkish":           n_hawkish,
        "n_dovish":            n_dovish,
        "palavras_hawkish":    encontradas_hawkish,
        "palavras_dovish":     encontradas_dovish,
    }