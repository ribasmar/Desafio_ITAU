# CopomLens — CLI da Camada 3: monta o painel do alvo DI 1Y a partir de
# data/raw/ (selic_meta.csv, focus_selic.csv, di1y_7806.csv, atas_listadas.json)
# e data/processed/ (copom_dataset.jsonl), grava painel_di1y.csv +
# funil_amostra.json e imprime o funil (cada corte com contagem e razão) e as
# estatísticas de validação da reação, no mesmo formato dos números medidos ao
# vivo na issue de reescopo, para conferência imediata.
import argparse
import json
import sys
from pathlib import Path

from copom.surprise.surpresa import (
    carregar_dataset,
    carregar_di1y,
    carregar_focus,
    carregar_reunioes_listadas,
    carregar_selic_meta,
    montar_painel_di1y,
)

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")


def _parse_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(
        description=(
            "Monta o painel do alvo DI 1Y (SGS 7806): uma linha por ata, com "
            "reação D0→D+1 na publicação, surpresa da decisão e regime, e o "
            "funil da amostra com a razão de cada corte."
        ),
    )
    parser.add_argument("--raw-path", type=str, default=str(RAW_DIR))
    parser.add_argument("--processed-path", type=str, default=str(PROCESSED_DIR))
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="CSV do painel (padrão: <processed>/painel_di1y.csv)",
    )
    parser.add_argument(
        "--funil",
        type=str,
        default=None,
        help="JSON do funil (padrão: <processed>/funil_amostra.json)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    raw = Path(args.raw_path)
    processed = Path(args.processed_path)
    out = Path(args.out) if args.out else processed / "painel_di1y.csv"
    funil_path = Path(args.funil) if args.funil else processed / "funil_amostra.json"

    entradas = {
        raw / "selic_meta.csv": "python -m copom.ingest.marketdata",
        raw / "focus_selic.csv": "python -m copom.ingest.marketdata",
        raw / "di1y_7806.csv": "python -m copom.ingest.marketdata",
        raw / "atas_listadas.json": "python -m copom.ingest.collect --last 300",
        processed / "copom_dataset.jsonl": "python -m copom.ingest.parser",
    }
    faltando = [(p, cmd) for p, cmd in entradas.items() if not p.exists()]
    if faltando:
        for p, cmd in faltando:
            print(f"FALTA {p} — gere com: {cmd}")
        return 1

    dataset = carregar_dataset(processed / "copom_dataset.jsonl")
    reunioes = carregar_reunioes_listadas(raw / "atas_listadas.json")
    selic = carregar_selic_meta(raw / "selic_meta.csv")
    focus = carregar_focus(raw / "focus_selic.csv")
    di1y = carregar_di1y(raw / "di1y_7806.csv")

    painel, funil = montar_painel_di1y(dataset, reunioes, selic, focus, di1y)

    out.parent.mkdir(parents=True, exist_ok=True)
    painel.to_csv(out, index=False, encoding="utf-8")
    with open(funil_path, "w", encoding="utf-8") as f:
        json.dump(funil, f, ensure_ascii=False, indent=2, default=str)

    print("Funil da amostra (cada corte com razão):")
    for etapa in funil["etapas"]:
        print(
            f"  {etapa['etapa']:<42} {etapa['restantes']:>4} "
            f"(−{etapa['removidas']}) · {etapa['motivo']}"
        )

    v = funil["validacao_reacao"]
    print(
        f"\nReações casadas (etapa 2): n={v['n_reacoes_casadas']} · "
        f"dp={v['dp_bps']} bps · min={v['min_bps']} · max={v['max_bps']} · "
        f"|reação| mediana={v['mediana_abs_bps']} bps · "
        f">1bp: {v['acima_1bp']}/{v['n_reacoes_casadas']} "
        f"(+{v['em_1bp_exato']} exatamente em 1.0 bp, fora do > estrito)"
    )
    print(
        "Referência medida ao vivo (issue do reescopo): 108 casadas · dp=12.3 · "
        "min=-31 · max=+33 · mediana |reação|=7.0 · >1bp: 95/108"
    )

    j = funil["janela_final"]
    print(f"\nJanela final: {j['inicio']} a {j['fim']} · {j['n_atas']} atas")
    print(
        "Referência da issue: 2006-01-18 a 2016-06-08 · 84 atas — se diferir, "
        "explicar a diferença no PR (ver funil), não ajustar até bater."
    )
    print(f"\nPainel  -> {out}")
    print(f"Funil   -> {funil_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
