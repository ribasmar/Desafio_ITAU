# `promptExec.py` (`src/copom/models/promptExec.py`)

Pipeline de execucao de prompt unico para extracao de tom Copom.
Responsavel por: preencher template → enviar ao LLM → parsear JSON →
validar schema.

## Fluxo

```
document dict → build_prompt() → llm.generate() → _parse_llm_json() → validacao → dict
```

## Funcoes

### `build_prompt(document, prompt_path)`

Preenche o template markdown com dados do documento.

**Parametros:**

| Parametro | Tipo | Descricao |
|---|---|---|
| `document` | `dict` | Deve conter `tipo`, `available_time`, `text` |
| `prompt_path` | `str \| Path \| None` | Caminho do template. Padrao: `prompts/copom_v1.md` |

**Placeholders substituidos:**

| Placeholder | Campo do documento |
|---|---|
| `{tipo}` | `document["tipo"]` (ex.: `"ata"`, `"comunicado"`) |
| `{data_publicacao}` | `document["available_time"]` (ex.: `"2025-05-13"`) |
| `{texto}` | `document["text"]` (conteudo completo do documento) |

**Retorno:** `str` — prompt completo pronto para enviar ao LLM.

### `execute(llm, document, prompt_path)`

Pipeline completo: `build_prompt()` → LLM → parse → validacao.

**Parametros:**

| Parametro | Tipo | Descricao |
|---|---|---|
| `llm` | `LLMClient` | Cliente LLM inicializado |
| `document` | `dict` | Documento com `tipo`, `available_time`, `text` |
| `prompt_path` | `str \| Path \| None` | Template de prompt (opcional) |

**Retorno:** `dict` — JSON validado com as chaves:
`stance`, `stance_delta`, `forward_guidance`, `incerteza`,
`conviccao`, `justificativa`.

**Excecoes:** `ValueError` se o LLM nao retornar JSON valido ou
se os campos estiverem fora das faixas validas.

## Parsing de JSON

A funcao `_parse_llm_json()` tenta extrair JSON da resposta do LLM
usando tres padroes (em ordem):

1. Bloco ` ```json {...} ``` `
2. Bloco ` ``` {...} ``` `
3. Regex `\{.*\}` (qualquer objeto JSON na saida)

A funcao `_loads_sanitized()` aplica limpezas antes do `json.loads()`:
- Remove comentarios estilo JS (`// ...`)
- Converte aspas simples para duplas
- Remove virgulas finais antes de `}` ou `]`

## Schema de validacao

### Campos numericos

| Campo | Tipo | Faixa | Descricao |
|---|---|---|---|
| `stance` | `float` | `[-1.0, 1.0]` | Tom geral (-1 = pessimista, +1 = optimista) |
| `stance_delta` | `float` | `[-1.0, 1.0]` | Mudanca em relacao a reuniao anterior |
| `incerteza` | `float` | `[0.0, 1.0]` | Nivel de incerteza expresso |
| `conviccao` | `float` | `[0.0, 1.0]` | Nivel de conviccao na decisao |

### Campo categorico

**`forward_guidance`** — valores validos:

| Valor | Significado |
|---|---|
| `aperto` | Sinalizacao de aperto monetario |
| `manutencao` | Manutencao da taxa atual |
| `afrouxamento` | Sinalizacao de afrouxamento |
| `neutro` | Sem sinalizacao clara |

### Normalizacao de forward_guidance

O LLM pode retornar texto livre. O `_FORWARD_GUIDANCE_MAP` normaliza
para os valores canonicos:

| Texto do LLM | Valor canônico |
|---|---|
| `calibracao`, `ajuste`, `ajuste de calibracao` | `manutencao` |
| `reducao`, `corte`, `queda` | `afrouxamento` |
| `alta`, `subida` | `aperto` |

### Campo de texto

**`justificativa`** — texto livre do LLM justificando os scores.
Nao e validado, apenas armazenado.

## Exemplo de uso

```python
from copom.models import LLMClient
from copom.models.promptExec import execute

llm = LLMClient(provider="openrouter")

document = {
    "tipo": "ata",
    "available_time": "2025-05-13",
    "text": "O Comite de Politica Monetaria decidiu..."
}

result = execute(llm, document)
print(result["stance"])          # ex.: 0.8
print(result["forward_guidance"]) # ex.: "aperto"
```
