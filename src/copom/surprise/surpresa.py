# CopomLens — Camada 3 (módulo único, funde o antigo decision.py + surpresa.py):
# calendário oficial do Copom (tabela estática 2025–2026 validada contra o BCB
# + lista oficial de reuniões gravada pela ingestão para o histórico), regime
# por presidente do BC (tabela de fato público, nunca inferido por LLM),
# surpresa da decisão (Selic efetiva − mediana Focus pré-reunião, point-in-time,
# sem look-ahead), reação do DI 1Y (SGS 7806: taxa(D+1) − taxa(D0) em bps, em
# torno da DATA DE PUBLICAÇÃO da ata — nunca da reunião) e o painel final do
# alvo com funil documentado: cada corte com contagem e razão escrita.
"""Decisão, surpresa monetária e alvo DI 1Y do Copom em um único módulo."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
from pandas.tseries.offsets import BDay

# Janela máxima aceita entre a última pesquisa Focus de um rótulo e a data da
# reunião; acima disso o rótulo é considerado mal pareado e a função falha alto.
TOLERANCIA_ROTULO_DIAS = 10

# Janela máxima aceita entre a reunião e a primeira observação seguinte da
# série de meta: a meta votada vigora no dia útil seguinte, então um salto
# maior significa que a série não cobre o pós-reunião (ex.: reuniões de
# 1998–2003 com a 432 carregada desde 2004) e o pareamento seria espúrio.
TOLERANCIA_PAREAMENTO_DIAS = 10

# Defasagem máxima aceita entre a publicação da ata e cada pregão vizinho
# (D0 = véspera, D1 = dia da publicação): 5 dias corridos toleram feriados
# prolongados sem deixar publicações fora da janela viva da série (out/2019+)
# casarem com 30/09/2019 como se fossem pregões legítimos do evento.
MAX_DEFASAGEM_D0_DIAS = 5

# Calendario do Copom (inicio da reuniao de 2 dias e data da decisao = 2o dia).
# A surpresa por reuniao recente precisa do inicio (corte point-in-time do
# Focus) e da data da decisao (leitura da meta efetiva). Datas de 2025 e 2026
# validadas contra o calendario oficial do BCB. Para o HISTORICO, o calendario
# vem da lista oficial de reunioes gravada pela ingestao (atas_listadas.json,
# ver carregar_reunioes_listadas) — esta tabela cobre apenas a operacao
# corrente e nao serve para rotular reunioes antigas.
COPOM_CALENDAR: dict[str, dict[str, date]] = {
    "R1/2025": {"inicio": date(2025, 1, 28), "decisao": date(2025, 1, 29)},
    "R2/2025": {"inicio": date(2025, 3, 18), "decisao": date(2025, 3, 19)},
    "R3/2025": {"inicio": date(2025, 5, 6), "decisao": date(2025, 5, 7)},
    "R4/2025": {"inicio": date(2025, 6, 17), "decisao": date(2025, 6, 18)},
    "R5/2025": {"inicio": date(2025, 7, 29), "decisao": date(2025, 7, 30)},
    "R6/2025": {"inicio": date(2025, 9, 16), "decisao": date(2025, 9, 17)},
    "R7/2025": {"inicio": date(2025, 11, 4), "decisao": date(2025, 11, 5)},
    "R8/2025": {"inicio": date(2025, 12, 9), "decisao": date(2025, 12, 10)},
    "R1/2026": {"inicio": date(2026, 1, 27), "decisao": date(2026, 1, 28)},
    "R2/2026": {"inicio": date(2026, 3, 17), "decisao": date(2026, 3, 18)},
    "R3/2026": {"inicio": date(2026, 4, 28), "decisao": date(2026, 4, 29)},
    "R4/2026": {"inicio": date(2026, 6, 16), "decisao": date(2026, 6, 17)},
    "R5/2026": {"inicio": date(2026, 8, 4), "decisao": date(2026, 8, 5)},
    "R6/2026": {"inicio": date(2026, 9, 15), "decisao": date(2026, 9, 16)},
    "R7/2026": {"inicio": date(2026, 11, 3), "decisao": date(2026, 11, 4)},
    "R8/2026": {"inicio": date(2026, 12, 8), "decisao": date(2026, 12, 9)},
}

# Regimes de presidência do BC — fato público à época, por tabela (nunca
# inferido por LLM). Atribuição pela DATA DA REUNIÃO: o texto da ata reflete o
# comitê presidido por aquele presidente. Meirelles presidiu de 01/01/2003 a
# 31/12/2010; Tombini de 01/01/2011 à posse de Goldfajn (09/06/2016); Goldfajn
# até a posse de Campos Neto (28/02/2019). Goldfajn e Campos Neto entraram
# junto com o bônus das atas PDF (reuniões 200–231); nenhuma reunião do Copom
# ocorre perto dessas fronteiras de posse (última de Tombini: 08/06/2016;
# primeira de Goldfajn: 20/07/2016; última de Goldfajn: 06/02/2019; primeira
# de Campos Neto: 20/03/2019), então a atribuição é insensível a ±dias.
# Fora da cobertura, regime_bc falha alto: estender a tabela é decisão
# explícita e documentada, não default herdado.
REGIMES_BC: tuple[tuple[date, date, str], ...] = (
    (date(2003, 1, 1), date(2010, 12, 31), "Meirelles"),
    (date(2011, 1, 1), date(2016, 6, 8), "Tombini"),
    (date(2016, 6, 9), date(2019, 2, 27), "Goldfajn"),
    (date(2019, 2, 28), date(2024, 12, 31), "Campos Neto"),
)


# ── Carregadores ────────────────────────────────────────────────────────────


def _serie_diaria(df: pd.DataFrame, coluna: str, nome: str) -> pd.DataFrame:
    """Valida uma série diária ['data', coluna]: deduplica datas repetidas com
    o mesmo valor; com valores conflitantes, levanta ValueError (falha alto em
    vez de escolher em silêncio)."""
    faltantes = {"data", coluna} - set(df.columns)
    if faltantes:
        raise ValueError(f"{nome} sem colunas obrigatórias: {sorted(faltantes)}")
    if df["data"].duplicated().any():
        conflitos = df.groupby("data")[coluna].nunique()
        datas_conflitantes = conflitos[conflitos > 1].index
        if len(datas_conflitantes):
            datas = [d.strftime("%Y-%m-%d") for d in datas_conflitantes]
            raise ValueError(f"{nome} com valores conflitantes nas datas: {datas}")
        df = df.drop_duplicates(subset="data")
    return df.sort_values("data").reset_index(drop=True)


def carregar_selic_meta(caminho: str | Path) -> pd.DataFrame:
    """Lê selic_meta.csv (data, selic_meta) ordenado por data.

    Datas duplicadas com o mesmo valor são deduplicadas; com valores
    conflitantes, levanta ValueError (falha alto em vez de escolher em silêncio).
    """
    df = pd.read_csv(caminho, parse_dates=["data"])
    return _serie_diaria(df, "selic_meta", "selic_meta")


def carregar_di1y(caminho: str | Path) -> pd.DataFrame:
    """Lê di1y_7806.csv (data, di1y) — swap DI×pré 360 dc, o alvo DI 1Y —
    ordenado por data, com a mesma validação de duplicatas de selic_meta."""
    df = pd.read_csv(caminho, parse_dates=["data"])
    return _serie_diaria(df, "di1y", "di1y_7806")


def carregar_focus(caminho: str | Path) -> pd.DataFrame:
    """Lê focus_selic.csv (reuniao, data, mediana, ...) ordenado por rótulo e data."""
    df = pd.read_csv(caminho, parse_dates=["data"])
    faltantes = {"reuniao", "data", "mediana"} - set(df.columns)
    if faltantes:
        raise ValueError(f"focus_selic sem colunas obrigatórias: {sorted(faltantes)}")
    return df.sort_values(["reuniao", "data"]).reset_index(drop=True)


def carregar_dataset(caminho: str | Path) -> pd.DataFrame:
    """Lê copom_dataset.jsonl com tipos normalizados.

    Linhas vazias são ignoradas; linha com JSON inválido levanta ValueError
    indicando o número da linha (arquivo truncado não passa despercebido).
    """
    linhas: list[dict] = []
    with open(caminho, encoding="utf-8") as f:
        for numero, linha in enumerate(f, start=1):
            linha = linha.strip()
            if not linha:
                continue
            try:
                linhas.append(json.loads(linha))
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSON inválido na linha {numero} de {caminho}: {exc}") from exc
    df = pd.DataFrame(linhas)
    obrigatorias = {"numero_reuniao", "data_reuniao", "tipo"}
    faltantes = obrigatorias - set(df.columns)
    if faltantes:
        raise ValueError(f"copom_dataset sem campos obrigatórios: {sorted(faltantes)}")
    df["numero_reuniao"] = df["numero_reuniao"].astype(int)
    df["data_reuniao"] = pd.to_datetime(df["data_reuniao"])
    if "available_time" in df.columns:
        df["available_time"] = pd.to_datetime(df["available_time"])
    return df


_CAMPOS_NUMERO = ("nroReuniao", "nro_reuniao", "numero_reuniao")
_CAMPOS_DATA = ("dataReferencia", "data_referencia", "dataReuniao", "data_reuniao")


def carregar_reunioes_listadas(caminho: str | Path) -> pd.DataFrame:
    """Lê atas_listadas.json (lista oficial de reuniões gravada pela ingestão)
    e devolve ['numero_reuniao', 'data_reuniao'] com TODAS as reuniões listadas
    pelo BCB, inclusive as sem texto HTML.

    É a base do rótulo R{k}/{ano}: o rank dentro do ano usa o calendário
    oficial completo, nunca um dataset parcial (com dataset parcial, a última
    reunião baixada de um ano viraria R1 daquele ano por engano).
    """
    with open(caminho, encoding="utf-8") as f:
        bruto = json.load(f)
    df = pd.DataFrame(bruto)
    campo_num = next((c for c in _CAMPOS_NUMERO if c in df.columns), None)
    campo_data = next((c for c in _CAMPOS_DATA if c in df.columns), None)
    if campo_num is None or campo_data is None:
        raise ValueError(
            "atas_listadas sem campos reconhecíveis de número/data de reunião; "
            f"campos disponíveis: {sorted(df.columns)}"
        )
    # ISO 8601 primeiro (formato do BCB); só então dd/mm/aaaa (dayfirst),
    # aplicado APENAS ao resíduo que o parse ISO não resolveu — um parse
    # genérico leria "05/03/2016" como 3 de maio sem erro, e reparsear datas
    # ISO com dayfirst gera warning do pandas. Datas inválidas/nulas viram NaT
    # nos dois parses e falham alto com as entradas nomeadas.
    datas = pd.to_datetime(df[campo_data], format="ISO8601", errors="coerce")
    faltantes = datas.isna()
    if faltantes.any():
        datas = datas.copy()
        datas.loc[faltantes] = pd.to_datetime(
            df.loc[faltantes, campo_data], dayfirst=True, errors="coerce"
        )
    if datas.isna().any():
        quebradas = df.loc[datas.isna(), campo_data].head(5).tolist()
        raise ValueError(
            f"atas_listadas com datas inválidas em {campo_data}: {quebradas}"
        )
    if getattr(datas.dt, "tz", None) is not None:
        datas = datas.dt.tz_localize(None)
    out = pd.DataFrame(
        {"numero_reuniao": df[campo_num].astype(int), "data_reuniao": datas.dt.normalize()}
    )
    return (
        out.drop_duplicates("numero_reuniao")
        .sort_values("data_reuniao")
        .reset_index(drop=True)
    )


# ── Calendário, rótulo e regime ─────────────────────────────────────────────


def rotulo_focus(data_reuniao: pd.Timestamp, datas_reunioes) -> str:
    """Rótulo Focus "R{k}/{ano}" da reunião: k-ésima reunião do ano.

    `datas_reunioes` deve conter todas as reuniões conhecidas do ano da data
    consultada — o rank dentro do ano define o k do rótulo. Use a lista oficial
    completa (carregar_reunioes_listadas), nunca um dataset parcial.
    """
    data_reuniao = pd.Timestamp(data_reuniao)
    datas = pd.DatetimeIndex(sorted(set(pd.DatetimeIndex(datas_reunioes))))
    if data_reuniao not in datas:
        raise ValueError(f"data {data_reuniao.date()} ausente da lista de reuniões")
    no_ano = datas[datas.year == data_reuniao.year]
    k = int(no_ano.get_loc(data_reuniao)) + 1
    return f"R{k}/{data_reuniao.year}"


def regime_bc(data_reuniao) -> str:
    """Presidente do BC no comando na data da reunião, por tabela de fato
    público (REGIMES_BC). Fora da cobertura da tabela, levanta ValueError:
    incluir um novo regime é decisão explícita, não default."""
    d = pd.Timestamp(data_reuniao).date()
    for inicio, fim, nome in REGIMES_BC:
        if inicio <= d <= fim:
            return nome
    raise ValueError(
        f"data {d} fora da cobertura de REGIMES_BC "
        f"({REGIMES_BC[0][0]} a {REGIMES_BC[-1][1]}); estenda a tabela com o "
        "fato público antes de usar."
    )


# ── Surpresa da decisão (reuniões recentes, calendário estático) ────────────


@dataclass(frozen=True)
class SurpresaDecisao:
    """Resultado auditavel da surpresa de uma reuniao."""

    reuniao: str
    data_decisao: date
    selic_efetiva: float
    selic_esperada: float
    surpresa: float
    data_expectativa: date  # data do survey Focus usado (prova do point-in-time)
    n_respondentes: int | None


def selic_esperada(
    focus: pd.DataFrame,
    reuniao: str,
    data_reuniao: date,
    base_calculo: int = 0,
    defasagem_dias_uteis: int = 1,
) -> tuple[float, date, int | None]:
    """Mediana Focus da reuniao no ultimo survey publico ANTES de `data_reuniao`.

    Retorna (mediana, data_do_survey, n_respondentes). Levanta ValueError se nao
    houver survey valido (evita lookahead).

    `defasagem_dias_uteis` recua o corte para refletir que o survey de referencia
    do dia D so se torna publico ~1 dia util depois: com o default 1, exige
    `data_survey < inicio - 1 dia util`. Use 0 para cortar exatamente no inicio.
    Aproximacao: BDay considera apenas fins de semana, nao feriados nacionais.
    """
    sel = focus[focus["reuniao"] == reuniao].copy()
    if "base_calculo" in sel.columns and base_calculo is not None:
        sel = sel[sel["base_calculo"] == base_calculo]

    corte = pd.Timestamp(data_reuniao) - BDay(defasagem_dias_uteis)
    sel = sel[(pd.to_datetime(sel["data"]) < corte) & sel["mediana"].notna()]
    if sel.empty:
        raise ValueError(
            f"Sem expectativa Focus valida para {reuniao} antes de {data_reuniao} "
            "(point-in-time): nada a usar como Selic esperada."
        )

    linha = sel.sort_values("data").iloc[-1]
    n = linha.get("n_respondentes")
    n = int(n) if pd.notna(n) else None
    return float(linha["mediana"]), pd.to_datetime(linha["data"]).date(), n


def selic_efetiva(selic_meta: pd.DataFrame, data_decisao: date) -> float:
    """Meta Selic vigente imediatamente APOS a decisao.

    Retorna o primeiro valor da serie 432 com data ESTRITAMENTE posterior a data
    da decisao — a meta votada passa a valer no dia seguinte. Levanta ValueError
    se a serie ainda nao cobrir o pos-decisao (ex.: rodando no mesmo dia da
    reuniao, antes de o SGS publicar a nova meta), em vez de devolver
    silenciosamente a meta antiga.
    """
    df = selic_meta.copy()
    df["data"] = pd.to_datetime(df["data"])
    pos = df[df["data"] > pd.Timestamp(data_decisao)].sort_values("data")
    if pos.empty:
        raise ValueError(
            f"Serie de Meta Selic nao cobre o pos-decisao de {data_decisao}: meta "
            "efetiva ainda indisponivel (reuniao corrente ou serie desatualizada?)."
        )
    return float(pos.iloc[0]["selic_meta"])


def surpresa_decisao(
    reuniao: str,
    selic_meta: pd.DataFrame,
    focus: pd.DataFrame,
    base_calculo: int = 0,
    defasagem_dias_uteis: int = 1,
) -> SurpresaDecisao:
    """Calcula a surpresa (p.p.) de uma reuniao do Copom.

    surpresa > 0 -> decisao mais dura (hawkish) que o esperado;
    surpresa < 0 -> mais branda (dovish); ~0 -> em linha com o Focus.
    `defasagem_dias_uteis` e repassado a `selic_esperada` (point-in-time).
    """
    if reuniao not in COPOM_CALENDAR:
        raise KeyError(f"Reuniao {reuniao} fora do calendario; atualize COPOM_CALENDAR.")

    cal = COPOM_CALENDAR[reuniao]
    esperada, data_exp, n = selic_esperada(
        focus, reuniao, cal["inicio"], base_calculo, defasagem_dias_uteis
    )
    efetiva = selic_efetiva(selic_meta, cal["decisao"])

    return SurpresaDecisao(
        reuniao=reuniao,
        data_decisao=cal["decisao"],
        selic_efetiva=efetiva,
        selic_esperada=esperada,
        surpresa=round(efetiva - esperada, 4),
        data_expectativa=data_exp,
        n_respondentes=n,
    )


# ── Pareamento histórico e Focus point-in-time ──────────────────────────────


def decisao_apos_reuniao(selic: pd.DataFrame, data_reuniao: pd.Timestamp) -> dict:
    """Decisão da Selic associada à reunião de `data_reuniao`.

    nivel_pre: último valor com data <= data_reuniao (vigente antes da decisão).
    decisao:   primeiro valor com data > data_reuniao (novo alvo, vigência D+1),
               desde que dentro de TOLERANCIA_PAREAMENTO_DIAS — acima disso a
               série não cobre o pós-reunião e o pareamento seria espúrio
               (uma reunião de 1998 não pode herdar a meta de 2004).
    delta:     decisao − nivel_pre.
    Sem observação posterior (reunião mais recente) ou fora da cobertura, os
    campos ficam NaN.
    """
    data_reuniao = pd.Timestamp(data_reuniao)
    antes = selic.loc[selic["data"] <= data_reuniao, "selic_meta"]
    depois = selic.loc[selic["data"] > data_reuniao]
    nivel_pre = float(antes.iloc[-1]) if len(antes) else math.nan
    decisao = math.nan
    if len(depois):
        primeira = depois.iloc[0]
        if (primeira["data"] - data_reuniao).days <= TOLERANCIA_PAREAMENTO_DIAS:
            decisao = float(primeira["selic_meta"])
    return {"nivel_pre": nivel_pre, "decisao": decisao, "delta": decisao - nivel_pre}


def mediana_focus_pre_reuniao(
    focus: pd.DataFrame, rotulo: str, data_reuniao: pd.Timestamp
) -> float:
    """Mediana Focus point-in-time para a reunião: última pesquisa ESTRITAMENTE
    anterior a `data_reuniao` (pesquisa do próprio dia da decisão é descartada
    por precaução contra look-ahead).

    Levanta ValueError se o rótulo não parecer corresponder à reunião (última
    pesquisa depois da decisão ou mais de TOLERANCIA_ROTULO_DIAS antes dela).
    Retorna NaN se o rótulo não existir ou não houver pesquisa anterior.
    """
    data_reuniao = pd.Timestamp(data_reuniao)
    grupo = focus.loc[focus["reuniao"] == rotulo]
    if grupo.empty:
        return math.nan
    ultima = grupo["data"].max()
    if ultima > data_reuniao or ultima < data_reuniao - pd.Timedelta(days=TOLERANCIA_ROTULO_DIAS):
        raise ValueError(
            f"rótulo {rotulo} não corresponde à reunião de {data_reuniao.date()}: "
            f"última pesquisa em {ultima.date()}"
        )
    pit = grupo.loc[grupo["data"] < data_reuniao]
    if pit.empty:
        return math.nan
    return float(pit.sort_values("data")["mediana"].iloc[-1])


# ── Alvo DI 1Y (SGS 7806) ───────────────────────────────────────────────────


def reacao_di1y(di1y: pd.DataFrame, data_publicacao) -> dict | None:
    """Reação do DI 1Y à ata: 7806(D1) − 7806(D0), em bps, em torno da DATA DE
    PUBLICAÇÃO da ata — nunca da data da reunião (a ata só vira informação
    pública na publicação; usar a reunião seria look-ahead).

    A ata é publicada pela manhã (8h30, antes da abertura do pregão): o
    fechamento do PRÓPRIO dia de publicação já reflete a ata. Por isso a
    janela atravessa o evento: D0 = último pregão ESTRITAMENTE anterior à
    publicação (fechamento que ainda não viu a ata) e D1 = primeiro pregão a
    partir da publicação (primeiro fechamento que já a viu). Medir
    publicação→dia seguinte capturaria o dia APÓS a absorção, quase só ruído.

    Retorna dict {d0, taxa_d0, d1, taxa_d1, reacao_bps} ou None quando a
    publicação cai fora da janela viva da série:
    - sem pregão anterior à publicação (ata anterior a 02/01/2004);
    - D0 mais de MAX_DEFASAGEM_D0_DIAS antes da publicação;
    - sem pregão a partir da publicação, ou D1 mais de MAX_DEFASAGEM_D0_DIAS
      depois dela (série já morta em 30/09/2019).
    """
    serie = di1y.sort_values("data")
    pub = pd.Timestamp(data_publicacao).normalize()
    antes = serie[serie["data"] < pub]
    if antes.empty:
        return None
    d0 = antes.iloc[-1]
    if (pub - d0["data"]).days > MAX_DEFASAGEM_D0_DIAS:
        return None
    depois = serie[serie["data"] >= pub]
    if depois.empty:
        return None
    d1 = depois.iloc[0]
    if (d1["data"] - pub).days > MAX_DEFASAGEM_D0_DIAS:
        return None
    return {
        "d0": d0["data"].date(),
        "taxa_d0": float(d0["di1y"]),
        "d1": d1["data"].date(),
        "taxa_d1": float(d1["di1y"]),
        "reacao_bps": round((float(d1["di1y"]) - float(d0["di1y"])) * 100.0, 2),
    }


# ── Painéis ─────────────────────────────────────────────────────────────────


def montar_painel(
    dataset: pd.DataFrame, selic: pd.DataFrame, focus: pd.DataFrame
) -> pd.DataFrame:
    """Painel por reunião: decisão pareada, mediana Focus PIT e surpresa.

    Colunas: numero_reuniao, data_reuniao, rotulo_focus, nivel_pre, decisao,
    delta, mediana_focus, surpresa (= decisao − mediana_focus).

    Atenção: o rótulo é rankeado dentro das reuniões PRESENTES no dataset; use
    montar_painel_di1y (com a lista oficial de reuniões) para o alvo DI 1Y.

    Uma reunião = uma linha, mesmo quando o BCB diverge de si próprio: há caso
    real de dataReferencia diferente entre ata e comunicado da MESMA reunião
    (reunião 94: ata 2004-03-17, comunicado 2004-03-18). A deduplicação é por
    numero_reuniao, preferindo a data da ATA (objeto primário do estudo).
    """
    reunioes = (
        dataset.sort_values(["numero_reuniao", "tipo"])  # "ata" < "comunicado"
        [["numero_reuniao", "data_reuniao"]]
        .drop_duplicates("numero_reuniao")
        .sort_values("data_reuniao")
        .reset_index(drop=True)
    )
    linhas = []
    for reuniao in reunioes.itertuples(index=False):
        rotulo = rotulo_focus(reuniao.data_reuniao, reunioes["data_reuniao"])
        decisao = decisao_apos_reuniao(selic, reuniao.data_reuniao)
        mediana = mediana_focus_pre_reuniao(focus, rotulo, reuniao.data_reuniao)
        linhas.append(
            {
                "numero_reuniao": reuniao.numero_reuniao,
                "data_reuniao": reuniao.data_reuniao,
                "rotulo_focus": rotulo,
                **decisao,
                "mediana_focus": mediana,
                "surpresa": decisao["decisao"] - mediana,
            }
        )
    return pd.DataFrame(linhas)


_COLUNAS_PAINEL_DI1Y = [
    "numero_reuniao",
    "data_reuniao",
    "rotulo_focus",
    "regime",
    "data_publicacao_ata",
    "d0",
    "taxa_d0",
    "d1",
    "taxa_d1",
    "reacao_bps",
    "nivel_pre",
    "decisao",
    "delta",
    "mediana_focus",
    "surpresa_decisao",
]


def montar_painel_di1y(
    dataset: pd.DataFrame,
    reunioes_oficiais: pd.DataFrame,
    selic: pd.DataFrame,
    focus: pd.DataFrame,
    di1y: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    """Painel do alvo DI 1Y: uma linha por ATA que sobrevive ao funil, com o
    funil inteiro documentado — cada corte com contagem e razão escrita
    (exigência do manual 2.4: explicar dados e premissas; nenhum número herdado
    de default).

    Etapas do funil:
      0. atas listadas pelo BCB (lista oficial completa, inclui as sem texto);
      1. com texto HTML no dataset (as demais estão em atas_sem_texto.json);
      2. com reação DI 1Y casada (publicação dentro da janela viva da SGS 7806,
         02/01/2004 a 30/09/2019, com D0 e D+1);
      3. com Focus por reunião e decisão pareada (o recurso do Olinda rotula
         reuniões a partir da R1/2006).

    Retorna (painel, funil). O painel tem colunas _COLUNAS_PAINEL_DI1Y; o funil
    traz {"etapas": [...], "descartes": [...], "validacao_reacao": {...},
    "janela_final": {...}} — "descartes" nomeia cada ata cortada e o motivo, e
    "validacao_reacao" resume a distribuição das reações casadas (etapa 2) para
    conferência com os números medidos ao vivo na issue de reescopo.
    """
    if "available_time" not in dataset.columns:
        raise ValueError(
            "dataset sem coluna available_time (data de publicação): reingira "
            "com collect+parser atuais — a reação é medida na publicação da ata."
        )

    etapas: list[dict] = []
    descartes: list[dict] = []

    n0 = len(reunioes_oficiais)
    etapas.append(
        {
            "etapa": "atas listadas pelo BCB",
            "restantes": n0,
            "removidas": 0,
            "motivo": "ponto de partida: lista oficial de reuniões (atas_listadas.json)",
        }
    )

    atas = (
        dataset.loc[dataset["tipo"] == "ata", ["numero_reuniao", "data_reuniao", "available_time"]]
        .drop_duplicates("numero_reuniao")
        .sort_values("data_reuniao")
        .reset_index(drop=True)
    )
    sem_texto = reunioes_oficiais[
        ~reunioes_oficiais["numero_reuniao"].isin(atas["numero_reuniao"])
    ]
    for r in sem_texto.itertuples(index=False):
        descartes.append(
            {
                "numero_reuniao": int(r.numero_reuniao),
                "data_reuniao": str(pd.Timestamp(r.data_reuniao).date()),
                "etapa": "com texto HTML",
                "motivo": "sem texto HTML no dataset (textoAta nulo ou HTTP 500; ver atas_sem_texto.json)",
            }
        )
    etapas.append(
        {
            "etapa": "com texto HTML",
            "restantes": len(atas),
            "removidas": n0 - len(atas),
            "motivo": "textoAta nulo ou HTTP 500 no detalhe: ata publicada só em PDF",
        }
    )

    com_reacao: list[dict] = []
    for ata in atas.itertuples(index=False):
        reacao = reacao_di1y(di1y, ata.available_time)
        pub = pd.Timestamp(ata.available_time).normalize()
        if reacao is None:
            descartes.append(
                {
                    "numero_reuniao": int(ata.numero_reuniao),
                    "data_reuniao": str(pd.Timestamp(ata.data_reuniao).date()),
                    "etapa": "com reação DI 1Y casada",
                    "motivo": (
                        f"publicação em {pub.date()} fora da janela viva da SGS 7806 "
                        "(02/01/2004–30/09/2019): sem D0/D+1"
                    ),
                }
            )
            continue
        com_reacao.append(
            {
                "numero_reuniao": int(ata.numero_reuniao),
                "data_reuniao": pd.Timestamp(ata.data_reuniao).normalize(),
                "data_publicacao_ata": pub,
                **reacao,
            }
        )
    etapas.append(
        {
            "etapa": "com reação DI 1Y casada (SGS 7806)",
            "restantes": len(com_reacao),
            "removidas": len(atas) - len(com_reacao),
            "motivo": "publicação fora da janela viva da 7806 (02/01/2004–30/09/2019)",
        }
    )

    finais: list[dict] = []
    datas_oficiais = reunioes_oficiais["data_reuniao"]
    for linha in com_reacao:
        rotulo = rotulo_focus(linha["data_reuniao"], datas_oficiais)
        mediana = mediana_focus_pre_reuniao(focus, rotulo, linha["data_reuniao"])
        par = decisao_apos_reuniao(selic, linha["data_reuniao"])
        if math.isnan(mediana) or math.isnan(par["decisao"]):
            motivo = (
                f"sem mediana Focus point-in-time para {rotulo} "
                "(ExpectativasMercadoSelic rotula reuniões a partir da R1/2006)"
                if math.isnan(mediana)
                else "série 432 sem observação pós-reunião: surpresa indefinida"
            )
            descartes.append(
                {
                    "numero_reuniao": linha["numero_reuniao"],
                    "data_reuniao": str(linha["data_reuniao"].date()),
                    "etapa": "com Focus por reunião",
                    "motivo": motivo,
                }
            )
            continue
        finais.append(
            {
                **linha,
                "rotulo_focus": rotulo,
                "regime": regime_bc(linha["data_reuniao"]),
                **par,
                "mediana_focus": mediana,
                "surpresa_decisao": round(par["decisao"] - mediana, 4),
            }
        )
    etapas.append(
        {
            "etapa": "com Focus por reunião",
            "restantes": len(finais),
            "removidas": len(com_reacao) - len(finais),
            "motivo": "ExpectativasMercadoSelic só rotula reuniões a partir da R1/2006",
        }
    )

    painel = pd.DataFrame(finais, columns=_COLUNAS_PAINEL_DI1Y)

    reacoes = pd.Series([l["reacao_bps"] for l in com_reacao], dtype="float64")
    # "acima_1bp" usa > estrito sobre o valor arredondado a 2 casas; reações
    # exatamente no limite (1.0 bp, o tick mínimo da série) ficam de fora e são
    # contadas à parte em "em_1bp_exato" — contagens com >= ou com float cru
    # diferem apenas pela alocação dessas bordas.
    validacao = {
        "n_reacoes_casadas": int(len(reacoes)),
        "dp_bps": round(float(reacoes.std()), 2) if len(reacoes) > 1 else None,
        "min_bps": round(float(reacoes.min()), 2) if len(reacoes) else None,
        "max_bps": round(float(reacoes.max()), 2) if len(reacoes) else None,
        "mediana_abs_bps": round(float(reacoes.abs().median()), 2) if len(reacoes) else None,
        "acima_1bp": int((reacoes.abs() > 1.0).sum()),
        "em_1bp_exato": int((reacoes.abs() == 1.0).sum()),
    }
    janela = {
        "inicio": str(painel["data_reuniao"].min().date()) if len(painel) else None,
        "fim": str(painel["data_reuniao"].max().date()) if len(painel) else None,
        "n_atas": int(len(painel)),
    }
    funil = {
        "etapas": etapas,
        "descartes": descartes,
        "validacao_reacao": validacao,
        "janela_final": janela,
    }
    return painel, funil
