# CopomLens — Testes negados e de borda da surpresa da decisao (Camada 3):
# serie de meta sem cobertura pos-decisao levanta (nao devolve meta antiga),
# reuniao fora do COPOM_CALENDAR levanta, mediana NaN recua para o survey
# anterior valido, survey exatamente na data de corte e excluido (corte
# estrito, anti-lookahead) e reuniao com um unico survey valido funciona.
import pandas as pd
import pytest

from copom.surprise.decision import (
    COPOM_CALENDAR,
    selic_efetiva,
    selic_esperada,
    surpresa_decisao,
)

REUNIAO = "R4/2026"


def test_selic_efetiva_sem_pos_decisao_levanta():
    serie = pd.DataFrame({"data": ["2026-06-16", "2026-06-17"], "selic_meta": [15.0, 15.0]})
    with pytest.raises(ValueError):
        selic_efetiva(serie, COPOM_CALENDAR[REUNIAO]["decisao"])


def test_reuniao_fora_do_calendario_levanta():
    vazio = pd.DataFrame(columns=["reuniao", "data", "mediana", "base_calculo"])
    with pytest.raises(KeyError):
        surpresa_decisao("R9/1999", vazio, vazio)


def test_mediana_nan_recua_para_survey_anterior():
    focus = pd.DataFrame(
        {
            "reuniao": [REUNIAO, REUNIAO],
            "data": ["2026-06-08", "2026-06-12"],
            "mediana": [14.75, float("nan")],
            "n_respondentes": [50, 52],
            "base_calculo": [0, 0],
        }
    )
    mediana, data_exp, _ = selic_esperada(focus, REUNIAO, COPOM_CALENDAR[REUNIAO]["inicio"])
    assert mediana == 14.75
    assert str(data_exp) == "2026-06-08"


def test_survey_na_data_do_corte_e_excluido():
    focus = pd.DataFrame(
        {
            "reuniao": [REUNIAO, REUNIAO],
            "data": ["2026-06-12", "2026-06-15"],
            "mediana": [14.75, 14.50],
            "n_respondentes": [50, 52],
            "base_calculo": [0, 0],
        }
    )
    mediana, data_exp, _ = selic_esperada(focus, REUNIAO, COPOM_CALENDAR[REUNIAO]["inicio"])
    assert str(data_exp) == "2026-06-12"
    assert mediana == 14.75


def test_reuniao_com_unico_survey_valido():
    focus = pd.DataFrame(
        {
            "reuniao": [REUNIAO],
            "data": ["2026-06-01"],
            "mediana": [14.75],
            "n_respondentes": [40],
            "base_calculo": [0],
        }
    )
    mediana, data_exp, n = selic_esperada(focus, REUNIAO, COPOM_CALENDAR[REUNIAO]["inicio"])
    assert (mediana, str(data_exp), n) == (14.75, "2026-06-01", 40)
