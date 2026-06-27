import json
import logging
from pathlib import Path

import httpx

urlBase = "https://www.bcb.gov.br/api/servico/sitebcb/copom"
caminhoRaw = Path("data/raw")
arquivoManifesto = "manifest.json"
usuarioAgente = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36'"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
registrador = logging.getLogger(__name__)


def _cliente() -> httpx.Client:
    return httpx.Client(
        base_url=urlBase,
        headers={"User-Agent": usuarioAgente},
        timeout=30.0,
    )


def _carregarManifesto(caminhoBase: Path) -> list[dict]:
    caminho = caminhoBase / arquivoManifesto
    if caminho.exists():
        with open(caminho, "r", encoding="utf-8") as arquivo:
            return json.load(arquivo)
    return []


def _escreverManifesto(caminhoBase: Path, manifesto: list[dict]) -> None:
    caminho = caminhoBase / arquivoManifesto
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(manifesto, arquivo, ensure_ascii=False, indent=2)


# ── API calls ──────────────────────────────────────────────────────────


def buscarListaAtas(quantidade: int = 30) -> list[dict]:
    with _cliente() as cliente:
        resposta = cliente.get(f"/atas?quantidade={quantidade}")
        resposta.raise_for_status()
        return resposta.json()["conteudo"]


def buscarDetalheAta(numeroReuniao: int) -> dict | None:
    with _cliente() as cliente:
        resposta = cliente.get(f"/atas_detalhes?nro_reuniao={numeroReuniao}")
        if resposta.status_code == 500:
            registrador.warning("Ata %d retornou 500 (PDF-only, sem texto HTML)", numeroReuniao)
            return None
        resposta.raise_for_status()
        return resposta.json()["conteudo"][0]


def buscarListaComunicados(quantidade: int = 30) -> list[dict]:
    with _cliente() as cliente:
        resposta = cliente.get(f"/comunicados?quantidade={quantidade}")
        resposta.raise_for_status()
        return resposta.json()["conteudo"]


def buscarDetalheComunicado(numeroReuniao: int) -> dict | None:
    with _cliente() as cliente:
        resposta = cliente.get(f"/comunicados_detalhes?nro_reuniao={numeroReuniao}")
        if resposta.status_code == 500:
            registrador.warning("Comunicado %d retornou 500", numeroReuniao)
            return None
        resposta.raise_for_status()
        return resposta.json()["conteudo"][0]


# ── Save helpers ───────────────────────────────────────────────────────


def _salvarArquivoRaw(
    caminhoBase: Path,
    nomeArquivo: str,
    conteudo: str,
) -> bool:
    caminhoArquivo = caminhoBase / nomeArquivo
    if caminhoArquivo.exists():
        registrador.info("  → j\u00e1 existe: %s (pulando)", nomeArquivo)
        return False
    caminhoArquivo.write_text(conteudo, encoding="utf-8")
    registrador.info("  → salvo: %s (%d bytes)", nomeArquivo, len(conteudo))
    return True


def _construirEntradaManifesto(
    tipo: str,
    numeroReuniao: int,
    dataReuniao: str,
    dataPublicacao: str,
    nomeArquivo: str,
) -> dict:
    endpointDetalhe = "atas_detalhes" if tipo == "ata" else "comunicados_detalhes"
    return {
        "url": f"{urlBase}/{endpointDetalhe}?nro_reuniao={numeroReuniao}",
        "data_publicacao": dataPublicacao,
        "data_reuniao": dataReuniao,
        "tipo": tipo,
        "numero_reuniao": numeroReuniao,
        "filename": nomeArquivo,
    }


# ── Collectors ─────────────────────────────────────────────────────────


