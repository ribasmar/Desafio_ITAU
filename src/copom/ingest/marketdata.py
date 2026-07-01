# CopomLens — Camada 1 (dados de mercado para a Camada 3): coleta a Meta Selic
# definida pelo Copom (SGS/BCB, serie 432) e a mediana das expectativas de Selic
# do boletim Focus (Olinda/BCB, ExpectativasMercadoSelic), normaliza e salva em
# data/raw/. Estes dois insumos alimentam o calculo da surpresa da decisao.
"""Ingestao de dados de mercado do Banco Central (Selic efetiva + Focus).

Fontes (publicas, sem chave):
- SGS serie 432 -> Meta Selic definida pelo Copom (% a.a.), diaria.
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
SGS_BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
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
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# Diretorio de dados imutaveis (reconstruivel pelo pipeline). Resolvido a partir
# da raiz do repositorio para funcionar independente do cwd.
DATA_RAW = Path(__file__).resolve().parents[3] / "data" / "raw"


def _get_json(url: str, params: dict | None = None) -> object:
    """GET com timeout, retry com backoff e checagem de status.

    As APIs do BCB sao publicas e por vezes lentas/instaveis; tenta novamente em
    timeout ou erro de rede (backoff exponencial), e levanta com o corpo da
    resposta em caso de status != 200.
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
            return resp.json()
        raise ultimo_erro  # type: ignore[misc]


def fetch_selic_meta(
    data_inicial: str | None = None, data_final: str | None = None
) -> pd.DataFrame:
    """Puxa a Meta Selic (serie SGS 432).

    Datas no formato dd/mm/aaaa (padrao da API SGS). O SGS exige `dataInicial`
    para series diarias e limita a janela a 10 anos; sem `data_inicial`, usa por
    padrao os ultimos ~10 anos (cobre todas as reunioes recentes do Copom).
    Saida: DataFrame ['data', 'selic_meta'] ordenado por data, `data` como
    datetime e `selic_meta` em float (% a.a.).
    """
    if data_inicial is None:
        data_inicial = (date.today() - timedelta(days=3650)).strftime("%d/%m/%Y")

    params = {"formato": "json", "dataInicial": data_inicial}
    if data_final:
        params["dataFinal"] = data_final

    raw = _get_json(SGS_BASE.format(codigo=SGS_SELIC_META), params=params)
    df = pd.DataFrame(raw)
    if df.empty:
        return pd.DataFrame(columns=["data", "selic_meta"])

    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df["selic_meta"] = pd.to_numeric(
        df["valor"].astype(str).str.replace(",", ".", regex=False)
    )
    return df[["data", "selic_meta"]].sort_values("data").reset_index(drop=True)


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
        # Codifica espaco como %20 (e nao '+'): o parser OData do Olinda rejeita '+'.
        url = f"{FOCUS_BASE}?{urlencode(params, quote_via=quote, safe='')}"
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


def main() -> None:
    """Coleta as duas series e grava em data/raw/. Janela do Focus a partir de
    2024 para cobrir as reunioes recentes sem baixar todo o historico."""
    selic = fetch_selic_meta()
    p1 = save_series(selic, "selic_meta")
    print(f"Selic meta: {len(selic)} linhas -> {p1}")

    focus = fetch_focus_selic(data_inicial="2024-01-01", base_calculo=0)
    p2 = save_series(focus, "focus_selic")
    print(f"Focus Selic: {len(focus)} linhas -> {p2}")


if __name__ == "__main__":
    main()
