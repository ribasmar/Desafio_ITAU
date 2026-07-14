# CopomLens — Testes da Camada 3 (surpresa da decisao). Usam fixtures em memoria (sem rede)
# para validar o calculo e, sobretudo, a disciplina point-in-time: a Selic
# esperada vem do ultimo survey Focus ANTERIOR a reuniao, nunca de um posterior.
import pandas as pd
import pytest

from copom.surprise.decision import (
    COPOM_CALENDAR,
    selic_efetiva,
    selic_esperada,
    surpresa_decisao,
)

REUNIAO = "R4/2026"  # decisao em 17/06/2026


@pytest.fixture
def selic_meta():
    return pd.DataFrame(
        {
            "data": ["2026-06-16", "2026-06-17", "2026-06-18", "2026-06-19"],
            "selic_meta": [15.00, 15.00, 14.50, 14.50],
        }
    )


@pytest.fixture
def focus():
    # Inclui um survey POSTERIOR a reuniao (2026-06-20) que NAO pode ser usado.
    return pd.DataFrame(
        {
            "reuniao": [REUNIAO] * 4,
            "data": ["2026-06-01", "2026-06-12", "2026-06-15", "2026-06-20"],
            "mediana": [15.00, 14.75, 14.75, 14.50],
            "media": [15.00, 14.74, 14.76, 14.50],
            "n_respondentes": [40, 52, 55, 50],
            "base_calculo": [0, 0, 0, 0],
        }
    )


def test_selic_efetiva_pos_decisao(selic_meta):
    assert selic_efetiva(selic_meta, COPOM_CALENDAR[REUNIAO]["decisao"]) == 14.50


def test_selic_esperada_com_defasagem_publicacao(focus):
    # Default defasagem=1 dia util: inicio 16/06 (ter) -> corte 15/06 (seg);
    # exige data_survey < 15/06, entao usa o de 12/06 (sex), nao o de 15/06.
    mediana, data_exp, n = selic_esperada(focus, REUNIAO, COPOM_CALENDAR[REUNIAO]["inicio"])
    assert mediana == 14.75
    assert str(data_exp) == "2026-06-12"
    assert n == 52


def test_selic_esperada_sem_defasagem(focus):
    # defasagem=0: corta exatamente no inicio (16/06), aceitando o survey de 15/06.
    mediana, data_exp, n = selic_esperada(
        focus, REUNIAO, COPOM_CALENDAR[REUNIAO]["inicio"], defasagem_dias_uteis=0
    )
    assert str(data_exp) == "2026-06-15"
    assert n == 55


def test_surpresa_uma_reuniao(selic_meta, focus):
    res = surpresa_decisao(REUNIAO, selic_meta, focus)
    assert res.selic_efetiva == 14.50
    assert res.selic_esperada == 14.75
    assert res.surpresa == pytest.approx(-0.25)  # corte maior que o esperado (dovish)


def test_sem_survey_anterior_levanta(focus):
    so_posterior = focus[focus["data"] == "2026-06-20"].copy()
    with pytest.raises(ValueError):
        selic_esperada(so_posterior, REUNIAO, COPOM_CALENDAR[REUNIAO]["inicio"])
