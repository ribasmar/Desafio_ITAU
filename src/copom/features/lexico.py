# CopomLens — Camada 2: baseline léxico hawkish/dovish. Conta as ocorrências de
# termos do léxico (palavra inteira, sem distinção de maiúsculas) no texto de
# uma ata/comunicado do Copom e produz um score de tom em [-1, +1]:
#   score = (ocorrências hawkish − ocorrências dovish) / (total de ocorrências)
# comparável ao score do LLM. Task #5 — Elder Nunes — Sprint 0.
"""Baseline léxico de tom (hawkish/dovish) por contagem de ocorrências."""
from __future__ import annotations

import re

# Versao do lexico: rastreia qual lista de termos gerou cada score salvo.
# Incrementar sempre que PALAVRAS_HAWKISH/PALAVRAS_DOVISH mudarem.
LEXICO_VERSAO = "1.1.0"
# Changelog v1.1.0 (validação histórica 2006-2016, issue Camada 2 + relatório):
#   Removidos por serem direcionalmente ambíguos (~50/50 entre docs hawkish e
#   dovish em 84 atas 2006-2016 — indicam que o tema "incerteza/risco" está
#   sendo discutido, não pra qual lado a política vai):
#     - "incerteza" (59% hawkish / 41% dovish em 56 docs)
#     - "riscos" (49% hawkish / 51% dovish em 83 docs)
#     - "cautela" e "cauteloso" (43% hawkish / 57% dovish em 7 docs)
#   Removidos por zero ocorrências em 84 atas 2006-2016 e serem redundantes
#   com sinônimo já presente na lista:
#     - "desequilíbrio" (zero também em 2025-2026; sem substituto na lista)
#     - "benignidade" (zero; "benigno" já cobre a mesma ideia, 134 ocorrências)
#     - "cedendo" (zero; "recuando" já cobre a mesma ideia, 60 ocorrências)
#   Mantidos apesar de zero em 2006-2016 (vocabulário mais recente do Copom,
#   confirmado presente nas atas de 2025-2026 — não são termos "quebrados",
#   são deriva de vocabulário ao longo do tempo):
#     - "desancoragem", "resiliente"
 
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
    "desancoragem",
    "persistência",
    "persistente",
    "resiliente",
    "aquecimento",
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
    "normalização",
    "alívio",
    "recuando",
]


def _contar_ocorrencias(texto: str, termos: list[str]) -> dict[str, int]:
    """Ocorrências de cada termo como palavra inteira (case-insensitive).

    Usa fronteira de palavra (\\b) para evitar falsos positivos por substring
    (ex.: 'alta' dentro de 'exaltada'). Termos ausentes ficam fora do dict.
    """
    contagens: dict[str, int] = {}
    for termo in termos:
        n = len(re.findall(rf"\b{re.escape(termo)}\b", texto, flags=re.IGNORECASE))
        if n:
            contagens[termo] = n
    return contagens


def calcular_lexico(texto: str) -> dict:
    """Score de tom hawkish/dovish de uma ata do Copom por contagem de termos.

    Parametros:
        texto: string com o conteudo da ata/comunicado.

    Retorna dict com:
        score: (hawkish − dovish) / total, em [-1, +1]; 0.0 se nenhum termo.
        n_hawkish / n_dovish: total de OCORRENCIAS (nao termos distintos).
        palavras_hawkish / palavras_dovish: {termo: ocorrencias} encontrados.
        versao_lexico: versao da lista de termos usada.
    """
    contagens_hawkish = _contar_ocorrencias(texto, PALAVRAS_HAWKISH)
    contagens_dovish = _contar_ocorrencias(texto, PALAVRAS_DOVISH)

    n_hawkish = sum(contagens_hawkish.values())
    n_dovish = sum(contagens_dovish.values())
    total = n_hawkish + n_dovish

    score = 0.0 if total == 0 else (n_hawkish - n_dovish) / total

    return {
        "score": round(score, 4),
        "n_hawkish": n_hawkish,
        "n_dovish": n_dovish,
        "palavras_hawkish": contagens_hawkish,
        "palavras_dovish": contagens_dovish,
        "versao_lexico": LEXICO_VERSAO,
    }


def _demo() -> None:
    """Demo de aceite: roda o lexico na ata mais recente de data/raw/."""
    from pathlib import Path

    raw = Path(__file__).resolve().parents[3] / "data" / "raw"
    atas = sorted(raw.glob("ata_*.txt"))
    if not atas:
        print(f"Nenhuma ata em {raw} (rode a ingestao primeiro).")
        return

    texto = atas[-1].read_text(encoding="utf-8")
    r = calcular_lexico(texto)
    print(f"=== CopomLens — Baseline Léxico v{r['versao_lexico']} — {atas[-1].name} ===")
    print(f"Score:   {r['score']:+.4f}")
    print(f"Hawkish: {r['n_hawkish']} ocorrências → {r['palavras_hawkish']}")
    print(f"Dovish:  {r['n_dovish']} ocorrências → {r['palavras_dovish']}")


if __name__ == "__main__":
    _demo()
