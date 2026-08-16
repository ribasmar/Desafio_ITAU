# CopomLens — CLI das Camadas 4 e 5: le o painel com features de tom, roda a
# comparacao aninhada walk-forward (media -> surpresa -> surpresa + tom), deriva
# as posicoes de cada sinal e simula o P&L liquido de custo, com sensibilidade
# ao custo de travessia e teste de permutacao contra o acaso. Grava
# resultado_backtest.json e imprime a tabela de estrategias para conferencia
# imediata. Repete tudo na subamostra homogenea indicada por --coluna-subamostra.
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from copom.backtest.motor import (
    CUSTO_BPS_PADRAO,
    EVENTOS_POR_ANO_PADRAO,
    PermutacaoDegenerada,
    permutacao_contra_acaso,
    sensibilidade_custo,
    simular,
)
from copom.strategy.sinais import (
    COLUNA_ALVO,
    COLUNA_DATA,
    TREINO_MINIMO_PADRAO,
    comparar_aninhados,
    sinal_da_previsao,
    sinal_da_regra,
)

PROCESSED_DIR = Path("data/processed")


def _parse_args(argv: list[str] | None = None):
    p = argparse.ArgumentParser(
        description=(
            "Roda a comparacao aninhada walk-forward e o backtest evento-a-evento "
            "do DI 1Y sobre o painel com features de tom."
        )
    )
    p.add_argument("--painel", type=str, default=str(PROCESSED_DIR / "analise" / "painel_com_tom.csv"))
    p.add_argument("--saida", type=str, default=str(PROCESSED_DIR / "analise" / "resultado_backtest.json"))
    p.add_argument("--custo-bps", type=float, default=CUSTO_BPS_PADRAO)
    p.add_argument("--treino-minimo", type=int, default=TREINO_MINIMO_PADRAO)
    p.add_argument("--eventos-por-ano", type=float, default=EVENTOS_POR_ANO_PADRAO)
    p.add_argument("--coluna-subamostra", type=str, default="fonte_texto")
    p.add_argument("--valor-subamostra", type=str, default="api_html")
    return p.parse_args(argv)


def carregar_painel(caminho: Path) -> pd.DataFrame:
    """Le o painel com data ISO explicita e deriva lex_delta na ordem cronologica.

    O formato da data e fixado: inferencia com dayfirst embaralharia os dias 1 a
    12 de cada mes num arquivo ISO, e o erro passaria despercebido porque as
    datas continuam validas.
    """
    df = pd.read_csv(caminho)
    if COLUNA_DATA not in df.columns:
        raise SystemExit(f"painel sem a coluna {COLUNA_DATA!r}: {caminho}")
    df[COLUNA_DATA] = pd.to_datetime(df[COLUNA_DATA], format="%Y-%m-%d")
    df = df.sort_values(COLUNA_DATA).reset_index(drop=True)
    df["lex_delta"] = df["lex_score"].diff().fillna(0.0)
    return df


def rodar(df: pd.DataFrame, rotulo: str, args) -> dict:
    aninhado = comparar_aninhados(df, treino_minimo=args.treino_minimo, rotulo=rotulo)
    mascara = ~np.isnan(aninhado.previsoes["M2_surpresa_tom"])
    oos = df.loc[mascara].reset_index(drop=True)
    reacao = oos[COLUNA_ALVO].to_numpy(float)

    sinais = {
        "S1_previsao_so_surpresa": sinal_da_previsao(aninhado.previsoes["M1_surpresa"][mascara]),
        "S2_previsao_surpresa_e_tom": sinal_da_previsao(aninhado.previsoes["M2_surpresa_tom"][mascara]),
        "S3_regra_delta_tom": sinal_da_regra(oos["lex_delta"]),
        "S4_regra_nivel_tom": sinal_da_regra(oos["lex_score"]),
        "B1_sempre_recebe_fixo": np.full(len(oos), -1.0),
    }

    estrategias = {}
    for nome, pos in sinais.items():
        res = simular(pos, reacao, args.custo_bps, args.eventos_por_ano)
        bruto = simular(pos, reacao, 0.0, args.eventos_por_ano)
        entrada = {
            **res.metricas,
            "pnl_bruto_bps": bruto.metricas["pnl_total_bps"],
            "sharpe_bruto": bruto.metricas["sharpe_anual"],
            "sensibilidade_custo": sensibilidade_custo(pos, reacao, eventos_por_ano=args.eventos_por_ano),
        }
        try:
            entrada["permutacao"] = permutacao_contra_acaso(pos, reacao, args.custo_bps, args.eventos_por_ano)
        except PermutacaoDegenerada as erro:
            entrada["permutacao"] = {"aplicavel": False, "razao": str(erro)}
        estrategias[nome] = entrada

    return {
        "amostra": rotulo,
        "n_total": aninhado.n_total,
        "n_oos": aninhado.n_oos,
        "janela_oos": [str(oos[COLUNA_DATA].min().date()), str(oos[COLUNA_DATA].max().date())],
        "comparacao_aninhada": {"metricas": aninhado.metricas, "clark_west": aninhado.clark_west},
        "estrategias": estrategias,
    }


def imprimir(resultado: dict) -> None:
    print(f"\n=== {resultado['amostra']} — {resultado['n_oos']} eventos OOS "
          f"({resultado['janela_oos'][0]} a {resultado['janela_oos'][1]}) ===")
    for nome, m in resultado["comparacao_aninhada"]["metricas"].items():
        print(f"  {nome:20s} RMSE={m['rmse']:7.3f}  R2oos={m['r2_oos']:+.4f}")
    for nome, cw in resultado["comparacao_aninhada"]["clark_west"].items():
        print(f"  Clark-West {nome:42s} {cw['cw_stat']:+.3f} (p={cw['p_valor_unicaudal']:.3f})")
    cab = f"  {'estrategia':30s} {'bruto':>8s} {'liquido':>9s} {'Sharpe':>8s} {'MaxDD':>8s} {'hit':>6s}"
    print("\n" + cab + "\n  " + "-" * (len(cab) - 2))
    for nome, e in resultado["estrategias"].items():
        print(f"  {nome:30s} {e['pnl_bruto_bps']:8.1f} {e['pnl_total_bps']:9.1f} "
              f"{e['sharpe_anual']:8.3f} {e['max_drawdown_bps']:8.1f} {e['hit_rate']:6.3f}")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    caminho = Path(args.painel)
    if not caminho.exists():
        raise SystemExit(f"painel nao encontrado: {caminho} — rode scripts/analise/01_features_lexico.py antes")

    df = carregar_painel(caminho)
    resultados = [rodar(df, "painel_completo", args)]

    col = args.coluna_subamostra
    if col in df.columns:
        sub = df[df[col] == args.valor_subamostra].reset_index(drop=True)
        if len(sub) > args.treino_minimo + 3:
            resultados.append(rodar(sub, f"subamostra_{args.valor_subamostra}", args))

    saida = Path(args.saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps({"custo_bps": args.custo_bps, "resultados": resultados},
                                indent=2, ensure_ascii=False), encoding="utf-8")
    for r in resultados:
        imprimir(r)
    print(f"\nGravado em {saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
