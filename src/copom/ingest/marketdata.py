# CopomLens — Camada 1 (dados de mercado para a Camada 3): coleta a Meta Selic
# definida pelo Copom (SGS/BCB, serie 432), a taxa do swap DI x pre 360 dias
# corridos (SGS 7806 — a serie de maturidade constante que E a variavel-alvo
# DI 1Y, viva de 02/01/2004 a 30/09/2019) e a mediana das expectativas de Selic
# do boletim Focus (Olinda/BCB, ExpectativasMercadoSelic), normaliza e salva em
# data/raw/. O acesso ao SGS fatia automaticamente janelas maiores que 10 anos
# (limite da API para series diarias, que responde HTTP 406 acima disso).
"""Ingestao de dados de mercado do Banco Central (Selic + DI 1Y + Focus).

Fontes (publicas, sem chave):
- SGS serie 432 -> Meta Selic definida pelo Copom (% a.a.), diaria.
- SGS serie 7806 -> swap DI x pre 360 dias corridos (% a.a.), diaria; serie de
  maturidade constante (sempre 360 dc, por construcao) = taxa DI 1Y ja
  interpolada, sem rolagem de contrato. Descontinuada em 30/09/2019.
- Olinda Expectativas/ExpectativasMercadoSelic -> expectativas por reuniao do
  Copom (mediana, media, n. de respondentes), com a data de cada survey.

A disciplina point-in-time deste projeto exige que a "Selic esperada" de uma
reuniao seja a mediana conhecida ANTES da reuniao; por isso preservamos a coluna
`data` (data do survey) em vez de colapsar para um unico numero aqui.
"""
from __future__ import annotations

import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote, urlencode

import httpx
import pandas as pd

SGS_SELIC_META = 432  # Meta Selic definida pelo Copom (% a.a.)
SGS_DI1Y_SWAP = 7806  # Swap DI x pre 360 dias corridos (% a.a.)
SGS_BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"

# Janela viva da 7806, verificada ao vivo (docs/bloqueio_DI_1Y.md): a BM&F/B3
# reportou a serie de 02/01/2004 a 30/09/2019; depois disso ela morre. Carga
# unica + guarda estatica: serie descontinuada nao sofre revisao.
DI1Y_DATA_INICIAL = "02/01/2004"
DI1Y_DATA_FINAL = "30/09/2019"

# O SGS limita consultas de series diarias a janelas de ate 10 anos e responde
# HTTP 406 acima disso (comportamento documentado da API de dados abertos do
# BCB). fetch_sgs fatia a janela pedida em blocos de ate 10 anos e concatena.
SGS_JANELA_MAX_ANOS = 10
FOCUS_BASE = (
    "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
    "ExpectativasMercadoSelic"
)

_TIMEOUT = httpx.Timeout(90.0, connect=15.0)
_MAX_TENTATIVAS = 4
# Headers padrao de cliente HTTP identificavel para as APIs publicas do BCB.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}

# Diretorio de dados imutaveis (reconstruivel pelo pipeline). Resolvido a partir
# da raiz do repositorio para funcionar independente do cwd.
DATA_RAW = Path(__file__).resolve().parents[3] / "data" / "raw"


def _get_json(url: str, params: dict | None = None) -> object:
    """GET com timeout, retry com backoff e checagem de status e de corpo.

    As APIs do BCB sao publicas e por vezes lentas/instaveis; tenta novamente em
    timeout, erro de rede OU resposta 200 sem JSON valido (o SGS devolve
    ocasionalmente corpo vazio/HTML transitorio com status 200). Levanta com o
    corpo da resposta em caso de status != 200 ou de corpo invalido persistente,
    para que o erro diga exatamente o que a API respondeu.
    """
    with httpx.Client(timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True) as client:
        ultimo_erro: Exception | None = None
        for tentativa in range(1, _MAX_TENTATIVAS + 1):
            try:
                resp = client.get(url, params=params)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                ultimo_erro = exc
                if tentativa < _MAX_TENTATIVAS:
                    time.sleep(2**tentativa)
                    continue
                raise
            if resp.status_code != 200:
                raise httpx.HTTPStatusError(
                    f"{resp.status_code} ao acessar {resp.url}\n--- corpo (300 chars) ---\n"
                    f"{resp.text[:300]}",
                    request=resp.request,
                    response=resp,
                )
            try:
                return resp.json()
            except ValueError as exc:  # json.JSONDecodeError e subclasse de ValueError
                ultimo_erro = exc
                if tentativa < _MAX_TENTATIVAS:
                    time.sleep(2**tentativa)
                    continue
                raise ValueError(
                    f"Resposta 200 sem JSON valido em {resp.url} "
                    f"(content-type: {resp.headers.get('content-type')!r}, "
                    f"{len(resp.content)} bytes)\n--- corpo (300 chars) ---\n"
                    f"{resp.text[:300]}"
                ) from exc
        raise ultimo_erro  # type: ignore[misc]


