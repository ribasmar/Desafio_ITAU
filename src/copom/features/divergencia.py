# CopomLens — Camada 2→4: divergência Ata × Comunicado, medida DIRETA.
#
# O pareado por subtração (features/pareamento.py) deriva a divergência de
# dois rótulos grossos de 15 degraus e joga fora a maior parte do sinal.
# Este módulo mede a divergência numa chamada única: o LLM recebe o
# comunicado e a ata da MESMA reunião e classifica a DIREÇÃO, a MAGNITUDE e
# o EIXO da divergência — campos discretos (enum), que o modelo classifica
# de forma determinística. O número `divergencia` é derivado em código via
# DIVERGENCIA_MAP (não pedido ao modelo), como o STANCE_MAP.
#
# Point-in-time: o comunicado é público ~6 dias antes da ata. Nada do futuro
# entra na chamada — o instrumento só existe na publicação da ata, a mesma
# janela em que a reação do DI 1Y é medida.
"""Extração de divergência ata↔comunicado (direção/magnitude/eixo discretos)."""
from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
from pathlib import Path

from ..models.llm_client import LLMClient
from ..models.promptExec import _extract_json_from_text

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROMPTS_DIR = PROJECT_ROOT / "prompts"
PROMPT_PATH_DEFAULT = PROMPTS_DIR / "copom_v3_divergencia.md"

_DIRECOES = {"ata_mais_hawkish", "igual", "ata_mais_dovish"}
_MAGNITUDES = {"leve", "clara", "forte", "nenhuma"}
_EIXOS = {"riscos", "conviccao", "horizonte", "condicionalidade", "nenhum"}

# divergencia = sinal(direcao) × magnitude. Mapa determinístico em código:
# o modelo classifica enums, o número sai daqui (nunca do modelo).
_MAG_MAP = {"nenhuma": 0.0, "leve": 0.25, "clara": 0.5, "forte": 0.75}


def divergencia_de(direcao: str, magnitude: str) -> float:
    """Mapeia direção+magnitude para float (grade de 7 valores)."""
    if direcao == "igual" or magnitude == "nenhuma":
        return 0.0
    sinal = 1.0 if direcao == "ata_mais_hawkish" else -1.0
    return sinal * _MAG_MAP[magnitude]


DIVERGENCIA_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "direcao": {"type": "string", "enum": sorted(_DIRECOES)},
        "magnitude": {"type": "string", "enum": sorted(_MAGNITUDES)},
        "eixo_divergencia": {"type": "string", "enum": sorted(_EIXOS)},
        "justificativa_ata": {"type": "string"},
        "justificativa_comunicado": {"type": "string"},
    },
    "required": [
        "direcao",
        "magnitude",
        "eixo_divergencia",
        "justificativa_ata",
        "justificativa_comunicado",
    ],
}


def build_prompt(
    ata: dict,
    comunicado: dict,
    prompt_path: str | Path | None = None,
) -> str:
    """Preenche o template de divergência com os dois documentos do par."""
    prompt_path = Path(prompt_path) if prompt_path else Path(PROMPT_PATH_DEFAULT)
    template = prompt_path.read_text(encoding="utf-8")
    replacements = {
        "{data_publicacao_comunicado}": comunicado.get("available_time", ""),
        "{texto_comunicado}": comunicado.get("text", ""),
        "{data_publicacao_ata}": ata.get("available_time", ""),
        "{texto_ata}": ata.get("text", ""),
    }
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
    return template


def _validate(result: dict) -> dict:
    direcao = (result.get("direcao") or "").strip().lower()
    magnitude = (result.get("magnitude") or "").strip().lower()
    eixo = (result.get("eixo_divergencia") or "").strip().lower()
    if direcao not in _DIRECOES:
        raise ValueError(f"'direcao' = '{direcao}' inválido")
    if magnitude not in _MAGNITUDES:
        raise ValueError(f"'magnitude' = '{magnitude}' inválido")
    if eixo not in _EIXOS:
        raise ValueError(f"'eixo_divergencia' = '{eixo}' inválido")
    # Consistência: igual ⇒ magnitude nenhuma e eixo nenhum.
    if direcao == "igual":
        magnitude = "nenhuma"
        if eixo not in ("nenhum",):
            eixo = "nenhum"
    else:
        if magnitude == "nenhuma":
            raise ValueError("magnitude='nenhuma' com direcao != 'igual'")
    return {
        "direcao": direcao,
        "magnitude": magnitude,
        "eixo_divergencia": eixo,
        "divergencia": divergencia_de(direcao, magnitude),
        "justificativa_ata": str(result.get("justificativa_ata", "")),
        "justificativa_comunicado": str(
            result.get("justificativa_comunicado", "")
        ),
    }


