# Testa a surpresa da decisao no evento em que ela e noticia: o comunicado,
# anunciado apos o fechamento do dia da reuniao — nao a ata, publicada 8 dias
# depois, quando a decisao ja esta precificada. Monta o painel paralelo
# (fechamento D0 -> D1 da decisao), roda o estudo de evento por tipo de dia,
# a comparacao aninhada M0 -> M1 walk-forward com Clark-West e o backtest da
# regra do sinal da surpresa, repetindo tudo na subamostra homogenea de 84.
# Ressalva de execucao valida para toda janela fechamento-a-fechamento deste
# trabalho: a posicao teria de ser montada antes do anuncio, entao o P&L e
# limite superior otimista, nao P&L executavel.
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[2]
OUT = BASE / "data" / "processed" / "analise"
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(BASE / "src"))
from copom.backtest.motor import (  # noqa: E402
    PermutacaoDegenerada,
    permutacao_contra_acaso,
    sensibilidade_custo,
    simular,
)
from copom.strategy import sinais  # noqa: E402
from copom.surprise.evento import estudo_evento, montar_painel_comunicado  # noqa: E402

CUSTO_BPS = 1.0
ESPECIFICACOES = {"M0_media": [], "M1_surpresa": ["surpresa_decisao"]}


def carregar() -> tuple[pd.DataFrame, pd.DataFrame]:
    painel = pd.read_csv(
        BASE / "data/processed/painel_di1y.csv",
        parse_dates=["data_reuniao", "data_publicacao_ata", "d0", "d1"],
    )
    di = pd.read_csv(BASE / "data/raw/di1y_7806.csv", parse_dates=["data"])
    return painel, di


def comparacao_aninhada(df: pd.DataFrame, rotulo: str) -> dict:
    df = df[["numero_reuniao", "d1_comunicado", "reacao_comunicado_bps", "surpresa_decisao"]].rename(
        columns={"reacao_comunicado_bps": sinais.COLUNA_ALVO, "d1_comunicado": sinais.COLUNA_DATA}
    )
    df = df.sort_values(sinais.COLUNA_DATA).reset_index(drop=True)
    aninhado = sinais.comparar_aninhados(df, especificacoes=ESPECIFICACOES, rotulo=rotulo)

    mascara = ~np.isnan(aninhado.previsoes["M1_surpresa"])
    oos = df.loc[mascara].reset_index(drop=True)
    reacao = oos[sinais.COLUNA_ALVO].to_numpy(float)
    posicoes = sinais.sinal_da_regra(oos["surpresa_decisao"])

    bruto = simular(posicoes, reacao, 0.0)
    liquido = simular(posicoes, reacao, CUSTO_BPS)
    estrategia = {
        **liquido.metricas,
        "pnl_bruto_bps": bruto.metricas["pnl_total_bps"],
        "sharpe_bruto": bruto.metricas["sharpe_anual"],
        "sensibilidade_custo": sensibilidade_custo(posicoes, reacao),
    }
    try:
        estrategia["permutacao"] = permutacao_contra_acaso(posicoes, reacao, CUSTO_BPS)
    except PermutacaoDegenerada as erro:
        estrategia["permutacao"] = {"aplicavel": False, "razao": str(erro)}

    surpresa = df["surpresa_decisao"].to_numpy(float)
    alvo = df[sinais.COLUNA_ALVO].to_numpy(float)
    return {
        "amostra": rotulo,
        "n_total": aninhado.n_total,
        "n_oos": aninhado.n_oos,
        "janela_oos": [str(oos[sinais.COLUNA_DATA].min().date()), str(oos[sinais.COLUNA_DATA].max().date())],
        "surpresa_nao_nula": int((surpresa != 0).sum()),
        "corr_surpresa_reacao": round(float(np.corrcoef(surpresa, alvo)[0, 1]), 4),
        "comparacao_aninhada": {"metricas": aninhado.metricas, "clark_west": aninhado.clark_west},
        "estrategia_sinal_da_surpresa": estrategia,
    }


def main() -> int:
    painel, di = carregar()
    painel_com = montar_painel_comunicado(painel, di)
    painel_com["fonte_texto"] = np.where(painel_com["numero_reuniao"] >= 200, "pdf", "api_html")
    painel_com.to_csv(OUT / "painel_comunicado.csv", index=False)

    resultado = {
        "leitura": (
            "reacao do DI 1Y ao comunicado: fechamento do dia da reuniao (anterior ao "
            "anuncio) ate o primeiro fechamento seguinte; mesma serie, mesmas 110 reunioes "
            "e mesma surpresa do painel da ata"
        ),
        "ressalva_execucao": (
            "janela fechamento-a-fechamento: a posicao teria de existir antes do anuncio, "
            "entao todo P&L e limite superior otimista, nao P&L executavel"
        ),
        "estudo_evento": estudo_evento(di, painel_com),
        "resultados": [
            comparacao_aninhada(painel_com, "painel_110"),
            comparacao_aninhada(
                painel_com[painel_com["fonte_texto"] == "api_html"].reset_index(drop=True),
                "subamostra_84_homogenea",
            ),
        ],
    }

    (OUT / "evento_comunicado.json").write_text(
        json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
    print(f"\nGravado em {OUT / 'evento_comunicado.json'} e {OUT / 'painel_comunicado.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
