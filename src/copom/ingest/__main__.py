from copom.ingest.collect import main as collect_main
from copom.ingest.parser import main as parser_main


def main():
    collect_main()
    parser_main()


if __name__ == "__main__":
    main()
