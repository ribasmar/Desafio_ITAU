import html
import json
import logging
import re
from pathlib import Path

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
DATASET_FILENAME = "copom_dataset.jsonl"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_html(data: str) -> str:
    text = re.sub(r"<[^>]+>", " ", data)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _load_dataset(path: Path) -> list[dict]:
    dataset_path = path / DATASET_FILENAME
    if not dataset_path.exists():
        return []
    records: list[dict] = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _append_to_dataset(path: Path, records: list[dict]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    dataset_path = path / DATASET_FILENAME
    with open(dataset_path, "a", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _build_record(entry: dict, text: str) -> dict:
    return {
        "available_time": entry["data_publicacao"],
        "tipo": entry["tipo"],
        "numero_reuniao": entry["numero_reuniao"],
        "data_reuniao": entry["data_reuniao"],
        "filename": entry["filename"],
        "text": text,
    }


def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Parseia HTML de atas/comunicados Copom para texto limpo e salva em JSONL com available_time.",
    )
    parser.add_argument(
        "--raw-path",
        type=str,
        default=str(RAW_DIR),
        help="Diretório com dados raw (manifest + HTML) (padrão: data/raw/)",
    )
    parser.add_argument(
        "--processed-path",
        type=str,
        default=str(PROCESSED_DIR),
        help="Diretório de saída para o dataset processado (padrão: data/processed/)",
    )
    args = parser.parse_args(argv)

    raw_path = Path(args.raw_path)
    processed_path = Path(args.processed_path)

    raw_manifest_path = raw_path / "manifest.json"
    if not raw_manifest_path.exists():
        logger.error("Manifesto raw não encontrado em %s", raw_manifest_path)
        return

    with open(raw_manifest_path, "r", encoding="utf-8") as f:
        raw_manifest: list[dict] = json.load(f)

    existing = _load_dataset(processed_path)
    existing_filenames: set[str] = {r["filename"] for r in existing}

    pending = [e for e in raw_manifest if e["filename"] not in existing_filenames]

    if not pending:
        logger.info("Nenhum documento novo para processar (total: %d)", len(existing))
        return

    new_records: list[dict] = []
    for entry in pending:
        filepath = raw_path / entry["filename"]
        if not filepath.exists():
            logger.warning("Arquivo raw não encontrado: %s (pulando)", filepath)
            continue
        raw_text = filepath.read_text(encoding="utf-8")
        clean_text = parse_html(raw_text)
        record = _build_record(entry, clean_text)
        new_records.append(record)

    _append_to_dataset(processed_path, new_records)

    total = len(existing) + len(new_records)
    logger.info(
        "Parse concluído: %d novos · total no dataset: %d documentos",
        len(new_records),
        total,
    )


if __name__ == "__main__":
    main()
