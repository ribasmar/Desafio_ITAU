"""
Deterministic LLM-based tone extraction from Copom documents.

``extract_tone()`` is the main entry point for layer 2 of the pipeline.
It runs the prompt once with a deterministic seed (temperature=0)
and includes stability metadata alongside the scores.
"""

import logging
import os
import statistics
from pathlib import Path

from ..models.llm_client import LLMClient
from ..models.promptExec import execute as exec_prompt
from ..models.promptExec import STANCE_MAP
from ..models.promptExec import TONE_JSON_SCHEMA

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"
PROMPT_PATH_DEFAULT = os.getenv("PROMPT_PATH") or str(PROMPTS_DIR / "copom_v3.md")

_NUMERIC_FIELDS = ["stance", "incerteza", "conviccao"]


def extract_tone(
    document: dict,
    model_id: str | None = None,
    seed: int = 42,
    n_runs: int = 1,
    prompt_path: str | Path | None = None,
    debug: bool = False,
    provider: str | None = None,
    openrouter_api_key: str | None = None,
    openrouter_provider: str | None = None,
) -> dict:
    """Extract tone scores from a Copom document using a local LLM via llama.cpp.

    Parameters
    ----------
    document : dict
        Must contain keys ``text``, ``tipo``, ``available_time``,
        ``numero_reuniao``.
    model_id : str, optional
        Model identifier. If ``None``, resolved via ``LLM_MODEL_LOCAL`` env var.
    seed : int
        Random seed fed to the LLM sampler.
    n_runs : int
        Number of repeated calls. With temperature=0 results are deterministic.
    prompt_path : str | Path, optional
        Path to the markdown prompt template.
    debug : bool
        Enable debug logging.

    Returns
    -------
    dict
        JSON-serialisable dict with tone fields, metadata and stability.
    """
    llm = LLMClient(
        model=model_id, seed=seed, debug=debug,
        provider=provider, openrouter_api_key=openrouter_api_key,
        openrouter_provider=openrouter_provider,
        json_schema=TONE_JSON_SCHEMA,
    )
    resolved_model = llm.model
    prompt_path = Path(prompt_path) if prompt_path else Path(PROMPT_PATH_DEFAULT)
    prompt_version = prompt_path.stem

    logger.debug("Extracting tone: meeting=%s, tipo=%s, date=%s",
                 document.get("numero_reuniao"), document.get("tipo"),
                 document.get("available_time"))

    runs: list[dict] = []
    errors: list[str] = []
    for run_idx in range(n_runs):
        try:
            result = exec_prompt(llm, document, prompt_path)
            # Rótulo desconhecido vira NaN, nunca neutro (0.0) — coerção
            # silenciosa para um valor plausível enviesaria amostra pequena.
            result["stance"] = STANCE_MAP.get(
                result.get("stance_label", ""), float("nan")
            )
            runs.append(result)
        except ValueError as e:
            logger.error("Run %d failed: %s", run_idx, e)
            errors.append(str(e))

    if not runs:
        error_msg = "; ".join(errors) if errors else "All runs failed"
        return {
            "error": error_msg,
            "numero_reuniao": document.get("numero_reuniao"),
            "tipo": document.get("tipo"),
            "available_time": document.get("available_time"),
            "model_id": resolved_model,
            "seed": seed,
            "prompt_version": prompt_version,
        }

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

    output["forward_guidance"] = runs[-1].get("forward_guidance")
    output["justificativa"] = runs[-1].get("justificativa", "")
    output["stance_label"] = runs[-1].get("stance_label", "")

    output["model_id"] = resolved_model
    output["seed"] = seed
    output["prompt_version"] = prompt_version
    output["numero_reuniao"] = document.get("numero_reuniao")
    output["tipo"] = document.get("tipo")
    output["available_time"] = document.get("available_time")
    output["stability"] = stability

    logger.debug("Tone result: stance=%s, fg=%s",
                 output.get("stance"), output.get("forward_guidance"))

    return output
