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

# === Passo 4: leave-one-out + gate calibrado pela taxa base do corpus =======
    # v2: o gate original (40%-60% fixo) assumia que o corpus é ~50/50 entre
    # documentos hawkish e dovish. Testamos e não é: o corpus real tem uma
    # taxa base própria. Um termo sem sinal nenhum deveria refletir ESSA taxa,
    # não 50%. O gate agora reprova um termo se o split dele estiver perto
    # DEMAIS da taxa base do corpus (não perto de 50% fixo).
    print(f"\n=== Passo 4: leave-one-out + gate calibrado pela taxa base do corpus ===")

    # Taxa base do corpus: proporção de documentos hawkish entre os que têm
    # score != 0 (mesmo critério usado pra classificar cada termo abaixo).
    docs_hawkish_corpus = sum(1 for r in resultados if r["score"] > 0)
    docs_dovish_corpus = sum(1 for r in resultados if r["score"] < 0)
    total_corpus = docs_hawkish_corpus + docs_dovish_corpus
    taxa_base = docs_hawkish_corpus / total_corpus

    MARGEM = 0.10  # termo reprova se ficar a menos de 10 p.p. da taxa base
    print(f"Taxa base do corpus: {docs_hawkish_corpus}/{total_corpus} = {taxa_base:.1%} hawkish "
          f"(vs. {1-taxa_base:.1%} dovish)")
    print(f"Gate: termo REPROVADO se |pct_hawkish do termo - taxa base| <= {MARGEM:.0%}\n")

    def score_loo(contagem_hawkish, contagem_dovish, termo, eh_hawkish):
        n_h = sum(contagem_hawkish.values())
        n_d = sum(contagem_dovish.values())
        if eh_hawkish:
            n_h -= contagem_hawkish.get(termo, 0)
        else:
            n_d -= contagem_dovish.get(termo, 0)
        total = n_h + n_d
        if total == 0:
            return 0.0
        return (n_h - n_d) / total

    def testar_termo(termo, eh_hawkish):
        docs_hawkish = 0
        docs_dovish = 0
        for r in resultados:
            contagem = r["palavras_hawkish"] if eh_hawkish else r["palavras_dovish"]
            if contagem.get(termo, 0) == 0:
                continue
            s = score_loo(r["palavras_hawkish"], r["palavras_dovish"], termo, eh_hawkish)
            if s > 0:
                docs_hawkish += 1
            elif s < 0:
                docs_dovish += 1
        total = docs_hawkish + docs_dovish
        if total == 0:
            return None
        pct_hawkish = docs_hawkish / total
        distancia_da_base = abs(pct_hawkish - taxa_base)
        return {
            "termo": termo, "total_docs": total,
            "pct_hawkish": pct_hawkish, "pct_dovish": 1 - pct_hawkish,
            "distancia_da_base": distancia_da_base,
            "reprovado": distancia_da_base <= MARGEM,
        }

    reprovados = []
    aprovados = []
    for termo in PALAVRAS_HAWKISH:
        res = testar_termo(termo, eh_hawkish=True)
        if res is None:
            continue
        (reprovados if res["reprovado"] else aprovados).append(("hawkish", res))
    for termo in PALAVRAS_DOVISH:
        res = testar_termo(termo, eh_hawkish=False)
        if res is None:
            continue
        (reprovados if res["reprovado"] else aprovados).append(("dovish", res))

    print(f"--- REPROVADOS (a <= {MARGEM:.0%} da taxa base, {len(reprovados)} termos) ---")
    for lista, r in sorted(reprovados, key=lambda x: x[1]["distancia_da_base"]):
        print(f"  [{lista:8s}] {r['termo']:16s} hawkish={r['pct_hawkish']:.0%} "
              f"(taxa base={taxa_base:.0%}, dist={r['distancia_da_base']:.0%})  "
              f"(n={r['total_docs']} docs)  <-- REPROVADO")

    print(f"\n--- Aprovados ({len(aprovados)} termos), ordenado por distância da base (menor pra maior) ---")
    for lista, r in sorted(aprovados, key=lambda x: x[1]["distancia_da_base"]):
        print(f"  [{lista:8s}] {r['termo']:16s} hawkish={r['pct_hawkish']:.0%} "
              f"(dist={r['distancia_da_base']:.0%})  (n={r['total_docs']} docs)")


if __name__ == "__main__":
    main()