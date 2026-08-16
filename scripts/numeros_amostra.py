# CopomLens — fecha os números da amostra usados no relatório. Lê os artefatos
# do pipeline (lista oficial de reuniões, corpus parseado, manifesto de fontes e
# painel do alvo DI 1Y), recalcula cada corte com a razão escrita, valida as
# identidades de reconciliação (HTML + PDF = painel; painel + sem-alvo = corpus
# escorado) e grava numeros_amostra.json. Nenhum número citado no relatório é
# digitado à mão: todos saem daqui, e uma identidade que não fecha derruba o
# script com código 1 em vez de imprimir um número silenciosamente errado.
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")

# Anos de reunião cobertos pela escoragem do LLM. Não é um limite dos dados: é
# a decisão do time de escorar a janela em que o alvo (SGS 7806, última
# observação em 30/09/2019) poderia existir. Fica como parâmetro para que a
# razão seja auditável e o número não venha de constante embutida.
JANELA_ESCORAGEM_PADRAO = "2006:2019"

FONTE_PADRAO = "api_html"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Recalcula os números da amostra citados no relatório (atas "
            "listadas, corpus escorado, linhas do painel, reuniões pareadas "
            "ata/comunicado) com a razão de cada corte e valida a "
            "reconciliação entre eles."
        ),
    )
    parser.add_argument("--raw-path", type=str, default=str(RAW_DIR))
    parser.add_argument("--processed-path", type=str, default=str(PROCESSED_DIR))
    parser.add_argument(
        "--janela-escoragem",
        type=str,
        default=JANELA_ESCORAGEM_PADRAO,
        help=(
            "anos de reunião escorados pelo LLM, formato ANO_INI:ANO_FIM "
            f"(padrão {JANELA_ESCORAGEM_PADRAO}, cobre a vida útil da SGS 7806)"
        ),
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="JSON de saída (padrão: <processed>/numeros_amostra.json)",
    )
    return parser.parse_args(argv)


def _janela(texto: str) -> tuple[int, int]:
    try:
        ini, fim = (int(p) for p in texto.split(":", 1))
    except ValueError as erro:
        raise ValueError(
            f"--janela-escoragem espera ANO_INI:ANO_FIM, recebeu {texto!r}"
        ) from erro
    if ini > fim:
        raise ValueError(f"janela invertida em --janela-escoragem: {texto!r}")
    return ini, fim


def carregar_listadas(caminho: Path) -> dict[int, str]:
    """Lista oficial de reuniões do BCB (atas_listadas.json): número → data de
    referência. É o universo de partida do funil e a base do rótulo R{k}/{ano};
    inclui reuniões sem texto disponível."""
    with open(caminho, encoding="utf-8") as f:
        bruto = json.load(f)
    return {int(item["nroReuniao"]): str(item["dataReferencia"])[:10] for item in bruto}


def carregar_corpus(caminho: Path) -> dict[int, dict[str, dict]]:
    """Corpus parseado (copom_dataset.jsonl): reunião → tipo → {data, chars}.
    Um documento por linha; `tipo` separa ata de comunicado da mesma reunião."""
    corpus: dict[int, dict[str, dict]] = {}
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            if not linha.strip():
                continue
            doc = json.loads(linha)
            numero = int(doc["numero_reuniao"])
            corpus.setdefault(numero, {})[str(doc["tipo"])] = {
                "data_reuniao": str(doc["data_reuniao"])[:10],
                "chars": len((doc.get("text") or "").strip()),
            }
    return corpus


def carregar_fontes(caminho: Path) -> dict[tuple[int, str], str]:
    """Manifesto da ingestão (manifest.json): (reunião, tipo) → fonte do texto.
    Ausência do campo `fonte` significa texto vindo do campo textoAta da API
    (derivado do HTML); o fallback de PDF grava fonte="pdf" explicitamente."""
    with open(caminho, encoding="utf-8") as f:
        bruto = json.load(f)
    return {
        (int(item["numero_reuniao"]), str(item["tipo"])): str(
            item.get("fonte") or FONTE_PADRAO
        )
        for item in bruto
    }


