# CopomLens — Testes do baseline léxico (task #5): contagem por ocorrências com
# fronteira de palavra, score em [-1, +1], casos neutro/vazio e sanidade das
# listas de termos (sem sobreposição hawkish/dovish, versão presente).
import pytest

from copom.features.lexico import (
    LEXICO_VERSAO,
    PALAVRAS_DOVISH,
    PALAVRAS_HAWKISH,
    calcular_lexico,
)


def test_score_hawkish_puro():
    r = calcular_lexico("A elevação da inflação exige aperto e vigilância.")
    assert r["n_hawkish"] == 3
    assert r["n_dovish"] == 0
    assert r["score"] == 1.0


def test_score_dovish_puro():
    r = calcular_lexico("A desaceleração e o arrefecimento apontam queda.")
    assert r["n_dovish"] == 3
    assert r["score"] == -1.0


def test_ocorrencias_multiplas_contam():
    r = calcular_lexico("Elevação, elevação e mais elevação.")
    assert r["n_hawkish"] == 3
    assert r["palavras_hawkish"]["elevação"] == 3


def test_score_misto_ponderado_por_ocorrencia():
    r = calcular_lexico("alta alta queda")  # (2 − 1) / 3
    assert r["score"] == pytest.approx(0.3333, abs=1e-4)


def test_fronteira_de_palavra_evita_substring():
    r = calcular_lexico("A plateia exaltada aplaudiu.")  # 'alta' em 'exaltada'
    assert r["n_hawkish"] == 0


def test_case_insensitive():
    assert calcular_lexico("ELEVAÇÃO")["n_hawkish"] == 1


def test_texto_neutro_score_zero():
    r = calcular_lexico("O comitê se reuniu conforme o calendário.")
    assert r["score"] == 0.0
    assert r["n_hawkish"] == 0 and r["n_dovish"] == 0


def test_texto_vazio():
    assert calcular_lexico("")["score"] == 0.0


def test_listas_sem_sobreposicao():
    assert not set(PALAVRAS_HAWKISH) & set(PALAVRAS_DOVISH)


def test_versao_do_lexico_definida():
    assert LEXICO_VERSAO
