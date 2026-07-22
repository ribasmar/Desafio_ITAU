# CopomLens — Testes das funções determinísticas da validação estatística:
# pareamento reunião → decisão da Selic seguinte, corte point-in-time do Focus
# (sem look-ahead), surpresa monetária, rótulo Focus e parsing/validação dos
# CSVs e do copom_dataset.jsonl (duplicatas, JSON truncado, casos de borda).
import math
from pathlib import Path

import pandas as pd
import pytest

from copom.surprise.surpresa import (
    carregar_dataset,
    carregar_focus,
    carregar_selic_meta,
    decisao_apos_reuniao,
    mediana_focus_pre_reuniao,
    montar_painel,
    rotulo_focus,
)


@pytest.fixture
def selic():
    return pd.DataFrame(
        {
            "data": pd.to_datetime(
                ["2024-01-29", "2024-01-30", "2024-01-31", "2024-02-01", "2024-02-02"]
            ),
            "selic_meta": [11.75, 11.75, 11.75, 11.25, 11.25],
        }
    )


@pytest.fixture
def focus():
    return pd.DataFrame(
        {
            "reuniao": ["R1/2024"] * 3,
            "data": pd.to_datetime(["2024-01-29", "2024-01-30", "2024-01-31"]),
            "mediana": [11.50, 11.25, 99.0],
        }
    )


# --- pareamento reunião → decisão seguinte -------------------------------


def test_pareamento_usa_primeiro_valor_apos_a_reuniao(selic):
    r = decisao_apos_reuniao(selic, "2024-01-31")
    assert r["nivel_pre"] == 11.75
    assert r["decisao"] == 11.25
    assert r["delta"] == -0.50


def test_reuniao_sem_decisao_posterior_retorna_nan(selic):
    r = decisao_apos_reuniao(selic, "2024-02-02")
    assert math.isnan(r["decisao"]) and math.isnan(r["delta"])
    assert r["nivel_pre"] == 11.25


def test_reuniao_anterior_a_serie_retorna_nan_no_nivel_pre(selic):
    r = decisao_apos_reuniao(selic, "2023-12-01")
    assert math.isnan(r["nivel_pre"])


def test_reuniao_fora_da_cobertura_nao_pareia_decisao_espuria(selic):
    # Reunião meses antes do início da série: a primeira observação posterior
    # existe (2024-01-29), mas está longe demais — parear seria atribuir a
    # meta de 2024 a uma reunião antiga. O guard devolve NaN.
    r = decisao_apos_reuniao(selic, "2023-06-01")
    assert math.isnan(r["decisao"]) and math.isnan(r["delta"])


# --- corte point-in-time do Focus -----------------------------------------


def test_pit_exclui_pesquisa_do_dia_da_decisao(focus):
    mediana = mediana_focus_pre_reuniao(focus, "R1/2024", "2024-01-31")
    assert mediana == 11.25


def test_pit_sem_pesquisa_anterior_retorna_nan(focus):
    apenas_no_dia = focus[focus["data"] == "2024-01-31"]
    assert math.isnan(mediana_focus_pre_reuniao(apenas_no_dia, "R1/2024", "2024-01-31"))


def test_rotulo_inexistente_retorna_nan(focus):
    assert math.isnan(mediana_focus_pre_reuniao(focus, "R9/2024", "2024-01-31"))


def test_rotulo_mal_pareado_falha_alto(focus):
    with pytest.raises(ValueError, match="R1/2024"):
        mediana_focus_pre_reuniao(focus, "R1/2024", "2024-06-19")


def test_surpresa_decisao_menos_mediana(selic, focus):
    decisao = decisao_apos_reuniao(selic, "2024-01-31")["decisao"]
    mediana = mediana_focus_pre_reuniao(focus, "R1/2024", "2024-01-31")
    assert decisao - mediana == 0.0


# --- rótulo Focus -----------------------------------------------------------


def test_rotulo_ordena_dentro_do_ano():
    datas = ["2024-01-31", "2024-03-20", "2025-01-29"]
    assert rotulo_focus("2024-03-20", datas) == "R2/2024"
    assert rotulo_focus("2025-01-29", datas) == "R1/2025"


def test_rotulo_data_desconhecida_falha():
    with pytest.raises(ValueError):
        rotulo_focus("2024-05-08", ["2024-01-31"])


# --- parsing e validação dos arquivos --------------------------------------


def test_selic_duplicata_identica_deduplicada(tmp_path):
    p = tmp_path / "selic.csv"
    p.write_text("data,selic_meta\n2024-01-01,11.75\n2024-01-01,11.75\n2024-01-02,11.75\n")
    df = carregar_selic_meta(p)
    assert len(df) == 2


def test_selic_duplicata_conflitante_falha(tmp_path):
    p = tmp_path / "selic.csv"
    p.write_text("data,selic_meta\n2024-01-01,11.75\n2024-01-01,11.25\n")
    with pytest.raises(ValueError, match="2024-01-01"):
        carregar_selic_meta(p)


