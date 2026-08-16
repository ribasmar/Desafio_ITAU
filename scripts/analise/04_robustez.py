# Verificacoes que sustentam a leitura dos resultados: (a) o dia de publicacao
# da ata e estatisticamente diferente de um dia qualquer para o DI 1Y?
# (b) o backtest sobrevive na subamostra homogenea de 84? (c) o teste de
# permutacao e valido para cada sinal (degenera quando a posicao e constante).
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

BASE = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parents[2] / "data" / "processed" / "analise"
EVENTOS_POR_ANO = 8.0
CUSTO_BPS = 1.0


def evento_vs_dia_qualquer() -> dict:
    di = pd.read_csv(BASE / "data/raw/di1y_7806.csv")
    col_data = [c for c in di.columns if "data" in c.lower()][0]
    col_val = [c for c in di.columns if c != col_data][0]
    di[col_data] = pd.to_datetime(di[col_data], format="%Y-%m-%d")
    di = di.sort_values(col_data).reset_index(drop=True)
    di["var_bps"] = di[col_val].diff() * 100.0

    painel = pd.read_csv(OUT / "painel_com_tom.csv", parse_dates=["data_publicacao_ata"])
    dias_ata = set(painel["data_publicacao_ata"])

    janela = di[(di[col_data] >= painel["data_publicacao_ata"].min()) & (di[col_data] <= painel["data_publicacao_ata"].max())].dropna(subset=["var_bps"])
    ev = janela[janela[col_data].isin(dias_ata)]["var_bps"].to_numpy()
    nao_ev = janela[~janela[col_data].isin(dias_ata)]["var_bps"].to_numpy()

    lev = stats.levene(np.abs(ev), np.abs(nao_ev))
    mw = stats.mannwhitneyu(np.abs(ev), np.abs(nao_ev), alternative="greater")
    return {
        "n_dias_ata": int(len(ev)),
        "n_dias_normais": int(len(nao_ev)),
        "abs_var_media_dia_ata_bps": round(float(np.mean(np.abs(ev))), 2),
        "abs_var_media_dia_normal_bps": round(float(np.mean(np.abs(nao_ev))), 2),
        "dp_dia_ata_bps": round(float(np.std(ev, ddof=1)), 2),
        "dp_dia_normal_bps": round(float(np.std(nao_ev, ddof=1)), 2),
        "razao_volatilidade": round(float(np.std(ev, ddof=1) / np.std(nao_ev, ddof=1)), 3),
        "levene_p": round(float(lev.pvalue), 4),
        "mannwhitney_p_ata_maior": round(float(mw.pvalue), 4),
        "leitura": "dia de ata NAO e mais volatil que um dia qualquer" if mw.pvalue > 0.05 else "dia de ata e mais volatil",
    }


def backtest_subamostra() -> dict:
    df = pd.read_csv(OUT / "painel_com_tom.csv", parse_dates=["data_publicacao_ata"]).sort_values("data_publicacao_ata").reset_index(drop=True)
    df["lex_delta"] = df["lex_score"].diff()
    saida = {}
    for rotulo, sub in [("painel_110", df), ("subamostra_84", df[df["fonte_texto"] == "api_html"])]:
        sub = sub.reset_index(drop=True)
        corte = 40
        if len(sub) <= corte + 5:
            continue
        oos = sub.iloc[corte:].reset_index(drop=True)
        r = oos["reacao_bps"].to_numpy(float)
        pos = np.sign(oos["lex_delta"].fillna(0.0).to_numpy(float))
        bruto = pos * r
        liq = bruto - CUSTO_BPS * np.abs(pos)
        saida[rotulo] = {
            "n_oos": int(len(oos)),
            "pnl_bruto_bps": round(float(bruto.sum()), 1),
            "pnl_liquido_bps": round(float(liq.sum()), 1),
            "sharpe_bruto": round(float(np.mean(bruto) / np.std(bruto, ddof=1) * np.sqrt(EVENTOS_POR_ANO)), 3),
            "sharpe_liquido": round(float(np.mean(liq) / np.std(liq, ddof=1) * np.sqrt(EVENTOS_POR_ANO)), 3),
            "hit_rate": round(float((liq > 0).mean()), 3),
        }
    return saida


def validade_permutacao() -> dict:
    bt = json.loads((OUT / "backtest.json").read_text(encoding="utf-8"))
    saida = {}
    for nome, res in bt["estrategias"].items():
        constante = nome.startswith("B1")
        saida[nome] = {
            "p_valor_reportado": res["permutacao"]["p_valor_empirico"],
            "valido": not constante,
            "nota": "posicao constante: permutar retornos nao altera media nem desvio, o p-valor e ruido numerico e deve ser descartado" if constante else "posicao varia entre eventos: teste valido",
        }
    return saida


def main() -> None:
    rel = {
        "evento_vs_dia_qualquer": evento_vs_dia_qualquer(),
        "backtest_por_subamostra_S3": backtest_subamostra(),
        "validade_do_teste_de_permutacao": validade_permutacao(),
    }
    (OUT / "robustez.json").write_text(json.dumps(rel, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(rel, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
