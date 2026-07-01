# CopomLens — Testes da ingestao de mercado (marketdata). Sem rede: o cliente
# HTTP (_get_json) e mockado para validar parsing dos payloads do BCB, a
# filtragem client-side do Focus e o encoding %20 da query OData (bug corrigido).
import re

import pandas as pd

import copom.ingest.marketdata as md


def test_fetch_selic_meta_parsing(monkeypatch):
    payload = [
        {"data": "18/06/2026", "valor": "14,50"},  # virgula decimal -> deve virar 14.50
        {"data": "16/06/2026", "valor": "15,00"},
    ]
    monkeypatch.setattr(md, "_get_json", lambda url, params=None: payload)

    df = md.fetch_selic_meta(data_inicial="01/01/2026")
    assert list(df.columns) == ["data", "selic_meta"]
    assert df["data"].is_monotonic_increasing  # ordenado por data
    assert df.iloc[0]["selic_meta"] == 15.0 and df.iloc[-1]["selic_meta"] == 14.5
    assert str(df["data"].dtype).startswith("datetime64")


def test_fetch_selic_meta_janela_padrao(monkeypatch):
    capturado = {}

    def fake(url, params=None):
        capturado["params"] = params
        return []

    monkeypatch.setattr(md, "_get_json", fake)
    md.fetch_selic_meta()  # sem datas -> deve preencher dataInicial (limite de 10 anos do SGS)
    assert "dataInicial" in capturado["params"]
    assert re.match(r"\d{2}/\d{2}/\d{4}", capturado["params"]["dataInicial"])


def test_fetch_focus_encoding_e_filtro(monkeypatch):
    capturado = {}
    payload = {
        "value": [
            {"Reuniao": "R4/2026", "Data": "2026-06-15", "Mediana": 14.75,
             "Media": 14.70, "numeroRespondentes": 55, "baseCalculo": 0},
            {"Reuniao": "R4/2026", "Data": "2026-06-15", "Mediana": 14.80,
             "Media": 14.80, "numeroRespondentes": 20, "baseCalculo": 1},  # base 1 -> descartada
            {"Reuniao": "R3/2023", "Data": "2023-01-10", "Mediana": 13.50,
             "Media": 13.50, "numeroRespondentes": 40, "baseCalculo": 0},  # < data_inicial
        ]
    }

    def fake(url, params=None):
        capturado["url"] = url
        return payload

    monkeypatch.setattr(md, "_get_json", fake)
    df = md.fetch_focus_selic(data_inicial="2024-01-01", base_calculo=0)

    # Encoding: espaco como %20 e nunca '+' (o parser OData do Olinda rejeita '+').
    assert "Data%20desc" in capturado["url"]
    assert "+" not in capturado["url"]

    # Filtro client-side: base_calculo=0 e data>=2024 deixam so a primeira linha.
    assert len(df) == 1
    assert df.iloc[0]["reuniao"] == "R4/2026"
    assert int(df.iloc[0]["base_calculo"]) == 0
    assert str(df["n_respondentes"].dtype) == "Int64"


def test_fetch_focus_vazio(monkeypatch):
    monkeypatch.setattr(md, "_get_json", lambda url, params=None: {"value": []})
    df = md.fetch_focus_selic()
    assert df.empty
    assert "mediana" in df.columns  # schema preservado mesmo vazio
