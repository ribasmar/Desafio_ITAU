# CopomLens — Camada 4: transforma o painel de eventos em previsoes e posicoes.
# A previsao e sempre walk-forward de janela expansiva (refit a cada evento,
# treino so com eventos anteriores), e cada regra de posicao usa apenas features
# ja publicas no instante da entrada. O ganho incremental entre modelos
# aninhados e medido por Clark-West, que corrige o vies de MSPE do modelo amplo.
"""Geracao de sinal: previsao walk-forward e regras de posicao point-in-time."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

COLUNA_ALVO = "reacao_bps"
COLUNA_DATA = "data_publicacao_ata"
TREINO_MINIMO_PADRAO = 40

ESPECIFICACOES: dict[str, list[str]] = {
    "M0_media": [],
    "M1_surpresa": ["surpresa_decisao"],
    "M2_surpresa_tom": ["surpresa_decisao", "lex_score", "lex_delta"],
}


class PainelInvalido(ValueError):
    """Painel sem as colunas exigidas ou com ordenacao/valores inconsistentes."""


@dataclass(frozen=True)
class ResultadoAninhado:
    """Saida da comparacao aninhada de um painel."""

    amostra: str
    n_total: int
    n_oos: int
    previsoes: dict[str, np.ndarray] = field(repr=False)
    metricas: dict[str, dict] = field(default_factory=dict)
    clark_west: dict[str, dict] = field(default_factory=dict)


def validar_painel(painel: pd.DataFrame, colunas: list[str]) -> None:
    """Falha alto se faltar coluna, houver NaN em feature ou a ordem estiver errada.

    Um painel desordenado quebraria silenciosamente a janela expansiva: o treino
    passaria a conter eventos posteriores ao previsto. Por isso a ordenacao e
    verificada, nao assumida.
    """
    exigidas = [COLUNA_DATA, COLUNA_ALVO, *colunas]
    faltando = [c for c in exigidas if c not in painel.columns]
    if faltando:
        raise PainelInvalido(f"colunas ausentes no painel: {faltando}")
    if not painel[COLUNA_DATA].is_monotonic_increasing:
        raise PainelInvalido(f"painel precisa estar ordenado por {COLUNA_DATA} crescente")
    if painel[COLUNA_DATA].duplicated().any():
        dup = painel.loc[painel[COLUNA_DATA].duplicated(), COLUNA_DATA].tolist()
        raise PainelInvalido(f"mais de um evento na mesma data: {dup}")
    for c in [COLUNA_ALVO, *colunas]:
        if painel[c].isna().any():
            raise PainelInvalido(f"coluna {c!r} tem NaN; trate antes de estimar")


def _ajustar(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    Xc = np.column_stack([np.ones(len(y)), X]) if X.size else np.ones((len(y), 1))
    beta, *_ = np.linalg.lstsq(Xc, y, rcond=None)
    return beta


def _prever(beta: np.ndarray, x: np.ndarray) -> float:
    xc = np.concatenate([[1.0], x]) if x.size else np.array([1.0])
    return float(xc @ beta)


def prever_walk_forward(
    painel: pd.DataFrame,
    colunas: list[str],
    treino_minimo: int = TREINO_MINIMO_PADRAO,
) -> np.ndarray:
    """Previsao de janela expansiva: o evento t so ve os eventos [0, t).

    Retorna vetor do tamanho do painel, com NaN nos primeiros `treino_minimo`
    eventos, que servem apenas de treino e nao produzem previsao avaliavel.
    """
    validar_painel(painel, colunas)
    if treino_minimo < len(colunas) + 2:
        raise PainelInvalido(
            f"treino_minimo={treino_minimo} e pequeno demais para {len(colunas)} features; "
            f"use ao menos {len(colunas) + 2} para o ajuste ter graus de liberdade"
        )
    if len(painel) <= treino_minimo:
        raise PainelInvalido(f"painel com {len(painel)} eventos nao excede treino_minimo={treino_minimo}")

    y = painel[COLUNA_ALVO].to_numpy(float)
    X = painel[colunas].to_numpy(float) if colunas else np.empty((len(painel), 0))
    previsoes = np.full(len(painel), np.nan)
    for t in range(treino_minimo, len(painel)):
        previsoes[t] = _prever(_ajustar(X[:t], y[:t]), X[t])
    return previsoes


def cauda_superior_normal(z: float) -> float:
    """P(Z > z) para a normal padrao, pela funcao de erro complementar da stdlib.

    Usa `erfc` em vez de `1 - cdf`: a subtracao perde toda a precisao na cauda
    direita por cancelamento — em z = 8,5 ela devolve exatamente 0, enquanto a
    `erfc` entrega 9,5e-18. Como o Clark-West e unicaudal a direita, e
    exatamente essa a regiao que interessa. De quebra, dispensa o scipy.
    """
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def clark_west(y: np.ndarray, previsao_restrita: np.ndarray, previsao_ampla: np.ndarray) -> dict:
    """Ganho preditivo out-of-sample entre modelos aninhados (Clark & West, 2007).

    Comparar MSPE direto penaliza o modelo amplo mesmo quando ele e o correto,
    porque ele estima parametros a mais que sob a hipotese nula valem zero. O
    ajuste `(restrita - ampla)^2` remove esse vies. Media de f > 0 indica ganho.
    """
    if not (len(y) == len(previsao_restrita) == len(previsao_ampla)):
        raise ValueError("vetores de tamanhos diferentes")
    if len(y) < 3:
        raise ValueError("amostra out-of-sample pequena demais para o teste")

    f = (y - previsao_restrita) ** 2 - ((y - previsao_ampla) ** 2 - (previsao_restrita - previsao_ampla) ** 2)
    erro_padrao = float(np.std(f, ddof=1) / np.sqrt(len(f)))
    if erro_padrao <= 0.0:
        return {"cw_stat": 0.0, "p_valor_unicaudal": 0.5, "n_oos": len(f), "degenerado": True}

    estatistica = float(np.mean(f) / erro_padrao)
    return {
        "cw_stat": round(estatistica, 3),
        "p_valor_unicaudal": round(cauda_superior_normal(estatistica), 4),
        "n_oos": len(f),
        "degenerado": False,
    }


def metricas_previsao(y: np.ndarray, previsao: np.ndarray, referencia: np.ndarray) -> dict:
    """RMSE, MAE e R2 out-of-sample contra a referencia (a media expandida)."""
    sse_ref = float(np.sum((y - referencia) ** 2))
    return {
        "rmse": round(float(np.sqrt(np.mean((y - previsao) ** 2))), 3),
        "mae": round(float(np.mean(np.abs(y - previsao))), 3),
        "r2_oos": round(1 - float(np.sum((y - previsao) ** 2)) / sse_ref, 4) if sse_ref > 0 else float("nan"),
        "corr_previsto_real": (
            round(float(np.corrcoef(previsao, y)[0, 1]), 4) if np.std(previsao) > 1e-12 else 0.0
        ),
    }


def comparar_aninhados(
    painel: pd.DataFrame,
    especificacoes: dict[str, list[str]] | None = None,
    treino_minimo: int = TREINO_MINIMO_PADRAO,
    rotulo: str = "painel",
) -> ResultadoAninhado:
    """Roda M0/M1/M2 no mesmo painel e mede o ganho de cada camada sobre a anterior."""
    especificacoes = especificacoes or ESPECIFICACOES
    nomes = list(especificacoes)
    previsoes = {n: prever_walk_forward(painel, c, treino_minimo) for n, c in especificacoes.items()}

    mascara = ~np.isnan(previsoes[nomes[-1]])
    y = painel[COLUNA_ALVO].to_numpy(float)[mascara]
    referencia = previsoes[nomes[0]][mascara]

    return ResultadoAninhado(
        amostra=rotulo,
        n_total=len(painel),
        n_oos=int(mascara.sum()),
        previsoes=previsoes,
        metricas={n: metricas_previsao(y, p[mascara], referencia) for n, p in previsoes.items()},
        clark_west={
            f"{amplo}_sobre_{restrito}": clark_west(y, previsoes[restrito][mascara], previsoes[amplo][mascara])
            for restrito, amplo in zip(nomes, nomes[1:])
        },
    )


def sinal_da_previsao(previsao: np.ndarray) -> np.ndarray:
    """Posicao pelo sinal da previsao: +1 paga fixo, -1 recebe fixo, 0 fora.

    NaN vira 0 — sem previsao, sem posicao. Nunca herda a posicao anterior, o
    que introduziria memoria nao declarada no backtest.
    """
    return np.nan_to_num(np.sign(previsao), nan=0.0)


def sinal_da_regra(coluna: pd.Series) -> np.ndarray:
    """Posicao pelo sinal de uma feature ja publica no instante da entrada."""
    return np.nan_to_num(np.sign(coluna.to_numpy(float)), nan=0.0)