def _janelas_sgs(data_inicial: str, data_final: str) -> list[tuple[str, str]]:
    """Fatia [data_inicial, data_final] (dd/mm/aaaa, inclusivas) em janelas
    contiguas de ate SGS_JANELA_MAX_ANOS, sem sobreposicao nem buraco."""
    inicio = pd.to_datetime(data_inicial, format="%d/%m/%Y")
    fim = pd.to_datetime(data_final, format="%d/%m/%Y")
    if fim < inicio:
        raise ValueError(
            f"data_final {data_final} anterior a data_inicial {data_inicial}"
        )
    janelas: list[tuple[str, str]] = []
    while inicio <= fim:
        fim_janela = min(
            fim, inicio + pd.DateOffset(years=SGS_JANELA_MAX_ANOS) - pd.Timedelta(days=1)
        )
        janelas.append((inicio.strftime("%d/%m/%Y"), fim_janela.strftime("%d/%m/%Y")))
        inicio = fim_janela + pd.Timedelta(days=1)
    return janelas


def fetch_sgs(
    codigo: int,
    data_inicial: str,
    data_final: str | None = None,
    coluna: str = "valor",
) -> pd.DataFrame:
    """Puxa uma serie diaria do SGS em qualquer janela, fatiando em blocos de
    ate 10 anos (limite da API; HTTP 406 acima).

    Datas em dd/mm/aaaa; `data_final` ausente vira hoje. Saida: DataFrame
    ['data', coluna] ordenado, `data` datetime e valor em float; duplicatas de
    borda entre blocos sao removidas.
    """
    if data_final is None:
        data_final = date.today().strftime("%d/%m/%Y")

    quadros: list[pd.DataFrame] = []
    for ini, fim in _janelas_sgs(data_inicial, data_final):
        raw = _get_json(
            SGS_BASE.format(codigo=codigo),
            params={"formato": "json", "dataInicial": ini, "dataFinal": fim},
        )
        if raw:
            quadros.append(pd.DataFrame(raw))

    if not quadros:
        return pd.DataFrame(columns=["data", coluna])

    df = pd.concat(quadros, ignore_index=True)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df[coluna] = pd.to_numeric(
        df["valor"].astype(str).str.replace(",", ".", regex=False)
    )
    df = df.drop_duplicates(subset="data", keep="first")
    return df[["data", coluna]].sort_values("data").reset_index(drop=True)


def fetch_selic_meta(
    data_inicial: str | None = None, data_final: str | None = None
) -> pd.DataFrame:
    """Puxa a Meta Selic (serie SGS 432).

    Datas no formato dd/mm/aaaa (padrao da API SGS). Sem `data_inicial`, usa os
    ultimos ~10 anos (cobre as reunioes recentes do Copom); janelas maiores sao
    fatiadas automaticamente por fetch_sgs. Saida: DataFrame
    ['data', 'selic_meta'] ordenado por data, `data` como datetime e
    `selic_meta` em float (% a.a.).
    """
    if data_inicial is None:
        data_inicial = (date.today() - timedelta(days=3650)).strftime("%d/%m/%Y")
    return fetch_sgs(SGS_SELIC_META, data_inicial, data_final, coluna="selic_meta")


def fetch_di1y(
    data_inicial: str = DI1Y_DATA_INICIAL, data_final: str = DI1Y_DATA_FINAL
) -> pd.DataFrame:
    """Puxa a taxa do swap DI x pre 360 dias corridos (SGS 7806), % a.a.

    E a serie de MATURIDADE CONSTANTE do DI 1Y: sempre 360 dc, todo dia, por
    construcao — ja e a "taxa interpolada" exigida como variavel-alvo, sem
    rolagem de contrato (o contrato cru envelhece e cria saltos artificiais).
    Janela default = vida inteira da serie (descontinuada em 30/09/2019).
    Saida: DataFrame ['data', 'di1y'] ordenado, taxa em float (% a.a.).
    """
    return fetch_sgs(SGS_DI1Y_SWAP, data_inicial, data_final, coluna="di1y")


def _coletar_focus_paginado(
    data_inicial: str | None, pagina: int, max_paginas: int
) -> list[dict]:
    """Coleta surveys do Focus via paginacao `$skip`/`$top`, ordenando por data
    desc. Para cedo quando a pagina ja contem datas < data_inicial (cobertura
    garantida) ou quando a API devolve uma pagina incompleta/vazia (fim)."""
    registros: list[dict] = []
    for n in range(max_paginas):
        params = {
            "$top": str(pagina),
            "$skip": str(n * pagina),
            "$format": "json",
            "$select": "Indicador,Data,Reuniao,Media,Mediana,numeroRespondentes,baseCalculo",
            "$orderby": "Data desc",
        }
        # Codifica espaco como %20 (e nao '+') e preserva '$' literal: o Olinda rejeita '%24'.
        url = f"{FOCUS_BASE}?{urlencode(params, quote_via=quote, safe='$')}"
        raw = _get_json(url)
        lote = raw.get("value", []) if isinstance(raw, dict) else (raw or [])
        if not lote:
            break
        registros.extend(lote)
        if len(lote) < pagina:
            break
        if data_inicial and min(str(r.get("Data", "")) for r in lote) < data_inicial:
            break
    return registros


