# CopomLens — Testes do alvo DI 1Y (Camada 3, módulo único), sem rede: regime
# por tabela de presidentes do BC (falha alto fora da cobertura), reação da
# 7806 em torno da PUBLICAÇÃO da ata (D0→D+1 em bps; None fora da janela viva),
# carregadores do alvo e da lista oficial de reuniões, e o painel completo com
# funil documentado — contagens por etapa, descartes nomeados e razão escrita.
import json

import pandas as pd
import pytest

from copom.surprise.surpresa import (
    MAX_DEFASAGEM_D0_DIAS,
    carregar_di1y,
    carregar_reunioes_listadas,
    montar_painel_di1y,
    reacao_di1y,
    regime_bc,
)

# --- regime por presidente (tabela de fato público, nunca LLM) --------------


def test_regime_meirelles_e_tombini():
    assert regime_bc("2010-12-08") == "Meirelles"
    assert regime_bc("2010-12-31") == "Meirelles"
    assert regime_bc("2011-01-19") == "Tombini"
    assert regime_bc("2016-06-08") == "Tombini"


@pytest.mark.parametrize("data", ["2002-12-31", "2016-06-09", "2025-01-29"])
def test_regime_fora_da_tabela_falha_alto(data):
    with pytest.raises(ValueError, match="REGIMES_BC"):
        regime_bc(data)


# --- reação do DI 1Y na publicação da ata -----------------------------------


@pytest.fixture
def di1y():
    return pd.DataFrame(
        {
            "data": pd.to_datetime(["2016-06-15", "2016-06-16", "2016-06-17"]),
            "di1y": [12.10, 12.05, 12.38],
        }
    )


def test_reacao_vespera_para_dia_da_publicacao(di1y):
    # Ata publicada às 8h30 de 16/06: D0 = fechamento de 15/06 (ainda não viu a
    # ata) e D1 = fechamento de 16/06 (primeiro que já a viu).
    r = reacao_di1y(di1y, "2016-06-16")
    assert (str(r["d0"]), str(r["d1"])) == ("2016-06-15", "2016-06-16")
    assert r["taxa_d0"] == 12.10 and r["taxa_d1"] == 12.05
    assert r["reacao_bps"] == pytest.approx(-5.0)


def test_reacao_na_ultima_observacao_da_serie(di1y):
    r = reacao_di1y(di1y, "2016-06-17")
    assert (str(r["d0"]), str(r["d1"])) == ("2016-06-16", "2016-06-17")
    assert r["reacao_bps"] == pytest.approx(33.0)


def test_publicacao_em_dia_sem_pregao_usa_ultima_observacao(di1y):
    extra = pd.concat(
        [di1y, pd.DataFrame({"data": pd.to_datetime(["2016-06-20"]), "di1y": [12.30]})],
        ignore_index=True,
    )
    r = reacao_di1y(extra, "2016-06-18")  # sábado
    assert str(r["d0"]) == "2016-06-17" and str(r["d1"]) == "2016-06-20"
    assert r["reacao_bps"] == pytest.approx(-8.0)


def test_publicacao_antes_da_serie_retorna_none(di1y):
    assert reacao_di1y(di1y, "2003-12-24") is None


def test_publicacao_apos_a_morte_da_serie_retorna_none(di1y):
    pub = di1y["data"].max() + pd.Timedelta(days=MAX_DEFASAGEM_D0_DIAS + 1)
    assert reacao_di1y(di1y, pub) is None


def test_publicacao_sem_d1_retorna_none(di1y):
    # Publicação na segunda-feira seguinte à última observação (17/06, sexta):
    # há D0 recente, mas nenhum pregão a partir da publicação — série morta.
    assert reacao_di1y(di1y, "2016-06-20") is None


# --- carregadores ------------------------------------------------------------


def test_carregar_di1y_valida_conflito(tmp_path):
    p = tmp_path / "di1y_7806.csv"
    p.write_text("data,di1y\n2016-06-16,12.05\n2016-06-16,12.06\n")
    with pytest.raises(ValueError, match="2016-06-16"):
        carregar_di1y(p)


def test_carregar_di1y_sem_coluna_obrigatoria(tmp_path):
    p = tmp_path / "di1y_7806.csv"
    p.write_text("data,valor\n2016-06-16,12.05\n")
    with pytest.raises(ValueError, match="di1y"):
        carregar_di1y(p)


def test_carregar_reunioes_listadas_deduplica_e_ordena(tmp_path):
    p = tmp_path / "atas_listadas.json"
    p.write_text(
        json.dumps(
            [
                {"nroReuniao": 200, "dataReferencia": "2016-06-08"},
                {"nroReuniao": 116, "dataReferencia": "2006-01-18"},
                {"nroReuniao": 116, "dataReferencia": "2006-01-18"},
            ]
        ),
        encoding="utf-8",
    )
    df = carregar_reunioes_listadas(p)
    assert df["numero_reuniao"].tolist() == [116, 200]
    assert str(df["data_reuniao"].iloc[0].date()) == "2006-01-18"