def extract_divergencia(
    ata: dict,
    comunicado: dict,
    model_id: str | None = None,
    seed: int = 42,
    n_runs: int = 3,
    prompt_path: str | Path | None = None,
    max_tokens: int = 1600,
    debug: bool = False,
    provider: str | None = None,
    openrouter_api_key: str | None = None,
    openrouter_provider: str | None = None,
) -> dict:
    """Divergência de tom da ata em relação ao comunicado (mesma reunião).

    O modelo classifica direção/magnitude/eixo; `divergencia` é derivada em
    código (DIVERGENCIA_MAP). n_runs com a MESMA seed mede determinismo:
    std=0 ⇔ mesma saída.
    """
    llm = LLMClient(
        model=model_id, seed=seed, debug=debug,
        provider=provider, openrouter_api_key=openrouter_api_key,
        openrouter_provider=openrouter_provider,
        json_schema=DIVERGENCIA_JSON_SCHEMA,
        max_tokens=max_tokens,
    )
    resolved_model = llm.model
    prompt_path = Path(prompt_path) if prompt_path else Path(PROMPT_PATH_DEFAULT)
    prompt = build_prompt(ata, comunicado, prompt_path)

    num = ata.get("numero_reuniao")
    logger.debug("Extracting divergencia: meeting=%s", num)

    runs: list[dict] = []
    errors: list[str] = []
    for run_idx in range(n_runs):
        try:
            # MESMA seed em todas as runs: stability mede determinismo
            # (std=0 ⇔ mesma saída), não variação entre seeds.
            raw = llm.generate(prompt, seed=seed)
            parsed = _extract_json_from_text(raw)
            runs.append(_validate(parsed))
        except (ValueError, RuntimeError) as e:
            logger.error("Divergencia run %d failed: %s", run_idx, e)
            errors.append(str(e))

    if not runs:
        return {
            "error": "; ".join(errors) if errors else "All runs failed",
            "numero_reuniao": num,
            "tipo": "par",
            "available_time": ata.get("available_time"),
            "model_id": resolved_model,
            "seed": seed,
            "prompt_version": prompt_path.stem,
        }

    valores = [r["divergencia"] for r in runs]
    stability = {
        "mean": round(statistics.mean(valores), 4),
        "std": round(statistics.stdev(valores), 4) if len(valores) > 1 else 0.0,
        "values": [round(v, 4) for v in valores],
    }
    return {
        "divergencia": round(statistics.mean(valores), 4),
        "direcao": runs[-1]["direcao"],
        "magnitude": runs[-1]["magnitude"],
        "eixo_divergencia": runs[-1]["eixo_divergencia"],
        "justificativa_ata": runs[-1]["justificativa_ata"],
        "justificativa_comunicado": runs[-1]["justificativa_comunicado"],
        "model_id": resolved_model,
        "seed": seed,
        "prompt_version": prompt_path.stem,
        "numero_reuniao": num,
        "tipo": "par",
        "available_time": ata.get("available_time"),
        "stability": stability,
    }


# ── CLI ───────────────────────────────────────────────────────────────────


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extrai a divergência ata↔comunicado (direção/magnitude/eixo "
            "discretos) por reunião e grava JSONL."
        )
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=str(PROJECT_ROOT / "data/processed/copom_dataset.jsonl"),
        help="dataset point-in-time",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(PROJECT_ROOT / "data/processed/divergencia_tone.jsonl"),
        help="JSONL de saída",
    )
    parser.add_argument(
        "--range",
        type=str,
        default=None,
        help="faixa de reuniões, ex.: '116:199' (inclusive)",
    )
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--prompt", type=str, default=str(PROMPT_PATH_DEFAULT))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    import os

    with open(args.dataset, encoding="utf-8") as f:
        docs = [json.loads(line) for line in f if line.strip()]

    atas = {d["numero_reuniao"]: d for d in docs if d.get("tipo") == "ata"}
    comunicados = {
        d["numero_reuniao"]: d for d in docs if d.get("tipo") == "comunicado"
    }
    reunioes = sorted(set(atas) & set(comunicados))
    if args.range is not None:
        inicio_s, fim_s = args.range.split(":")
        inicio = int(inicio_s) if inicio_s.strip() else None
        fim = int(fim_s) if fim_s.strip() else None
        if inicio is not None:
            reunioes = [n for n in reunioes if n >= inicio]
        if fim is not None:
            reunioes = [n for n in reunioes if n <= fim]
    if args.limit is not None:
        reunioes = reunioes[: args.limit]

    model = args.model or os.getenv("LLM_MODEL_LOCAL")
    provider = os.getenv("LLM_PROVIDER", "local")
    resultados: list[dict] = []
    ok = erros = 0
    for idx, num in enumerate(reunioes, start=1):
        print(f"[{idx}/{len(reunioes)}] Reunião {num} ... ", end="", flush=True)
        try:
            r = extract_divergencia(
                atas[num], comunicados[num],
                model_id=model, prompt_path=args.prompt,
                provider=provider, debug=args.debug,
            )
            if "error" in r:
                erros += 1
                print(f"ERROR: {r['error']}")
            else:
                ok += 1
                print(f"OK  (divergencia={r['divergencia']})")
            resultados.append(r)
        except Exception as e:
            erros += 1
            resultados.append(
                {
                    "numero_reuniao": num,
                    "tipo": "par",
                    "available_time": atas[num].get("available_time"),
                    "error": str(e),
                }
            )
            print(f"ERROR: {e}")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for r in resultados:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Done. {ok} OK, {erros} errors — saved to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
