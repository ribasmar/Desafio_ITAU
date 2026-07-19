"""
Validação do baseline léxico no período histórico 2006-2016 (issue: Camada 2
+ relatório, Parte 1).

Critérios de aceite:
  1. Roda nas 84 atas de 2006-2016; distribuição do score reportada
  2. mode-share < 30%
  3. Nenhum termo com zero ocorrências em todo o período
  4. Termos ambiguos revisados (incerteza, riscos, cautela — e alta/baixa)
  5. LEXICO_VERSAO incrementado com justificativa por termo alterado

Rodar da raiz do projeto:
    python scripts/validar_lexico_historico.py
"""

import json
import statistics
from collections import Counter
from pathlib import Path

from copom.features.lexico import (
    PALAVRAS_HAWKISH,
    PALAVRAS_DOVISH,
    calcular_lexico,
)

DATASET_PATH = Path("data/processed/copom_dataset.jsonl")
PERIODO_INICIO = "2006"
PERIODO_FIM = "2016"


def carregar_atas_periodo() -> list[dict]:
    """Carrega só as atas (não comunicados) do dataset dentro do período alvo."""
    registros = []
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha:
                continue
            r = json.loads(linha)
            if r.get("tipo") != "ata":
                continue
            ano = r.get("data_reuniao", "")[:4]
            if PERIODO_INICIO <= ano <= PERIODO_FIM:
                registros.append(r)
    return registros