def test_carregar_reunioes_listadas_com_timezone(tmp_path):
    p = tmp_path / "atas_listadas.json"
    p.write_text(
        json.dumps([{"nroReuniao": 116, "dataReferencia": "2006-01-18T00:00:00-03:00"}]),
        encoding="utf-8",
    )
    df = carregar_reunioes_listadas(p)
    assert str(df["data_reuniao"].iloc[0].date()) == "2006-01-18"
    assert df["data_reuniao"].dt.tz is None


def test_carregar_reunioes_sem_campos_reconheciveis(tmp_path):
    p = tmp_path / "atas_listadas.json"
    p.write_text(json.dumps([{"foo": 1}]), encoding="utf-8")
    with pytest.raises(ValueError, match="atas_listadas"):
        carregar_reunioes_listadas(p)


# --- painel completo com funil documentado -----------------------------------


@pytest.fixture
def cenario():
    reunioes = pd.DataFrame(
        {
            "numero_reuniao": [100, 101, 116, 157, 201],
            "data_reuniao": pd.to_datetime(
                ["2004-06-16", "2004-07-21", "2006-01-18", "2011-03-02", "2016-07-20"]
            ),
        }
    )
    # 100 e 201 sem texto; 116 duplicada; comunicado da 157 deve ser ignorado
    dataset = pd.DataFrame(
        {
            "numero_reuniao": [101, 116, 116, 157, 157],
            "data_reuniao": pd.to_datetime(
                ["2004-07-21", "2006-01-18", "2006-01-18", "2011-03-02", "2011-03-02"]
            ),
            "tipo": ["ata", "ata", "ata", "ata", "comunicado"],
            "available_time": pd.to_datetime(
                ["2004-07-29", "2006-01-26", "2006-01-26", "2011-03-10", "2011-03-02"]
            ),
        }
    )
    di1y = pd.DataFrame(
        {
            "data": pd.to_datetime(
                ["2004-07-28", "2004-07-29", "2006-01-25", "2006-01-26", "2011-03-09", "2011-03-10"]
            ),
            "di1y": [17.00, 17.10, 15.00, 15.20, 12.00, 11.90],
        }
    )
    selic = pd.DataFrame(
        {
            "data": pd.to_datetime(
                ["2004-07-20", "2004-07-22", "2006-01-17", "2006-01-19", "2011-03-01", "2011-03-03"]
            ),
            "selic_meta": [16.00, 16.25, 18.00, 17.25, 11.25, 11.75],
        }
    )
    focus = pd.DataFrame(
        {
            "reuniao": ["R1/2006", "R1/2006", "R1/2011"],
            "data": pd.to_datetime(["2006-01-10", "2006-01-17", "2011-02-24"]),
            "mediana": [17.50, 17.75, 11.75],
        }
    )
    return dataset, reunioes, selic, focus, di1y


def test_painel_di1y_linhas_finais(cenario):
    painel, _ = montar_painel_di1y(*cenario)
    assert painel["numero_reuniao"].tolist() == [116, 157]

    r116 = painel.iloc[0]
    assert r116["rotulo_focus"] == "R1/2006"
    assert r116["regime"] == "Meirelles"
    assert str(pd.Timestamp(r116["data_publicacao_ata"]).date()) == "2006-01-26"
    assert r116["reacao_bps"] == pytest.approx(20.0)
    assert r116["mediana_focus"] == 17.75  # última pesquisa ANTES da reunião
    assert r116["surpresa_decisao"] == pytest.approx(-0.5)
    assert (r116["nivel_pre"], r116["decisao"]) == (18.00, 17.25)

    r157 = painel.iloc[1]
    assert r157["rotulo_focus"] == "R1/2011"
    assert r157["regime"] == "Tombini"
    assert r157["reacao_bps"] == pytest.approx(-10.0)
    assert r157["surpresa_decisao"] == pytest.approx(0.0)


def test_painel_di1y_funil_com_razoes(cenario):
    _, funil = montar_painel_di1y(*cenario)
    assert [e["restantes"] for e in funil["etapas"]] == [5, 3, 3, 2]
    assert [e["removidas"] for e in funil["etapas"]] == [0, 2, 0, 1]
    assert all(e["motivo"] for e in funil["etapas"])

    cortadas = {(d["numero_reuniao"], d["etapa"]) for d in funil["descartes"]}
    assert (100, "com texto HTML") in cortadas
    assert (201, "com texto HTML") in cortadas
    assert (101, "com Focus por reunião") in cortadas
    assert all(d["motivo"] for d in funil["descartes"])

    assert funil["validacao_reacao"]["n_reacoes_casadas"] == 3
    assert funil["validacao_reacao"]["acima_1bp"] == 3
    assert funil["validacao_reacao"]["em_1bp_exato"] == 0
    assert funil["janela_final"] == {
        "inicio": "2006-01-18",
        "fim": "2011-03-02",
        "n_atas": 2,
    }


def test_painel_di1y_exige_available_time():
    dataset = pd.DataFrame(
        {
            "numero_reuniao": [1],
            "data_reuniao": pd.to_datetime(["2006-01-18"]),
            "tipo": ["ata"],
        }
    )
    reunioes = dataset[["numero_reuniao", "data_reuniao"]]
    with pytest.raises(ValueError, match="available_time"):
        montar_painel_di1y(dataset, reunioes, None, None, None)
