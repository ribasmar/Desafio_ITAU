# CopomLens — Gates de aceite do instrumento v3 (issue da descontaminação).
#
# Mede, SEM olhar o alvo DI 1Y, os critérios numéricos de aceite:
#   1. eta²(stance ~ ação da decisão) < 0.30        (hoje, v2: 0.67)
#   2. justificativa cita nível/magnitude/votação < 0.20  (v2: 0.94–0.97)
#   3. divergências não-nulas > 0.60                (subtração v2: 0.32–0.47)
#   4. determinismo: std=0 em 100% dos docs no modelo de produção
#   5. mode-share do stance_label < 0.30            (não regredir o aceite da #21)
#
# Desvios não derrubam o pipeline: são medidos e gravados em
# data/processed/gates_v3.json para registro explícito no relatório.
"""Medição dos gates de aceite do instrumento de tom v3."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

from .pareamento import (
    carregar_dataset,
    carregar_tone,
    decisao_por_reuniao,
    eta2_anova,
    parear,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Gate #2: padrão de citação da decisão na justificativa (nível, magnitude em
# p.p., taxa em % a.a. ou menção à votação). Conservador: qualquer ocorrência
# conta como citação.
_PADRAO_DECISAO = re.compile(
    r"(p\.\s*p\.|selic|\d{1,2},\d{2}\s*%|taxa de juros|un[aâ]nim|maioria|vota[cç])",
    re.IGNORECASE,
)


def medir_gates(
    tone_path: str | Path,
    dataset_path: str | Path,
    selic_path: str | Path,
    divergencia_path: str | Path | None = None,
    pares_path: str | Path | None = None,
) -> dict:
    tone_rows = carregar_tone(tone_path)
    dataset_rows = carregar_dataset(dataset_path)
    decisao = decisao_por_reuniao(selic_path, dataset_rows)
    tone = pd.DataFrame(tone_rows)
    tone["delta"] = tone["numero_reuniao"].map(decisao)

    medidas: dict = {"alvo": {}, "medido": {}, "passa": {}}

    # Gate 1 — eta² stance ~ decisão (grupos de delta da Selic)
    pool = tone.dropna(subset=["stance", "delta"])
    eta2_pooled = eta2_anova(pool["stance"], pool["delta"])
    medidas["medido"]["eta2_stance_pooled"] = round(eta2_pooled, 4)
    medidas["alvo"]["eta2_stance_pooled"] = 0.30
    medidas["passa"]["eta2_stance_pooled"] = bool(eta2_pooled < 0.30)

    # Gate 2 — justificativa sem citação da decisão
    just = tone["justificativa"].fillna("").astype(str)
    frac_cita = float(just.str.contains(_PADRAO_DECISAO).mean()) if len(just) else float("nan")
    medidas["medido"]["justificativa_cita_decisao"] = round(frac_cita, 4)
    medidas["alvo"]["justificativa_cita_decisao"] = 0.20
    medidas["passa"]["justificativa_cita_decisao"] = bool(frac_cita < 0.20)

    # Gate 4 — determinismo (std=0 em todos os campos, todos os docs)
    stds = []
    for r in tone_rows:
        st = r.get("stability") or {}
        for campo in ("stance", "incerteza", "conviccao"):
            stds.append(float(st.get(campo, {}).get("std", 0.0) or 0.0))
    frac_std0 = float(sum(s == 0.0 for s in stds) / len(stds)) if stds else float("nan")
    medidas["medido"]["frac_std_zero"] = round(frac_std0, 4)
    medidas["alvo"]["frac_std_zero"] = 1.0
    medidas["passa"]["frac_std_zero"] = bool(frac_std0 == 1.0)

    # Gate 5 — mode-share do stance_label
    if "stance_label" in tone.columns and len(tone):
        mode_share = float(tone["stance_label"].value_counts(normalize=True).iloc[0])
    else:
        mode_share = float("nan")
    medidas["medido"]["mode_share_stance_label"] = round(mode_share, 4)
    medidas["alvo"]["mode_share_stance_label"] = 0.30
    medidas["passa"]["mode_share_stance_label"] = bool(mode_share < 0.30)

    # Gate 3 — divergências não-nulas (medida direta)
    if divergencia_path and Path(divergencia_path).exists():
        div_rows = carregar_tone(divergencia_path)
        div_df = pd.DataFrame(div_rows)
        nao_nula = float(
            (div_df["divergencia"] != 0).mean()
        ) if len(div_df) else float("nan")
        medidas["medido"]["divergencia_nao_nula"] = round(nao_nula, 4)
        medidas["alvo"]["divergencia_nao_nula"] = 0.60
        medidas["passa"]["divergencia_nao_nula"] = bool(nao_nula > 0.60)
    else:
        medidas["medido"]["divergencia_nao_nula"] = None
        medidas["alvo"]["divergencia_nao_nula"] = 0.60
        medidas["passa"]["divergencia_nao_nula"] = None

    # Controle: pareado por subtração (não é o regressor, é robustez)
    if pares_path and Path(pares_path).exists():
        pares = pd.read_json(pares_path, lines=True)
        pares["delta"] = pares["numero_reuniao"].map(decisao)
        medidas["medido"]["eta2_pareado_subtracao"] = round(
            eta2_anova(pares["stance_pareado"], pares["delta"]), 4
        )
    else:
        medidas["medido"]["eta2_pareado_subtracao"] = None

    medidas["n_docs"] = len(tone_rows)
    medidas["n_pares"] = int(
        len(pd.DataFrame(parear(tone_rows, dataset_rows)[0]))
    )
    medidas["desvio_documentado"] = {
        k: v for k, v in medidas["passa"].items() if v is False
    }
    return medidas


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mede os gates de aceite do instrumento v3 (sem tocar no alvo)."
    )
    parser.add_argument(
        "--tone",
        type=str,
        default=str(PROJECT_ROOT / "data/processed/tone_results_v3.jsonl"),
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=str(PROJECT_ROOT / "data/processed/copom_dataset.jsonl"),
    )
    parser.add_argument(
        "--selic",
        type=str,
        default=str(PROJECT_ROOT / "data/raw/selic_meta.csv"),
    )
    parser.add_argument(
        "--divergencia",
        type=str,
        default=str(PROJECT_ROOT / "data/processed/divergencia_tone.jsonl"),
    )
    parser.add_argument(
        "--pares",
        type=str,
        default=str(PROJECT_ROOT / "data/processed/pares_tone.jsonl"),
    )
    parser.add_argument(
        "--out",
        type=str,
        default=str(PROJECT_ROOT / "data/processed/gates_v3.json"),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    gates = medir_gates(
        args.tone, args.dataset, args.selic, args.divergencia, args.pares
    )
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(gates, f, ensure_ascii=False, indent=2)
    print(f"Gates -> {args.out}")
    for chave, alvo in gates["alvo"].items():
        medido = gates["medido"][chave]
        passa = gates["passa"][chave]
        if medido is None:
            status = "pendente (sem dado)"
        elif passa is None:
            status = "n/a"
        else:
            status = "PASSA" if passa else "DESVIO (documentado)"
        print(f"  {chave:<34} medido={medido}  alvo={alvo}  -> {status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
