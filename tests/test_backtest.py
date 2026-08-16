# Testes da Camada 5: o P&L tem que respeitar a convencao de sinal, o custo so
# incide sobre quem esta posicionado, e o teste de permutacao precisa se recusar
# a rodar sobre posicao constante — bug real, em que o p-valor virava ruido de
# ponto flutuante e parecia significancia de 0,0000.
from __future__ import annotations

import numpy as np
import pytest

from copom.backtest.motor import (
    BacktestInvalido,
    PermutacaoDegenerada,
    metricas,
    sensibilidade_custo,
    simular,
    permutacao_contra_acaso,
)


class TestConvencaoDeSinal:
    def test_pagar_fixo_ganha_quando_a_taxa_sobe(self):
        r = simular(np.array([1.0, 1.0]), np.array([10.0, 20.0]), custo_bps=0.0)
        np.testing.assert_array_equal(r.pnl_bps, [10.0, 20.0])

    def test_receber_fixo_ganha_quando_a_taxa_cai(self):
        r = simular(np.array([-1.0, -1.0]), np.array([-10.0, -20.0]), custo_bps=0.0)
        np.testing.assert_array_equal(r.pnl_bps, [10.0, 20.0])

    def test_posicao_zero_nao_ganha_nem_paga_custo(self):
        r = simular(np.array([0.0, 1.0]), np.array([50.0, 10.0]), custo_bps=2.0)
        np.testing.assert_array_equal(r.pnl_bps, [0.0, 8.0])
        assert r.metricas["n_trades"] == 1

    def test_equity_e_a_soma_acumulada(self):
        r = simular(np.array([1.0, 1.0, -1.0]), np.array([5.0, 5.0, -5.0]), custo_bps=0.0)
        np.testing.assert_array_equal(r.equity_bps, [5.0, 10.0, 15.0])


class TestEntradasInvalidas:
    def test_tamanhos_diferentes_falham(self):
        with pytest.raises(BacktestInvalido, match="tamanhos diferentes"):
            simular(np.zeros(3), np.zeros(4))

    def test_custo_negativo_falha(self):
        with pytest.raises(BacktestInvalido, match="subsídio|subsidio"):
            simular(np.ones(3), np.zeros(3), custo_bps=-1.0)

    def test_nan_falha_em_vez_de_propagar(self):
        with pytest.raises(BacktestInvalido, match="NaN"):
            simular(np.array([1.0, np.nan]), np.array([1.0, 2.0]))

    def test_um_evento_so_nao_tem_dispersao(self):
        with pytest.raises(BacktestInvalido, match="indefinid"):
            metricas(np.array([1.0]), np.array([1.0]))

    def test_eventos_por_ano_zero_falha(self):
        with pytest.raises(BacktestInvalido, match="positivo"):
            simular(np.ones(3), np.zeros(3), eventos_por_ano=0.0)


class TestMetricas:
    def test_drawdown_mede_do_pico_e_e_negativo(self):
        r = simular(np.ones(4), np.array([10.0, -30.0, 5.0, 5.0]), custo_bps=0.0)
        assert r.metricas["max_drawdown_bps"] == -30.0

    def test_drawdown_zero_quando_so_sobe(self):
        r = simular(np.ones(3), np.array([1.0, 2.0, 3.0]), custo_bps=0.0)
        assert r.metricas["max_drawdown_bps"] == 0.0

    def test_pnl_constante_tem_sharpe_zero_e_nao_divide_por_zero(self):
        r = simular(np.ones(5), np.full(5, 7.0), custo_bps=0.0)
        assert r.metricas["sharpe_anual"] == 0.0

    def test_hit_rate_ignora_eventos_sem_posicao(self):
        r = simular(np.array([1.0, 0.0, 1.0]), np.array([10.0, -99.0, -10.0]), custo_bps=0.0)
        assert r.metricas["hit_rate"] == 0.5

    def test_giro_reflete_a_fracao_posicionada(self):
        r = simular(np.array([1.0, 0.0, -1.0, 0.0]), np.zeros(4), custo_bps=0.0)
        assert r.metricas["giro"] == 0.5


class TestCusto:
    def test_custo_incide_por_trade_e_nao_por_evento(self):
        pos = np.array([1.0, 0.0, -1.0])
        r = simular(pos, np.zeros(3), custo_bps=1.5)
        assert r.metricas["pnl_total_bps"] == -3.0

    def test_sensibilidade_e_monotonicamente_decrescente(self):
        rng = np.random.default_rng(3)
        pos = rng.choice([-1.0, 1.0], size=60)
        s = sensibilidade_custo(pos, rng.normal(scale=10, size=60))
        valores = [s[k] for k in ("0", "0.5", "1", "2")]
        assert valores == sorted(valores, reverse=True)


class TestPermutacao:
    def test_posicao_constante_e_recusada(self):
        """Com posicao constante, permutar retornos nao muda media nem desvio:
        qualquer p-valor ali e artefato numerico."""
        with pytest.raises(PermutacaoDegenerada, match="constante"):
            permutacao_contra_acaso(np.full(40, -1.0), np.random.default_rng(1).normal(size=40))

    def test_posicao_constante_entre_negociados_tambem_e_recusada(self):
        pos = np.where(np.arange(40) % 3 == 0, 0.0, 1.0)
        with pytest.raises(PermutacaoDegenerada):
            permutacao_contra_acaso(pos, np.random.default_rng(2).normal(size=40))

    def test_sinal_verdadeiro_bate_o_acaso(self):
        rng = np.random.default_rng(5)
        reacao = rng.normal(scale=10.0, size=80)
        r = permutacao_contra_acaso(np.sign(reacao), reacao, custo_bps=0.0, n_sorteios=800)
        assert r["p_valor_empirico"] < 0.01

    def test_sinal_aleatorio_nao_bate_o_acaso(self):
        rng = np.random.default_rng(9)
        r = permutacao_contra_acaso(
            rng.choice([-1.0, 1.0], size=80), rng.normal(scale=10.0, size=80), custo_bps=0.0, n_sorteios=800
        )
        assert r["p_valor_empirico"] > 0.05

    def test_e_reprodutivel_pela_seed(self):
        rng = np.random.default_rng(4)
        pos, reacao = rng.choice([-1.0, 1.0], size=50), rng.normal(size=50)
        a = permutacao_contra_acaso(pos, reacao, n_sorteios=400, seed=123)
        b = permutacao_contra_acaso(pos, reacao, n_sorteios=400, seed=123)
        assert a == b
