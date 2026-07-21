# CopomLens — Camada 1 (ingestão de documentos): coleta atas e comunicados do
# Copom via API do site do BCB e salva o texto HTML em data/raw/ com manifesto
# point-in-time (data de publicação real). Além do manifesto, grava três
# insumos do funil da amostra e do rótulo de reuniões da Camada 3:
# atas_listadas.json / comunicados_listados.json (lista oficial COMPLETA de
# reuniões, inclusive as sem texto) e atas_sem_texto.json /
# comunicados_sem_texto.json (documentos que a API devolve com texto nulo —
# só em PDF — com a urlPdfAta preservada para ingestão futura). Não há piso
# silencioso de quantidade: o valor de --last é o valor pedido à API, e o log
# reporta o que foi listado, salvo e pulado.
import json
import logging
import time
from contextlib import nullcontext
from pathlib import Path

import httpx

BASE_URL = "https://www.bcb.gov.br/api/servico/sitebcb/copom"
RAW_DIR = Path("data/raw")
MANIFEST_FILENAME = "manifest.json"
ATAS_LISTADAS_FILENAME = "atas_listadas.json"
COMUNICADOS_LISTADOS_FILENAME = "comunicados_listados.json"
ATAS_SEM_TEXTO_FILENAME = "atas_sem_texto.json"
COMUNICADOS_SEM_TEXTO_FILENAME = "comunicados_sem_texto.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36'"

# Decisão de amostra (issue de reescopo do DI 1Y): o default cobre TODO o
# histórico listado pelo BCB (259 atas em jul/2026, desde 1998), com folga para
# reuniões futuras. Quem quiser menos passa --last explicitamente.
DEFAULT_LAST = 300

_MAX_TENTATIVAS = 3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL,
        headers={"User-Agent": USER_AGENT},
        timeout=30.0,
    )


def _ctx(client: httpx.Client | None):
    """Reusa o cliente recebido ou abre um novo (fechado ao sair do with)."""
    return nullcontext(client) if client is not None else _client()


def _get(client: httpx.Client, url: str) -> httpx.Response:
    """GET com retry e backoff exponencial para instabilidade transitória da
    API do BCB — uma coleta de ~260 documentos não deve morrer num timeout."""
    ultimo_erro: Exception | None = None
    for tentativa in range(1, _MAX_TENTATIVAS + 1):
        try:
            return client.get(url)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            ultimo_erro = exc
            if tentativa < _MAX_TENTATIVAS:
                time.sleep(2**tentativa)
    raise ultimo_erro  # type: ignore[misc]