def main() -> None:
    atas = carregar_atas_periodo()
    print(f"=== Passo 1: carregamento ===")
    print(f"Atas encontradas no período {PERIODO_INICIO}-{PERIODO_FIM}: {len(atas)}")

    if not atas:
        print("Nenhuma ata encontrada — confira o caminho do dataset e o schema.")
        return

    atas.sort(key=lambda r: r["numero_reuniao"])
    print(f"Primeira reunião: {atas[0]['numero_reuniao']} ({atas[0]['data_reuniao']})")
    print(f"Última reunião:   {atas[-1]['numero_reuniao']} ({atas[-1]['data_reuniao']})")

    # Roda o léxico em cada ata
    resultados = []
    for r in atas:
        lex = calcular_lexico(r["text"])
        resultados.append({
            "numero_reuniao": r["numero_reuniao"],
            "data_reuniao": r["data_reuniao"],
            "filename": r["filename"],
            "score": lex["score"],
            "n_hawkish": lex["n_hawkish"],
            "n_dovish": lex["n_dovish"],
            "palavras_hawkish": lex["palavras_hawkish"],
            "palavras_dovish": lex["palavras_dovish"],
            "tamanho_texto": len(r["text"]),
        })

    scores = [r["score"] for r in resultados]

    print(f"\n=== Distribuição do score (n={len(scores)}) ===")
    print(f"Média:    {statistics.mean(scores):+.4f}")
    print(f"Mediana:  {statistics.median(scores):+.4f}")
    print(f"Stdev:    {statistics.stdev(scores):.4f}")
    print(f"Min:      {min(scores):+.4f}")
    print(f"Max:      {max(scores):+.4f}")

    # Histograma em texto (10 bins de -1 a 1)
    print(f"\n=== Histograma (10 bins, -1 a +1) ===")
    bins = [0] * 10
    for s in scores:
        idx = min(int((s + 1) / 2 * 10), 9)
        bins[idx] += 1
    for i, count in enumerate(bins):
        lo = -1 + i * 0.2
        hi = lo + 0.2
        barra = "█" * count
        print(f"[{lo:+.1f}, {hi:+.1f}): {barra} ({count})")

    # Salva resultado bruto pra usar nos próximos passos
    out_path = Path("data/processed/lexico_historico_2006_2016.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for r in resultados:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nResultado salvo em: {out_path}")

    # === Passo 2: mode-share ===================================================
    print(f"\n=== Passo 2: mode-share (critério de aceite: < 30%) ===")
    contagem_scores = Counter(scores)
    valor_mais_comum, freq_mais_comum = contagem_scores.most_common(1)[0]
    mode_share = freq_mais_comum / len(scores)
    print(f"Valor de score mais frequente: {valor_mais_comum:+.4f} ({freq_mais_comum}/{len(scores)} documentos)")
    print(f"Mode-share: {mode_share:.1%}")
    status = "PASSOU" if mode_share < 0.30 else "FALHOU"
    print(f"Critério (< 30%): {status}")

    # Mostra os top-5 valores mais repetidos, pra contexto
    print(f"\nTop 5 valores mais repetidos:")
    for valor, freq in contagem_scores.most_common(5):
        print(f"  {valor:+.4f} → {freq} documentos ({freq/len(scores):.1%})")

    # === Passo 3: termos com zero ocorrência no período =========================
    print(f"\n=== Passo 3: termos com zero ocorrências (critério: nenhum) ===")

    total_hawkish: Counter = Counter()
    total_dovish: Counter = Counter()
    for r in resultados:
        total_hawkish.update(r["palavras_hawkish"])
        total_dovish.update(r["palavras_dovish"])

    zerados_hawkish = [t for t in PALAVRAS_HAWKISH if total_hawkish.get(t, 0) == 0]
    zerados_dovish = [t for t in PALAVRAS_DOVISH if total_dovish.get(t, 0) == 0]

    print(f"Termos hawkish com 0 ocorrências ({len(zerados_hawkish)}/{len(PALAVRAS_HAWKISH)}):")
    for t in zerados_hawkish:
        print(f"  - {t}")
    print(f"Termos dovish com 0 ocorrências ({len(zerados_dovish)}/{len(PALAVRAS_DOVISH)}):")
    for t in zerados_dovish:
        print(f"  - {t}")

    if not zerados_hawkish and not zerados_dovish:
        print("Nenhum termo zerado — critério PASSOU.")
    else:
        print("Existem termos zerados — critério FALHOU (remover e justificar).")

    # Contexto extra: frequência total de cada termo, do mais raro pro mais comum
    print(f"\n--- Frequência total de cada termo hawkish (ordenado, menos comum primeiro) ---")
    for termo in sorted(PALAVRAS_HAWKISH, key=lambda t: total_hawkish.get(t, 0)):
        print(f"  {termo:20s} {total_hawkish.get(termo, 0)}")

    print(f"\n--- Frequência total de cada termo dovish (ordenado, menos comum primeiro) ---")
    for termo in sorted(PALAVRAS_DOVISH, key=lambda t: total_dovish.get(t, 0)):
        print(f"  {termo:20s} {total_dovish.get(termo, 0)}")

    # === Passo 4: revisão de termos ambíguos com evidência textual ==============
    print(f"\n=== Passo 4: termos ambíguos — incerteza / riscos / cautela ===")

    import re

    TERMOS_AMBIGUOS = ["incerteza", "riscos", "cautela"]

    for termo in TERMOS_AMBIGUOS:
        print(f"\n--- '{termo}' ---")
        docs_com_termo_hawkish = 0  # documento com score geral > 0
        docs_com_termo_dovish = 0   # documento com score geral < 0
        ocorrencias_totais = 0
        frases_exemplo = []

        for r in resultados:
            texto = None
            for reg in atas:
                if reg["numero_reuniao"] == r["numero_reuniao"]:
                    texto = reg["text"]
                    break
            if texto is None:
                continue

            n_no_doc = len(re.findall(rf"\b{termo}\b", texto, flags=re.IGNORECASE))
            if n_no_doc == 0:
                continue
            ocorrencias_totais += n_no_doc
            if r["score"] > 0:
                docs_com_termo_hawkish += 1
            elif r["score"] < 0:
                docs_com_termo_dovish += 1

            if len(frases_exemplo) < 4:
                # pega a primeira frase com o termo, pra leitura de contexto
                for frase in re.split(r"(?<=[.!?])\s+", texto):
                    if re.search(rf"\b{termo}\b", frase, flags=re.IGNORECASE):
                        sinal = "hawkish" if r["score"] > 0 else ("dovish" if r["score"] < 0 else "neutro")
                        frases_exemplo.append((r["numero_reuniao"], sinal, frase.strip()[:220]))
                        break

        total_docs_com_termo = docs_com_termo_hawkish + docs_com_termo_dovish
        if total_docs_com_termo:
            pct_hawkish = docs_com_termo_hawkish / total_docs_com_termo
            print(f"Ocorrências totais: {ocorrencias_totais}")
            print(f"Aparece em {total_docs_com_termo} documentos: "
                  f"{docs_com_termo_hawkish} de score hawkish (>0) [{pct_hawkish:.0%}], "
                  f"{docs_com_termo_dovish} de score dovish (<0) [{1-pct_hawkish:.0%}]")
            print("Exemplos de frase (numero_reuniao, score geral do doc, trecho):")
            for num, sinal, frase in frases_exemplo:
                print(f"  [{num}, {sinal}] \"{frase}...\"")
        else:
            print("Termo não encontrado em nenhum documento do período.")


if __name__ == "__main__":
    main()