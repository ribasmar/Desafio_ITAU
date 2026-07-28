"""
Single prompt execution for CopomLens tone extraction.

Workflow
--------
1. Load the markdown prompt template (e.g. ``prompts/copom_v2.md``).
2. Fill ``{tipo}``, ``{data_publicacao}``, ``{texto}`` placeholders
   from a document record.
3. Send the completed prompt to an ``LLMClient`` instance.
4. Parse the JSON response and validate it against the expected schema.
5. Retry with modified seed if parsing fails.
"""

import json
import logging
import os
import re
import unicodedata
from json import JSONDecodeError
from pathlib import Path

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"
PROMPT_PATH_DEFAULT = os.getenv("PROMPT_PATH") or str(PROMPTS_DIR / "copom_v2.md")

# ── forward_guidance normalization ──────────────────────────────────

_FORWARD_GUIDANCE_MAP: dict[str, str] = {
    # Portuguese canonical forms
    "aperto": "aperto",
    "manutencao": "manutencao",
    "afrouxamento": "afrouxamento",
    "neutro": "neutro",
    # Portuguese with accents
    "manutenção": "manutencao",
    "manutencão": "manutencao",
    # Portuguese synonyms / free text
    "calibracao": "manutencao",
    "calibração": "manutencao",
    "calibragem": "manutencao",
    "ajuste": "manutencao",
    "ajuste de calibracao": "manutencao",
    "ajuste de calibração": "manutencao",
    "reducao": "afrouxamento",
    "redução": "afrouxamento",
    "corte": "afrouxamento",
    "queda": "afrouxamento",
    "alta": "aperto",
    "subida": "aperto",
    "elevacao": "aperto",
    "elevação": "aperto",
    "flexibilizacao": "afrouxamento",
    "flexibilização": "afrouxamento",
    # English (models sometimes output English even with PT prompt)
    "hawkish": "aperto",
    "dovish": "afrouxamento",
    "neutral": "neutro",
    "tightening": "aperto",
    "easing": "afrouxamento",
    "hold": "manutencao",
    "maintenance": "manutencao",
    "unchanged": "manutencao",
    # Empty / none
    "none": "neutro",
    "n/a": "neutro",
    "sem sinalizacao": "neutro",
    "sem sinalização": "neutro",
    "data-dependent": "neutro",
}

# ── stance_label mapping ────────────────────────────────────────────

STANCE_MAP: dict[str, float] = {
    "emergencial_dovish":    -1.0000,
    "agressivo_dovish":      -0.7500,
    "claramente_dovish":     -0.6250,
    "moderadamente_dovish":  -0.5000,
    "levemente_dovish":      -0.3750,
    "marginalmente_dovish":  -0.2500,
    "neutro_dovish":         -0.1250,
    "neutro":                 0.0000,
    "neutro_hawkish":         0.1250,
    "marginalmente_hawkish":  0.2500,
    "levemente_hawkish":      0.3750,
    "moderadamente_hawkish":  0.5000,
    "claramente_hawkish":     0.6250,
    "agressivo_hawkish":      0.7500,
    "emergencial_hawkish":    1.0000,
}

_STANCE_LABELS: set[str] = set(STANCE_MAP.keys())

# ── schema ──────────────────────────────────────────────────────────

_SCHEMA_FIELDS: list[tuple[str, type, float, float]] = [
    ("incerteza", float, 0.0, 1.0),
    ("conviccao", float, 0.0, 1.0),
]

# ── JSON parsing ────────────────────────────────────────────────────


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(c)
    )


def _normalize_fg(raw: str) -> str:
    fg = raw.strip().lower()
    fg = _strip_accents(fg)
    return _FORWARD_GUIDANCE_MAP.get(fg, fg)


def _normalize_field_name(name: str) -> str:
    return _strip_accents(name)


def _clamp_field(name: str, val: float, lo: float, hi: float) -> float:
    if val < lo or val > hi:
        logger.warning(
            "Field '%s' = %s clamped to [%s, %s]", name, val, lo, hi
        )
    return max(lo, min(hi, val))


def _try_json_loads(text: str) -> dict:
    """Parse a string that should be valid JSON, with sanitization."""
    text = re.sub(r"//[^\n]*", "", text)
    if '"' not in text:
        text = text.replace("'", '"')
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return json.loads(text.strip())


def _extract_json_from_text(raw: str) -> dict:
    """Extract a JSON object from arbitrary text using multiple strategies.

    Uses ``json.JSONDecoder.raw_decode()`` to find the first valid JSON
    object by scanning character-by-character. Falls back to regex
    block extraction if raw_decode fails.
    """
    # Strategy 1 — scan with raw_decode (most robust)
    decoder = json.JSONDecoder()
    cleaned = _clean_text_for_json(raw)
    for i in range(len(cleaned)):
        if cleaned[i] == "{":
            try:
                obj, _end = decoder.raw_decode(cleaned, i)
                if isinstance(obj, dict):
                    return obj
            except JSONDecodeError:
                continue

    # Strategy 2 — try fenced code blocks
    for pattern in [
        r"```json\s*(\{.*?\})\s*```",
        r"```\s*(\{.*?\})\s*```",
    ]:
        m = re.search(pattern, raw, re.DOTALL)
        if m:
            try:
                return _try_json_loads(m.group(1))
            except JSONDecodeError:
                continue

    # Strategy 3 — greedy regex over raw text
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            return _try_json_loads(m.group(0))
        except JSONDecodeError:
            pass

    # Strategy 4 — balanced brace scanning
    try:
        return _extract_balanced_json(raw)
    except (JSONDecodeError, ValueError, IndexError):
        pass

    # Strategy 5 — repair truncated JSON (unclosed strings, missing braces)
    try:
        return _repair_truncated_json(raw)
    except (JSONDecodeError, ValueError):
        pass

    raise ValueError(
        f"No JSON object found in LLM response:\n{raw[:800]}"
    )


