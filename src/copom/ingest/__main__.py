# CopomLens — ponto de entrada da ingestão de documentos: coleta (collect) e
# parse (parser) em sequência, repassando --last e --path para as duas etapas.
from pathlib import Path

from copom.ingest import collect, parser


def main() -> None:
    args = collect._parse_args()
    collect.executar(args.last, Path(args.path))
    parser.main(["--raw-path", args.path])


if __name__ == "__main__":
    main()
