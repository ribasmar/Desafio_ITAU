# CopomLens — Testes do instrumento pareado (camada 2→4):
# stance(ata) − stance(comunicado) por reunião, com funil de descartes
# explícito (nunca default) e diagnóstico de contaminação pela decisão.
import json
import math

import pandas as pd
import pytest

from copom.features.pareamento import (
    carregar_tone,
    diagnostico_contaminacao,
    eta2_anova,
    parear,
    r2_linear,
)


def make_tone(numero_reuniao, tipo, stance, prompt_version="copom_v3",
              model_id="qwen/qwen3-32b", **extra):
    row = {
        "numero_reuniao": numero_reuniao,
        "tipo": tipo,
        "stance": stance,
        "forward_guidance": "neutro",
        "prompt_version": prompt_version,
        "model_id": model_id,
        "available_time": "2025-05-13",
    }
    row.update(extra)
    return row


def make_doc(numero_reuniao, tipo, texto, data_reuniao="2025-05-07"):
    return {
        "numero_reuniao": numero_reuniao,
        "tipo": tipo,
        "text": texto,
        "data_reuniao": data_reuniao,
        "available_time": "2025-05-13",
    }


@pytest.fixture
def docs():
    return [
        make_doc(100, "ata", "elevação e pressão inflacionária"),
        make_doc(100, "comunicado", "elevação da Selic"),
        make_doc(101, "ata", "redução e arrefecimento"),
        make_doc(101, "comunicado", "redução da Selic"),
        make_doc(102, "ata", "manutenção com vigilância"),
    ]


# ---------------------------------------------------------------------------
# parear(): pares completos
# ---------------------------------------------------------------------------

def test_par_completo_gera_pareado(docs):
    tone = [
        make_tone(100, "ata", 0.5),
        make_tone(100, "comunicado", 0.25),
    ]
    pares, descartes = parear(tone, docs)
    assert len(pares) == 1
    assert len(descartes) == 0
    row = pares.iloc[0]
    assert row["numero_reuniao"] == 100
    assert row["stance_ata"] == 0.5
    assert row["stance_com"] == 0.25
    assert row["stance_pareado"] == 0.25


def test_pareado_arredondado_4_casas(docs):
    tone = [
        make_tone(100, "ata", 0.5),
        make_tone(100, "comunicado", 0.3333),
    ]
    pares, _ = parear(tone, docs)
    assert pares.iloc[0]["stance_pareado"] == round(0.5 - 0.3333, 4)


def test_stances_iguais_pareado_zero(docs):
    tone = [
        make_tone(100, "ata", -0.25),
        make_tone(100, "comunicado", -0.25),
    ]
    pares, _ = parear(tone, docs)
    assert pares.iloc[0]["stance_pareado"] == 0.0


def test_available_time_vem_da_ata(docs):
    tone = [
        make_tone(100, "ata", 0.5, available_time="2025-05-13"),
        make_tone(100, "comunicado", 0.25, available_time="2025-05-07"),
    ]
    pares, _ = parear(tone, docs)
    assert pares.iloc[0]["available_time_ata"] == "2025-05-13"


def test_lex_pareado_calculado_dos_textos(docs):
    tone = [
        make_tone(100, "ata", 0.5),
        make_tone(100, "comunicado", 0.25),
    ]
    pares, _ = parear(tone, docs)
    assert pares.iloc[0]["lex_ata"] is not None
    assert pares.iloc[0]["lex_com"] is not None
    assert pares.iloc[0]["lex_pareado"] == round(
        pares.iloc[0]["lex_ata"] - pares.iloc[0]["lex_com"], 4
    )


# ---------------------------------------------------------------------------
# parear(): descartes explícitos (falha-alto)
# ---------------------------------------------------------------------------

def test_sem_tone_comunicado_vira_descarte(docs):
    tone = [make_tone(102, "ata", 0.5)]
    pares, descartes = parear(tone, docs)
    assert len(pares) == 0
    assert len(descartes) == 1
    assert descartes[0]["numero_reuniao"] == 102
    assert "comunicado" in descartes[0]["motivo"]


