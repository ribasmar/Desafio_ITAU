# Backtest orientado a evento no DI 1Y: cada publicacao de ata e um trade que
# abre no fechamento anterior (D0) e fecha no fechamento do dia da publicacao.
# Convencao de posicao: +1 paga fixo (ganha se a taxa sobe), -1 recebe fixo.
# Todos os sinais sao point-in-time: previsoes vem da janela expansiva do
# walk-forward e as regras usam apenas o tom da propria ata, ja publica no
# momento da entrada. P&L em bps de taxa capturada, liquido de custo de
# travessia. Inclui teste de permutacao contra o acaso.
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[2] / "data" / "processed" / "analise"
CUSTO_BPS = 1.0
CUSTOS_CENARIO = [0.0, 0.5, 1.0, 2.0]
EVENTOS_POR_ANO = 8.0
SEED = 20260811


def metricas(pnl: np.ndarray, n_trades: int) -> dict:
    equity = np.cumsum(pnl)
    pico = np.maximum.accumulate(np.concatenate([[0.0], equity]))[1:]
    dd = equity - pico
    dp = float(np.std(pnl, ddof=1))
    sharpe = float(np.mean(pnl) / dp * np.sqrt(EVENTOS_POR_ANO)) if dp > 1e-12 else 0.0
    ganhos = pnl[pnl > 0]
    perdas = pnl[pnl < 0]
    return {
        "n_trades": int(n_trades),
        "pnl_total_bps": round(float(equity[-1]), 1),
        "pnl_medio_bps": round(float(np.mean(pnl)), 3),
        "dp_bps": round(dp, 2),
        "sharpe_anual": round(sharpe, 3),
        "max_drawdown_bps": round(float(dd.min()), 1),
        "hit_rate": round(float((pnl > 0).mean()), 3),
        "ganho_medio_bps": round(float(ganhos.mean()), 2) if len(ganhos) else 0.0,
        "perda_media_bps": round(float(perdas.mean()), 2) if len(perdas) else 0.0,
    }


def permutacao(pnl_bruto_unit: np.ndarray, posicoes: np.ndarray, custo: float, n: int = 5000) -> dict:
    """Sharpe sob H0: mesmas posicoes, ordem dos retornos embaralhada."""
    rng = np.random.default_rng(SEED)
    obs = metricas(posicoes * pnl_bruto_unit - custo * np.abs(posicoes), int(np.sum(posicoes != 0)))["sharpe_anual"]
    nulos = np.empty(n)
    for i in range(n):
        emb = rng.permutation(pnl_bruto_unit)
        p = posicoes * emb - custo * np.abs(posicoes)
        dp = np.std(p, ddof=1)
        nulos[i] = np.mean(p) / dp * np.sqrt(EVENTOS_POR_ANO) if dp > 1e-12 else 0.0
    return {
        "sharpe_observado": obs,
        "sharpe_nulo_media": round(float(np.mean(nulos)), 3),
        "sharpe_nulo_p95": round(float(np.percentile(nulos, 95)), 3),
        "p_valor_empirico": round(float((nulos >= obs).mean()), 4),
    }


def main() -> None:
    df = pd.read_csv(OUT / "painel_com_tom.csv", parse_dates=["data_publicacao_ata"])
    df = df.sort_values("data_publicacao_ata").reset_index(drop=True)
    df["lex_delta"] = df["lex_score"].diff()

    prev = pd.read_csv(OUT / "previsoes_walkforward.csv", parse_dates=["data_publicacao_ata"])
    df = df.merge(prev, on="data_publicacao_ata", validate="one_to_one")

    oos = df[df["M2_surpresa_tom"].notna()].reset_index(drop=True)
    r = oos["reacao_bps"].to_numpy(float)

    sinais = {
        "S1_previsao_so_surpresa": np.sign(oos["M1_surpresa"].to_numpy(float)),
        "S2_previsao_surpresa_e_tom": np.sign(oos["M2_surpresa_tom"].to_numpy(float)),
        "S3_regra_delta_tom": np.sign(oos["lex_delta"].fillna(0.0).to_numpy(float)),
        "S4_regra_nivel_tom": np.sign(oos["lex_score"].to_numpy(float)),
        "B1_sempre_recebe_fixo": np.full(len(oos), -1.0),
    }

    resultados = {}
    for nome, pos in sinais.items():
        pnl = pos * r - CUSTO_BPS * np.abs(pos)
        res = metricas(pnl, int(np.sum(pos != 0)))
        res["por_custo_bps"] = {
            str(c): metricas(pos * r - c * np.abs(pos), int(np.sum(pos != 0)))["sharpe_anual"] for c in CUSTOS_CENARIO
        }
        res["permutacao"] = permutacao(r, pos, CUSTO_BPS)
        resultados[nome] = res

    resumo = {
        "convencao": "+1 paga fixo (ganha com alta de taxa); -1 recebe fixo. P&L em bps de taxa capturada.",
        "custo_travessia_bps": CUSTO_BPS,
        "janela_oos": [str(oos["data_publicacao_ata"].min().date()), str(oos["data_publicacao_ata"].max().date())],
        "n_eventos_oos": int(len(oos)),
        "eventos_por_ano": EVENTOS_POR_ANO,
        "estrategias": resultados,
    }
    (OUT / "backtest.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False), encoding="utf-8")

    curvas = pd.DataFrame({"data": oos["data_publicacao_ata"]})
    for nome, pos in sinais.items():
        curvas[nome] = np.cumsum(pos * r - CUSTO_BPS * np.abs(pos))
    curvas.to_csv(OUT / "curvas_equity.csv", index=False)

    print(f"OOS: {resumo['janela_oos'][0]} a {resumo['janela_oos'][1]} | {len(oos)} eventos | custo {CUSTO_BPS} bp\n")
    cab = f"{'estrategia':30s} {'trades':>7s} {'P&L bps':>9s} {'Sharpe':>8s} {'MaxDD':>8s} {'hit':>6s} {'p-perm':>8s}"
    print(cab)
    print("-" * len(cab))
    for nome, res in resultados.items():
        print(f"{nome:30s} {res['n_trades']:7d} {res['pnl_total_bps']:9.1f} {res['sharpe_anual']:8.3f} "
              f"{res['max_drawdown_bps']:8.1f} {res['hit_rate']:6.3f} {res['permutacao']['p_valor_empirico']:8.4f}")


if __name__ == "__main__":
    main()
