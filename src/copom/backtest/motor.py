# CopomLens — Camada 5: motor de backtest orientado a evento no DI 1Y. Cada
# publicacao de ata e um trade que abre no fechamento anterior (D0) e fecha no
# fechamento do dia da publicacao; o P&L sai em bps de taxa capturada, liquido
# de custo de travessia. Convencao de posicao: +1 paga fixo (ganha com alta de
# taxa), -1 recebe fixo, 0 fora. O teste de permutacao se recusa a rodar sobre
# posicao constante, caso em que embaralhar retornos nao muda media nem desvio
# e o p-valor seria ruido numerico.
"""Motor de backtest evento-a-evento e metricas de risco/retorno."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

EVENTOS_POR_ANO_PADRAO = 8.0
CUSTO_BPS_PADRAO = 1.0


class BacktestInvalido(ValueError):
    """Entrada incompativel com a simulacao (tamanhos, custo ou posicao)."""


class PermutacaoDegenerada(ValueError):
    """Teste de permutacao pedido sobre posicao constante, onde ele nao informa nada."""


@dataclass(frozen=True)
class Resultado:
    """P&L por evento e metricas agregadas de uma estrategia."""

    pnl_bps: np.ndarray
    equity_bps: np.ndarray
    metricas: dict


def simular(
    posicoes: np.ndarray,
    reacao_bps: np.ndarray,
    custo_bps: float = CUSTO_BPS_PADRAO,
    eventos_por_ano: float = EVENTOS_POR_ANO_PADRAO,
) -> Resultado:
    """P&L liquido por evento: posicao x reacao, menos o custo de quem esta posicionado.

    O custo incide sobre |posicao|, entao evento sem posicao nao paga travessia.
    """
    posicoes = np.asarray(posicoes, dtype=float)
    reacao_bps = np.asarray(reacao_bps, dtype=float)
    if posicoes.shape != reacao_bps.shape:
        raise BacktestInvalido(f"posicoes {posicoes.shape} e reacao {reacao_bps.shape} têm tamanhos diferentes")
    if custo_bps < 0:
        raise BacktestInvalido(f"custo_bps={custo_bps} negativo seria subsidio, não custo")
    if eventos_por_ano <= 0:
        raise BacktestInvalido(f"eventos_por_ano={eventos_por_ano} precisa ser positivo")
    if np.isnan(posicoes).any() or np.isnan(reacao_bps).any():
        raise BacktestInvalido("NaN em posicoes ou reacao; resolva antes de simular")

    pnl = posicoes * reacao_bps - custo_bps * np.abs(posicoes)
    return Resultado(pnl_bps=pnl, equity_bps=np.cumsum(pnl), metricas=metricas(pnl, posicoes, eventos_por_ano))


def metricas(pnl_bps: np.ndarray, posicoes: np.ndarray, eventos_por_ano: float = EVENTOS_POR_ANO_PADRAO) -> dict:
    """Sharpe anualizado, drawdown maximo, hit rate e giro da estrategia."""
    pnl_bps = np.asarray(pnl_bps, dtype=float)
    if len(pnl_bps) < 2:
        raise BacktestInvalido("menos de 2 eventos: dispersao e Sharpe indefinidos")

    equity = np.cumsum(pnl_bps)
    pico = np.maximum.accumulate(np.concatenate([[0.0], equity]))[1:]
    desvio = float(np.std(pnl_bps, ddof=1))
    negociados = pnl_bps[np.asarray(posicoes, dtype=float) != 0]
    ganhos, perdas = pnl_bps[pnl_bps > 0], pnl_bps[pnl_bps < 0]

    return {
        "n_eventos": int(len(pnl_bps)),
        "n_trades": int(np.count_nonzero(posicoes)),
        "pnl_total_bps": round(float(equity[-1]), 1),
        "pnl_medio_bps": round(float(np.mean(pnl_bps)), 3),
        "desvio_bps": round(desvio, 2),
        "sharpe_anual": round(float(np.mean(pnl_bps) / desvio * np.sqrt(eventos_por_ano)), 3) if desvio > 1e-12 else 0.0,
        "max_drawdown_bps": round(float((equity - pico).min()), 1),
        "hit_rate": round(float((negociados > 0).mean()), 3) if len(negociados) else 0.0,
        "ganho_medio_bps": round(float(ganhos.mean()), 2) if len(ganhos) else 0.0,
        "perda_media_bps": round(float(perdas.mean()), 2) if len(perdas) else 0.0,
        "giro": round(float(np.mean(np.abs(posicoes))), 3),
    }


def permutacao_contra_acaso(
    posicoes: np.ndarray,
    reacao_bps: np.ndarray,
    custo_bps: float = CUSTO_BPS_PADRAO,
    eventos_por_ano: float = EVENTOS_POR_ANO_PADRAO,
    n_sorteios: int = 5000,
    seed: int = 20260811,
) -> dict:
    """Sharpe observado contra a nula de que a ordem dos retornos e irrelevante.

    Mantem as posicoes e embaralha os retornos. Se a posicao for constante, a
    media e o desvio do P&L nao mudam com a permutacao: o teste degenera e um
    p-valor ali seria artefato de ponto flutuante, nao evidencia. Nesse caso o
    metodo levanta PermutacaoDegenerada em vez de devolver numero enganoso.
    """
    posicoes = np.asarray(posicoes, dtype=float)
    reacao_bps = np.asarray(reacao_bps, dtype=float)
    nao_nulas = posicoes[posicoes != 0]
    if len(np.unique(nao_nulas)) < 2:
        raise PermutacaoDegenerada(
            "posicao constante entre os eventos negociados: permutar os retornos nao altera "
            "media nem desvio do P&L, e o teste nao distingue sinal de acaso"
        )

    observado = simular(posicoes, reacao_bps, custo_bps, eventos_por_ano).metricas["sharpe_anual"]
    rng = np.random.default_rng(seed)
    nulos = np.empty(n_sorteios)
    for i in range(n_sorteios):
        pnl = posicoes * rng.permutation(reacao_bps) - custo_bps * np.abs(posicoes)
        desvio = np.std(pnl, ddof=1)
        nulos[i] = np.mean(pnl) / desvio * np.sqrt(eventos_por_ano) if desvio > 1e-12 else 0.0

    return {
        "sharpe_observado": observado,
        "sharpe_nulo_media": round(float(np.mean(nulos)), 3),
        "sharpe_nulo_p95": round(float(np.percentile(nulos, 95)), 3),
        "p_valor_empirico": round(float((nulos >= observado).mean()), 4),
        "n_sorteios": n_sorteios,
    }


def sensibilidade_custo(
    posicoes: np.ndarray,
    reacao_bps: np.ndarray,
    custos_bps: tuple[float, ...] = (0.0, 0.5, 1.0, 2.0),
    eventos_por_ano: float = EVENTOS_POR_ANO_PADRAO,
) -> dict[str, float]:
    """Sharpe da mesma estrategia sob varios custos de travessia.

    Separa borda de execucao: se o Sharpe ja e nulo a custo zero, o custo nao e
    a explicacao do resultado — nao ha borda para ele consumir.
    """
    return {
        f"{c:g}": simular(posicoes, reacao_bps, c, eventos_por_ano).metricas["sharpe_anual"] for c in custos_bps
    }
