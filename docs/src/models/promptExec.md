# `promptExec.py` (`src/copom/models/promptExec.py`)

Pipeline de execucao de prompt unico para extracao de tom Copom.
Responsavel por: preencher template → enviar ao LLM → parsear JSON →
validar schema.

## Fluxo

```
document dict → build_prompt() → llm.generate() → _extract_json_from_text() → _validate() → dict
```

Retry com seed modificado (`seed + 1`, `seed + 2`) se o parse ou validacao falhar.

## Funcoes

### `build_prompt(document, prompt_path)`

Preenche o template markdown com dados do documento.

**Parametros:**

| Parametro | Tipo | Descricao |
|---|---|---|
| `document` | `dict` | Deve conter `tipo`, `available_time`, `text` |
| `prompt_path` | `str \| Path \| None` | Caminho do template. Padrao: `prompts/cb_lens_v1.md` |

**Placeholders substituidos:**

| Placeholder | Campo do documento |
|---|---|
| `{tipo}` | `document["tipo"]` (ex.: `"ata"`, `"comunicado"`) |
| `{data_publicacao}` | `document["available_time"]` (ex.: `"2005-05-13"`) |
| `{texto}` | `document["text"]` (conteudo completo do documento) |

**Retorno:** `str` — prompt completo pronto para enviar ao LLM.

### `execute(llm, document, prompt_path, max_retries=2)`

Pipeline completo: `build_prompt()` → LLM → parse → validacao.
Tenta ate `max_retries + 1` vezes (3 no total), incrementando a
seed a cada tentativa.

**Parametros:**

| Parametro | Tipo | Descricao |
|---|---|---|
| `llm` | `LLMClient` | Cliente LLM inicializado |
| `document` | `dict` | Documento com `tipo`, `available_time`, `text` |
| `prompt_path` | `str \| Path \| None` | Template de prompt (opcional) |
| `max_retries` | `int` | Tentativas adicionais em caso de falha (default 2 = ate 3 total) |

**Retorno:** `dict` — JSON validado com as chaves:
`stance_label`, `forward_guidance`, `incerteza`, `conviccao`, `justificativa`.

**Excecoes:** `ValueError` se todas as tentativas falharem (parse ou validacao).

## Parsing de JSON

`_extract_json_from_text()` tenta extrair JSON da resposta do LLM
usando 5 estrategias (em ordem):

1. `json.JSONDecoder.raw_decode()` — scan character-by-character
2. Blocos ```json / ``` fenced code blocks
3. Regex greedy `\{.*\}`
4. Balanced brace scanning
5. Reparo de JSON truncado (strings abertas, chaves desbalanceadas)

`_try_json_loads()` aplica limpezas antes do `json.loads()`:
- Remove comentarios estilo JS (`// ...`)
- Converte aspas simples para duplas
- Remove virgulas finais antes de `}` ou `]`

## Schema de validacao

### `stance_label` — classificação categorica

O campo `stance_label` deve ser **exatamente um** dos 15 rótulos
em português definidos no prompt `cb_lens_v1.md`.

Normalizacao aplicada antes da validacao:
- Remove acentos (`ç` → `c`, `ã` → `a`)
- Converte para lowercase
- Substitui espacos e hifens por `_`

O `STANCE_MAP` (dict `label → float`) mapeia cada rótulo para seu
valor numerico:

| Rótulo | Stance | Descricao |
|---|---|---|
| `emergencial_dovish` | -1.0000 | Cortes de crise + linguagem acomodaticia |
| `agressivo_dovish` | -0.7500 | Corte grande + sinal decisivo de flexibilizacao |
| `claramente_dovish` | -0.6250 | Corte significativo + forward guidance dovish |
| `moderadamente_dovish` | -0.5000 | Corte moderado com vies dovish |
| `levemente_dovish` | -0.3750 | Corte modesto, tom cauteloso |
| `marginalmente_dovish` | -0.2500 | Corte pequeno ou manutencao com vies dovish |
| `neutro_dovish` | -0.1250 | Manutencao, inclinando para flexibilizacao |
| `neutro` | 0.0000 | Genuinamente equilibrado |
| `neutro_hawkish` | 0.1250 | Manutencao, inclinando para aperto |
| `marginalmente_hawkish` | 0.2500 | Alta pequena ou manutencao com vies hawkish |
| `levemente_hawkish` | 0.3750 | Alta modesta, tom cauteloso |
| `moderadamente_hawkish` | 0.5000 | Alta moderada com vies hawkish |
| `claramente_hawkish` | 0.6250 | Alta significativa + forward guidance hawkish |
| `agressivo_hawkish` | 0.7500 | Alta grande + sinal decisivo de aperto |
| `emergencial_hawkish` | 1.0000 | Altas de crise + linguagem restritiva |

### Campos numericos

| Campo | Tipo | Faixa | Descricao |
|---|---|---|---|
| `incerteza` | `float` | `[0.0, 1.0]` | Nivel de incerteza expresso |
| `conviccao` | `float` | `[0.0, 1.0]` | Nivel de conviccao na decisao |

Valores fora da faixa sao **clampados** (nao levantam excecao).
Um warning e registrado no log.

### Campo categorico

**`forward_guidance`** — valores validos: `aperto`, `manutencao`, `afrouxamento`, `neutro`.

### Normalizacao de forward_guidance

O `_FORWARD_GUIDANCE_MAP` normaliza texto livre para os valores canonicos:

| Texto do LLM | Valor canonico |
|---|---|
| `calibracao`, `ajuste`, `ajuste de calibracao` | `manutencao` |
| `reducao`, `corte`, `queda`, `flexibilizacao` | `afrouxamento` |
| `alta`, `subida`, `elevacao` | `aperto` |
| `hawkish`, `tightening` | `aperto` |
| `dovish`, `easing` | `afrouxamento` |
| `neutral`, `none`, `data-dependent` | `neutro` |

### Campo de texto

**`justificativa`** — texto livre do LLM justificando os scores.
Nao e validado, apenas armazenado.

## Exemplo de uso

```python
from copom.models import LLMClient
from copom.models.promptExec import execute

llm = LLMClient(provider="local")

document = {
    "tipo": "ata",
    "available_time": "2005-05-13",
    "text": "O Comite de Politica Monetaria decidiu..."
}

result = execute(llm, document)
print(result["stance_label"])       # ex.: "moderadamente_hawkish"
print(result["forward_guidance"])   # ex.: "aperto"
```
