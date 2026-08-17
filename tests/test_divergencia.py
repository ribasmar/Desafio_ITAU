# CopomLens — Testes da divergência ata↔comunicado (direção/magnitude/eixo
# discretos, número derivado por DIVERGENCIA_MAP em código) e dos gates de
# aceite do instrumento v3 (medição sem tocar no alvo).
import importlib
import json
from unittest.mock import MagicMock

import pandas as pd
import pytest

div = importlib.import_module("copom.features.divergencia")
gates = importlib.import_module("copom.features.gates")


def make_doc(numero_reuniao, tipo, texto, available_time="2025-05-13"):
    return {
        "numero_reuniao": numero_reuniao,
        "tipo": tipo,
        "text": texto,
        "available_time": available_time,
        "data_reuniao": "2025-05-07",
    }


@pytest.fixture
def par():
    return make_doc(100, "ata", "ATA longo texto"), make_doc(
        100, "comunicado", "COM curto", available_time="2025-05-07"
    )


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------

def test_build_prompt_preenche_os_dois_documentos(par, tmp_path):
    p = tmp_path / "div.md"
    p.write_text(
        "COM ({data_publicacao_comunicado}): {texto_comunicado} | "
        "ATA ({data_publicacao_ata}): {texto_ata}",
        encoding="utf-8",
    )
    ata, com = par
    preenchido = div.build_prompt(ata, com, p)
    assert "2025-05-07" in preenchido and "2025-05-13" in preenchido
    assert "ATA longo texto" in preenchido and "COM curto" in preenchido


# ---------------------------------------------------------------------------
# divergencia_de (mapa determinístico)
# ---------------------------------------------------------------------------

def test_divergencia_de_mapa():
    assert div.divergencia_de("igual", "nenhuma") == 0.0
    assert div.divergencia_de("ata_mais_hawkish", "leve") == 0.25
    assert div.divergencia_de("ata_mais_hawkish", "clara") == 0.5
    assert div.divergencia_de("ata_mais_hawkish", "forte") == 0.75
    assert div.divergencia_de("ata_mais_dovish", "clara") == -0.5
    assert div.divergencia_de("ata_mais_dovish", "nenhuma") == 0.0


# ---------------------------------------------------------------------------
# _validate
# ---------------------------------------------------------------------------

def test_validate_valido_hawkish_forte():
    out = div._validate(
        {
            "direcao": "ata_mais_hawkish",
            "magnitude": "forte",
            "eixo_divergencia": "riscos",
            "justificativa_ata": "a",
            "justificativa_comunicado": "c",
        }
    )
    assert out["divergencia"] == 0.75
    assert out["direcao"] == "ata_mais_hawkish"


def test_validate_igual_forca_nenhuma_e_nenhum():
    out = div._validate(
        {
            "direcao": "igual",
            "magnitude": "clara",  # inconsistente de propósito
            "eixo_divergencia": "riscos",
            "justificativa_ata": "a",
            "justificativa_comunicado": "c",
        }
    )
    assert out["divergencia"] == 0.0
    assert out["magnitude"] == "nenhuma"
    assert out["eixo_divergencia"] == "nenhum"


def test_validate_direcao_invalida():
    with pytest.raises(ValueError):
        div._validate({"direcao": "vies", "magnitude": "leve",
                       "eixo_divergencia": "riscos"})


def test_validate_magnitude_nenhuma_sem_igual():
    with pytest.raises(ValueError):
        div._validate({"direcao": "ata_mais_hawkish", "magnitude": "nenhuma",
                       "eixo_divergencia": "riscos"})


def test_validate_eixo_invalido():
    with pytest.raises(ValueError):
        div._validate({"direcao": "igual", "magnitude": "nenhuma",
                       "eixo_divergencia": "vies"})


# ---------------------------------------------------------------------------
# extract_divergencia (LLM mockado)
# ---------------------------------------------------------------------------

def _mock_llm(monkeypatch, respostas):
    mock_cls = MagicMock(name="LLMClient")
    mock_inst = mock_cls.return_value
    mock_inst.model = "teste"
    mock_inst.generate = MagicMock(side_effect=respostas)
    monkeypatch.setattr(div, "LLMClient", mock_cls)
    monkeypatch.setattr(div, "_extract_json_from_text", lambda raw: json.loads(raw))
    return mock_cls, mock_inst


def _resposta(direcao, magnitude, eixo="riscos"):
    return json.dumps(
        {
            "direcao": direcao,
            "magnitude": magnitude,
            "eixo_divergencia": eixo,
            "justificativa_ata": "a",
            "justificativa_comunicado": "c",
        }
    )


