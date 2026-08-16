# Comparacao aninhada walk-forward da reacao do DI 1Y a publicacao da ata:
# M0 media expandida, M1 so surpresa, M2 surpresa + tom lexico. Cada previsao
# usa apenas eventos anteriores ao evento previsto (janela expansiva, refit a
# cada evento). O ganho incremental de M2 sobre M1 e testado por Clark-West,
# apropriado para modelos aninhados. Roda no painel de 110 e na subamostra
# homogenea de 84 (texto so via API/HTML).
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

OUT = Path(__file__).resolve().parents[2] / "data" / "processed" / "analise"
MIN_TREINO = 40

ESPECIFICACOES = {
    "M0_media": [],
    "M1_surpresa": ["surpresa_decisao"],
    "M2_surpresa_tom": ["surpresa_decisao", "lex_score", "lex_delta"],
}


def ols_fit(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    Xc = np.column_stack([np.ones(len(X)), X]) if X.size else np.ones((len(y), 1))
    beta, *_ = np.linalg.lstsq(Xc, y, rcond=None)
    return beta


def ols_pred(beta: np.ndarray, x: np.ndarray) -> float:
    xc = np.concatenate([[1.0], x]) if x.size else np.array([1.0])
    return float(xc @ beta)


def walk_forward(df: pd.DataFrame, cols: list[str]) -> np.ndarray:
    y = df["reacao_bps"].to_numpy(float)
    X = df[cols].to_numpy(float) if cols else np.empty((len(df), 0))
    preds = np.full(len(df), np.nan)
    for t in range(MIN_TREINO, len(df)):
        beta = ols_fit(X[:t], y[:t])
        preds[t] = ols_pred(beta, X[t])
    return preds


def clark_west(y: np.ndarray, p_restrito: np.ndarray, p_amplo: np.ndarray) -> dict:
    """Teste de ganho preditivo OOS entre modelos aninhados (Clark & West, 2007).

    f_t = (y - p_restrito)^2 - [(y - p_amplo)^2 - (p_restrito - p_amplo)^2]
    Media de f significativamente > 0 indica que o modelo amplo agrega.
    """
    f = (y - p_restrito) ** 2 - ((y - p_amplo) ** 2 - (p_restrito - p_amplo) ** 2)
    n = len(f)
    t_stat = float(np.mean(f) / (np.std(f, ddof=1) / np.sqrt(n)))
    return {"cw_stat": round(t_stat, 3), "p_valor_unicaudal": round(1 - stats.norm.cdf(t_stat), 4), "n_oos": n}


def metricas(y: np.ndarray, pred: np.ndarray, bench: np.ndarray) -> dict:
    sse = float(np.sum((y - pred) ** 2))
    sse_b = float(np.sum((y - bench) ** 2))
    return {
        "rmse": round(float(np.sqrt(np.mean((y - pred) ** 2))), 3),
        "mae": round(float(np.mean(np.abs(y - pred))), 3),
        "r2_oos_vs_media": round(1 - sse / sse_b, 4),
        "corr_pred_real": round(float(np.corrcoef(pred, y)[0, 1]), 4) if np.std(pred) > 1e-12 else 0.0,
    }


def rodar(df: pd.DataFrame, rotulo: str) -> dict:
    df = df.sort_values("data_publicacao_ata").reset_index(drop=True).copy()
    df["lex_delta"] = df["lex_score"].diff().fillna(0.0)

    preds = {nome: walk_forward(df, cols) for nome, cols in ESPECIFICACOES.items()}
    mask = ~np.isnan(preds["M2_surpresa_tom"])
    y = df["reacao_bps"].to_numpy(float)[mask]

    res = {
        "amostra": rotulo,
        "n_total": int(len(df)),
        "n_oos": int(mask.sum()),
        "periodo_oos": [str(df.loc[mask, "data_publicacao_ata"].min().date()), str(df.loc[mask, "data_publicacao_ata"].max().date())],
        "dp_reacao_bps": round(float(np.std(y, ddof=1)), 2),
        "modelos": {nome: metricas(y, p[mask], preds["M0_media"][mask]) for nome, p in preds.items()},
        "clark_west": {
            "M1_sobre_M0": clark_west(y, preds["M0_media"][mask], preds["M1_surpresa"][mask]),
            "M2_sobre_M1": clark_west(y, preds["M1_surpresa"][mask], preds["M2_surpresa_tom"][mask]),
        },
    }

    import statsmodels.api as sm

    Xi = sm.add_constant(df[ESPECIFICACOES["M2_surpresa_tom"]])
    mod = sm.OLS(df["reacao_bps"], Xi).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
    res["in_sample_M2_HAC"] = {
        "r2": round(float(mod.rsquared), 4),
        "coef": {k: round(float(v), 3) for k, v in mod.params.items()},
        "p_valor": {k: round(float(v), 4) for k, v in mod.pvalues.items()},
    }
    res["_preds"] = {nome: p.tolist() for nome, p in preds.items()}
    return res


def main() -> None:
    df = pd.read_csv(OUT / "painel_com_tom.csv", parse_dates=["data_publicacao_ata"])
    resultados = [rodar(df, "painel_110"), rodar(df[df["fonte_texto"] == "api_html"], "subamostra_84_homogenea")]

    limpo = [{k: v for k, v in r.items() if not k.startswith("_")} for r in resultados]
    (OUT / "walkforward.json").write_text(json.dumps(limpo, indent=2, ensure_ascii=False), encoding="utf-8")

    pd.DataFrame({"data_publicacao_ata": df.sort_values("data_publicacao_ata")["data_publicacao_ata"].values,
                  **{n: v for n, v in resultados[0]["_preds"].items()}}).to_csv(OUT / "previsoes_walkforward.csv", index=False)

    print(json.dumps(limpo, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
