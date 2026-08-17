# CopomLens — Camada 2→4: instrumento de tom pareado por reunião.
#
# Problema (diagnóstico): o stance extraído pelo prompt v2 era dominado pela
# decisão de juros — os 15 rótulos eram definidos por tamanho de corte e os 10
# exemplos começavam todos pela decisão. Contra a decisão (delta da Selic), a
# parcela da variância do stance explicada por ela é alta nos dois modelos
# (LLM e léxico). O prompt v3 redefine os rótulos pela COMUNICAÇÃO, e o
# instrumento que desce para a camada 4 elimina a decisão por construção:
#
#     stance_pareado = stance(ata) − stance(comunicado)
#
# Ata e comunicado da mesma reunião descrevem a MESMA decisão — ela se cancela
# — e sobra o tom que a ata acrescentou ao comunicado. O mesmo vale para o
# baseline léxico: lex_pareado = lex(ata) − lex(comunicado).
#
# Point-in-time: o pareado só existe quando a ata é publicada (o comunicado sai
# na data da decisão, a ata ~1 semana depois). Como a reação do DI 1Y é medida
# na publicação da ata (surpresa.reacao_di1y), não há look-ahead.
#
# Funil documentado: par sem tone em um dos lados, com prompt_version/model_id
# divergente entre os lados, ou sem texto para o léxico é DESCARTE com motivo —
# nunca preenchido com default.
"""Instrumento de tom pareado (ata − comunicado) e diagnóstico de contaminação."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from .lexico import calcular_lexico
from ..surprise.surpresa import decisao_apos_reuniao

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"

_PAIRS_COLUMNS = [
    "numero_reuniao",
    "data_reuniao",
    "available_time_ata",
    "stance_ata",
    "stance_com",
    "stance_pareado",
    "fg_ata",
    "fg_com",
    "lex_ata",
    "lex_com",
    "lex_pareado",
    "lex_versao",
    "prompt_version",
    "model_id",
]


def carregar_tone(path: str | Path) -> list[dict]:
    """Linhas OK de um tone_results*.jsonl (linhas com erro são ignoradas).

    Se uma reunião+tipo aparecer mais de uma vez (re-execução parcial), vale a
    última linha — comportamento idêntico ao pós-processamento da extração.
    """
    rows: list[dict] = []
    erros = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if "error" in r:
                erros += 1
                continue
            rows.append(r)
    if erros:
        print(f"[pareamento] {erros} linha(s) de erro ignoradas em {path}")
    return rows


def carregar_dataset(path: str | Path) -> list[dict]:
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _dict_por_reuniao(rows: list[dict], tipo: str) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for r in rows:
        if r.get("tipo") == tipo and r.get("numero_reuniao") is not None:
            out[int(r["numero_reuniao"])] = r
    return out


def _lexico_dataset(rows: list[dict]) -> dict[tuple[int, str], dict]:
    out: dict[tuple[int, str], dict] = {}
    for r in rows:
        chave = (int(r.get("numero_reuniao", -1)), r.get("tipo"))
        out[chave] = calcular_lexico(r.get("text", ""))
    return out


def parear(
    tone_rows: list[dict],
    dataset_rows: list[dict],
) -> tuple[pd.DataFrame, list[dict]]:
    """Pareia stance(ata) e stance(comunicado) por reunião.

    Regras de pareamento (falha-alto, nunca default):
    - sem tone OK na ata OU no comunicado -> descarte com motivo;
    - prompt_version divergente entre os lados -> descarte;
    - model_id divergente entre os lados -> descarte;
    - léxico é calculado dos textos do dataset; lado sem texto fica NaN e o
      motivo entra no descarte do léxico (não invalida o par de stance).

    Retorna (pares, descartes). Pares têm as colunas _PAIRS_COLUMNS; descartes
    são dicts com numero_reuniao, data_reuniao, motivo.
    """
    atas = _dict_por_reuniao(tone_rows, "ata")
    comunicados = _dict_por_reuniao(tone_rows, "comunicado")
    lex = _lexico_dataset(dataset_rows)
    datas = {}
    for r in dataset_rows:
        if r.get("numero_reuniao") is not None and r.get("data_reuniao"):
            datas[int(r["numero_reuniao"])] = r["data_reuniao"]

    reunioes = sorted(set(atas) | set(comunicados))
    pares: list[dict] = []
    descartes: list[dict] = []

    for num in reunioes:
        ata, com = atas.get(num), comunicados.get(num)
        if ata is None or com is None:
            lados = []
            if ata is None:
                lados.append("ata")
            if com is None:
                lados.append("comunicado")
            descartes.append(
                {
                    "numero_reuniao": num,
                    "data_reuniao": datas.get(num),
                    "motivo": f"sem tone OK em: {', '.join(lados)}",
                }
            )
            continue
        lados_sem_stance = [
            tipo
            for tipo, doc in (("ata", ata), ("comunicado", com))
            if doc.get("stance") is None
        ]
        if lados_sem_stance:
            descartes.append(
                {
                    "numero_reuniao": num,
                    "data_reuniao": datas.get(num),
                    "motivo": f"stance ausente em: {', '.join(lados_sem_stance)}",
                }
            )
            continue
        if ata.get("prompt_version") != com.get("prompt_version"):
            descartes.append(
                {
                    "numero_reuniao": num,
                    "data_reuniao": datas.get(num),
                    "motivo": (
                        f"prompt_version divergente: ata={ata.get('prompt_version')} "
                        f"comunicado={com.get('prompt_version')}"
                    ),
                }
            )
            continue
        if ata.get("model_id") != com.get("model_id"):
            descartes.append(
                {
                    "numero_reuniao": num,
                    "data_reuniao": datas.get(num),
                    "motivo": (
                        f"model_id divergente: ata={ata.get('model_id')} "
                        f"comunicado={com.get('model_id')}"
                    ),
                }
            )
            continue
        lex_ata = lex.get((num, "ata"))
        lex_com = lex.get((num, "comunicado"))
        if lex_ata is None or lex_com is None:
            descartes.append(
                {
                    "numero_reuniao": num,
                    "data_reuniao": datas.get(num),
                    "motivo": "sem texto no dataset para o léxico pareado",
                }
            )
        pares.append(
            {
                "numero_reuniao": num,
                "data_reuniao": datas.get(num),
                "available_time_ata": ata.get("available_time"),
                "stance_ata": ata.get("stance"),
                "stance_com": com.get("stance"),
                "stance_pareado": round(
                    (ata.get("stance") or 0.0) - (com.get("stance") or 0.0), 4
                ),
                "fg_ata": ata.get("forward_guidance"),
                "fg_com": com.get("forward_guidance"),
                "lex_ata": lex_ata.get("score") if lex_ata else None,
                "lex_com": lex_com.get("score") if lex_com else None,
                "lex_pareado": (
                    round(lex_ata["score"] - lex_com["score"], 4)
                    if lex_ata and lex_com
                    else None
                ),
                "lex_versao": lex_ata.get("versao_lexico") if lex_ata else None,
                "prompt_version": ata.get("prompt_version"),
                "model_id": ata.get("model_id"),
            }
        )

    return pd.DataFrame(pares, columns=_PAIRS_COLUMNS), descartes


def decisao_por_reuniao(
    selic_csv: str | Path, dataset_rows: list[dict]
) -> pd.Series:
    """Delta da Selic (p.p., decisão − nível pré) por reunião, via série 432."""
    selic = pd.read_csv(selic_csv, parse_dates=["data"])
    dec: dict[int, float] = {}
    datas: dict[int, str] = {}
    for r in dataset_rows:
        if r.get("numero_reuniao") is not None and r.get("data_reuniao"):
            datas[int(r["numero_reuniao"])] = r["data_reuniao"]
    for num, data_reuniao in datas.items():
        par = decisao_apos_reuniao(selic, pd.Timestamp(data_reuniao))
        dec[num] = par["delta"]
    return pd.Series(dec, name="delta_selic")


def eta2_anova(y: pd.Series, x: pd.Series) -> float:
    """Eta² clássico: variância entre grupos de decisão / variância total."""
    d = pd.DataFrame({"y": y, "x": x}).dropna()
    if len(d) < 2 or d["x"].nunique() < 2:
        return float("nan")
    medias = d.groupby("x")["y"].transform("mean")
    ss_res = ((d["y"] - medias) ** 2).sum()
    ss_tot = ((d["y"] - d["y"].mean()) ** 2).sum()
    if ss_tot == 0:
        return 0.0
    return float(1.0 - ss_res / ss_tot)


def r2_linear(y: pd.Series, x: pd.Series) -> float:
    """R² da regressão linear simples (decisão contínua)."""
    d = pd.DataFrame({"y": y, "x": x}).dropna()
    if len(d) < 2 or d["x"].std() == 0:
        return float("nan")
    return float(pd.Series(d["y"]).corr(d["x"]) ** 2)


def diagnostico_contaminacao(
    tone_rows: list[dict],
    dataset_rows: list[dict],
    selic_csv: str | Path,
) -> dict:
    """Quanto da variância do tom a decisão explica, por instrumento.

    Três camadas por modelo (LLM e léxico):
      1. stance/lex bruto de cada lado (pooled ata+comunicado);
      2. stance/lex da ata e do comunicado, lado a lado, nas reuniões pareadas;
      3. stance_pareado / lex_pareado — o instrumento da camada 4.

    Para cada célula: n, eta² (ANOVA por grupos de decisão) e R² linear.
    """
    decisao = decisao_por_reuniao(selic_csv, dataset_rows)
    tone = pd.DataFrame(tone_rows)
    tone["delta"] = tone["numero_reuniao"].map(decisao)

    lex_rows = []
    for r in dataset_rows:
        s = calcular_lexico(r.get("text", ""))
        lex_rows.append(
            {
                "numero_reuniao": r.get("numero_reuniao"),
                "tipo": r.get("tipo"),
                "lex": s["score"],
            }
        )
    lex_df = pd.DataFrame(lex_rows)
    lex_df["delta"] = lex_df["numero_reuniao"].map(decisao)

    pares, _ = parear(tone_rows, dataset_rows)
    pares["delta"] = pares["numero_reuniao"].map(decisao)

    def celula(y: pd.Series, x: pd.Series) -> dict:
        return {
            "n": int(y.notna().sum()),
            "eta2": round(eta2_anova(y, x), 4),
            "r2_linear": round(r2_linear(y, x), 4),
        }

    out: dict = {"amostra_bruta_llm": {}, "amostra_bruta_lexico": {}, "pareado": {}}

    pool = tone.dropna(subset=["stance", "delta"])
    out["amostra_bruta_llm"] = celula(pool["stance"], pool["delta"])

    pool_lex = lex_df.dropna(subset=["lex", "delta"])
    out["amostra_bruta_lexico"] = celula(pool_lex["lex"], pool_lex["delta"])

    out["pareado"] = {
        "stance_ata": celula(pares["stance_ata"], pares["delta"]),
        "stance_com": celula(pares["stance_com"], pares["delta"]),
        "stance_pareado": celula(pares["stance_pareado"], pares["delta"]),
        "lex_ata": celula(pares["lex_ata"], pares["delta"]),
        "lex_com": celula(pares["lex_com"], pares["delta"]),
        "lex_pareado": celula(pares["lex_pareado"], pares["delta"]),
    }
    return out


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Pareia stance(ata) − stance(comunicado) por reunião e mede quanto "
            "da variância do tom a decisão explica (eta²), nas camadas bruta e "
            "pareada."
        )
    )
    parser.add_argument(
        "--tone",
        type=str,
        default=str(DATA_PROCESSED / "tone_results.jsonl"),
        help="tone_results*.jsonl com a extração (padrão: data/processed/tone_results.jsonl)",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=str(DATA_PROCESSED / "copom_dataset.jsonl"),
        help="dataset point-in-time (padrão: data/processed/copom_dataset.jsonl)",
    )
    parser.add_argument(
        "--selic",
        type=str,
        default=str(DATA_RAW / "selic_meta.csv"),
        help="série 432 (padrão: data/raw/selic_meta.csv)",
    )
    parser.add_argument(
        "--out-pares",
        type=str,
        default=str(DATA_PROCESSED / "pares_tone.jsonl"),
        help="saída dos pares (padrão: data/processed/pares_tone.jsonl)",
    )
    parser.add_argument(
        "--out-eta2",
        type=str,
        default=str(DATA_PROCESSED / "eta2_pareamento.json"),
        help="saída do diagnóstico (padrão: data/processed/eta2_pareamento.json)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    tone_rows = carregar_tone(args.tone)
    dataset_rows = carregar_dataset(args.dataset)

    pares, descartes = parear(tone_rows, dataset_rows)
    with open(args.out_pares, "w", encoding="utf-8") as f:
        for row in pares.to_dict(orient="records"):
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    diag = diagnostico_contaminacao(tone_rows, dataset_rows, args.selic)
    with open(args.out_eta2, "w", encoding="utf-8") as f:
        json.dump(diag, f, ensure_ascii=False, indent=2)

    print(f"Pares: {len(pares)} reuniões -> {args.out_pares}")
    print(f"Descartes: {len(descartes)}")
    from collections import Counter

    for motivo, n in Counter(d["motivo"] for d in descartes).items():
        print(f"  - {n}: {motivo}")
    p = diag["pareado"]
    print(
        "\nFunil eta² (ANOVA por grupos de decisão) — quanto a decisão explica:"
    )
    print(f"  bruto LLM (pooled ata+com):  {diag['amostra_bruta_llm']['eta2']}")
    print(f"  bruto léxico (pooled):       {diag['amostra_bruta_lexico']['eta2']}")
    print(f"  stance_ata:  {p['stance_ata']['eta2']}   stance_com: {p['stance_com']['eta2']}")
    print(f"  lex_ata:     {p['lex_ata']['eta2']}   lex_com:    {p['lex_com']['eta2']}")
    print(f"  stance_pareado: {p['stance_pareado']['eta2']}   lex_pareado: {p['lex_pareado']['eta2']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
