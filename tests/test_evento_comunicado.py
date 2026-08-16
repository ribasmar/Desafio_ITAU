# Testes da janela de evento do comunicado: D0 tem que ser o ultimo fechamento
# antes do anuncio e D1 o primeiro depois, fim de semana nao pode virar reacao
# errada, buraco na serie tem que falhar alto, e a janela do comunicado nunca
# pode invadir a publicacao da ata — senao os dois eventos deixam de ser
# separaveis e a comparacao pareada perde o sentido.
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from copom.surprise.evento import (
    JanelaInvalida,
    dias_de_evento,
    estudo_evento,
    janela_comunicado,
    montar_painel_comunicado,
    variacoes_diarias,
)


def serie_di(datas: list[str], taxas: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"data": pd.to_datetime(datas), "di1y": taxas})


def serie_util(inicio: str = "2010-01-04", n: int = 260, seed: int = 11) -> pd.DataFrame:
    datas = pd.bdate_range(inicio, periods=n)
    rng = np.random.default_rng(seed)
    return pd.DataFrame({"data": datas, "di1y": 12.0 + np.cumsum(rng.normal(scale=0.03, size=n))})


class TestJanelaComunicado:
    def test_reuniao_em_dia_util_usa_o_proprio_fechamento_como_d0(self):
        di = serie_di(["2010-03-08", "2010-03-09", "2010-03-10"], [12.00, 12.25, 12.10])
        j = janela_comunicado(di, pd.Timestamp("2010-03-09"))
        assert j["d0_comunicado"] == pd.Timestamp("2010-03-09")
        assert j["d1_comunicado"] == pd.Timestamp("2010-03-10")
        assert j["reacao_comunicado_bps"] == pytest.approx(-15.0)

    def test_fim_de_semana_nao_distorce_a_janela(self):
        di = serie_di(["2010-03-05", "2010-03-08"], [12.00, 12.40])
        j = janela_comunicado(di, pd.Timestamp("2010-03-06"))
        assert j["d0_comunicado"] == pd.Timestamp("2010-03-05")
        assert j["d1_comunicado"] == pd.Timestamp("2010-03-08")
        assert j["reacao_comunicado_bps"] == pytest.approx(40.0)

    def test_buraco_na_serie_falha_em_vez_de_virar_reacao(self):
        di = serie_di(["2010-03-01", "2010-03-20"], [12.00, 13.00])
        with pytest.raises(JanelaInvalida, match="gap"):
            janela_comunicado(di, pd.Timestamp("2010-03-02"))

    def test_reuniao_fora_da_janela_viva_falha(self):
        di = serie_di(["2010-03-08", "2010-03-09"], [12.0, 12.1])
        with pytest.raises(JanelaInvalida, match="fora da janela"):
            janela_comunicado(di, pd.Timestamp("2009-01-01"))
        with pytest.raises(JanelaInvalida, match="fora da janela"):
            janela_comunicado(di, pd.Timestamp("2010-03-09") + pd.Timedelta(days=30))

    def test_serie_desordenada_falha_alto(self):
        di = serie_di(["2010-03-09", "2010-03-08"], [12.1, 12.0])
        with pytest.raises(JanelaInvalida, match="ordenada"):
            janela_comunicado(di, pd.Timestamp("2010-03-09"))

    def test_alterar_fechamentos_futuros_nao_muda_a_reacao(self):
        di = serie_util()
        reuniao = di["data"].iloc[30]
        antes = janela_comunicado(di, reuniao)["reacao_comunicado_bps"]
        depois_do_evento = di["data"] > di["data"].iloc[31]
        alterada = di.copy()
        alterada.loc[depois_do_evento, "di1y"] += 5.0
        assert janela_comunicado(alterada, reuniao)["reacao_comunicado_bps"] == pytest.approx(antes)


def painel_minimo(di: pd.DataFrame, reunioes: list[int]) -> pd.DataFrame:
    linhas = []
    for k, numero in enumerate(reunioes):
        data_reuniao = di["data"].iloc[10 + 20 * k]
        linhas.append({
            "numero_reuniao": numero,
            "data_reuniao": data_reuniao,
            "data_publicacao_ata": data_reuniao + pd.Timedelta(days=8),
            "surpresa_decisao": [0.0, 0.25, -0.25][k % 3],
        })
    return pd.DataFrame(linhas)


class TestPainelComunicado:
    def test_painel_cobre_todas_as_reunioes_e_preserva_a_surpresa(self):
        di = serie_util()
        painel = painel_minimo(di, [116, 117, 118])
        com = montar_painel_comunicado(painel, di)
        assert list(com["numero_reuniao"]) == [116, 117, 118]
        assert (com["d1_comunicado"] > com["d0_comunicado"]).all()
        assert (com["surpresa_decisao"] == painel["surpresa_decisao"]).all()

    def test_janela_que_invade_a_publicacao_da_ata_falha(self):
        di = serie_util()
        painel = painel_minimo(di, [116])
        painel["data_publicacao_ata"] = painel["data_reuniao"]
        with pytest.raises(JanelaInvalida, match="invadiu"):
            montar_painel_comunicado(painel, di)


class TestEstudoEvento:
    def test_categorias_sao_disjuntas_e_cobrem_a_janela(self):
        di = serie_util()
        painel = painel_minimo(di, [116, 117, 118])
        com = montar_painel_comunicado(painel, di)
        eventos = dias_de_evento(com)
        assert not eventos["comunicado"] & eventos["ata"]

        estudo = estudo_evento(di, com)
        assert estudo["comunicado"]["n_dias"] == 3
        assert estudo["ata"]["n_dias"] == 3
        var = variacoes_diarias(di)
        inicio, fim = com["d0_comunicado"].min(), com["data_publicacao_ata"].max()
        n_janela = int(((var["data"] >= inicio) & (var["data"] <= fim)).sum())
        assert estudo["dia_comum"]["n_dias"] == n_janela - 6