def fetch_focus_selic(
    data_inicial: str | None = None,
    base_calculo: int | None = 0,
    pagina: int = 1000,
    max_paginas: int = 500,
) -> pd.DataFrame:
    """Puxa as expectativas de Selic do Focus (Olinda ExpectativasMercadoSelic).

    Parametros:
    - data_inicial: 'aaaa-mm-dd'; mantem surveys com data >= data_inicial.
    - base_calculo: 0 = janela cheia de coleta; 1 = ultimos 5 dias uteis.
      Default 0 (mais respondentes). Use None para trazer ambas as bases.
    - pagina: tamanho de cada requisicao (paginacao via $skip/$top).
    - max_paginas: trava de seguranca contra loop (pagina * max_paginas linhas).

    O filtro de data e de base_calculo e feito no cliente (pandas): o parser
    OData do Olinda rejeita o `$filter` combinado com erro de tipo. Em vez de um
    teto fixo, paginamos por `$skip` ordenando por data desc e paramos assim que
    a pagina ja alcanca `data_inicial` — cobre qualquer janela sem baixar tudo.

    Saida: DataFrame ['reuniao', 'data', 'mediana', 'media', 'n_respondentes',
    'base_calculo'] com `data` datetime e numericos em float.
    """
    registros = _coletar_focus_paginado(data_inicial, pagina, max_paginas)
    df = pd.DataFrame(registros)
    if df.empty:
        return pd.DataFrame(
            columns=["reuniao", "data", "mediana", "media", "n_respondentes", "base_calculo"]
        )

    df = df.rename(
        columns={
            "Reuniao": "reuniao",
            "Data": "data",
            "Mediana": "mediana",
            "Media": "media",
            "numeroRespondentes": "n_respondentes",
            "baseCalculo": "base_calculo",
        }
    )
    df["data"] = pd.to_datetime(df["data"])
    for col in ("mediana", "media"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["n_respondentes"] = pd.to_numeric(df["n_respondentes"], errors="coerce").astype("Int64")
    df["base_calculo"] = pd.to_numeric(df["base_calculo"], errors="coerce").astype("Int64")

    if data_inicial:
        df = df[df["data"] >= pd.Timestamp(data_inicial)]
    if base_calculo is not None:
        df = df[df["base_calculo"] == int(base_calculo)]

    return (
        df[["reuniao", "data", "mediana", "media", "n_respondentes", "base_calculo"]]
        .sort_values(["reuniao", "data"])
        .reset_index(drop=True)
    )


def save_series(df: pd.DataFrame, nome: str, destino: Path = DATA_RAW) -> Path:
    """Salva o DataFrame como CSV em data/raw/ e retorna o caminho gravado."""
    destino.mkdir(parents=True, exist_ok=True)
    caminho = destino / f"{nome}.csv"
    df.to_csv(caminho, index=False, encoding="utf-8")
    return caminho


def _faixa(df: pd.DataFrame, col: str = "data") -> str:
    if df.empty:
        return "vazia"
    return f"{df[col].min().date()} -> {df[col].max().date()}"


def main() -> None:
    """Carga completa das tres series em data/raw/, com janelas explicitas e
    justificadas (nenhuma herdada de default):

    - selic_meta (432) desde 01/01/2004: cobre o nivel pre-reuniao da R1/2006
      com folga e segue ate hoje para as reunioes recentes;
    - di1y_7806 na janela viva inteira (02/01/2004 a 30/09/2019): carga unica,
      serie descontinuada nao sofre revisao;
    - focus_selic desde 01/11/2004: inicio do recurso ExpectativasMercadoSelic
      no Olinda (historico completo por reuniao; a paginacao desc percorre tudo
      — a carga inteira leva alguns minutos).
    """
    selic = fetch_selic_meta(data_inicial="01/01/2004")
    p1 = save_series(selic, "selic_meta")
    print(f"Selic meta (SGS 432): {len(selic)} linhas [{_faixa(selic)}] -> {p1}")

    di1y = fetch_di1y()
    p2 = save_series(di1y, "di1y_7806")
    print(f"DI 1Y swap 360dc (SGS 7806): {len(di1y)} linhas [{_faixa(di1y)}] -> {p2}")

    focus = fetch_focus_selic(data_inicial="2004-11-01", base_calculo=0)
    p3 = save_series(focus, "focus_selic")
    print(f"Focus Selic: {len(focus)} linhas [{_faixa(focus)}] -> {p3}")


if __name__ == "__main__":
    main()
