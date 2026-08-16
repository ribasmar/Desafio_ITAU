# CopomLens — Camada 1 (bônus): ingestão das atas publicadas só em PDF
# (reuniões 200–231, jul/2016–jun/2020). Lê data/raw/atas_sem_texto.json
# (gravado pela coleta), baixa cada url_pdf para data/raw/pdf/, extrai o texto
# com pdfminer.six, limpa (des-hifenização das quebras de linha + colapso de
# espaços, a mesma normalização do texto vindo de HTML) e registra no
# manifesto com fonte="pdf" — o parser incorpora ao dataset sem passar pelo
# strip de tags HTML. Falha alto por ata quando falta data de publicação
# (sem carimbo point-in-time não entra) ou quando a extração devolve texto
# curto demais (PDF corrompido/escaneado), listando cada falha no resumo.
from __future__ import annotations

import json
import logging
import re
import sys
import time
from pathlib import Path

import httpx

from copom.ingest.collect import (
    ATAS_SEM_TEXTO_FILENAME,
    RAW_DIR,
    USER_AGENT,
    _load_manifest,
    _write_manifest,
)

PDF_SUBDIR = "pdf"

# Uma ata real tem dezenas de milhares de caracteres (20k–85k no histórico
# HTML); extração muito menor que isso indica PDF escaneado/corrompido e o
# registro vira falha explícita em vez de texto lixo no dataset.
TAMANHO_MINIMO_TEXTO = 5000

_MAX_TENTATIVAS = 3
_TIMEOUT = httpx.Timeout(90.0, connect=15.0)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _get(client: httpx.Client, url: str) -> httpx.Response:
    """GET com retry e backoff exponencial (mesmo padrão da coleta)."""
    ultimo_erro: Exception | None = None
    for tentativa in range(1, _MAX_TENTATIVAS + 1):
        try:
            return client.get(url)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            ultimo_erro = exc
            if tentativa < _MAX_TENTATIVAS:
                time.sleep(2**tentativa)
    raise ultimo_erro  # type: ignore[misc]


def limpar_texto(texto: str) -> str:
    """Normaliza o texto extraído do PDF: junta palavras hifenizadas na virada
    de linha ("infla-\\ncao" -> "inflacao") e colapsa todo espaçamento em
    espaço simples — mesma normalização que o parser aplica ao texto HTML,
    para que léxico e LLM enxerguem os dois formatos do mesmo jeito."""
    texto = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def _extrair_pdfminer(caminho_pdf: Path) -> str:
    from pdfminer.high_level import extract_text

    return extract_text(str(caminho_pdf))


def _extrair_pypdf(caminho_pdf: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(caminho_pdf), strict=False)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extrair_texto(caminho_pdf: Path) -> str:
    """Extrai o texto bruto do PDF: pdfminer.six primeiro (melhor qualidade de
    layout) e pypdf como fallback — o BCB publicou PDFs com xref quebrado
    (ex.: ata 217) que o pdfminer, estrito, rejeita, e o pypdf reconstrói.
    Imports tardios: as dependências são exclusivas deste bônus."""
    try:
        return _extrair_pdfminer(caminho_pdf)
    except Exception as erro_pdfminer:
        try:
            texto = _extrair_pypdf(caminho_pdf)
        except Exception as erro_pypdf:
            raise RuntimeError(
                f"extração falhou nos dois extratores — pdfminer: {erro_pdfminer!r} "
                f"· pypdf: {erro_pypdf!r}"
            ) from erro_pypdf
        logger.info(
            "  → %s extraído via fallback pypdf (pdfminer falhou: %s)",
            caminho_pdf.name,
            type(erro_pdfminer).__name__,
        )
        return texto


