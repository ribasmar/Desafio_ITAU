"""
Testes unitários de extract_tone() (camada 2 — issue #4).

Cobrem os três critérios de aceite: (1) estrutura JSON conforme o schema do
README, (2) execução n_runs com estatísticas de estabilidade, (3) gravação de
model_id e seed junto ao score. LLMClient e exec_prompt são mockados no
namespace de extract_tone — a função não faz rede nem valida faixas/categorias
(responsabilidade de promptExec.execute).
"""

import importlib
import json
import statistics
from unittest.mock import MagicMock

import pytest

# O __init__ de copom.features re-exporta a função extract_tone, sombreando o
# atributo homônimo do submódulo; import_module recupera o módulo de sys.modules.
et = importlib.import_module("copom.features.extract_tone")

_NUMERIC_FIELDS = ["stance", "stance_delta", "incerteza", "conviccao"]
_SCHEMA_FIELDS = [
    "stance",
    "stance_delta",
    "forward_guidance",
    "incerteza",
    "conviccao",
    "justificativa",
]


def make_run(
    stance=0.3,
    stance_delta=0.0,
    incerteza=0.4,
    conviccao=0.6,
    forward_guidance="aperto",
    justificativa="trecho citado",
):
    return {
        "stance": stance,
        "stance_delta": stance_delta,
        "incerteza": incerteza,
        "conviccao": conviccao,
        "forward_guidance": forward_guidance,
        "justificativa": justificativa,
    }


def make_document(**overrides):
    doc = {
        "text": "texto do documento do Copom",
        "tipo": "ata",
        "available_time": "2025-05-13",
        "numero_reuniao": 270,
    }
    doc.update(overrides)
    return doc


@pytest.fixture
def mocks(monkeypatch):
    """Substitui LLMClient e exec_prompt no módulo extract_tone.

    Retorna (mock_client_cls, mock_instance, mock_exec). O patch é feito em
    copom.features.extract_tone porque exec_prompt/LLMClient já foram
    importados para lá; patchear o módulo de origem não afeta esses nomes.
    """
    mock_client_cls = MagicMock(name="LLMClient")
    mock_instance = mock_client_cls.return_value
    mock_instance.model = "qwen2.5:7b"

    mock_exec = MagicMock(name="exec_prompt")
    mock_exec.return_value = make_run()

    monkeypatch.setattr(et, "LLMClient", mock_client_cls)
    monkeypatch.setattr(et, "exec_prompt", mock_exec)
    return mock_client_cls, mock_instance, mock_exec


# ---------------------------------------------------------------------------
# Critério 1 — JSON válido conforme o schema do README
# ---------------------------------------------------------------------------

def test_output_contem_campos_do_schema(mocks):
    out = et.extract_tone(make_document(), prompt_path="prompts/copom_v1.md")
    for key in _SCHEMA_FIELDS:
        assert key in out


def test_output_serializavel_em_json(mocks):
    out = et.extract_tone(make_document(), prompt_path="prompts/copom_v1.md")
    json.dumps(out)


def test_forward_guidance_vem_do_ultimo_run(mocks):
    _, _, mock_exec = mocks
    mock_exec.side_effect = [
        make_run(forward_guidance="aperto"),
        make_run(forward_guidance="manutencao"),
        make_run(forward_guidance="afrouxamento"),
    ]
    out = et.extract_tone(make_document(), n_runs=3, prompt_path="prompts/copom_v1.md")
    assert out["forward_guidance"] == "afrouxamento"


def test_forward_guidance_ausente_vira_none(mocks):
    _, _, mock_exec = mocks
    run = make_run()
    del run["forward_guidance"]
    mock_exec.return_value = run
    out = et.extract_tone(make_document(), prompt_path="prompts/copom_v1.md")
    assert out["forward_guidance"] is None


def test_justificativa_vem_do_ultimo_run(mocks):
    _, _, mock_exec = mocks
    mock_exec.side_effect = [
        make_run(justificativa="a"),
        make_run(justificativa="b"),
        make_run(justificativa="c"),
    ]
    out = et.extract_tone(make_document(), n_runs=3, prompt_path="prompts/copom_v1.md")
    assert out["justificativa"] == "c"


def test_justificativa_ausente_vira_string_vazia(mocks):
    _, _, mock_exec = mocks
    run = make_run()
    del run["justificativa"]
    mock_exec.return_value = run
    out = et.extract_tone(make_document(), prompt_path="prompts/copom_v1.md")
    assert out["justificativa"] == ""


def test_metadados_do_documento_preservados(mocks):
    doc = make_document(
        numero_reuniao=271, tipo="comunicado", available_time="2025-06-18"
    )
    out = et.extract_tone(doc, prompt_path="prompts/copom_v1.md")
    assert out["numero_reuniao"] == 271
    assert out["tipo"] == "comunicado"
    assert out["available_time"] == "2025-06-18"


