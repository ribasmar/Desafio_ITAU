# Testes do join dos scores LLM: schema e faixas invalidas tem que falhar alto,
# cobertura parcial so entra quando pedida explicitamente e sai registrada na
# auditoria, o delta respeita a ordem cronologica de publicacao e a divergencia
# so existe onde ata e comunicado da mesma reuniao foram ambos escorados.
from __future__ import annotations

import json

import pandas as pd
import pytest

from copom.features.tom_llm import ScoresInvalidos, anexar_tom_llm, carregar_scores


def gravar_jsonl(caminho, linhas):
    caminho.write_text("\n".join(json.dumps(l) for l in linhas), encoding="utf-8")
    return caminho


def score(numero, stance, tipo="ata", **extras):
    return {"numero_reuniao": numero, "tipo": tipo, "stance": stance, **extras}


def painel_minimo(reunioes):
    return pd.DataFrame({
        "numero_reuniao": reunioes,
        "data_publicacao_ata": pd.date_range("2010-01-04", periods=len(reunioes), freq="45D"),
        "reacao_bps": [1.0] * len(reunioes),
    })


class TestCarga:
    def test_arquivo_ausente_explica_o_schema(self, tmp_path):
        with pytest.raises(ScoresInvalidos, match="Formato esperado"):
            carregar_scores(tmp_path / "scores_llm.jsonl")

    def test_stance_fora_da_faixa_falha(self, tmp_path):
        arq = gravar_jsonl(tmp_path / "s.jsonl", [score(116, 1.4)])
        with pytest.raises(ScoresInvalidos, match="fora de"):
            carregar_scores(arq)

    def test_campo_obrigatorio_ausente_falha(self, tmp_path):
        arq = gravar_jsonl(tmp_path / "s.jsonl", [{"numero_reuniao": 116, "tipo": "ata"}])
        with pytest.raises(ScoresInvalidos, match="obrigatorios"):
            carregar_scores(arq)

    def test_documento_escorado_duas_vezes_falha(self, tmp_path):
        arq = gravar_jsonl(tmp_path / "s.jsonl", [score(116, 0.1), score(116, 0.2)])
        with pytest.raises(ScoresInvalidos, match="mais de uma vez"):
            carregar_scores(arq)


class TestJoin:
    def test_cobertura_total_anexa_nivel_e_delta_na_ordem_cronologica(self, tmp_path):
        arq = gravar_jsonl(tmp_path / "s.jsonl", [score(116, 0.1), score(117, 0.4), score(118, 0.2)])
        df, auditoria = anexar_tom_llm(painel_minimo([116, 117, 118]), carregar_scores(arq))
        assert list(df["llm_stance"]) == [0.1, 0.4, 0.2]
        assert list(df["llm_stance_delta"]) == pytest.approx([0.0, 0.3, -0.2])
        assert auditoria["reunioes_descartadas_sem_score"] == []

    def test_cobertura_parcial_sem_permissao_falha(self, tmp_path):
        arq = gravar_jsonl(tmp_path / "s.jsonl", [score(116, 0.1)])
        with pytest.raises(ScoresInvalidos, match="sem score de ata"):
            anexar_tom_llm(painel_minimo([116, 117]), carregar_scores(arq))

    def test_cobertura_parcial_permitida_registra_o_corte(self, tmp_path):
        arq = gravar_jsonl(tmp_path / "s.jsonl", [score(116, 0.1)])
        df, auditoria = anexar_tom_llm(painel_minimo([116, 117]), carregar_scores(arq), permitir_parcial=True)
        assert list(df["numero_reuniao"]) == [116]
        assert auditoria["reunioes_descartadas_sem_score"] == [117]

    def test_divergencia_so_onde_o_comunicado_foi_escorado(self, tmp_path):
        arq = gravar_jsonl(tmp_path / "s.jsonl", [
            score(116, 0.5), score(116, 0.2, tipo="comunicado"), score(117, -0.1),
        ])
        df, auditoria = anexar_tom_llm(painel_minimo([116, 117]), carregar_scores(arq))
        assert df.loc[0, "llm_divergencia"] == pytest.approx(0.3)
        assert pd.isna(df.loc[1, "llm_divergencia"])
        assert auditoria["reunioes_com_divergencia"] == 1
