# Testes da Camada 4: a janela expansiva nao pode ver o futuro, o painel
# desordenado tem que falhar alto em vez de vazar lookahead silencioso, e o
# Clark-West precisa detectar ganho quando ele existe de verdade.
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from copom.strategy.sinais import (
    PainelInvalido,
    cauda_superior_normal,
    clark_west,
    comparar_aninhados,
    prever_walk_forward,
    sinal_da_previsao,
    sinal_da_regra,
    validar_painel,
)


def painel_sintetico(n: int = 60, seed: int = 7, com_sinal: bool = False) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    surpresa = rng.normal(size=n)
    lex = rng.normal(size=n)
    ruido = rng.normal(scale=5.0, size=n)
    alvo = (8.0 * surpresa + 6.0 * lex + ruido) if com_sinal else ruido
    return pd.DataFrame({
        "data_publicacao_ata": pd.date_range("2010-01-04", periods=n, freq="35D"),
        "reacao_bps": alvo,
        "surpresa_decisao": surpresa,
        "lex_score": lex,
        "lex_delta": np.concatenate([[0.0], np.diff(lex)]),
    })


class TestValidacao:
    def test_painel_desordenado_falha(self):
        p = painel_sintetico(50).sort_values("reacao_bps")
        with pytest.raises(PainelInvalido, match="ordenado"):
            validar_painel(p, ["surpresa_decisao"])

    def test_data_duplicada_falha(self):
        p = painel_sintetico(50)
        p.loc[10, "data_publicacao_ata"] = p.loc[9, "data_publicacao_ata"]
        with pytest.raises(PainelInvalido, match="mesma data"):
            validar_painel(p, ["surpresa_decisao"])

    def test_nan_em_feature_falha(self):
        p = painel_sintetico(50)
        p.loc[3, "lex_score"] = np.nan
        with pytest.raises(PainelInvalido, match="NaN"):
            validar_painel(p, ["lex_score"])

    def test_coluna_ausente_falha(self):
        with pytest.raises(PainelInvalido, match="ausentes"):
            validar_painel(painel_sintetico(50), ["tom_llm"])

    def test_treino_minimo_menor_que_features_falha(self):
        with pytest.raises(PainelInvalido, match="graus de liberdade"):
            prever_walk_forward(painel_sintetico(50), ["surpresa_decisao", "lex_score"], treino_minimo=3)

    def test_painel_curto_demais_falha(self):
        with pytest.raises(PainelInvalido, match="nao excede"):
            prever_walk_forward(painel_sintetico(30), ["surpresa_decisao"], treino_minimo=40)


class TestSemLookahead:
    def test_primeiras_previsoes_sao_nan(self):
        p = prever_walk_forward(painel_sintetico(60), ["surpresa_decisao"], treino_minimo=40)
        assert np.isnan(p[:40]).all()
        assert not np.isnan(p[40:]).any()

    def test_alterar_o_futuro_nao_muda_o_passado(self):
        """A prova operacional de ausencia de lookahead: mexer no alvo dos
        eventos posteriores nao pode alterar previsao ja emitida."""
        base = painel_sintetico(60)
        p1 = prever_walk_forward(base, ["surpresa_decisao", "lex_score"], treino_minimo=40)

        adulterado = base.copy()
        adulterado.loc[50:, "reacao_bps"] = 999.0
        p2 = prever_walk_forward(adulterado, ["surpresa_decisao", "lex_score"], treino_minimo=40)

        np.testing.assert_allclose(p1[40:50], p2[40:50], rtol=1e-12)
        assert not np.allclose(p1[51:], p2[51:])

    def test_previsao_do_evento_t_ignora_a_propria_reacao(self):
        base = painel_sintetico(60)
        p1 = prever_walk_forward(base, ["surpresa_decisao"], treino_minimo=40)
        adulterado = base.copy()
        adulterado.loc[45, "reacao_bps"] += 500.0
        p2 = prever_walk_forward(adulterado, ["surpresa_decisao"], treino_minimo=40)
        assert p1[45] == pytest.approx(p2[45])


class TestCaudaNormal:
    """Trava a p-valor contra tabela conhecida — sem depender do scipy estar instalado."""

    @pytest.mark.parametrize(
        "z, esperado",
        [(0.0, 0.5), (1.0, 0.158655253931), (1.644853627, 0.05), (1.959963985, 0.025),
         (2.326347874, 0.01), (-1.0, 0.841344746069), (3.5, 0.000232629079)],
    )
    def test_bate_com_a_tabela_normal(self, z, esperado):
        assert cauda_superior_normal(z) == pytest.approx(esperado, abs=1e-9)

    def test_nao_colapsa_para_zero_na_cauda_extrema(self):
        """`1 - cdf` devolveria 0 aqui por cancelamento; a erfc preserva o valor."""
        assert 0 < cauda_superior_normal(8.5) < 1e-16

    def test_e_simetrica(self):
        for z in (0.3, 1.7, 4.2):
            assert cauda_superior_normal(z) + cauda_superior_normal(-z) == pytest.approx(1.0)


class TestClarkWest:
    def test_detecta_ganho_quando_existe(self):
        p = painel_sintetico(120, com_sinal=True)
        r = comparar_aninhados(p, rotulo="com_sinal")
        assert r.clark_west["M1_surpresa_sobre_M0_media"]["cw_stat"] > 0
        assert r.clark_west["M1_surpresa_sobre_M0_media"]["p_valor_unicaudal"] < 0.05

    def test_nao_inventa_ganho_em_ruido_puro(self):
        r = comparar_aninhados(painel_sintetico(120, seed=11, com_sinal=False))
        assert r.clark_west["M2_surpresa_tom_sobre_M1_surpresa"]["p_valor_unicaudal"] > 0.05

    def test_previsoes_identicas_sao_degeneradas(self):
        y = np.array([1.0, -2.0, 3.0, 0.5, -1.5])
        igual = np.zeros(5)
        assert clark_west(y, igual, igual)["degenerado"] is True

    def test_amostra_minuscula_falha(self):
        with pytest.raises(ValueError, match="pequena demais"):
            clark_west(np.array([1.0, 2.0]), np.zeros(2), np.zeros(2))

    def test_tamanhos_diferentes_falham(self):
        with pytest.raises(ValueError, match="tamanhos diferentes"):
            clark_west(np.zeros(5), np.zeros(4), np.zeros(5))


class TestSinais:
    def test_nan_vira_posicao_zero_e_nao_herda_anterior(self):
        s = sinal_da_previsao(np.array([2.0, np.nan, -3.0]))
        np.testing.assert_array_equal(s, [1.0, 0.0, -1.0])

    def test_regra_usa_o_sinal_da_feature(self):
        s = sinal_da_regra(pd.Series([0.4, -0.1, 0.0, np.nan]))
        np.testing.assert_array_equal(s, [1.0, -1.0, 0.0, 0.0])

    def test_comparar_aninhados_reporta_contagens_coerentes(self):
        r = comparar_aninhados(painel_sintetico(100), treino_minimo=40)
        assert r.n_total == 100
        assert r.n_oos == 60
        assert r.metricas["M0_media"]["r2_oos"] == 0.0
