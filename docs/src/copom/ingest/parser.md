# Docs — `parser.py`

Remove tags HTML, decodifica entidades HTML e gera um dataset JSONL
com texto limpo e carimbo `available_time` (data de publicação).

Depende de [`collect.py`](collect.py) — o diretório `data/raw/` precisa estar populado
com os arquivos HTML e o `manifest.json`.

## Uso

```bash
# Direto
.venv/bin/python src/copom/ingest/parser.py

# Via módulo (já encadeia collect + parser)
PYTHONPATH=src .venv/bin/python -m copom.ingest
```

### Argumentos

| Argumento | Padrão | Descrição |
|---|---|---|
| `--raw-path DIR` | `data/raw/` | Diretório com os arquivos raw e manifesto |
| `--processed-path DIR` | `data/processed/` | Diretório de saída do dataset |

## Formato de saída

`data/processed/copom_dataset.jsonl` — uma linha por documento, cada linha
é um JSON com o texto limpo e metadados:

```jsonl
{"available_time":"2024-02-06","tipo":"ata","numero_reuniao":260,"data_reuniao":"2024-01-31","filename":"ata_260_2024-01-31.txt","text":"1. O ambiente externo segue volátil..."}
```

### Campos do registro

| Campo | Descrição |
|---|---|
| `available_time` | Data de publicação efetiva do documento (ponto-no-tempo) |
| `tipo` | `"ata"` ou `"comunicado"` |
| `numero_reuniao` | Número sequencial da reunião do Copom |
| `data_reuniao` | Data em que a reunião ocorreu |
| `filename` | Nome do arquivo raw de origem em `data/raw/` |
| `text` | Texto limpo, tags HTML removidas e entidades decodificadas |

## Disciplina point-in-time

Cada registro carrega `available_time = data_publicacao` do manifesto raw.
Isso permite que consumidores downstream (features, modelos) apliquem
filtros do tipo "apenas documentos disponíveis até a data T",
eliminando viés de look-ahead em backtests.

O `available_time` difere conforme o tipo:

- **Atas**: publicadas dias após a reunião (`data_publicacao > data_reuniao`)
- **Comunicados**: publicados no mesmo dia da reunião (`data_publicacao == data_reuniao`)

## Pipeline completo

```bash
PYTHONPATH=src .venv/bin/python -m copom.ingest
```

Encadeia:
1. `collect.py` — baixa documentos da API do BCB → `data/raw/`
2. `parser.py` — parseia HTML → `data/processed/copom_dataset.jsonl`

## Imutabilidade e idempotência

O JSONL é append-only. Se um documento já está no dataset (verificado pelo `filename`),
o parser o pula. Execuções repetidas são seguras e incrementais.

## Arquivos

| Arquivo | Papel |
|---|---|
| `parser.py` | Parse HTML → texto limpo, gera JSONL com `available_time` |
| `__init__.py` | *docstring* do pacote |
| `__main__.py` | Entry point que encadeia `collect` → `parser` |
