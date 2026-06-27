# Entendendo o Padrão **Collector** no Pipeline de Dados do Copom

## Introdução

No universo da engenharia de dados, um **collector** (coletor) é um componente responsável por **extrair dados de uma fonte externa** (API, banco de dados, site) e **persisti-los localmente** para processamento posterior. Este documento explica o padrão utilizado no módulo `collect.py` do projeto **Copom Quant AI**, que coleta atas e comunicados do Comitê de Política Monetária (Copom) do Banco Central do Brasil.

---

## Visão Geral do Fluxo

```
┌──────────────┐       ┌────────────────┐       ┌───────────────┐
│  API do BCB  │ ◄──── │   Collector    │ ────► │  data/raw/    │
│  (httpx)     │       │  (collect.py)  │       │  *.txt        │
└──────────────┘       └────────────────┘       │  manifest.json│
                                                └───────────────┘
```

1. O collector consulta a API pública do Banco Central.
2. Para cada ata/comunicado novo, baixa o texto completo.
3. Salva o texto em um arquivo `.txt` no diretório `data/raw/`.
4. Registra o metadado (URL, data, tipo) em um arquivo `manifest.json`.

---

## Estrutura do Código

O código está organizado em três camadas funcionais:

| Camada | Funções | Responsabilidade |
|--------|---------|------------------|
| **API calls** | `fetch_atas_list`, `fetch_ata_detalhe`, `fetch_comunicados_list`, `fetch_comunicado_detalhe` | Comunicação direta com a API do BCB |
| **Save helpers** | `_save_raw_file`, `_build_manifest_entry`, `_load_manifest`, `_write_manifest` | Persistência e gerenciamento do manifesto |
| **Collectors** | `collect_atas`, `collect_comunicados`, `coletar_tudo` | Orquestração do fluxo completo de coleta |

---

## 1. Camada de API: Funções `fetch_*`

Essas funções encapsulam as chamadas HTTP para a API do Banco Central.

```python
BASE_URL = "https://www.bcb.gov.br/api/servico/sitebcb/copom"

def _client() -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL,
        headers={"User-Agent": USER_AGENT},
        timeout=30.0,
    )
```

**O que está acontecendo:**

- **`httpx.Client`** é uma alternativa moderna ao `requests`. Ele permite reutilizar conexões (connection pooling) e define um `base_url` para que as chamadas usem apenas o path relativo.
- **`User-Agent`** é enviado para evitar que a API rejeite a requisição (muitas APIs bloqueiam bots que não se identificam).
- **`timeout=30.0`** protege o programa de travar caso a API demore ou fique fora do ar.

### Exemplo: `fetch_atas_list`

```python
def fetch_atas_list(quantidade: int = 30) -> list[dict]:
    with _client() as client:
        resp = client.get(f"/atas?quantidade={quantidade}")
        resp.raise_for_status()
        return resp.json()["conteudo"]
```

- Faz uma requisição GET para `/atas?quantidade=30`.
- `raise_for_status()` levanta uma exceção se o HTTP status code for 4xx ou 5xx — isso evita que dados corrompidos passem despercebidos.
- O retorno é a lista de atas contida na chave `"conteudo"` do JSON.

### Exemplo: `fetch_ata_detalhe`

```python
def fetch_ata_detalhe(numero_reuniao: int) -> dict | None:
    with _client() as client:
        resp = client.get(f"/atas_detalhes?numero_reuniao={numero_reuniao}")
        if resp.status_code == 500:
            logger.warning("Ata %d retornou 500 (PDF-only, sem texto HTML)", numero_reuniao)
            return None
        resp.raise_for_status()
        return resp.json()["conteudo"][0]
```

- Algumas atas mais antigas existem apenas em PDF e a API retorna erro 500. O código trata esse caso específico e retorna `None` em vez de quebrar o pipeline.
- A assinatura `dict | None` (Python 3.10+) indica que a função pode ou não retornar um dicionário — um **optional type**.

---

## 2. Camada de Persistência: Helpers `_save_*`

```python
def _save_raw_file(base_path: Path, filename: str, content: str) -> bool:
    filepath = base_path / filename
    if filepath.exists():
        logger.info("  → já existe: %s (imutável, pulando)", filename)
        return False
    filepath.write_text(content, encoding="utf-8")
    logger.info("  → salvo: %s (%d bytes)", filename, len(content))
    return True
```

**Conceito importante — Idempotência:**

