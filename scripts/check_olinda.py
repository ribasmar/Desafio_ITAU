"""Smoke test da API Olinda (Expectativas de Mercado / Focus) para a task #6.

Verifica os dois recursos que a camada de surpresa consome:
  1. ExpectativasMercadoSelic  - expectativa por reuniao do Copom (esperado: inicio ~nov/2004)
  2. ExpectativaMercadoMensais - mediana mensal da Selic, proxy do periodo anterior (~nov/2001)

O Olinda rejeita query strings com '$' percent-encodado ('%24') e espaco como '+',
entao a URL e montada manualmente com '$' literal e '%20'/'%27' nos valores.

Uso: python scripts/check_olinda.py
Saida esperada: HTTP 200 nos dois recursos, primeira/ultima data e campos disponiveis.
"""

import sys

import httpx

BASE = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata"
TIMEOUT = httpx.Timeout(30.0)
HEADERS = {"Accept": "application/json", "User-Agent": "copom-quant-ai/0.1 (smoke test)"}

CHECKS = [
    {
        "recurso": "ExpectativasMercadoSelic",
        "filtro": None,
        "esperado_inicio": "2004-11",
    },
    {
        "recurso": "ExpectativaMercadoMensais",
        "filtro": "Indicador eq 'Selic'",
        "esperado_inicio": "2001-11",
    },
]


def consultar(client: httpx.Client, recurso: str, filtro: str | None, ordem: str) -> list[dict]:
    query = f"$top=3&$orderby=Data%20{ordem}&$format=json"
    if filtro:
        query += "&$filter=" + filtro.replace(" ", "%20").replace("'", "%27")
    resp = client.get(f"{BASE}/{recurso}?{query}")
    resp.raise_for_status()
    return resp.json()["value"]


def main() -> int:
    falhas = 0
    with httpx.Client(timeout=TIMEOUT, headers=HEADERS, follow_redirects=True) as client:
        for check in CHECKS:
            recurso, filtro = check["recurso"], check["filtro"]
            print(f"\n=== {recurso} ===")
            try:
                primeiros = consultar(client, recurso, filtro, "asc")
                ultimos = consultar(client, recurso, filtro, "desc")
            except httpx.HTTPError as exc:
                print(f"FALHA: {exc}")
                falhas += 1
                continue

            if not primeiros:
                print("FALHA: resposta vazia")
                falhas += 1
                continue

            print(f"campos: {sorted(primeiros[0].keys())}")
            print(f"primeira data: {primeiros[0]['Data']} (esperado ~{check['esperado_inicio']})")
            print(f"ultima data:   {ultimos[0]['Data']}")
            print(f"exemplo: {primeiros[0]}")

            if not primeiros[0]["Data"].startswith(check["esperado_inicio"]):
                print("AVISO: inicio da serie difere do esperado - revisar premissa da amostra")

    print(f"\n{'OK - premissas confirmadas' if falhas == 0 else f'{falhas} recurso(s) com falha'}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