def carregar_painel(caminho: Path) -> list[dict]:
    """Painel do alvo (painel_di1y.csv): uma linha por ata que sobreviveu ao
    funil completo — texto, reação DI 1Y casada e mediana Focus point-in-time."""
    with open(caminho, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def carregar_descartes(caminho: Path) -> dict[int, str]:
    """Razão de descarte por reunião, como gravada pelo próprio pipeline em
    funil_amostra.json. Evita reescrever à mão o motivo de cada corte."""
    if not caminho.exists():
        return {}
    with open(caminho, encoding="utf-8") as f:
        funil = json.load(f)
    return {
        int(item["numero_reuniao"]): str(item["motivo"])
        for item in funil.get("descartes", [])
    }


def _resumo_janela(linhas: list[dict]) -> dict:
    datas = sorted(linha["data_reuniao"] for linha in linhas)
    numeros = sorted(int(linha["numero_reuniao"]) for linha in linhas)
    return {
        "n": len(linhas),
        "inicio": datas[0] if datas else None,
        "fim": datas[-1] if datas else None,
        "primeira_reuniao": numeros[0] if numeros else None,
        "ultima_reuniao": numeros[-1] if numeros else None,
    }


def montar_numeros(
    listadas: dict[int, str],
    corpus: dict[int, dict[str, dict]],
    fontes: dict[tuple[int, str], str],
    painel: list[dict],
    descartes: dict[int, str],
    janela: tuple[int, int],
) -> tuple[dict, list[str]]:
    """Monta o bloco de números do relatório e a lista de falhas de
    reconciliação. Cada número vem com a razão do corte que o produziu."""
    ano_ini, ano_fim = janela
    falhas: list[str] = []

    atas_corpus = {n: d["ata"] for n, d in corpus.items() if "ata" in d}
    comunicados_corpus = {n: d["comunicado"] for n, d in corpus.items() if "comunicado" in d}
    vazios = sorted(n for n, ata in atas_corpus.items() if ata["chars"] == 0)
    if vazios:
        falhas.append(f"atas com texto vazio no corpus: {vazios[:10]}")

    escoradas = {
        n: ata
        for n, ata in atas_corpus.items()
        if ano_ini <= int(ata["data_reuniao"][:4]) <= ano_fim
    }
    no_painel = {int(linha["numero_reuniao"]) for linha in painel}
    sem_alvo = sorted(set(escoradas) - no_painel)

    por_fonte: dict[str, list[dict]] = {}
    for linha in painel:
        numero = int(linha["numero_reuniao"])
        fonte = fontes.get((numero, "ata"), FONTE_PADRAO)
        por_fonte.setdefault(fonte, []).append(linha)

    pareadas_painel = sorted(n for n in no_painel if n in comunicados_corpus)
    fora_da_lista = sorted(n for n in no_painel if n not in listadas)
    if fora_da_lista:
        falhas.append(
            f"reuniões no painel ausentes da lista oficial do BCB: {fora_da_lista}"
        )

    soma_fontes = sum(len(v) for v in por_fonte.values())
    if soma_fontes != len(painel):
        falhas.append(
            f"soma por fonte ({soma_fontes}) difere das linhas do painel ({len(painel)})"
        )
    if len(escoradas) != len(painel) + len(sem_alvo):
        falhas.append(
            f"corpus escorado ({len(escoradas)}) != painel ({len(painel)}) + "
            f"sem alvo ({len(sem_alvo)})"
        )

    numeros = {
        "janela_escoragem": {"ano_inicial": ano_ini, "ano_final": ano_fim},
        "atas_listadas_bcb": {
            "n": len(listadas),
            "razao": "lista oficial de reuniões do BCB (atas_listadas.json), universo de partida",
        },
        "documentos_no_corpus": {
            "n_atas": len(atas_corpus),
            "n_comunicados": len(comunicados_corpus),
            "razao": "documentos com texto extraído (API/HTML ou fallback PDF)",
        },
        "corpus_escorado_llm": {
            "n": len(escoradas),
            "razao": (
                f"atas com texto de reuniões de {ano_ini} a {ano_fim} — janela "
                "escorada pelo LLM, definida pela vida útil da série do alvo"
            ),
            **_resumo_janela(
                [
                    {"numero_reuniao": n, "data_reuniao": ata["data_reuniao"]}
                    for n, ata in escoradas.items()
                ]
            ),
        },
        "painel_alvo_di1y": {
            "n": len(painel),
            "razao": (
                "atas do corpus escorado com reação DI 1Y casada (SGS 7806 viva "
                "na publicação) E mediana Focus point-in-time da reunião"
            ),
            **_resumo_janela(painel),
            "por_fonte_do_texto": {
                fonte: _resumo_janela(linhas) for fonte, linhas in sorted(por_fonte.items())
            },
            "por_regime": dict(sorted(Counter(l["regime"] for l in painel).items())),
        },
        "escoradas_sem_alvo": {
            "n": len(sem_alvo),
            "razao": "atas escoradas cuja publicação cai fora da janela viva da SGS 7806",
            "reunioes": [
                {
                    "numero_reuniao": n,
                    "data_reuniao": escoradas[n]["data_reuniao"],
                    "motivo": descartes.get(n, "motivo não gravado no funil"),
                }
                for n in sem_alvo
            ],
        },
        "pareadas_ata_comunicado": {
            "n_no_painel": len(pareadas_painel),
            "n_no_corpus": len(set(atas_corpus) & set(comunicados_corpus)),
            "razao": (
                "reuniões do painel que também têm comunicado com texto — "
                "amostra máxima da feature de divergência ata↔comunicado; o "
                "recorte efetivo da feature é decidido na issue que a implementa"
            ),
        },
    }
    return numeros, falhas


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    raw = Path(args.raw_path)
    processed = Path(args.processed_path)
    out = Path(args.out) if args.out else processed / "numeros_amostra.json"

    entradas = {
        raw / "atas_listadas.json": "python -m copom.ingest.collect --last 300",
        raw / "manifest.json": "python -m copom.ingest.collect --last 300",
        processed / "copom_dataset.jsonl": "python -m copom.ingest.parser",
        processed / "painel_di1y.csv": "python -m copom.surprise",
    }
    faltando = [(p, cmd) for p, cmd in entradas.items() if not p.exists()]
    if faltando:
        for p, cmd in faltando:
            print(f"FALTA {p} — gere com: {cmd}")
        return 1

    try:
        janela = _janela(args.janela_escoragem)
    except ValueError as erro:
        print(f"ERRO: {erro}")
        return 1

    numeros, falhas = montar_numeros(
        listadas=carregar_listadas(raw / "atas_listadas.json"),
        corpus=carregar_corpus(processed / "copom_dataset.jsonl"),
        fontes=carregar_fontes(raw / "manifest.json"),
        painel=carregar_painel(processed / "painel_di1y.csv"),
        descartes=carregar_descartes(processed / "funil_amostra.json"),
        janela=janela,
    )

    painel = numeros["painel_alvo_di1y"]
    escorado = numeros["corpus_escorado_llm"]
    sem_alvo = numeros["escoradas_sem_alvo"]
    pareadas = numeros["pareadas_ata_comunicado"]

    print("Números da amostra (cada um com a razão do corte):")
    print(
        f"  atas listadas pelo BCB                    {numeros['atas_listadas_bcb']['n']:>4}"
        f"  · {numeros['atas_listadas_bcb']['razao']}"
    )
    print(
        f"  atas escoradas pelo LLM                   {escorado['n']:>4}"
        f"  · {escorado['inicio']} a {escorado['fim']}"
        f" (reuniões {escorado['primeira_reuniao']}–{escorado['ultima_reuniao']})"
    )
    print(
        f"  linhas do painel do alvo DI 1Y            {painel['n']:>4}"
        f"  · {painel['inicio']} a {painel['fim']}"
        f" (reuniões {painel['primeira_reuniao']}–{painel['ultima_reuniao']})"
    )
    for fonte, resumo in painel["por_fonte_do_texto"].items():
        print(
            f"    ├─ texto via {fonte:<10}                {resumo['n']:>4}"
            f"  · {resumo['inicio']} a {resumo['fim']}"
        )
    print(
        f"  escoradas sem alvo                        {sem_alvo['n']:>4}"
        f"  · {sem_alvo['razao']}"
    )
    for reuniao in sem_alvo["reunioes"]:
        print(f"    ├─ reunião {reuniao['numero_reuniao']} ({reuniao['data_reuniao']}): {reuniao['motivo']}")
    print(
        f"  reuniões com ata e comunicado pareados    {pareadas['n_no_painel']:>4}"
        f"  · dentro do painel ({pareadas['n_no_corpus']} no corpus inteiro)"
    )
    print("\nIdentidades de reconciliação:")
    partes = " + ".join(
        f"{resumo['n']} ({fonte})" for fonte, resumo in painel["por_fonte_do_texto"].items()
    )
    print(f"  {partes} = {painel['n']} linhas do painel")
    print(f"  {painel['n']} + {sem_alvo['n']} sem alvo = {escorado['n']} atas escoradas")

    if falhas:
        print("\nRECONCILIAÇÃO QUEBRADA:")
        for falha in falhas:
            print(f"  - {falha}")
        return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(numeros, f, ensure_ascii=False, indent=2)
    print(f"\nNúmeros -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
