# CopomLens — Testes do fatiamento de janelas do SGS (a API limita séries
# diárias a 10 anos por consulta e responde HTTP 406 acima) e da carga do alvo
# DI 1Y (SGS 7806), sem rede: janelas contíguas e inclusivas, concatenação com
# deduplicação de borda e defaults documentados da 7806 (janela viva completa).
import pandas as pd
import pytest

import copom.ingest.marketdata as md


def test_janela_unica_quando_cabe_em_10_anos():
    assert md._janelas_sgs("01/01/2020", "31/12/2024") == [("01/01/2020", "31/12/2024")]


def test_janela_da_7806_vira_duas_fatias_contiguas():
    janelas = md._janelas_sgs(md.DI1Y_DATA_INICIAL, md.DI1Y_DATA_FINAL)
    assert janelas == [("02/01/2004", "01/01/2014"), ("02/01/2014", "30/09/2019")]


def test_janelas_cobrem_sem_buraco_nem_sobreposicao():
    janelas = md._janelas_sgs("01/01/2006", "19/07/2026")
    assert janelas[0][0] == "01/01/2006" and janelas[-1][1] == "19/07/2026"
    for (_, fim), (ini, _) in zip(janelas, janelas[1:]):
        gap = pd.to_datetime(ini, format="%d/%m/%Y") - pd.to_datetime(fim, format="%d/%m/%Y")
        assert gap.days == 1
    for ini, fim in janelas:
        inicio = pd.to_datetime(ini, format="%d/%m/%Y")
        final = pd.to_datetime(fim, format="%d/%m/%Y")
        assert final < inicio + pd.DateOffset(years=md.SGS_JANELA_MAX_ANOS)


def test_data_final_antes_da_inicial_levanta():
    with pytest.raises(ValueError):
        md._janelas_sgs("02/01/2014", "01/01/2014")


def test_fetch_sgs_concatena_fatias_e_deduplica(monkeypatch):
    chamadas = []
    payloads = [
        [{"data": "02/01/2004", "valor": "16,00"}, {"data": "01/01/2014", "valor": "10,50"}],
        [{"data": "01/01/2014", "valor": "10,50"}, {"data": "30/09/2019", "valor": "4,96"}],
    ]

    def fake(url, params=None):
        chamadas.append(params)
        return payloads[len(chamadas) - 1]

    monkeypatch.setattr(md, "_get_json", fake)
    df = md.fetch_sgs(7806, "02/01/2004", "30/09/2019", coluna="di1y")
    assert len(chamadas) == 2
    assert chamadas[0]["dataInicial"] == "02/01/2004"
    assert chamadas[0]["dataFinal"] == "01/01/2014"
    assert chamadas[1]["dataInicial"] == "02/01/2014"
    assert chamadas[1]["dataFinal"] == "30/09/2019"
    assert list(df.columns) == ["data", "di1y"]
    assert len(df) == 3  # observação duplicada na borda das fatias removida
    assert df["data"].is_monotonic_increasing
    assert df.iloc[0]["di1y"] == 16.0 and df.iloc[-1]["di1y"] == 4.96


def test_fetch_di1y_usa_janela_viva_por_padrao(monkeypatch):
    chamadas = []

    def fake(url, params=None):
        chamadas.append((url, params))
        return []

    monkeypatch.setattr(md, "_get_json", fake)
    df = md.fetch_di1y()
    assert str(md.SGS_DI1Y_SWAP) in chamadas[0][0]
    assert chamadas[0][1]["dataInicial"] == "02/01/2004"
    assert chamadas[-1][1]["dataFinal"] == "30/09/2019"
    assert df.empty and list(df.columns) == ["data", "di1y"]
