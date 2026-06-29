import json
import logging
from pathlib import Path

import httpx

BASE_URL = "https://www.bcb.gov.br/api/servico/sitebcb/copom"
RAW_DIR = Path("data/raw")
MANIFEST_FILENAME = "manifest.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36'"

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


# ── API calls ──────────────────────────────────────────────────────────


def fetch_minutes_list(count: int = 30) -> list[dict]:
    with _client() as client:
        response = client.get(f"/atas?quantidade={count}")
        response.raise_for_status()
        return response.json()["conteudo"]


def fetch_minute_detail(meeting_number: int) -> dict | None:
    with _client() as client:
        response = client.get(f"/atas_detalhes?nro_reuniao={meeting_number}")
        if response.status_code == 500:
            logger.warning("Ata %d retornou 500 (PDF-only, sem texto HTML)", meeting_number)
            return None
        response.raise_for_status()
        return response.json()["conteudo"][0]


def fetch_statements_list(count: int = 30) -> list[dict]:
    with _client() as client:
        response = client.get(f"/comunicados?quantidade={count}")
        response.raise_for_status()
        return response.json()["conteudo"]


def fetch_statement_detail(meeting_number: int) -> dict | None:
    with _client() as client:
        response = client.get(f"/comunicados_detalhes?nro_reuniao={meeting_number}")
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


# ── Collectors ─────────────────────────────────────────────────────────


def collect_minutes(count: int = 20, base_path: Path = RAW_DIR) -> int:
    base = Path(base_path)
    base.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest(base)
    existing_ids: set[int] = {
        e["numero_reuniao"] for e in manifest if e["tipo"] == "ata"
    }
    minutes_list = fetch_minutes_list(count)
    new_entries: list[dict] = []
    for minute in minutes_list:
        num = minute["nroReuniao"]
        if num in existing_ids:
            logger.info("Ata %d já registrada no manifesto, pulando", num)
            continue
        detail = fetch_minute_detail(num)
        if detail is None:
            continue
        meeting_date = detail["dataReferencia"]
        publication_date = detail["dataPublicacao"]
        filename = f"ata_{num}_{meeting_date}.txt"
        text = detail["textoAta"]
        saved = _save_raw_file(base, filename, text)
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
    if new_entries:
        manifest.extend(new_entries)
        _write_manifest(base, manifest)
    return len(new_entries)


def collect_statements(count: int = 20, base_path: Path = RAW_DIR) -> int:
    base = Path(base_path)
    base.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest(base)
    existing_ids: set[int] = {
        e["numero_reuniao"] for e in manifest if e["tipo"] == "comunicado"
    }
    statements_list = fetch_statements_list(count)
    new_entries: list[dict] = []
    for stmt in statements_list:
        num = stmt["nro_reuniao"]
        if num in existing_ids:
            logger.info("Comunicado %d já registrado no manifesto, pulando", num)
            continue
        detail = fetch_statement_detail(num)
        if detail is None:
            continue
        meeting_date = detail["dataReferencia"]
        filename = f"comunicado_{num}_{meeting_date}.txt"
        text = detail["textoComunicado"]
        saved = _save_raw_file(base, filename, text)
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
    if new_entries:
        manifest.extend(new_entries)
        _write_manifest(base, manifest)
    return len(new_entries)


def collect_all(count: int = 20, base_path: Path = RAW_DIR) -> dict[str, int]:
    return {
        "minutes": collect_minutes(count, base_path),
        "statements": collect_statements(count, base_path),
    }


# ── CLI ────────────────────────────────────────────────────────────────


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="Coleta atas e comunicados do Copom via API do BCB e salva em data/raw/ com manifesto.",
    )
    parser.add_argument(
        "--last",
        type=int,
        default=20,
        help="Quantidade de atas/comunicados a baixar (padrão: 20)",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=str(RAW_DIR),
        help="Diretório de destino (padrão: data/raw/)",
    )
    args = parser.parse_args()
    path = Path(args.path)
    logger.info("Coletando últimas %d atas e comunicados do Copom...", args.last)
    result = collect_all(count=max(args.last, 5), base_path=path)
    manifest = _load_manifest(path)
    logger.info(
        "Resumo: %d atas novas · %d comunicados novos · total no manifesto: %d documentos",
        result["minutes"],
        result["statements"],
        len(manifest),
    )


if __name__ == "__main__":
    main()
