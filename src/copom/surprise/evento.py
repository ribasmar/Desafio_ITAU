# CopomLens — janela de evento do comunicado: a decisao e anunciada apos o
# fechamento do dia em que a reuniao termina, entao a reacao e medida do
# fechamento desse dia (D0, ainda sem a decisao no preco) ate o primeiro
# fechamento seguinte (D1, primeiro preco que a incorpora). O modulo monta o
# painel paralelo ao da ata usando a mesma serie SGS 7806 e as mesmas linhas do
# painel point-in-time, sem tocar na reacao original.
"""Janela de evento do comunicado e painel paralelo de reacao do DI 1Y."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

GAP_MAXIMO_DIAS = 7


class JanelaInvalida(ValueError):
    """Evento sem par D0/D1 valido na serie do alvo."""


def janela_comunicado(di: pd.DataFrame, data_reuniao: pd.Timestamp) -> dict:
    """D0 = ultima observacao <= data da reuniao; D1 = primeira observacao seguinte.

    O anuncio sai depois do fechamento de D0, entao o fechamento de D0 ainda nao
    contem a decisao e o de D1 e o primeiro que contem. Um intervalo D0->D1 maior
    que ``GAP_MAXIMO_DIAS`` dias corridos indica buraco na serie e derruba o
    evento em vez de virar reacao silenciosamente errada.
    """
    if not di["data"].is_monotonic_increasing:
        raise JanelaInvalida("serie do DI precisa estar ordenada por data crescente")

    data_reuniao = pd.Timestamp(data_reuniao)
    anteriores = di[di["data"] <= data_reuniao]
    posteriores = di[di["data"] > data_reuniao]
    if anteriores.empty or posteriores.empty:
        raise JanelaInvalida(f"reuniao {data_reuniao.date()} fora da janela viva da serie")

    d0 = anteriores.iloc[-1]
    d1 = posteriores.iloc[0]
    if (d1["data"] - d0["data"]).days > GAP_MAXIMO_DIAS:
        raise JanelaInvalida(
            f"gap de {(d1['data'] - d0['data']).days} dias entre {d0['data'].date()} "
            f"e {d1['data'].date()}: buraco na serie, nao janela de evento"
        )

    return {
        "d0_comunicado": d0["data"],
        "taxa_d0_comunicado": float(d0["di1y"]),
        "d1_comunicado": d1["data"],
        "taxa_d1_comunicado": float(d1["di1y"]),
        "reacao_comunicado_bps": round(100.0 * (float(d1["di1y"]) - float(d0["di1y"])), 4),
    }


def montar_painel_comunicado(painel: pd.DataFrame, di: pd.DataFrame) -> pd.DataFrame:
    """Anexa a cada linha do painel a reacao do DI 1Y no evento do comunicado.

    Reaproveita as linhas do painel point-in-time (mesmas reunioes, mesma
    surpresa, mesmo funil) e acrescenta apenas a janela do comunicado. Evento
    sem janela valida derruba a execucao: o painel do comunicado tem de cobrir
    exatamente as mesmas reunioes do painel da ata, ou a comparacao entre os
    dois eventos deixaria de ser pareada.
    """
    di = di.sort_values("data").reset_index(drop=True)
    linhas = []
    for _, ev in painel.iterrows():
        janela = janela_comunicado(di, ev["data_reuniao"])
        linhas.append({"numero_reuniao": int(ev["numero_reuniao"]), **janela})
    df = painel.merge(pd.DataFrame(linhas), on="numero_reuniao", validate="one_to_one")

    sobrepostos = df[df["d1_comunicado"] >= df["data_publicacao_ata"]]
    if len(sobrepostos):
        raise JanelaInvalida(
            "janela do comunicado invadiu a publicacao da ata nas reunioes "
            f"{sobrepostos['numero_reuniao'].tolist()}: os dois eventos deixariam de ser separaveis"
        )
    return df


def dias_de_evento(painel_comunicado: pd.DataFrame) -> dict[str, set]:
    """Conjuntos de datas em que cada evento foi absorvido pelo fechamento.

    ``comunicado`` usa D1 (primeiro fechamento apos o anuncio); ``ata`` usa a
    propria data de publicacao, que ja e o dia em que o fechamento absorve a
    ata publicada as 8h30.
    """
    return {
        "comunicado": set(pd.to_datetime(painel_comunicado["d1_comunicado"])),
        "ata": set(pd.to_datetime(painel_comunicado["data_publicacao_ata"])),
    }


def variacoes_diarias(di: pd.DataFrame) -> pd.DataFrame:
    """Serie de variacoes diarias do DI 1Y em bps, na ordem cronologica."""
    di = di.sort_values("data").reset_index(drop=True).copy()
    di["var_bps"] = di["di1y"].diff() * 100.0
    return di.dropna(subset=["var_bps"]).reset_index(drop=True)


def estudo_evento(di: pd.DataFrame, painel_comunicado: pd.DataFrame) -> dict:
    """|variacao| media do DI 1Y por tipo de dia: comunicado, ata e dia comum.

    A comparacao e restrita a janela do painel e cada dia pertence a uma unica
    categoria — dia de comunicado que coincidisse com dia de ata seria erro de
    desenho, ja barrado em ``montar_painel_comunicado``.
    """
    var = variacoes_diarias(di)
    eventos = dias_de_evento(painel_comunicado)
    inicio = min(painel_comunicado["d0_comunicado"].min(), painel_comunicado["data_publicacao_ata"].min())
    fim = max(painel_comunicado["d1_comunicado"].max(), painel_comunicado["data_publicacao_ata"].max())
    var = var[(var["data"] >= inicio) & (var["data"] <= fim)]

    em_comunicado = var["data"].isin(eventos["comunicado"])
    em_ata = var["data"].isin(eventos["ata"])
    grupos = {
        "comunicado": var.loc[em_comunicado, "var_bps"].to_numpy(float),
        "ata": var.loc[em_ata & ~em_comunicado, "var_bps"].to_numpy(float),
        "dia_comum": var.loc[~em_comunicado & ~em_ata, "var_bps"].to_numpy(float),
    }

    comum = np.abs(grupos["dia_comum"])
    resultado = {}
    for nome, serie in grupos.items():
        bloco = {
            "n_dias": int(len(serie)),
            "abs_var_media_bps": round(float(np.mean(np.abs(serie))), 2),
            "dp_bps": round(float(np.std(serie, ddof=1)), 2),
        }
        if nome != "dia_comum":
            mw = stats.mannwhitneyu(np.abs(serie), comum, alternative="greater")
            bloco["mannwhitney_p_maior_que_dia_comum"] = round(float(mw.pvalue), 4)
        resultado[nome] = bloco
    return resultado
