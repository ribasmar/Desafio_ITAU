"""
Testa a hipótese C: os termos reprovados no gate 40-60% estão concentrados
dentro do parágrafo de "balanço de riscos" (que descreve riscos de alta E
de baixa simetricamente), em vez de espalhados pelo resto do documento —
o mesmo mecanismo já identificado antes para riscos/incerteza/cautela.

Rodar da raiz do projeto: python scripts/teste_boilerplate.py
"""
import json
import re
from pathlib import Path

DATASET_PATH = Path("data/processed/copom_dataset.jsonl")
PERIODO_INICIO, PERIODO_FIM = "2006", "2016"

TERMOS_REPROVADOS = [
    "recuando", "desaceleração", "melhora", "recuo", "benigno",
    "flexibilização", "queda", "moderação", "persistente",
    "arrefecimento", "redução", "pressão", "alívio",
]
TERMOS_CONTROLE = [  # alta frequência, NÃO reprovados, pra comparar
    "elevação", "pressões", "convergência", "deterioração", "aceleração",
]

# Marcadores do parágrafo de balanço de riscos (ajuste se o texto usar outra frase)
MARCADORES_RISCO = [
    "balanço de riscos", "riscos de alta", "riscos de baixa",
    "riscos para a inflação",
]


def carregar_atas():
    registros = []
    with open(DATASET_PATH, encoding="utf-8") as f:
        for linha in f:
            r = json.loads(linha)
            if r.get("tipo") != "ata":
                continue
            ano = r.get("data_reuniao", "")[:4]
            if PERIODO_INICIO <= ano <= PERIODO_FIM:
                registros.append(r)
    return registros


def extrair_paragrafo_risco(texto):
    """Extrai o trecho do texto entre o primeiro marcador de risco encontrado
    e o próximo cabeçalho de seção (heurística simples: até 1200 chars depois)."""
    texto_lower = texto.lower()
    for marcador in MARCADORES_RISCO:
        idx = texto_lower.find(marcador)
        if idx != -1:
            return texto[idx:idx + 1200]
    return ""


def contar_dentro_e_fora(atas, termo):
    dentro, fora = 0, 0
    for r in atas:
        texto = r["text"]
        paragrafo_risco = extrair_paragrafo_risco(texto)
        n_total = len(re.findall(rf"\b{termo}\b", texto, flags=re.IGNORECASE))
        n_no_risco = len(re.findall(rf"\b{termo}\b", paragrafo_risco, flags=re.IGNORECASE))
        dentro += n_no_risco
        fora += max(n_total - n_no_risco, 0)
    return dentro, fora


def main():
    atas = carregar_atas()
    print(f"Atas carregadas: {len(atas)}\n")

    print(f"{'termo':16s} {'grupo':11s} {'%no parag. risco':>18s}  n_dentro  n_fora")
    print("-" * 70)
    for termo in TERMOS_REPROVADOS:
        dentro, fora = contar_dentro_e_fora(atas, termo)
        total = dentro + fora
        pct = dentro / total if total else 0
        print(f"{termo:16s} {'REPROVADO':11s} {pct:17.1%}  {dentro:8d}  {fora:6d}")

    print()
    for termo in TERMOS_CONTROLE:
        dentro, fora = contar_dentro_e_fora(atas, termo)
        total = dentro + fora
        pct = dentro / total if total else 0
        print(f"{termo:16s} {'controle':11s} {pct:17.1%}  {dentro:8d}  {fora:6d}")


if __name__ == "__main__":
    main()