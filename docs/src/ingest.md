# Docs — `src/copom/ingest/`

Coletor de atas e comunicados do Copom via API pública do BCB.
Os arquivos são salvos em `data/raw/` com um manifesto JSON.

## Setup

```bash
# Na raiz do projeto, criar e ativar ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependências
pip install httpx
```

## Uso

```bash
# Direto via script
.venv/bin/python src/copom/ingest/collect.py
```

Ou via módulo (precisa de `PYTHONPATH` se o pacote não está instalado):

```bash
PYTHONPATH=src .venv/bin/python -m copom.ingest
```

### Argumentos

| Argumento | Padrão | Descrição |
|---|---|---|
| `--last N` | 20 | Quantidade de atas e comunicados a baixar |
| `--path DIR` | `data/raw/` | Diretório de destino |

### Exemplos

```bash
# Baixar 30 atas e 30 comunicados
.venv/bin/python src/copom/ingest/collect.py --last 30

# Salvar em outro diretório
.venv/bin/python src/copom/ingest/collect.py --last 10 --path data/raw/teste
```

## Manifesto

O arquivo `manifest.json` em `data/raw/` registra cada documento coletado:

```json
{
  "url": "https://www.bcb.gov.br/api/servico/sitebcb/copom/atas_detalhes?nro_reuniao=279",
  "data_publicacao": "2026-06-23",
  "data_reuniao": "2026-06-17",
  "tipo": "ata",
  "numero_reuniao": 279,
  "filename": "ata_279_2026-06-17.txt"
}
```

| Campo | Descrição |
|---|---|
| `url` | Endpoint da API de detalhes do documento |
| `data_publicacao` | Data real de publicação (atas: dias após a reunião; comunicados: mesmo dia) |
| `data_reuniao` | Data da reunião do Copom |
| `tipo` | `"ata"` ou `"comunicado"` |
| `numero_reuniao` | Número sequencial da reunião |
| `filename` | Nome do arquivo salvo em `data/raw/` |

## Imutabilidade

`data/raw/` é imutável: se o arquivo já existe, a coleta o pula.
Isso garante que execuções repetidas nunca sobrescrevem dados baixados anteriormente.

## Arquivos

| Arquivo | Papel |
|---|---|
| `collect.py` | Cliente HTTP da API do BCB, coleta e persistência |
| `__init__.py` | *docstring* do pacote |
| `__main__.py` | Entry point para `python -m` |
