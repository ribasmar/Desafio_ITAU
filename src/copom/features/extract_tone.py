"""
Deterministic LLM-based tone extraction from Copom documents.

``extract_tone()`` is the main entry point for layer 2 of the pipeline.
It runs the prompt *n_runs* times with the same seed to confirm
determinism, then reports stability statistics alongside the scores.
"""

import os
import statistics
from pathlib import Path

from ..models.llm_client import LLMClient
from ..models.promptExec import execute as exec_prompt

PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"
PROMPT_PATH_DEFAULT = os.getenv("PROMPT_PATH") or str(PROMPTS_DIR / "copom_v1.md")

_NUMERIC_FIELDS = ["stance", "stance_delta", "incerteza", "conviccao"]


def extract_tone(
    document: dict,
    model_id: str | None = None,
    seed: int = 42,
    n_runs: int = 3,
    prompt_path: str | Path | None = None,
    provider: str = "ollama",
) -> dict:
    """Extract tone scores from a Copom document using a local LLM.

    Runs the prompt *n_runs* times with an identical seed to validate
    deterministic output (temperature = 0).  Scores are averaged and
    stability (mean, std per field) is included in the result.

    Parameters
    ----------
    document : dict
        Must contain keys ``text``, ``tipo``, ``available_time``,
        ``numero_reuniao``.  See ``data/processed/copom_dataset.jsonl``.
    model_id : str, optional
        Model identifier. If ``None``, resolved via ``LLM_MODEL_<PROVIDER>``
        env var then provider-specific default.
    seed : int
        Random seed fed to the LLM sampler.
    n_runs : int
        Number of repeated calls.  With temperature = 0 the results
        should be identical; *n_runs > 1* lets us confirm empirically.
    prompt_path : str | Path, optional
        Path to the markdown prompt template.
        Defaults to ``prompts/copom_v1.md``.
    provider : str
        LLM backend.  Must be a provider known to ``LLMClient``.
        Default ``"ollama"``.

    Returns
    -------
    dict
        JSON-serialisable dict with tone fields, metadata and stability::

            {
                "stance": 0.30,
                "stance_delta": 0.0,
                "forward_guidance": "aperto",
                "incerteza": 0.40,
                "conviccao": 0.60,
                "justificativa": "...",
                "model_id": "qwen2.5:7b",
                "seed": 42,
                "prompt_version": "copom_v1",
                "numero_reuniao": 270,
                "tipo": "ata",
                "available_time": "2025-05-13",
                "stability": {
                    "stance": {"mean": 0.30, "std": 0.00,
                               "values": [0.30, 0.30, 0.30]},
                    ...
                }
            }
    """
    llm = LLMClient(provider=provider, model=model_id, seed=seed)
    resolved_model = llm.model  # actual model after env/default resolution
    prompt_path = Path(prompt_path) if prompt_path else Path(PROMPT_PATH_DEFAULT)
    prompt_version = prompt_path.stem

    runs: list[dict] = []
    for _ in range(n_runs):
        result = exec_prompt(llm, document, prompt_path)
        runs.append(result)

    # Aggregate numeric fields
    stability: dict[str, dict] = {}
    output: dict = {}

    for field in _NUMERIC_FIELDS:
        values = [float(r[field]) for r in runs]
        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0.0
        stability[field] = {
            "mean": round(mean, 4),
            "std": round(stdev, 4),
            "values": [round(v, 4) for v in values],
        }
        output[field] = round(mean, 4)

    # Non-numeric fields (take the last run)
    output["forward_guidance"] = runs[-1].get("forward_guidance")
    output["justificativa"] = runs[-1].get("justificativa", "")

    # Metadata
    output["model_id"] = resolved_model
    output["seed"] = seed
    output["prompt_version"] = prompt_version
    output["numero_reuniao"] = document.get("numero_reuniao")
    output["tipo"] = document.get("tipo")
    output["available_time"] = document.get("available_time")
    output["stability"] = stability

    return output