def test_prompt_version_do_stem(mocks):
    out = et.extract_tone(make_document(), prompt_path="qualquer/dir/copom_v1.md")
    assert out["prompt_version"] == "copom_v1"


# ---------------------------------------------------------------------------
# Critério 2 — roda n vezes e mostra estabilidade dos scores
# ---------------------------------------------------------------------------

def test_executa_n_runs_default_3(mocks):
    _, _, mock_exec = mocks
    et.extract_tone(make_document(), prompt_path="prompts/copom_v1.md")
    assert mock_exec.call_count == 3


def test_n_runs_customizado(mocks):
    _, _, mock_exec = mocks
    out = et.extract_tone(make_document(), n_runs=5, prompt_path="prompts/copom_v1.md")
    assert mock_exec.call_count == 5
    assert len(out["stability"]["stance"]["values"]) == 5


def test_estabilidade_por_campo_numerico(mocks):
    out = et.extract_tone(make_document(), prompt_path="prompts/copom_v1.md")
    for field in _NUMERIC_FIELDS:
        assert field in out["stability"]
        assert set(out["stability"][field]) == {"mean", "std", "values"}


def test_scores_identicos_std_zero(mocks):
    out = et.extract_tone(make_document(), prompt_path="prompts/copom_v1.md")
    for field in _NUMERIC_FIELDS:
        assert out["stability"][field]["std"] == 0.0


def test_scores_divergentes_media_e_std(mocks):
    _, _, mock_exec = mocks
    stances = [0.1, 0.2, 0.35]
    mock_exec.side_effect = [make_run(stance=s) for s in stances]
    out = et.extract_tone(make_document(), n_runs=3, prompt_path="prompts/copom_v1.md")
    esperado_mean = round(statistics.mean(stances), 4)
    esperado_std = round(statistics.stdev(stances), 4)
    assert out["stance"] == esperado_mean
    assert out["stability"]["stance"]["mean"] == esperado_mean
    assert out["stability"]["stance"]["std"] == esperado_std
    assert out["stability"]["stance"]["values"] == [round(s, 4) for s in stances]


def test_n_runs_1_std_zero(mocks):
    _, _, mock_exec = mocks
    mock_exec.return_value = make_run(stance=0.5)
    out = et.extract_tone(make_document(), n_runs=1, prompt_path="prompts/copom_v1.md")
    assert out["stability"]["stance"]["std"] == 0.0
    assert out["stability"]["stance"]["values"] == [0.5]


def test_valores_arredondados_4_casas(mocks):
    _, _, mock_exec = mocks
    stances = [0.123456, 0.234567, 0.345678]
    mock_exec.side_effect = [make_run(stance=s) for s in stances]
    out = et.extract_tone(make_document(), n_runs=3, prompt_path="prompts/copom_v1.md")
    st = out["stability"]["stance"]
    assert st["mean"] == round(statistics.mean(stances), 4)
    assert st["std"] == round(statistics.stdev(stances), 4)
    assert st["values"] == [round(s, 4) for s in stances]
    assert out["stance"] == round(statistics.mean(stances), 4)
    for value in st["values"] + [st["mean"], st["std"], out["stance"]]:
        assert value == round(value, 4)


# ---------------------------------------------------------------------------
# Critério 3 — grava model_id e seed junto ao score
# ---------------------------------------------------------------------------

def test_model_id_gravado_do_llm_resolvido(mocks):
    _, mock_instance, _ = mocks
    mock_instance.model = "qwen2.5:7b"
    out = et.extract_tone(
        make_document(), model_id=None, prompt_path="prompts/copom_v1.md"
    )
    assert out["model_id"] == "qwen2.5:7b"


def test_seed_default_42_gravado(mocks):
    out = et.extract_tone(make_document(), prompt_path="prompts/copom_v1.md")
    assert out["seed"] == 42


def test_seed_customizado_gravado(mocks):
    out = et.extract_tone(make_document(), seed=7, prompt_path="prompts/copom_v1.md")
    assert out["seed"] == 7


def test_llmclient_recebe_provider_model_seed(mocks):
    mock_client_cls, _, _ = mocks
    et.extract_tone(
        make_document(),
        model_id="qwen2.5:7b",
        seed=7,
        provider="ollama",
        prompt_path="prompts/copom_v1.md",
    )
    mock_client_cls.assert_called_once_with(
        provider="ollama", model="qwen2.5:7b", seed=7
    )


# ---------------------------------------------------------------------------
# Contrato observado (não desejado): campo numérico ausente propaga KeyError
# ---------------------------------------------------------------------------

def test_campo_numerico_ausente_levanta_keyerror(mocks):
    _, _, mock_exec = mocks
    run = make_run()
    del run["stance"]
    mock_exec.return_value = run
    with pytest.raises(KeyError):
        et.extract_tone(make_document(), prompt_path="prompts/copom_v1.md")
