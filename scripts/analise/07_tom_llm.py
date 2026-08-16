# Camada que da nome ao projeto: o tom extraido pelo LLM entra na comparacao
# aninhada (M3 = surpresa + tom lexico + tom LLM) e vira regra de posicao no
# mesmo backtest walk-forward das outras camadas, com Clark-West medindo o
# ganho incremental sobre o M2 e repeticao na subamostra homogenea de 84.
# Requer data/processed/scores_llm.jsonl (schema em copom.features.tom_llm);
# sem ele, falha explicando exatamente o que falta — o piso lexico ja esta
# medido, este script existe para o extrator tentar bate-lo. A amostra inteira
# precede o corte de treino dos modelos usados, entao a contaminacao por
# hindsight nao e separavel aqui: o teste pos-cutoff exige atas posteriores ao
# corte e fica registrado no artefato como pendencia estrutural.
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[2]
OUT = BASE / "data" / "processed" / "analise"
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(BASE / "src"))
from copom.backtest.motor import (  # noqa: E402
    PermutacaoDegenerada,
    permutacao_contra_acaso,
    sensibilidade_custo,
    simular,
)
from copom.features.tom_llm import anexar_tom_llm, carregar_scores  # noqa: E402
from copom.strategy import sinais  # noqa: E402

SCORES = BASE / "data" / "processed" / "scores_llm.jsonl"
CUSTO_BPS = 1.0

ESPECIFICACOES = {
    "M0_media": [],
    "M1_surpresa": ["surpresa_decisao"],
    "M2_surpresa_tom_lexico": ["surpresa_decisao", "lex_score", "lex_delta"],
    "M3_mais_tom_llm": ["surpresa_decisao", "lex_score", "lex_delta", "llm_stance", "llm_stance_delta"],
}


def rodar(df: pd.DataFrame, rotulo: str) -> dict:
    df = df.sort_values(sinais.COLUNA_DATA).reset_index(drop=True).copy()
    df["lex_delta"] = df["lex_score"].diff().fillna(0.0)
    aninhado = sinais.comparar_aninhados(df, especificacoes=ESPECIFICACOES, rotulo=rotulo)

    mascara = ~np.isnan(aninhado.previsoes["M3_mais_tom_llm"])
    oos = df.loc[mascara].reset_index(drop=True)
    reacao = oos[sinais.COLUNA_ALVO].to_numpy(float)

    posicoes = {
        "S5_regra_delta_tom_llm": sinais.sinal_da_regra(oos["llm_stance_delta"]),
        "S6_regra_nivel_tom_llm": sinais.sinal_da_regra(oos["llm_stance"]),
        "S7_previsao_M3": sinais.sinal_da_previsao(aninhado.previsoes["M3_mais_tom_llm"][mascara]),
    }
    if "llm_divergencia" in oos.columns and oos["llm_divergencia"].notna().all():
        posicoes["S8_regra_divergencia_ata_comunicado"] = sinais.sinal_da_regra(oos["llm_divergencia"])

    estrategias = {}
    for nome, pos in posicoes.items():
        liquido = simular(pos, reacao, CUSTO_BPS)
        bruto = simular(pos, reacao, 0.0)
        entrada = {
            **liquido.metricas,
            "pnl_bruto_bps": bruto.metricas["pnl_total_bps"],
            "sharpe_bruto": bruto.metricas["sharpe_anual"],
            "sensibilidade_custo": sensibilidade_custo(pos, reacao),
        }
        try:
            entrada["permutacao"] = permutacao_contra_acaso(pos, reacao, CUSTO_BPS)
        except PermutacaoDegenerada as erro:
            entrada["permutacao"] = {"aplicavel": False, "razao": str(erro)}
        estrategias[nome] = entrada

    return {
        "amostra": rotulo,
        "n_total": aninhado.n_total,
        "n_oos": aninhado.n_oos,
        "janela_oos": [str(oos[sinais.COLUNA_DATA].min().date()), str(oos[sinais.COLUNA_DATA].max().date())],
        "comparacao_aninhada": {"metricas": aninhado.metricas, "clark_west": aninhado.clark_west},
        "estrategias": estrategias,
    }


def main() -> int:
    painel_caminho = OUT / "painel_com_tom.csv"
    if not painel_caminho.exists():
        raise SystemExit(f"painel nao encontrado: {painel_caminho} — rode 01_features_lexico.py antes")

    scores = carregar_scores(SCORES)
    painel = pd.read_csv(painel_caminho, parse_dates=["data_publicacao_ata"])
    df, auditoria_join = anexar_tom_llm(painel, scores, permitir_parcial="--permitir-parcial" in sys.argv)

    resultado = {
        "scores": str(SCORES),
        "auditoria_join": auditoria_join,
        "contaminacao_por_hindsight": (
            "toda a amostra (2006-2019) precede o corte de treino dos modelos de "
            "escoragem: efeito de memoria e efeito de leitura nao sao separaveis "
            "aqui; o teste pos-cutoff exige atas posteriores ao corte do modelo"
        ),
        "resultados": [rodar(df, "painel_completo")],
    }
    sub = df[df["fonte_texto"] == "api_html"].reset_index(drop=True)
    if len(sub) > sinais.TREINO_MINIMO_PADRAO + 3:
        resultado["resultados"].append(rodar(sub, "subamostra_api_html"))

    (OUT / "tom_llm.json").write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
    print(f"\nGravado em {OUT / 'tom_llm.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
