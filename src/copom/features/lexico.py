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
LEXICO_VERSAO = "1.2.0"
# Changelog v1.2.0 (revisão do critério de aceite da issue "lexico-viés-
# historico", review do mentor):
#
#   O critério original (mode-share < 30%) não discriminava nada — passava
#   3,6% antes e 2,4% depois da v1.1.0, com folga de 10x. Não testava o que
#   a mudança de fato mudou.
#
#   Gate proposto pelo mentor: termo reprova se aparecer em 40%-60% dos
#   documentos hawkish (split quase empatado = sem direção). Rodado com
#   correção de leave-one-out (o termo não pode votar na própria classi-
#   ficação do documento que o julga — brecha de circularidade apontada
#   no review). Resultado: 13/33 termos reprovaram, incluindo os dovish
#   mais frequentes do léxico (redução, queda, moderação, desaceleração).
#
#   Investigação antes de remover (decisão por argumento linguístico/
#   estatístico, não por olhar mercado):
#     - Hipótese A (diluição estatística: termo comum dilui pra 50% no
#       leave-one-out): correlação frequência x distância-de-50% = -0,276
#       (fraca), refutada por contraexemplos (elevação e pressões, as
#       mais frequentes do léxico, continuam extremas, não diluem)
#     - Hipótese C (termos concentrados no parágrafo de balanço de riscos,
#       mesmo mecanismo já achado em incerteza/riscos/cautela): testado
#       contando ocorrências dentro vs. fora desse parágrafo — reprovados
#       (0-9%) e termos de controle (0,8-6%) não se separam. Refutada.
#     - Causa raiz encontrada: o corpus NÃO é 50/50 — é 66,3% dovish /
#       33,7% hawkish (n=83 atas com score != 0). O gate 40-60% comparava
#       contra um ponto de referência (50%) que não é o "neutro" real do
#       corpus. Um termo sem sinal deveria refletir a taxa base (66/34),
#       não 50/50; cair perto de 50% significa "mais fraco que a média",
#       não "sem sinal".
#
#   Gate corrigido: termo reprova se |pct_hawkish do termo − taxa base do
#   corpus| <= 10 pontos percentuais (em vez de comparar contra 50% fixo).
#   Reaplicado com leave-one-out: 14/33 termos reprovaram sob esse critério
#   corrigido — um conjunto bem diferente do gate ingênuo. Note que
#   redução/queda/desaceleração, que reprovariam no gate ingênuo, SOBRE-
#   VIVEM aqui — são mais dovish que a média do corpus, carregam sinal real.
#
#   Removidos (hawkish, 5): persistência, aperto, aceleração, pressão,
#   deterioração — todos a <=8pp da taxa base do corpus (sem sinal extra
#   além da média).
#   Removidos (dovish, 9): afrouxamento, convergência, estabilização,
#   normalização, ancoragem, acomodação, alívio, arrefecimento, moderação
#   — mesmo motivo.
#
#   Ressalva: "vigilância" sobrevive (100% hawkish, muito longe da base),
#   mas com apenas 1 ocorrência em 84 atas — amostra pequena demais pra
#   dar confiança à aprovação; mantido por ora, candidato a nova revisão
#   se seguir tão raro no restante do corpus (2016+).
#
#   Ver docs/features/validacao_lexico_2006_2016.md para a análise
#   completa (as 3 hipóteses testadas, a taxa base do corpus, código).
 
# Lista de palavras que indicam postura hawkish (preocupado, aperto)
PALAVRAS_HAWKISH = [
    "elevação",
    "alta",
    "pressões",
    "vigilância",
    "contracionista",
    "restritiva",
    "desancoragem",
    "persistente",
    "resiliente",
    "aquecimento",
]
 
# Lista de palavras que indicam postura dovish (tranquilo, afrouxamento)
PALAVRAS_DOVISH = [
    "redução",
    "queda",
    "desaceleração",
    "flexibilização",
    "recuo",
    "melhora",
    "benigno",
    "desinflação",
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