O collector é **idempotente**: se você executá-lo duas vezes, o resultado é o mesmo. Isso é garantido pela verificação `if filepath.exists()`. Se o arquivo já existe, ele é pulado. Isso evita:

- Sobrescrever dados já baixados.
- Gastar banda e tempo à toa.
- Inconsistências no manifesto.

### Manifesto

```python
def _build_manifest_entry(tipo, numero_reuniao, data_reuniao, data_publicacao, filename):
    detail_endpoint = "atas_detalhes" if tipo == "ata" else "comunicados_detalhes"
    return {
        "url": f"{BASE_URL}/{detail_endpoint}?numero_reuniao={numero_reuniao}",
        "data_publicacao": data_publicacao,
        "data_reuniao": data_reuniao,
        "tipo": tipo,
        "numero_reuniao": numero_reuniao,
        "filename": filename,
    }
```

O **manifesto** é um JSON que funciona como um **catálogo** de todos os documentos já baixados. Cada entrada contém:

- `url`: permite rastrear a origem do dado.
- `data_publicacao` e `data_reuniao`: metadados temporais essenciais para análises futuras.
- `tipo`: `"ata"` ou `"comunicado"`.
- `filename`: ligação direta com o arquivo em disco.

Exemplo de `manifest.json`:

```json
[
  {
    "url": "https://www.bcb.gov.br/api/servico/sitebcb/copom/atas_detalhes?numero_reuniao=290",
    "data_publicacao": "2024-01-31",
    "data_reuniao": "2024-01-30",
    "tipo": "ata",
    "numero_reuniao": 290,
    "filename": "ata_290_2024-01-30.txt"
  }
]
```

---

## 3. Os Collectors: `collect_atas` e `collect_comunicados`

Aqui está o coração do padrão **collector**:

```python
def collect_atas(quantidade: int = 20, base_path: Path = RAW_PATH) -> int:
    base = Path(base_path)
    base.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest(base)
    existing_numeros: set[int] = {
        e["numero_reuniao"] for e in manifest if e["tipo"] == "ata"
    }
    atas_list = fetch_atas_list(quantidade)
    new_entries: list[dict] = []
    for ata in atas_list:
        numero = ata["numeroReuniao"]
        if numero in existing_numeros:
            logger.info("Ata %d já registrada no manifesto, pulando", numero)
            continue
        detalhe = fetch_ata_detalhe(numero)
        if detalhe is None:
            continue
        data_reuniao = detalhe["dataReferencia"]
        data_publicacao = detalhe["dataPublicacao"]
        filename = f"ata_{numero}_{data_reuniao}.txt"
        texto = detalhe["textoAta"]
        saved = _save_raw_file(base, filename, texto)
        if not saved:
            continue
        entry = _build_manifest_entry(...)
        new_entries.append(entry)
    if new_entries:
        manifest.extend(new_entries)
        _write_manifest(base, manifest)
    return len(new_entries)
```

### Passo a passo do algoritmo:

| Etapa | Código | O que faz |
|-------|--------|-----------|
| 1 | `base.mkdir(parents=True, exist_ok=True)` | Garante que o diretório `data/raw/` existe |
| 2 | `_load_manifest(base)` | Carrega o manifesto existente (ou lista vazia) |
| 3 | `existing_numeros = {...}` | Cria um `set` com os números de reunião já baixados para consulta rápida (O(1)) |
| 4 | `fetch_atas_list(quantidade)` | Busca a lista de atas disponíveis na API |
| 5 | `for ata in atas_list:` | Itera sobre cada ata |
| 6 | `if numero in existing_numeros: continue` | Pula se já foi baixada (idempotência) |
| 7 | `fetch_ata_detalhe(numero)` | Baixa o texto completo da ata |
| 8 | `_save_raw_file(...)` | Salva o texto em disco |
| 9 | `_build_manifest_entry(...)` | Cria a entrada do manifesto |
| 10 | `manifest.extend(...)` / `_write_manifest(...)` | Atualiza o manifesto no disco |

### Por que usar `set` para `existing_numeros`?

```python
existing_numeros: set[int] = {
    e["numero_reuniao"] for e in manifest if e["tipo"] == "ata"
}
```

A verificação `numero in existing_numeros` é **O(1)** — constante. Se usássemos uma lista, seria **O(n)** — linear. Para um manifesto com centenas de documentos, a diferença é significativa.

---

## 4. O Collector Geral: `coletar_tudo`