def test_focus_sem_coluna_obrigatoria_falha(tmp_path):
    p = tmp_path / "focus.csv"
    p.write_text("reuniao,data\nR1/2024,2024-01-02\n")
    with pytest.raises(ValueError, match="mediana"):
        carregar_focus(p)


def test_dataset_jsonl_valido_com_tipos(tmp_path):
    p = tmp_path / "dataset.jsonl"
    p.write_text(
        '{"numero_reuniao": "260", "data_reuniao": "2024-01-31", "tipo": "ata"}\n'
        "\n"
        '{"numero_reuniao": 261, "data_reuniao": "2024-03-20", "tipo": "comunicado"}\n'
    )
    df = carregar_dataset(p)
    assert len(df) == 2
    assert df["numero_reuniao"].tolist() == [260, 261]
    assert pd.api.types.is_datetime64_any_dtype(df["data_reuniao"])


def test_dataset_jsonl_truncado_falha_com_numero_da_linha(tmp_path):
    p = tmp_path / "dataset.jsonl"
    p.write_text(
        '{"numero_reuniao": 260, "data_reuniao": "2024-01-31", "tipo": "ata"}\n'
        '{"numero_reuniao": 261, "data_reu'
    )
    with pytest.raises(ValueError, match="linha 2"):
        carregar_dataset(p)


# --- painel ponta a ponta ---------------------------------------------------

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def test_painel_reuniao_com_datas_divergentes_vira_uma_linha(selic, focus):
    # Caso real (reunião 94): ata com dataReferencia 2004-03-17 e comunicado com
    # 2004-03-18 — uma reunião não pode virar duas linhas; vence a data da ata.
    dataset = pd.DataFrame(
        {
            "numero_reuniao": [260, 260],
            "data_reuniao": pd.to_datetime(["2024-01-31", "2024-02-01"]),
            "tipo": ["ata", "comunicado"],
        }
    )
    painel = montar_painel(dataset, selic, focus)
    assert len(painel) == 1
    assert str(painel.iloc[0]["data_reuniao"].date()) == "2024-01-31"


def test_painel_sintetico(selic, focus):
    dataset = pd.DataFrame(
        {
            "numero_reuniao": [260, 260, 261],
            "data_reuniao": pd.to_datetime(["2024-01-31", "2024-01-31", "2024-02-02"]),
            "tipo": ["ata", "comunicado", "ata"],
        }
    )
    focus_261 = pd.DataFrame(
        {
            "reuniao": ["R2/2024"],
            "data": pd.to_datetime(["2024-02-01"]),
            "mediana": [11.25],
        }
    )
    painel = montar_painel(dataset, selic, pd.concat([focus, focus_261]))
    assert list(painel["numero_reuniao"]) == [260, 261]
    assert list(painel["rotulo_focus"]) == ["R1/2024", "R2/2024"]
    r260 = painel.iloc[0]
    assert (r260["delta"], r260["surpresa"]) == (-0.50, 0.0)
    r261 = painel.iloc[1]
    assert math.isnan(r261["decisao"]) and math.isnan(r261["surpresa"])


@pytest.mark.skipif(
    not (DATA_DIR / "raw" / "selic_meta.csv").exists(), reason="dados reais ausentes"
)
def test_painel_dados_reais_sem_nan_inesperado():
    # Com o histórico completo (1998–2026), NaN deixa de ser sempre erro e
    # passa a codificar fronteira de cobertura: decisão só existe a partir da
    # carga da série 432 (2004+) e Focus por reunião só a partir da R1/2006 —
    # os mesmos cortes documentados no funil do alvo DI 1Y.
    dataset = carregar_dataset(DATA_DIR / "processed" / "copom_dataset.jsonl")
    selic_real = carregar_selic_meta(DATA_DIR / "raw" / "selic_meta.csv")
    focus_real = carregar_focus(DATA_DIR / "raw" / "focus_selic.csv")
    painel = montar_painel(dataset, selic_real, focus_real)
    assert len(painel) == dataset["numero_reuniao"].nunique()

    ultima = painel["data_reuniao"].idxmax()
    completas = painel.drop(index=ultima)
    inicio_serie = selic_real["data"].min()

    cobertas = completas[completas["data_reuniao"] >= inicio_serie]
    fora_da_serie = completas[completas["data_reuniao"] < inicio_serie]
    assert cobertas["decisao"].notna().all()
    assert fora_da_serie["decisao"].isna().all()  # sem pareamento espúrio

    com_focus = cobertas[cobertas["data_reuniao"] >= pd.Timestamp("2006-01-01")]
    pre_focus = completas[completas["data_reuniao"] < pd.Timestamp("2006-01-01")]
    assert com_focus[["mediana_focus", "surpresa"]].notna().all().all()
    assert pre_focus[["mediana_focus", "surpresa"]].isna().all().all()

    assert painel["decisao"].dropna().between(2.0, 20.0).all()
