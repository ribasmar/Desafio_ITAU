"""
CLI entry point for batch tone extraction via llama.cpp.

Usage
-----
    python -m copom.models --ata 270
    python -m copom.models --ata-range 21:30
    python -m copom.models --limit 5 --debug
    python -m copom.models --provider openrouter --ata-range 100:110
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from copom.features.extract_tone import extract_tone

PROJECT_ROOT = Path(__file__).resolve().parents[3]

_DEFAULT_MODEL = "Qwen2.5-14B-Instruct-Q5_K_M.gguf"
_DEFAULT_PROMPT = "copom_v2.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract tone scores from Copom documents using llama.cpp.",
    )
    parser.add_argument(
        "--provider",
        default=None,
        help="LLM backend: 'local' (llama.cpp) or 'openrouter'. "
             "Falls back to LLM_PROVIDER env var, then 'local'.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="OpenRouter API key. Falls back to OPENROUTER_API_KEY env var.",
    )
    parser.add_argument(
        "--openrouter-provider",
        default=None,
        help="Force OpenRouter to use a specific provider (e.g. 'Groq'). "
             "Falls back to OPENROUTER_PROVIDER env var.",
    )
    parser.add_argument(
        "--dataset",
        default=PROJECT_ROOT / "data/processed/copom_dataset.jsonl",
        help="Path to the input JSONL dataset",
    )
    parser.add_argument(
        "--output",
        default=PROJECT_ROOT / "data/processed/tone_results.jsonl",
        help="Path for the output JSONL results",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model identifier. Falls back to LLM_MODEL_LOCAL env var "
             "or the default GGUF.",
    )
    parser.add_argument(
        "--prompt",
        default=os.getenv("PROMPT_PATH")
        or str(PROJECT_ROOT / "prompts" / _DEFAULT_PROMPT),
        help="Path to the prompt template",
    )
    parser.add_argument(
        "--ata",
        type=int,
        default=None,
        help="Process only the meeting with this number",
    )
    parser.add_argument(
        "--ata-range",
        type=str,
        default=None,
        help="Process documents in this meeting range, e.g. '21:30' (inclusive). "
             "Use '21:' for from 21 to end, ':30' for start to 30.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N documents",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging to data/processed/debug.log and stderr",
    )
    return parser


def _parse_range(raw: str) -> tuple[int | None, int | None]:
    parts = raw.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid range format '{raw}'. Use 'start:end'.")
    start_s, end_s = parts
    start = int(start_s) if start_s.strip() else None
    end = int(end_s) if end_s.strip() else None
    return start, end


def _setup_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.WARNING
    log_path = PROJECT_ROOT / "data/processed" / "debug.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)

    fh = logging.FileHandler(str(log_path), mode="a", encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    root.addHandler(fh)

    if debug:
        sh = logging.StreamHandler(sys.stderr)
        sh.setLevel(logging.DEBUG)
        sh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
        root.addHandler(sh)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    _setup_logging(args.debug)
    logger = logging.getLogger(__name__)

    dataset_path = Path(args.dataset)
    output_path = Path(args.output)
    prompt_path = Path(args.prompt)

    model = args.model
    provider = args.provider or os.getenv("LLM_PROVIDER", "local")
    if not model:
        if provider == "openrouter":
            model = os.getenv("LLM_MODEL_OPENROUTER")
        if not model:
            model = os.getenv("LLM_MODEL_LOCAL")
    if not model:
        model = os.getenv("LLAMA_MODEL_PATH")
    if not model:
        model = _DEFAULT_MODEL

    if not dataset_path.exists():
        print(f"Error: dataset not found at {dataset_path}", file=sys.stderr)
        sys.exit(1)

    if not prompt_path.exists():
        print(f"Error: prompt not found at {prompt_path}", file=sys.stderr)
        sys.exit(1)

    with open(dataset_path, "r", encoding="utf-8") as f:
        documents = [json.loads(line) for line in f if line.strip()]

    if args.ata is not None:
        documents = [d for d in documents if d.get("numero_reuniao") == args.ata]
        if not documents:
            print(
                f"Error: no document found for ata number {args.ata}",
                file=sys.stderr,
            )
            sys.exit(1)

    if args.ata_range is not None:
        start, end = _parse_range(args.ata_range)
        if start is not None:
            documents = [d for d in documents if (d.get("numero_reuniao") or 0) >= start]
        if end is not None:
            documents = [d for d in documents if (d.get("numero_reuniao") or 0) <= end]
        if not documents:
            print(
                f"Error: no document found in range '{args.ata_range}'",
                file=sys.stderr,
            )
            sys.exit(1)

    if args.limit is not None and args.ata is None and args.ata_range is None:
        documents = documents[: args.limit]

    total = len(documents)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ok_count = 0
    error_count = 0
    results: list[dict] = []

    for idx, doc in enumerate(documents, start=1):
        doc_id = (
            f"Ata {doc.get('numero_reuniao')}"
            if doc.get("tipo") == "ata"
            else f"Comunicado {doc.get('numero_reuniao')}"
        )
        pub = doc.get("available_time", "?")
        label = f"[{idx}/{total}] {doc_id} ({pub})"
        print(f"{label} ... ", end="", flush=True)

        try:
                result = extract_tone(
                    document=doc,
                    model_id=model,
                    prompt_path=prompt_path,
                    n_runs=3,
                    debug=args.debug,
                    provider=provider,
                    openrouter_api_key=args.api_key,
                    openrouter_provider=args.openrouter_provider,
                )
                results.append(result)
                ok_count += 1
                stance = result.get("stance", "?")
                print(f"OK  (stance={stance})")
        except Exception as e:
            error_count += 1
            err_doc = {
                "numero_reuniao": doc.get("numero_reuniao"),
                "tipo": doc.get("tipo"),
                "available_time": doc.get("available_time"),
                "error": str(e),
            }
            results.append(err_doc)
            print(f"ERROR: {e}")

    # ── Post-processing: stance_delta ─────────────────────────────────
    results.sort(key=lambda r: r.get("numero_reuniao", 0) or 0)
    prev_stance: float | None = None
    for r in results:
        if "error" in r:
            r["stance_delta"] = None
            prev_stance = None
            continue
        if prev_stance is None:
            r["stance_delta"] = 0.0
        else:
            r["stance_delta"] = round(r.get("stance", 0.0) - prev_stance, 4)
        prev_stance = r.get("stance", 0.0)

    # ── Write output ──────────────────────────────────────────────────
    with open(output_path, "w", encoding="utf-8") as out:
        for r in results:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")

    print()
    print(f"Done. {ok_count} OK, {error_count} errors — saved to {output_path}")


if __name__ == "__main__":
    main()