```python
def coletar_tudo(quantidade: int = 30, base_path: Path = RAW_PATH) -> dict[str, int]:
    return {
        "atas": collect_atas(quantidade, base_path),
        "comunicados": collect_comunicados(quantidade, base_path),
    }
```

Esta função orquestra os dois coletores e retorna um dicionário com a contagem de novos documentos baixados para cada tipo. O retorno `dict[str, int]` é útil para:

- Logs de execução.
- Métricas de pipeline.
- Gatilhos para próximas etapas (ex.: "se baixou novas atas, rode o processamento").

---

## 5. CLI (Interface de Linha de Comando)

```python
def main() -> None:
    parser = argparse.ArgumentParser(...)
    parser.add_argument("--last", type=int, default=20)
    parser.add_argument("--path", type=str, default=str(RAW_PATH))
    args = parser.parse_args()
    result = coletar_tudo(quantidade=max(args.last, 5), base_path=path)
    ...
```

Isso permite executar o coletor diretamente do terminal:

```bash
# Baixar as últimas 10 atas e comunicados
python -m src.copom.ingest.collect --last 10

# Especificar diretório alternativo
python -m src.copom.ingest.collect --last 30 --path /tmp/dados
```

---

## Padrões de Projeto Identificados

### 1. **Separator Pattern** (Separação em Camadas)
O código separa claramente:
- **Comunicação com API** (`fetch_*`)
- **Lógica de negócio/coleta** (`collect_*`)
- **Persistência** (`_save_*`, `_write_manifest`)

Isso facilita testes, manutenção e reuso.

### 2. **Idempotência**
Executar o coletor múltiplas vezes não altera o resultado final. Isso é crucial para pipelines de dados que rodam em agendamento (cron, Airflow).

### 3. **Manifest Pattern**
O manifesto (`manifest.json`) funciona como uma **fonte da verdade** (source of truth) sobre o que já foi coletado, evitando retrabalho e permitindo rastreabilidade.

### 4. **Graceful Degradation**
Tratamento específico para erro 500 (atas em PDF) — o pipeline não quebra, apenas registra um aviso e continua.

---

## Tratamento de Erros

```python
def fetch_ata_detalhe(numero_reuniao: int) -> dict | None:
    with _client() as client:
        resp = client.get(f"/atas_detalhes?numero_reuniao={numero_reuniao}")
        if resp.status_code == 500:
            logger.warning("Ata %d retornou 500 (PDF-only, sem texto HTML)", numero_reuniao)
            return None
        resp.raise_for_status()
        return resp.json()["conteudo"][0]
```

| Situação | Comportamento |
|----------|---------------|
| API responde 200 OK | Retorna o dicionário com os dados |
| API responde 500 (atas PDF) | Loga aviso, retorna `None` — a ata é pulada |
| API responde 404, 403 etc. | `raise_for_status()` levanta exceção — o programa para |
| Timeout ou erro de rede | `httpx` levanta exceção — o programa para |

---

## Conclusão

O padrão **collector** implementado neste código é um exemplo didático e robusto de como construir um pipeline de extração de dados:

1. **Simples** — cada função tem uma responsabilidade única.
2. **Resiliente** — trata erros conhecidos sem quebrar.
3. **Idempotente** — pode ser executado repetidamente sem efeitos colaterais.
4. **Rastreável** — o manifesto mantém um histórico completo do que foi coletado.

Esse padrão é a base de sistemas maiores de ETL (Extract, Transform, Load) e aparece em ferramentas como Apache NiFi, Airbyte e em coletores customizados para dados financeiros, climáticos, de redes sociais, entre outros.

---

## Exercícios para Fixação

1. **Modifique o collector** para aceitar um intervalo de datas (`--start-date` e `--end-date`) e baixar apenas atas dentro desse período.

2. **Adicione um novo tipo de documento**: o collector atual lida com `atas` e `comunicados`. Como você adicionaria um terceiro tipo, como `relatorios`?

3. **Implemente um teste**: escreva um teste unitário para `_build_manifest_entry` que verifique se a URL está sendo montada corretamente.

---

## Referências

- [httpx — Python HTTP client](https://www.python-httpx.org/)
- [Banco Central do Brasil — API Copom](https://www.bcb.gov.br/)
- [Pattern: Idempotent Consumer](https://www.enterpriseintegrationpatterns.com/patterns/messaging/IdempotentReceiver.html)
