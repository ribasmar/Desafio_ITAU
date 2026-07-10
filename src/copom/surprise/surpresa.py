# CopomLens — Camada 3: dados determinísticos para a validação estatística do
# tom (tasks #5/#8). Carrega e valida selic_meta.csv, focus_selic.csv e
# copom_dataset.jsonl; pareia cada reunião com a decisão da Selic seguinte
# (nível pré, novo nível e delta); calcula a mediana do Focus com corte
# point-in-time (somente pesquisas estritamente anteriores à data da decisão,
# evitando look-ahead) e a surpresa monetária (decisão − mediana Focus
# pré-reunião). montar_painel() junta tudo em um DataFrame por reunião.
"""Pareamento reunião↔Selic, corte point-in-time do Focus e surpresa monetária."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

# Janela máxima aceita entre a última pesquisa Focus de um rótulo e a data da
# reunião; acima disso o rótulo é considerado mal pareado e a função falha alto.
TOLERANCIA_ROTULO_DIAS = 10


def carregar_selic_meta(caminho: str | Path) -> pd.DataFrame:
    """Lê selic_meta.csv (data, selic_meta) ordenado por data.

    Datas duplicadas com o mesmo valor são deduplicadas; com valores
    conflitantes, levanta ValueError (falha alto em vez de escolher em silêncio).
    """
    df = pd.read_csv(caminho, parse_dates=["data"])
    faltantes = {"data", "selic_meta"} - set(df.columns)
    if faltantes:
        raise ValueError(f"selic_meta sem colunas obrigatórias: {sorted(faltantes)}")
    if df["data"].duplicated().any():
        conflitos = df.groupby("data")["selic_meta"].nunique()
        datas_conflitantes = conflitos[conflitos > 1].index
        if len(datas_conflitantes):
            datas = [d.strftime("%Y-%m-%d") for d in datas_conflitantes]
            raise ValueError(f"selic_meta com valores conflitantes nas datas: {datas}")
        df = df.drop_duplicates(subset="data")
    return df.sort_values("data").reset_index(drop=True)


def carregar_focus(caminho: str | Path) -> pd.DataFrame:
    """Lê focus_selic.csv (reuniao, data, mediana, ...) ordenado por rótulo e data."""
    df = pd.read_csv(caminho, parse_dates=["data"])
    faltantes = {"reuniao", "data", "mediana"} - set(df.columns)
    if faltantes:
        raise ValueError(f"focus_selic sem colunas obrigatórias: {sorted(faltantes)}")
    return df.sort_values(["reuniao", "data"]).reset_index(drop=True)


def carregar_dataset(caminho: str | Path) -> pd.DataFrame:
    """Lê copom_dataset.jsonl com tipos normalizados.

    Linhas vazias são ignoradas; linha com JSON inválido levanta ValueError
    indicando o número da linha (arquivo truncado não passa despercebido).
    """
    linhas: list[dict] = []
    with open(caminho, encoding="utf-8") as f:
        for numero, linha in enumerate(f, start=1):
            linha = linha.strip()
            if not linha:
                continue
            try:
                linhas.append(json.loads(linha))
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSON inválido na linha {numero} de {caminho}: {exc}") from exc
    df = pd.DataFrame(linhas)
    obrigatorias = {"numero_reuniao", "data_reuniao", "tipo"}
    faltantes = obrigatorias - set(df.columns)
    if faltantes:
        raise ValueError(f"copom_dataset sem campos obrigatórios: {sorted(faltantes)}")
    df["numero_reuniao"] = df["numero_reuniao"].astype(int)
    df["data_reuniao"] = pd.to_datetime(df["data_reuniao"])
    if "available_time" in df.columns:
        df["available_time"] = pd.to_datetime(df["available_time"])
    return df


def rotulo_focus(data_reuniao: pd.Timestamp, datas_reunioes) -> str:
    """Rótulo Focus "R{k}/{ano}" da reunião: k-ésima reunião do ano.

    `datas_reunioes` deve conter todas as reuniões conhecidas do ano da data
    consultada — o rank dentro do ano define o k do rótulo.
    """
    data_reuniao = pd.Timestamp(data_reuniao)
    datas = pd.DatetimeIndex(sorted(set(pd.DatetimeIndex(datas_reunioes))))
    if data_reuniao not in datas:
        raise ValueError(f"data {data_reuniao.date()} ausente da lista de reuniões")
    no_ano = datas[datas.year == data_reuniao.year]
    k = int(no_ano.get_loc(data_reuniao)) + 1
    return f"R{k}/{data_reuniao.year}"


def decisao_apos_reuniao(selic: pd.DataFrame, data_reuniao: pd.Timestamp) -> dict:
    """Decisão da Selic associada à reunião de `data_reuniao`.

    nivel_pre: último valor com data <= data_reuniao (vigente antes da decisão).
    decisao:   primeiro valor com data > data_reuniao (novo alvo, vigência D+1).
    delta:     decisao − nivel_pre.
    Sem observação posterior (reunião mais recente), os campos ficam NaN.
    """
    data_reuniao = pd.Timestamp(data_reuniao)
    antes = selic.loc[selic["data"] <= data_reuniao, "selic_meta"]
    depois = selic.loc[selic["data"] > data_reuniao, "selic_meta"]
    nivel_pre = float(antes.iloc[-1]) if len(antes) else math.nan
    decisao = float(depois.iloc[0]) if len(depois) else math.nan
    return {"nivel_pre": nivel_pre, "decisao": decisao, "delta": decisao - nivel_pre}


def mediana_focus_pre_reuniao(
    focus: pd.DataFrame, rotulo: str, data_reuniao: pd.Timestamp
) -> float:
    """Mediana Focus point-in-time para a reunião: última pesquisa ESTRITAMENTE
    anterior a `data_reuniao` (pesquisa do próprio dia da decisão é descartada
    por precaução contra look-ahead).

    Levanta ValueError se o rótulo não parecer corresponder à reunião (última
    pesquisa depois da decisão ou mais de TOLERANCIA_ROTULO_DIAS antes dela).
    Retorna NaN se o rótulo não existir ou não houver pesquisa anterior.
    """
    data_reuniao = pd.Timestamp(data_reuniao)
    grupo = focus.loc[focus["reuniao"] == rotulo]
    if grupo.empty:
        return math.nan
    ultima = grupo["data"].max()
    if ultima > data_reuniao or ultima < data_reuniao - pd.Timedelta(days=TOLERANCIA_ROTULO_DIAS):
        raise ValueError(
            f"rótulo {rotulo} não corresponde à reunião de {data_reuniao.date()}: "
            f"última pesquisa em {ultima.date()}"
        )
    pit = grupo.loc[grupo["data"] < data_reuniao]
    if pit.empty:
        return math.nan
    return float(pit.sort_values("data")["mediana"].iloc[-1])


def montar_painel(
    dataset: pd.DataFrame, selic: pd.DataFrame, focus: pd.DataFrame
) -> pd.DataFrame:
    """Painel por reunião: decisão pareada, mediana Focus PIT e surpresa.

    Colunas: numero_reuniao, data_reuniao, rotulo_focus, nivel_pre, decisao,
    delta, mediana_focus, surpresa (= decisao − mediana_focus).
    """
    reunioes = (
        dataset[["numero_reuniao", "data_reuniao"]]
        .drop_duplicates()
        .sort_values("data_reuniao")
        .reset_index(drop=True)
    )
    linhas = []
    for reuniao in reunioes.itertuples(index=False):
        rotulo = rotulo_focus(reuniao.data_reuniao, reunioes["data_reuniao"])
        decisao = decisao_apos_reuniao(selic, reuniao.data_reuniao)
        mediana = mediana_focus_pre_reuniao(focus, rotulo, reuniao.data_reuniao)
        linhas.append(
            {
                "numero_reuniao": reuniao.numero_reuniao,
                "data_reuniao": reuniao.data_reuniao,
                "rotulo_focus": rotulo,
                **decisao,
                "mediana_focus": mediana,
                "surpresa": decisao["decisao"] - mediana,
            }
        )
    return pd.DataFrame(linhas)