def test_sem_tone_ata_vira_descarte(docs):
    tone = [make_tone(102, "comunicado", 0.5)]
    pares, descartes = parear(tone, docs)
    assert len(pares) == 0
    assert len(descartes) == 1
    assert "ata" in descartes[0]["motivo"]


def test_prompt_version_divergente_vira_descarte(docs):
    tone = [
        make_tone(100, "ata", 0.5, prompt_version="copom_v3"),
        make_tone(100, "comunicado", 0.25, prompt_version="copom_v2"),
    ]
    pares, descartes = parear(tone, docs)
    assert len(pares) == 0
    assert len(descartes) == 1
    assert "prompt_version" in descartes[0]["motivo"]


def test_model_id_divergente_vira_descarte(docs):
    tone = [
        make_tone(100, "ata", 0.5, model_id="qwen/qwen3-32b"),
        make_tone(100, "comunicado", 0.25, model_id="qwen/qwen2.5-14b"),
    ]
    pares, descartes = parear(tone, docs)
    assert len(pares) == 0
    assert len(descartes) == 1
    assert "model_id" in descartes[0]["motivo"]


def test_descarrete_nao_inventa_stance(docs):
    tone = [
        make_tone(102, "ata", 0.5),
        make_tone(102, "comunicado", None),
    ]
    pares, descartes = parear(tone, docs)
    assert len(pares) == 0
    assert len(descartes) == 1


# ---------------------------------------------------------------------------
# carregar_tone(): linhas de erro ignoradas
# ---------------------------------------------------------------------------

def test_carregar_tone_ignora_erros(tmp_path):
    p = tmp_path / "tone.jsonl"
    p.write_text(
        json.dumps(make_tone(100, "ata", 0.5))
        + "\n"
        + json.dumps({"numero_reuniao": 100, "tipo": "comunicado", "error": "x"})
        + "\n"
        + json.dumps(make_tone(101, "ata", -0.5))
        + "\n",
        encoding="utf-8",
    )
    rows = carregar_tone(p)
    assert len(rows) == 2


# ---------------------------------------------------------------------------
# Diagnóstico: eta² e R²
# ---------------------------------------------------------------------------

def test_eta2_anova_perfeito():
    y = pd.Series([0.0, 0.0, 1.0, 1.0])
    x = pd.Series(["a", "a", "b", "b"])
    assert eta2_anova(y, x) == pytest.approx(1.0)


def test_eta2_anova_nulo():
    y = pd.Series([0.0, 1.0, 0.0, 1.0])
    x = pd.Series(["a", "a", "b", "b"])
    assert eta2_anova(y, x) == pytest.approx(0.0)


def test_eta2_anova_sem_variacao_no_grupo_e_nan():
    y = pd.Series([1.0, 1.0, 1.0])
    x = pd.Series(["a", "a", "a"])
    assert math.isnan(eta2_anova(y, x))


def test_r2_linear_perfeito():
    y = pd.Series([0.0, 1.0, 2.0])
    x = pd.Series([0.0, 1.0, 2.0])
    assert r2_linear(y, x) == pytest.approx(1.0)


def test_r2_linear_nulo():
    y = pd.Series([0.0, 1.0, 0.0, 1.0])
    x = pd.Series([1.0, 1.0, 2.0, 2.0])
    assert r2_linear(y, x) == pytest.approx(0.0)


def test_diagnostico_estrutura(docs, tmp_path):
    selic = tmp_path / "selic_meta.csv"
    pd.DataFrame(
        {
            "data": pd.to_datetime(["2025-05-06", "2025-05-08"]),
            "selic_meta": [10.0, 10.5],
        }
    ).to_csv(selic, index=False)
    tone = [
        make_tone(100, "ata", 0.5),
        make_tone(100, "comunicado", 0.25),
    ]
    diag = diagnostico_contaminacao(tone, docs, selic)
    assert set(diag) == {"amostra_bruta_llm", "amostra_bruta_lexico", "pareado"}
    for chave in ("stance_ata", "stance_com", "stance_pareado",
                  "lex_ata", "lex_com", "lex_pareado"):
        assert {"n", "eta2", "r2_linear"} <= set(diag["pareado"][chave])
    assert diag["pareado"]["stance_pareado"]["n"] == 1