def ingerir_atas_pdf(base_path: Path = RAW_DIR) -> dict:
    """Baixa, extrai e registra no manifesto as atas PDF listadas em
    atas_sem_texto.json. Idempotente: PDF já baixado não é rebaixado e ata já
    presente no manifesto é pulada. Retorna stats com as falhas nomeadas."""
    base = Path(base_path)
    caminho_sem_texto = base / ATAS_SEM_TEXTO_FILENAME
    if not caminho_sem_texto.exists():
        raise FileNotFoundError(
            f"{caminho_sem_texto} não existe — rode a coleta antes "
            "(python -m copom.ingest.collect --last 300)."
        )
    with open(caminho_sem_texto, encoding="utf-8") as f:
        registros = json.load(f)

    manifest = _load_manifest(base)
    existentes: set[int] = {
        e["numero_reuniao"] for e in manifest if e["tipo"] == "ata"
    }
    pdf_dir = base / PDF_SUBDIR
    pdf_dir.mkdir(parents=True, exist_ok=True)

    stats: dict = {
        "sem_url": 0,
        "candidatas": 0,
        "ja_registradas": 0,
        "ingeridas": 0,
        "falhas": [],
    }
    novas: list[dict] = []
    with httpx.Client(
        headers={"User-Agent": USER_AGENT}, timeout=_TIMEOUT, follow_redirects=True
    ) as client:
        for reg in sorted(registros, key=lambda r: r["numero_reuniao"]):
            url = reg.get("url_pdf")
            num = reg["numero_reuniao"]
            if not url:
                stats["sem_url"] += 1
                continue
            stats["candidatas"] += 1
            if num in existentes:
                stats["ja_registradas"] += 1
                continue
            data_reuniao = reg.get("data_reuniao")
            data_publicacao = reg.get("data_publicacao")
            if not data_publicacao:
                stats["falhas"].append(
                    {
                        "numero_reuniao": num,
                        "motivo": "sem data_publicacao: não há carimbo point-in-time",
                    }
                )
                logger.warning("Ata %d sem data_publicacao — pulada (point-in-time)", num)
                continue

            caminho_pdf = pdf_dir / f"ata_{num}_{data_reuniao}.pdf"
            try:
                if not caminho_pdf.exists():
                    resp = _get(client, url)
                    resp.raise_for_status()
                    caminho_pdf.write_bytes(resp.content)
                    logger.info(
                        "  → baixado: %s (%d bytes)", caminho_pdf.name, len(resp.content)
                    )
                texto = limpar_texto(extrair_texto(caminho_pdf))
            except Exception as exc:
                # Uma ata problemática não pode derrubar o lote: vira falha
                # nomeada no resumo e o restante segue.
                stats["falhas"].append(
                    {"numero_reuniao": num, "motivo": f"{type(exc).__name__}: {exc}"}
                )
                logger.warning("Ata %d falhou (%s) — pulada", num, type(exc).__name__)
                continue
            if len(texto) < TAMANHO_MINIMO_TEXTO:
                stats["falhas"].append(
                    {
                        "numero_reuniao": num,
                        "motivo": (
                            f"texto extraído curto demais ({len(texto)} chars < "
                            f"{TAMANHO_MINIMO_TEXTO}): PDF escaneado/corrompido?"
                        ),
                    }
                )
                logger.warning("Ata %d com extração suspeita (%d chars) — pulada", num, len(texto))
                continue

            filename = f"ata_{num}_{data_reuniao}.txt"
            (base / filename).write_text(texto, encoding="utf-8")
            novas.append(
                {
                    "url": url,
                    "data_publicacao": data_publicacao,
                    "data_reuniao": data_reuniao,
                    "tipo": "ata",
                    "numero_reuniao": num,
                    "filename": filename,
                    "fonte": "pdf",
                }
            )
            stats["ingeridas"] += 1
            logger.info("  → salvo: %s (%d chars)", filename, len(texto))

    if novas:
        manifest.extend(novas)
        _write_manifest(base, manifest)
    return stats


def _parse_args(argv: list[str] | None = None):
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Bônus: baixa e ingere as atas publicadas só em PDF, a partir das "
            "urls registradas em atas_sem_texto.json pela coleta."
        ),
    )
    parser.add_argument(
        "--path",
        type=str,
        default=str(RAW_DIR),
        help="Diretório de dados raw (padrão: data/raw/)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    stats = ingerir_atas_pdf(Path(args.path))
    logger.info(
        "Atas PDF: %d candidatas · %d ingeridas · %d já registradas · %d sem url · %d falhas",
        stats["candidatas"],
        stats["ingeridas"],
        stats["ja_registradas"],
        stats["sem_url"],
        len(stats["falhas"]),
    )
    for falha in stats["falhas"]:
        logger.warning("FALHA ata %d: %s", falha["numero_reuniao"], falha["motivo"])
    if stats["ingeridas"]:
        logger.info(
            "Próximo passo: python -m copom.ingest.parser (incorpora ao dataset) "
            "e python -m copom.surprise (reconstrói o painel)."
        )
    return 1 if stats["falhas"] else 0


if __name__ == "__main__":
    sys.exit(main())