def coletarAtas(quantidade: int = 20, caminhoBase: Path = caminhoRaw) -> int:
    base = Path(caminhoBase)
    base.mkdir(parents=True, exist_ok=True)
    manifesto = _carregarManifesto(base)
    numerosExistentes: set[int] = {
        e["numero_reuniao"] for e in manifesto if e["tipo"] == "ata"
    }
    listaAtas = buscarListaAtas(quantidade)
    novasEntradas: list[dict] = []
    for ata in listaAtas:
        numero = ata["nroReuniao"]
        if numero in numerosExistentes:
            registrador.info("Ata %d j\u00e1 registrada no manifesto, pulando", numero)
            continue
        detalhe = buscarDetalheAta(numero)
        if detalhe is None:
            continue
        dataReuniao = detalhe["dataReferencia"]
        dataPublicacao = detalhe["dataPublicacao"]
        nomeArquivo = f"ata_{numero}_{dataReuniao}.txt"
        texto = detalhe["textoAta"]
        salvo = _salvarArquivoRaw(base, nomeArquivo, texto)
        if not salvo:
            continue
        entrada = _construirEntradaManifesto(
            tipo="ata",
            numeroReuniao=numero,
            dataReuniao=dataReuniao,
            dataPublicacao=dataPublicacao,
            nomeArquivo=nomeArquivo,
        )
        novasEntradas.append(entrada)
    if novasEntradas:
        manifesto.extend(novasEntradas)
        _escreverManifesto(base, manifesto)
    return len(novasEntradas)


def coletarComunicados(quantidade: int = 20, caminhoBase: Path = caminhoRaw) -> int:
    base = Path(caminhoBase)
    base.mkdir(parents=True, exist_ok=True)
    manifesto = _carregarManifesto(base)
    numerosExistentes: set[int] = {
        e["numero_reuniao"] for e in manifesto if e["tipo"] == "comunicado"
    }
    listaComunicados = buscarListaComunicados(quantidade)
    novasEntradas: list[dict] = []
    for com in listaComunicados:
        numero = com["nro_reuniao"]
        if numero in numerosExistentes:
            registrador.info("Comunicado %d j\u00e1 registrado no manifesto, pulando", numero)
            continue
        detalhe = buscarDetalheComunicado(numero)
        if detalhe is None:
            continue
        dataReuniao = detalhe["dataReferencia"]
        nomeArquivo = f"comunicado_{numero}_{dataReuniao}.txt"
        texto = detalhe["textoComunicado"]
        salvo = _salvarArquivoRaw(base, nomeArquivo, texto)
        if not salvo:
            continue
        entrada = _construirEntradaManifesto(
            tipo="comunicado",
            numeroReuniao=numero,
            dataReuniao=dataReuniao,
            dataPublicacao=dataReuniao,
            nomeArquivo=nomeArquivo,
        )
        novasEntradas.append(entrada)
    if novasEntradas:
        manifesto.extend(novasEntradas)
        _escreverManifesto(base, manifesto)
    return len(novasEntradas)


def coletarTudo(quantidade: int = 20, caminhoBase: Path = caminhoRaw) -> dict[str, int]:
    return {
        "atas": coletarAtas(quantidade, caminhoBase),
        "comunicados": coletarComunicados(quantidade, caminhoBase),
    }


# ── CLI ────────────────────────────────────────────────────────────────


def principal() -> None:
    import argparse
    analisador = argparse.ArgumentParser(
        description="Coleta atas e comunicados do Copom via API do BCB e salva em data/raw/ com manifesto.",
    )
    analisador.add_argument(
        "--last",
        type=int,
        default=20,
        help="Quantidade de atas/comunicados a baixar (padr\u00e3o: 20)",
    )
    analisador.add_argument(
        "--path",
        type=str,
        default=str(caminhoRaw),
        help="Diret\u00f3rio de destino (padr\u00e3o: data/raw/)",
    )
    argumentos = analisador.parse_args()
    caminho = Path(argumentos.path)
    registrador.info("Coletando \u00faltimas %d atas e comunicados do Copom...", argumentos.last)
    resultado = coletarTudo(quantidade=max(argumentos.last, 5), caminhoBase=caminho)
    manifesto = _carregarManifesto(caminho)
    registrador.info(
        "Resumo: %d atas novas \u00b7 %d comunicados novos \u00b7 total no manifesto: %d documentos",
        resultado["atas"],
        resultado["comunicados"],
        len(manifesto),
    )


if __name__ == "__main__":
    principal()
