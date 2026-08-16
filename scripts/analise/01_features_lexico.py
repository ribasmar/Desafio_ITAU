# Anexa ao painel de eventos as features de tom lexico da ata, casando por
# numero_reuniao e conferindo que o texto usado ja era publico na data em que a
# reacao do DI e medida. Gera painel_com_tom.csv e um relatorio de auditoria
# point-in-time. Nenhuma feature deriva de informacao posterior ao evento.
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parents[2] / "data" / "processed" / "analise"
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(BASE / "src"))
from copom.features.lexico import calcular_lexico, LEXICO_VERSAO  # noqa: E402

painel = pd.read_csv(BASE / "data/processed/painel_di1y.csv", parse_dates=["data_reuniao", "data_publicacao_ata", "d0", "d1"])

atas: dict[int, dict] = {}
with open(BASE / "data/processed/copom_dataset.jsonl", encoding="utf-8") as fh:
    for linha in fh:
        doc = json.loads(linha)
        if doc.get("tipo") != "ata":
            continue
        atas[int(doc["numero_reuniao"])] = doc

faltando = [int(n) for n in painel["numero_reuniao"] if int(n) not in atas]
if faltando:
    raise SystemExit(f"Reunioes do painel sem ata no corpus: {faltando}")

linhas = []
violacoes = []
for _, ev in painel.iterrows():
    num = int(ev["numero_reuniao"])
    doc = atas[num]
    texto = doc["text"]

    disponivel = pd.Timestamp(doc["available_time"])
    if disponivel > ev["d0"] + pd.Timedelta(days=0) and disponivel > ev["data_publicacao_ata"]:
        violacoes.append({"numero_reuniao": num, "available_time": str(disponivel.date()),
                          "data_publicacao_ata": str(ev["data_publicacao_ata"].date())})

    r = calcular_lexico(texto)
    n_chars = len(texto)
    total_termos = r["n_hawkish"] + r["n_dovish"]
    linhas.append({
        "numero_reuniao": num,
        "available_time": disponivel,
        "n_chars": n_chars,
        "lex_score": r["score"],
        "lex_n_hawkish": r["n_hawkish"],
        "lex_n_dovish": r["n_dovish"],
        "lex_intensidade": 1000.0 * total_termos / n_chars if n_chars else 0.0,
        "lex_hawk_norm": 1000.0 * r["n_hawkish"] / n_chars if n_chars else 0.0,
        "lex_dov_norm": 1000.0 * r["n_dovish"] / n_chars if n_chars else 0.0,
    })

feat = pd.DataFrame(linhas)
df = painel.merge(feat, on="numero_reuniao", validate="one_to_one")
df = df.sort_values("data_publicacao_ata").reset_index(drop=True)

df["lex_delta"] = df["lex_score"].diff()
df["lex_intens_delta"] = df["lex_intensidade"].diff()
df["fonte_texto"] = (df["numero_reuniao"] >= 200).map({True: "pdf", False: "api_html"})

df.to_csv(OUT / "painel_com_tom.csv", index=False)

auditoria = {
    "versao_lexico": LEXICO_VERSAO,
    "n_eventos": int(len(df)),
    "violacoes_point_in_time": violacoes,
    "available_time_igual_publicacao": int((df["available_time"] == df["data_publicacao_ata"]).sum()),
    "available_time_posterior_a_publicacao": int((df["available_time"] > df["data_publicacao_ata"]).sum()),
    "por_fonte": df["fonte_texto"].value_counts().to_dict(),
    "n_chars_por_fonte": df.groupby("fonte_texto")["n_chars"].agg(["min", "median", "max"]).round(0).to_dict(),
    "lex_score_por_fonte": df.groupby("fonte_texto")["lex_score"].agg(["mean", "std"]).round(4).to_dict(),
    "lex_intensidade_por_fonte": df.groupby("fonte_texto")["lex_intensidade"].agg(["mean", "std"]).round(4).to_dict(),
}
(OUT / "auditoria_features.json").write_text(json.dumps(auditoria, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

print(json.dumps(auditoria, indent=2, ensure_ascii=False, default=str))
print()
print(df[["numero_reuniao", "data_publicacao_ata", "fonte_texto", "surpresa_decisao", "lex_score", "lex_intensidade", "reacao_bps"]].head(8).to_string(index=False))
print("...")
print(df[["numero_reuniao", "data_publicacao_ata", "fonte_texto", "surpresa_decisao", "lex_score", "lex_intensidade", "reacao_bps"]].tail(5).to_string(index=False))
