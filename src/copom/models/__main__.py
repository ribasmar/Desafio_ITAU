"""
CLI entry point for batch tone extraction.

Usage
-----
    python -m copom.models --ata 270
    python -m copom.models --limit 5 --provider ollama
    python -m copom.models --model llama3.1:8b --provider ollama --prompt prompts/copom_v1.md
"""

import argparse
import json
import os
import sys
from pathlib import Path

from copom.features.extract_tone import extract_tone

PROJECT_ROOT = Path(__file__).resolve().parents[3]

_DEFAULT_MODELS = {
    "local": "Meta-Llama-3.1-8B-Instruct-Q8_0.gguf",
    "ollama": "llama3.1:8B",
    "openrouter": "meta-llama/llama-3.1-8b-instruct",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract tone scores from Copom documents using a local LLM.",
    )
    parser.add_argument(
        "--dataset",
        default=PROJECT_ROOT / "data/processed/copom_dataset.jsonl",
        help="Path to the input JSONL dataset (default: data/processed/copom_dataset.jsonl)",
    )
    parser.add_argument(
        "--output",
        default=PROJECT_ROOT / "data/processed/tone_results.jsonl",
        help="Path for the output JSONL results (default: data/processed/tone_results.jsonl)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model identifier: OpenRouter slug, Ollama tag, or local path. "
             "If omitted, resolved via LLM_MODEL_<PROVIDER> env var then "
             "a provider-specific default "
             "(openrouter: qwen/qwen-2.5-7b-instruct, "
             "ollama: qwen2.5:7b, local: Qwen2.5-7B-Instruct-Q8_0.gguf)",
    )
    parser.add_argument(
        "--provider",
        default="openrouter",
        choices=["local", "ollama", "openrouter"],
        help="LLM backend provider (default: openrouter)",
    )
    parser.add_argument(
        "--prompt",
        default=os.getenv("PROMPT_PATH") or str(PROJECT_ROOT / "prompts/copom_v1.md"),
        help="Path to the prompt template (default: prompts/copom_v1.md, "
             "can be overridden via PROMPT_PATH env var)",
    )
    parser.add_argument(
        "--ata",
        type=int,
        default=None,
        help="Process only the meeting with this number (e.g. --ata 270)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N documents (ignored if --ata is set)",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    output_path = Path(args.output)
    prompt_path = Path(args.prompt)

    # Resolve model: CLI arg → env var → provider default
    model = args.model
    if not model:
        model = os.getenv(f"LLM_MODEL_{args.provider.upper()}")
    if not model and args.provider == "openrouter":
        model = os.getenv("OPENROUTER_MODEL")  # backward-compat fallback
    if not model and args.provider == "local":
        model = os.getenv("LLAMA_MODEL_PATH")
    if not model:
        model = _DEFAULT_MODELS.get(args.provider)
    if not model:
        print(f"Error: no model resolved for provider '{args.provider}'", file=sys.stderr)
        sys.exit(1)

    if not dataset_path.exists():
        print(f"Error: dataset not found at {dataset_path}", file=sys.stderr)
        sys.exit(1)

    if not prompt_path.exists():
        print(f"Error: prompt not found at {prompt_path}", file=sys.stderr)
        sys.exit(1)

    # Load dataset
    with open(dataset_path, "r", encoding="utf-8") as f:
        documents = [json.loads(line) for line in f if line.strip()]

    # Filter by --ata
    if args.ata is not None:
        documents = [d for d in documents if d.get("numero_reuniao") == args.ata]
        if not documents:
            print(
                f"Error: no document found for ata number {args.ata}",
                file=sys.stderr,
            )
            sys.exit(1)

    # Apply --limit (only if --ata was not used)
    if args.limit is not None and args.ata is None:
        documents = documents[: args.limit]

    total = len(documents)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ok_count = 0
    error_count = 0

    with open(output_path, "w", encoding="utf-8") as out:
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
                    provider=args.provider,
                    prompt_path=prompt_path,
                    n_runs=3,
                )
                out.write(json.dumps(result, ensure_ascii=False) + "\n")
                out.flush()
                ok_count += 1
                stance = result.get("stance", "?")
                std = result.get("stability", {}).get("stance", {}).get("std", "?")
                print(f"OK  (stance={stance}, std={std})")
            except Exception as e:
                error_count += 1
                err_doc = {
                    "numero_reuniao": doc.get("numero_reuniao"),
                    "tipo": doc.get("tipo"),
                    "available_time": doc.get("available_time"),
                    "error": str(e),
                }
                out.write(json.dumps(err_doc, ensure_ascii=False) + "\n")
                out.flush()
                print(f"ERROR: {e}")

    print()
    print(f"Done. {ok_count} OK, {error_count} errors — saved to {output_path}")


if __name__ == "__main__":
    main()