def _load_manifest(base_path: Path) -> list[dict]:
    path = base_path / MANIFEST_FILENAME
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _write_manifest(base_path: Path, manifest: list[dict]) -> None:
    path = base_path / MANIFEST_FILENAME
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def _write_json(base_path: Path, filename: str, payload: object) -> None:
    with open(base_path / filename, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _merge_sem_texto(base_path: Path, filename: str, novos: list[dict]) -> None:
    """Funde os registros sem texto com os de execuções anteriores, chaveando
    por numero_reuniao — reexecuções parciais não apagam registros antigos."""
    path = base_path / filename
    por_numero: dict[int, dict] = {}
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            for registro in json.load(f):
                por_numero[registro["numero_reuniao"]] = registro
    for registro in novos:
        por_numero[registro["numero_reuniao"]] = registro
    ordenados = [por_numero[k] for k in sorted(por_numero)]
    _write_json(base_path, filename, ordenados)


# ── API calls ──────────────────────────────────────────────────────────


def fetch_minutes_list(count: int = DEFAULT_LAST, client: httpx.Client | None = None) -> list[dict]:
    with _ctx(client) as c:
        response = _get(c, f"/atas?quantidade={count}")
        response.raise_for_status()
        return response.json()["conteudo"]


def fetch_minute_detail(meeting_number: int, client: httpx.Client | None = None) -> dict | None:
    with _ctx(client) as c:
        response = _get(c, f"/atas_detalhes?nro_reuniao={meeting_number}")
        if response.status_code == 500:
            logger.warning("Ata %d retornou 500 (PDF-only, sem texto HTML)", meeting_number)
            return None
        response.raise_for_status()
        return response.json()["conteudo"][0]


def fetch_statements_list(count: int = DEFAULT_LAST, client: httpx.Client | None = None) -> list[dict]:
    with _ctx(client) as c:
        response = _get(c, f"/comunicados?quantidade={count}")
        response.raise_for_status()
        return response.json()["conteudo"]


def fetch_statement_detail(meeting_number: int, client: httpx.Client | None = None) -> dict | None:
    with _ctx(client) as c:
        response = _get(c, f"/comunicados_detalhes?nro_reuniao={meeting_number}")
        if response.status_code == 500:
            logger.warning("Comunicado %d retornou 500", meeting_number)
            return None
        response.raise_for_status()
        return response.json()["conteudo"][0]


# ── Save helpers ───────────────────────────────────────────────────────


def _save_raw_file(
    base_path: Path,
    filename: str,
    content: str,
) -> bool:
    file_path = base_path / filename
    if file_path.exists():
        logger.info("  → já existe: %s (pulando)", filename)
        return False
    file_path.write_text(content, encoding="utf-8")
    logger.info("  → salvo: %s (%d bytes)", filename, len(content))
    return True


def _build_manifest_entry(
    doc_type: str,
    meeting_number: int,
    meeting_date: str,
    publication_date: str,
    filename: str,
) -> dict:
    detail_endpoint = "atas_detalhes" if doc_type == "ata" else "comunicados_detalhes"
    return {
        "url": f"{BASE_URL}/{detail_endpoint}?nro_reuniao={meeting_number}",
        "data_publicacao": publication_date,
        "data_reuniao": meeting_date,
        "tipo": doc_type,
        "numero_reuniao": meeting_number,
        "filename": filename,
    }


def _registro_sem_texto(num: int, listado: dict, detail: dict | None, motivo: str) -> dict:
    fonte = detail or listado or {}
    return {
        "numero_reuniao": num,
        "data_reuniao": fonte.get("dataReferencia"),
        "data_publicacao": fonte.get("dataPublicacao"),
        "url_pdf": fonte.get("urlPdfAta") or fonte.get("urlPdf"),
        "motivo": motivo,
    }


# ── Collectors ─────────────────────────────────────────────────────────


def collect_minutes(count: int = DEFAULT_LAST, base_path: Path = RAW_DIR) -> dict[str, int]:
    base = Path(base_path)
    base.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest(base)
    existing_ids: set[int] = {
        e["numero_reuniao"] for e in manifest if e["tipo"] == "ata"
    }
    stats = {"listadas": 0, "novas": 0, "sem_texto": 0, "ja_registradas": 0}
    sem_texto: list[dict] = []
    new_entries: list[dict] = []
    with _client() as client:
        minutes_list = fetch_minutes_list(count, client=client)
        stats["listadas"] = len(minutes_list)
        _write_json(base, ATAS_LISTADAS_FILENAME, minutes_list)
        for minute in minutes_list:
            num = minute["nroReuniao"]
            if num in existing_ids:
                stats["ja_registradas"] += 1
                continue
            detail = fetch_minute_detail(num, client=client)
            if detail is None or not detail.get("textoAta"):
                motivo = (
                    "HTTP 500 no detalhe (PDF-only)"
                    if detail is None
                    else "textoAta nulo (ata publicada só em PDF)"
                )
                registro = _registro_sem_texto(num, minute, detail, motivo)
                sem_texto.append(registro)
                stats["sem_texto"] += 1
                logger.warning(
                    "Ata %d sem texto HTML (%s); registrada em %s",
                    num,
                    motivo,
                    ATAS_SEM_TEXTO_FILENAME,
                )
                continue
            meeting_date = detail["dataReferencia"]
            publication_date = detail["dataPublicacao"]
            filename = f"ata_{num}_{meeting_date}.txt"
            saved = _save_raw_file(base, filename, detail["textoAta"])
            if not saved:
                continue
            entry = _build_manifest_entry(
                doc_type="ata",
                meeting_number=num,
                meeting_date=meeting_date,
                publication_date=publication_date,
                filename=filename,
            )
            new_entries.append(entry)
            stats["novas"] += 1
    if sem_texto:
        _merge_sem_texto(base, ATAS_SEM_TEXTO_FILENAME, sem_texto)
    if new_entries:
        manifest.extend(new_entries)
        _write_manifest(base, manifest)
    return stats


def collect_statements(count: int = DEFAULT_LAST, base_path: Path = RAW_DIR) -> dict[str, int]:
    base = Path(base_path)
    base.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest(base)
    existing_ids: set[int] = {
        e["numero_reuniao"] for e in manifest if e["tipo"] == "comunicado"
    }
    stats = {"listados": 0, "novos": 0, "sem_texto": 0, "ja_registrados": 0}
    sem_texto: list[dict] = []
    new_entries: list[dict] = []
    with _client() as client:
        statements_list = fetch_statements_list(count, client=client)
        stats["listados"] = len(statements_list)
        _write_json(base, COMUNICADOS_LISTADOS_FILENAME, statements_list)
        for stmt in statements_list:
            num = stmt["nro_reuniao"]
            if num in existing_ids:
                stats["ja_registrados"] += 1
                continue
            detail = fetch_statement_detail(num, client=client)
            if detail is None or not detail.get("textoComunicado"):
                motivo = (
                    "HTTP 500 no detalhe"
                    if detail is None
                    else "textoComunicado nulo"
                )
                registro = _registro_sem_texto(num, stmt, detail, motivo)
                sem_texto.append(registro)
                stats["sem_texto"] += 1
                logger.warning(
                    "Comunicado %d sem texto HTML (%s); registrado em %s",
                    num,
                    motivo,
                    COMUNICADOS_SEM_TEXTO_FILENAME,
                )
                continue
            meeting_date = detail["dataReferencia"]
            filename = f"comunicado_{num}_{meeting_date}.txt"
            saved = _save_raw_file(base, filename, detail["textoComunicado"])
            if not saved:
                continue
            entry = _build_manifest_entry(
                doc_type="comunicado",
                meeting_number=num,
                meeting_date=meeting_date,
                publication_date=detail.get("dataPublicacao", meeting_date),
                filename=filename,
            )
            new_entries.append(entry)
            stats["novos"] += 1
    if sem_texto:
        _merge_sem_texto(base, COMUNICADOS_SEM_TEXTO_FILENAME, sem_texto)
    if new_entries:
        manifest.extend(new_entries)
        _write_manifest(base, manifest)
    return stats


def collect_all(count: int = DEFAULT_LAST, base_path: Path = RAW_DIR) -> dict[str, dict[str, int]]:
    return {
        "minutes": collect_minutes(count, base_path),
        "statements": collect_statements(count, base_path),
    }


# ── CLI ────────────────────────────────────────────────────────────────


def _parse_args(argv: list[str] | None = None):
    import argparse

    parser = argparse.ArgumentParser(
        description="Coleta atas e comunicados do Copom via API do BCB e salva em data/raw/ com manifesto.",
    )
    parser.add_argument(
        "--last",
        type=int,
        default=DEFAULT_LAST,
        help=(
            "Quantidade de atas/comunicados a pedir à API (padrão: "
            f"{DEFAULT_LAST} — cobre todo o histórico listado pelo BCB, "
            "259 atas em jul/2026). O valor pedido é o valor usado, sem piso."
        ),
    )
    parser.add_argument(
        "--path",
        type=str,
        default=str(RAW_DIR),
        help="Diretório de destino (padrão: data/raw/)",
    )
    return parser.parse_args(argv)


def executar(last: int, base_path: Path) -> dict[str, dict[str, int]]:
    """Roda a coleta completa com log honesto: o que foi pedido (--last), o que
    a API listou e o que foi salvo, pulado por já existir ou pulado sem texto."""
    logger.info("Pedindo à API do BCB as últimas %d atas e comunicados (--last, sem piso)", last)
    result = collect_all(count=last, base_path=base_path)
    m, s = result["minutes"], result["statements"]
    manifest = _load_manifest(base_path)
    logger.info(
        "Atas: %d listadas · %d novas com texto · %d sem texto HTML (ver %s) · %d já registradas",
        m["listadas"],
        m["novas"],
        m["sem_texto"],
        ATAS_SEM_TEXTO_FILENAME,
        m["ja_registradas"],
    )
    logger.info(
        "Comunicados: %d listados · %d novos com texto · %d sem texto · %d já registrados",
        s["listados"],
        s["novos"],
        s["sem_texto"],
        s["ja_registrados"],
    )
    logger.info("Total no manifesto: %d documentos", len(manifest))
    return result


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    executar(args.last, Path(args.path))


if __name__ == "__main__":
    main()