def test_extract_media_e_estabilidade(par, monkeypatch):
    ata, com = par
    respostas = [
        _resposta("ata_mais_hawkish", "clara"),
        _resposta("ata_mais_hawkish", "leve"),
        _resposta("ata_mais_hawkish", "leve"),
    ]
    _mock_llm(monkeypatch, respostas)
    out = div.extract_divergencia(ata, com, n_runs=3)
    assert round(out["divergencia"], 4) == round((0.5 + 0.25 + 0.25) / 3, 4)
    assert out["stability"]["values"] == [0.5, 0.25, 0.25]
    assert out["direcao"] == "ata_mais_hawkish"
    assert out["numero_reuniao"] == 100
    assert out["available_time"] == "2025-05-13"


def test_extract_mesma_seed_std_zero(par, monkeypatch):
    ata, com = par
    mock_cls, mock_inst = _mock_llm(monkeypatch, [_resposta("igual", "nenhuma", "nenhum")] * 3)
    out = div.extract_divergencia(ata, com, n_runs=3)
    assert out["stability"]["std"] == 0.0
    # mesma seed em todas as runs (determinismo)
    seeds = [c.kwargs.get("seed") for c in mock_inst.generate.call_args_list]
    assert seeds == [42, 42, 42]


def test_extract_todas_falham_devolve_erro(par, monkeypatch):
    ata, com = par
    _mock_llm(monkeypatch, ["{json quebrado", "ainda quebrado", "nao json"])
    monkeypatch.setattr(
        div, "_extract_json_from_text",
        MagicMock(side_effect=ValueError("No JSON")),
    )
    out = div.extract_divergencia(ata, com, n_runs=3)
    assert "error" in out
    assert out["numero_reuniao"] == 100


def test_schema_imposto_no_client(par, monkeypatch):
    ata, com = par
    mock_cls, _ = _mock_llm(monkeypatch, [_resposta("igual", "nenhuma", "nenhum")])
    div.extract_divergencia(ata, com, n_runs=1)
    kwargs = mock_cls.call_args.kwargs
    props = kwargs["json_schema"]["properties"]
    assert props["direcao"]["enum"] == sorted(
        {"ata_mais_hawkish", "igual", "ata_mais_dovish"}
    )
    assert props["magnitude"]["enum"] == sorted(
        {"leve", "clara", "forte", "nenhuma"}
    )


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------

def test_gates_estrutura_e_medidas(tmp_path):
    tone = tmp_path / "tone.jsonl"
    with open(tone, "w", encoding="utf-8") as f:
        for i in range(4):
            f.write(
                json.dumps(
                    {
                        "numero_reuniao": 200 + i,
                        "tipo": "ata",
                        "stance": 0.25 if i % 2 else -0.25,
                        "stance_label": "marginalmente_hawkish" if i % 2 else "marginalmente_dovish",
                        "justificativa": "pressões inflacionárias generalizadas",
                        "stability": {
                            "stance": {"std": 0.0},
                            "incerteza": {"std": 0.0},
                            "conviccao": {"std": 0.0},
                        },
                    }
                )
                + "\n"
            )
    dataset = tmp_path / "dataset.jsonl"
    dias = ["2024-01-30", "2024-02-28", "2024-03-27", "2024-04-30"]
    with open(dataset, "w", encoding="utf-8") as f:
        for i in range(4):
            f.write(
                json.dumps(
                    {
                        "numero_reuniao": 200 + i,
                        "tipo": "ata",
                        "text": "texto",
                        "data_reuniao": dias[i],
                        "available_time": "2024-02-05",
                    }
                )
                + "\n"
            )
    selic = tmp_path / "selic.csv"
    pd.DataFrame(
        {
            "data": pd.to_datetime(
                ["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01", "2024-05-01"]
            ),
            "selic_meta": [10.0, 10.25, 10.25, 10.5, 10.5],
        }
    ).to_csv(selic, index=False)

    g = gates.medir_gates(tone, dataset, selic)
    assert g["n_docs"] == 4
    assert {"eta2_stance_pooled", "justificativa_cita_decisao",
            "frac_std_zero", "mode_share_stance_label"} <= set(g["medido"])
    assert g["medido"]["frac_std_zero"] == 1.0
    assert g["medido"]["justificativa_cita_decisao"] == 0.0


def test_padrao_decisao_detecta_citacao():
    assert gates._PADRAO_DECISAO.search("reduziu a Selic para 17,25% a.a.")
    assert gates._PADRAO_DECISAO.search("corte de 0,75 p.p.")
    assert gates._PADRAO_DECISAO.search("por unanimidade")
    assert not gates._PADRAO_DECISAO.search(
        "balanço de riscos assimétrico e inflação resiliente"
    )
