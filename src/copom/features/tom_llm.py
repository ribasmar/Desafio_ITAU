# CopomLens — join dos scores do extrator LLM no painel de eventos. Le o JSONL
# de escoragem (uma linha por documento, com numero_reuniao e o JSON auditavel
# da CopomLens), valida schema e faixas antes de qualquer estatistica, e anexa
# ao painel as features de tom por LLM: nivel, delta e, quando o comunicado da
# mesma reuniao tambem foi escorado, a divergencia ata-comunicado — a medida
# que separa o tom da ata da decisao ja precificada. Cobertura parcial e corte
# de amostra, nunca imputacao silenciosa: ou falha alto, ou registra o corte.
"""Features de tom por LLM: carga validada dos scores e join point-in-time."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

CAMPOS_OBRIGATORIOS = ("numero_reuniao", "tipo", "stance")
FAIXAS = {"stance": (-1.0, 1.0), "incerteza": (0.0, 1.0), "conviccao": (0.0, 1.0)}
TIPOS_VALIDOS = ("ata", "comunicado")


class ScoresInvalidos(ValueError):
    """Arquivo de scores ausente, fora do schema ou fora das faixas declaradas."""


def carregar_scores(caminho: Path) -> pd.DataFrame:
    """Le e valida o JSONL de escoragem: um documento por linha.

    Schema minimo por linha: ``numero_reuniao`` (int), ``tipo`` ("ata" ou
    "comunicado") e ``stance`` em [-1, 1]. ``incerteza`` e ``conviccao`` sao
    opcionais, em [0, 1]. Score fora da faixa e erro de escoragem, nao dado:
    derruba a carga em vez de entrar na regressao como numero valido.
    """
    caminho = Path(caminho)
    if not caminho.exists():
        raise ScoresInvalidos(
            f"arquivo de scores nao encontrado: {caminho}\n"
            "Formato esperado: JSONL com uma linha por documento escorado, ex.:\n"
            '{"numero_reuniao": 116, "tipo": "ata", "stance": 0.3, '
            '"forward_guidance": "aperto", "incerteza": 0.4, "conviccao": 0.6, '
            '"justificativa": "trecho citado do proprio documento"}'
        )

    linhas = []
    for i, bruto in enumerate(caminho.read_text(encoding="utf-8").splitlines(), start=1):
        if not bruto.strip():
            continue
        try:
            doc = json.loads(bruto)
        except json.JSONDecodeError as erro:
            raise ScoresInvalidos(f"linha {i} nao e JSON valido: {erro}") from erro
        faltando = [c for c in CAMPOS_OBRIGATORIOS if c not in doc]
        if faltando:
            raise ScoresInvalidos(f"linha {i} sem campos obrigatorios {faltando}")
        if doc["tipo"] not in TIPOS_VALIDOS:
            raise ScoresInvalidos(f"linha {i} com tipo invalido {doc['tipo']!r}; use {TIPOS_VALIDOS}")
        for campo, (minimo, maximo) in FAIXAS.items():
            if campo in doc and doc[campo] is not None and not minimo <= float(doc[campo]) <= maximo:
                raise ScoresInvalidos(
                    f"linha {i}: {campo}={doc[campo]} fora de [{minimo}, {maximo}]"
                )
        linhas.append(doc)

    if not linhas:
        raise ScoresInvalidos(f"arquivo de scores vazio: {caminho}")

    df = pd.DataFrame(linhas)
    duplicados = df.duplicated(subset=["numero_reuniao", "tipo"])
    if duplicados.any():
        pares = df.loc[duplicados, ["numero_reuniao", "tipo"]].to_records(index=False).tolist()
        raise ScoresInvalidos(f"documentos escorados mais de uma vez: {pares}")
    return df


def anexar_tom_llm(
    painel: pd.DataFrame,
    scores: pd.DataFrame,
    permitir_parcial: bool = False,
) -> tuple[pd.DataFrame, dict]:
    """Anexa llm_stance, llm_stance_delta e llm_divergencia ao painel.

    Por padrao exige score de ata para toda reuniao do painel: cobertura parcial
    so entra com ``permitir_parcial=True``, e ai o corte e devolvido no bloco de
    auditoria com a lista das reunioes descartadas — corte declarado, nunca
    silencioso. A divergencia ata-comunicado so e calculada onde o comunicado da
    mesma reuniao tambem foi escorado; onde nao foi, fica NaN e cabe ao consumidor
    decidir (a especificacao M3 padrao nao a usa).
    """
    atas = scores[scores["tipo"] == "ata"].set_index("numero_reuniao")
    comunicados = scores[scores["tipo"] == "comunicado"].set_index("numero_reuniao")

    reunioes = painel["numero_reuniao"].astype(int)
    sem_score = sorted(set(reunioes) - set(atas.index))
    if sem_score and not permitir_parcial:
        raise ScoresInvalidos(
            f"{len(sem_score)} reunioes do painel sem score de ata: {sem_score}\n"
            "Escore as atas faltantes ou rode com cobertura parcial explicita."
        )

    df = painel[reunioes.isin(atas.index)].copy()
    df["llm_stance"] = df["numero_reuniao"].map(atas["stance"]).astype(float)
    for opcional in ("incerteza", "conviccao"):
        if opcional in atas.columns:
            df[f"llm_{opcional}"] = df["numero_reuniao"].map(atas[opcional]).astype(float)

    if len(comunicados):
        df["llm_stance_comunicado"] = df["numero_reuniao"].map(comunicados["stance"]).astype(float)
        df["llm_divergencia"] = df["llm_stance"] - df["llm_stance_comunicado"]

    df = df.sort_values("data_publicacao_ata").reset_index(drop=True)
    df["llm_stance_delta"] = df["llm_stance"].diff().fillna(0.0)

    auditoria = {
        "reunioes_no_painel": int(len(painel)),
        "reunioes_com_score_de_ata": int(len(df)),
        "reunioes_descartadas_sem_score": sem_score,
        "reunioes_com_divergencia": int(df["llm_divergencia"].notna().sum()) if "llm_divergencia" in df else 0,
    }
    return df, auditoria
