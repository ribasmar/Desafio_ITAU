"""
Single prompt execution for Copom tone extraction.

Workflow
--------
1. Load the markdown prompt template (e.g. ``prompts/copom_v1.md``).
2. Fill ``{tipo}``, ``{data_publicacao}``, ``{texto}`` placeholders
   from a document record.
3. Send the completed prompt to an ``LLMClient`` instance.
4. Parse the JSON response and validate it against the expected schema.
"""

import json
import os
import re
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"
PROMPT_PATH_DEFAULT = os.getenv("PROMPT_PATH") or str(PROMPTS_DIR / "copom_v1.md")

# Field spec: (name, type, min, max)
_FORWARD_GUIDANCE_MAP: dict[str, str] = {
    "calibração": "manutencao",
    "ajuste": "manutencao",
    "ajuste de calibração": "manutencao",
    "redução": "afrouxamento",
    "corte": "afrouxamento",
    "queda": "afrouxamento",
    "alta": "aperto",
    "subida": "aperto",
}

_SCHEMA_FIELDS: list[tuple[str, type, float, float]] = [
    ("stance", float, -1.0, 1.0),
    ("stance_delta", float, -1.0, 1.0),
    ("incerteza", float, 0.0, 1.0),
    ("conviccao", float, 0.0, 1.0),
]


def _loads_sanitized(text: str) -> dict:
    text = re.sub(r"//[^\n]*", "", text)
    if '"' not in text:
        text = text.replace("'", '"')
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return json.loads(text.strip())


def _parse_llm_json(raw: str) -> dict:
    m = re.search(r"```json\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if m:
        return _loads_sanitized(m.group(1))

    m = re.search(r"```\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if m:
        return _loads_sanitized(m.group(1))

    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        return _loads_sanitized(m.group(0))

    raise ValueError(
        f"No JSON object found in LLM response:\n{raw[:500]}"
    )


def build_prompt(
    document: dict,
    prompt_path: str | Path | None = None,
) -> str:
    """Fill the copom markdown template with data from *document*.

    Parameters
    ----------
    document : dict
        Must contain keys ``tipo``, ``available_time``, ``text``.
        See ``data/processed/copom_dataset.jsonl`` for the schema.
    prompt_path : str | Path, optional
        Path to the prompt template. Defaults to ``prompts/copom_v1.md``.

    Returns
    -------
    str
        Completed prompt ready to send to the LLM.
    """
    prompt_path = Path(prompt_path) if prompt_path else Path(PROMPT_PATH_DEFAULT)
    template = prompt_path.read_text(encoding="utf-8")

    replacements = {
        "{tipo}": document.get("tipo", "ata"),
        "{data_publicacao}": document.get("available_time", ""),
        "{texto}": document.get("text", ""),
    }

    filled = template
    for placeholder, value in replacements.items():
        filled = filled.replace(placeholder, value)

    return filled


def execute(
    llm,  # should be an LLMClient instance
    document: dict,
    prompt_path: str | Path | None = None,
) -> dict:
    """Build prompt, call the LLM, parse and validate the JSON response.

    Parameters
    ----------
    llm : LLMClient
        Initialised LLM client.
    document : dict
        Document record with ``tipo``, ``available_time``, ``text``.
    prompt_path : str | Path, optional
        Prompt template path. Defaults to ``prompts/copom_v1.md``.

    Returns
    -------
    dict
        Parsed JSON with keys: ``stance``, ``stance_delta``,
        ``forward_guidance``, ``incerteza``, ``conviccao``,
        ``justificativa``.
    """
    prompt = build_prompt(document, prompt_path)
    raw = llm.generate(prompt)

    result = _parse_llm_json(raw)

    # Validate numeric fields
    for name, typ, lo, hi in _SCHEMA_FIELDS:
        val = result.get(name)
        if val is None or not isinstance(val, (int, float)):
            raise ValueError(
                f"Field '{name}' is missing or not numeric. "
                f"Got: {result}"
            )
        val_f = float(val)
        if not (lo <= val_f <= hi):
            raise ValueError(
                f"Field '{name}' = {val_f} is outside range [{lo}, {hi}]. "
                f"Full result: {result}"
            )

    # Validate categorical field
    valid_fg = {"aperto", "manutencao", "afrouxamento", "neutro"}
    fg = result.get("forward_guidance", "").strip().lower()
    fg = _FORWARD_GUIDANCE_MAP.get(fg, fg)
    if fg not in valid_fg:
        raise ValueError(
            f"'forward_guidance' = '{fg}' is not one of {valid_fg}. "
            f"Full result: {result}"
        )
    result["forward_guidance"] = fg

    return result