def _clean_text_for_json(text: str) -> str:
    """Remove content outside the outermost braces to help raw_decode."""
    first_brace = text.find("{")
    if first_brace == -1:
        return text
    last_brace = text.rfind("}")
    if last_brace == -1:
        return text
    return text[first_brace : last_brace + 1]


def _extract_balanced_json(text: str) -> dict:
    """Extract a JSON object by scanning for balanced braces."""
    start = text.find("{")
    if start == -1:
        raise ValueError("No opening brace found")

    depth = 0
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        ch = text[i]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                return _try_json_loads(candidate)

    raise ValueError("No balanced JSON object found")


def _repair_truncated_json(text: str) -> dict:
    """Try to salvage truncated JSON by closing unclosed strings and braces."""
    # Extract content from fenced blocks or find raw braces
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fenced:
        raw = fenced.group(1)
    else:
        raw = text

    start = raw.find("{")
    if start == -1:
        raise JSONDecodeError("No opening brace", text, 0)
    last_brace = raw.rfind("}")
    if last_brace == -1:
        last_brace = len(raw)
    candidate = raw[start : last_brace + 1]

    candidate = re.sub(r"//[^\n]*", "", candidate)
    if '"' not in candidate:
        candidate = candidate.replace("'", '"')

    repaired = _close_unclosed_strings(candidate)
    repaired = _balance_braces(repaired)
    repaired = re.sub(r",\s*([}\]])", r"\1", repaired)

    return json.loads(repaired.strip())


def _close_unclosed_strings(text: str) -> str:
    """Add closing quotes to any string value that was truncated."""
    result = []
    in_string = False
    escape_next = False

    for i, ch in enumerate(text):
        if escape_next:
            escape_next = False
            result.append(ch)
            continue
        if ch == "\\":
            escape_next = True
            result.append(ch)
            continue
        if ch == '"' and not escape_next:
            if in_string:
                in_string = False
            else:
                in_string = True
        result.append(ch)

    if in_string:
        result.append('"')

    return "".join(result)


def _balance_braces(text: str) -> str:
    """Add missing closing braces/spaces to balance JSON."""
    depth = 0
    for ch in text:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1

    if depth > 0:
        text = text.rstrip() + "\n" + "}" * depth
    return text


# ── prompt building ─────────────────────────────────────────────────


def build_prompt(
    document: dict,
    prompt_path: str | Path | None = None,
) -> str:
    """Fill the copom markdown template with data from *document*."""
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


# ── execution ───────────────────────────────────────────────────────


def execute(
    llm,  # LLMClient instance
    document: dict,
    prompt_path: str | Path | None = None,
    max_retries: int = 2,
) -> dict:
    """Build prompt, call the LLM, parse and validate the JSON response.

    Retries with a different seed on parse/validation failure.

    Parameters
    ----------
    llm : LLMClient
        Initialised LLM client.
    document : dict
        Document record with ``tipo``, ``available_time``, ``text``.
    prompt_path : str | Path, optional
        Prompt template path.
    max_retries : int
        Number of additional attempts on failure (default 2 = up to 3 total).

    Returns
    -------
    dict
        Parsed JSON with keys: ``stance_label``, ``forward_guidance``,
        ``incerteza``, ``conviccao``, ``justificativa``.
    """
    prompt = build_prompt(document, prompt_path)
    base_seed = getattr(llm, "seed", 42)

    logger.debug("Prompt length: %d chars", len(prompt))

    last_error = None
    t0 = __import__("time").perf_counter()
    for attempt in range(max_retries + 1):
        seed = base_seed + attempt
        raw = llm.generate(prompt, seed=seed)

        try:
            result = _extract_json_from_text(raw)
        except ValueError as e:
            last_error = str(e)
            continue

        try:
            _validate(result)
        except ValueError as e:
            last_error = str(e)
            continue

        return result

    raise ValueError(f"All {max_retries + 1} attempts failed. Last error: {last_error}")


def _validate(result: dict) -> None:
    for key in list(result.keys()):
        norm = _normalize_field_name(key)
        if norm != key:
            result[norm] = result.pop(key)

    label = (result.get("stance_label") or "").strip().lower()
    label = _strip_accents(label).replace(" ", "_").replace("-", "_")
    if label not in _STANCE_LABELS:
        raise ValueError(
            f"'stance_label' = '{label}' is not one of {sorted(_STANCE_LABELS)}. "
            f"Full result: {result}"
        )
    result["stance_label"] = label

    for name, typ, lo, hi in _SCHEMA_FIELDS:
        val = result.get(name)
        if val is None or not isinstance(val, (int, float)):
            raise ValueError(
                f"Field '{name}' is missing or not numeric. Got: {result}"
            )
        result[name] = _clamp_field(name, float(val), lo, hi)

    valid_fg = {"aperto", "manutencao", "afrouxamento", "neutro"}
    fg = _normalize_fg(result.get("forward_guidance", "") or "")
    if fg not in valid_fg:
        raise ValueError(
            f"'forward_guidance' = '{fg}' is not one of {valid_fg}. "
            f"Full result: {result}"
        )
    result["forward_guidance"] = fg
