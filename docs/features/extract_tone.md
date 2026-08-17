# `extract_tone()` (`src/copom/features/extract_tone.py`)

Funcao principal da camada 2 do pipeline CopomLens. Recebe um
documento Copom e retorna scores de tom (stance, forward_guidance,
incerteza, conviccao) com estatisticas de estabilidade.

## Fluxo

```
document dict
      │
      ▼
┌─────────────────────────────────┐
│       extract_tone()            │
│                                 │
│  1. Instancia LLMClient         │
│  2. Loop n_runs vezes:          │
│     └─ promptExec.execute()     │
│        (template → LLM → JSON)  │
│     └─ STANCE_MAP[label → float]│
│  3. Agrega campos numericos     │
│     (mean / std por campo)      │
│  4. Coleta metadados            │
└───────────────┬─────────────────┘
                │
                ▼
         dict com scores + stability
```

## Assinatura

```python
extract_tone(
    document: dict,
    model_id: str | None = None,
    seed: int = 42,
    n_runs: int = 1,
    prompt_path: str | Path | None = None,
    debug: bool = False,
    provider: str | None = None,
    openrouter_api_key: str | None = None,
    openrouter_provider: str | None = None,
) -> dict
```

## Parametros

| Parametro | Tipo | Padrao | Descricao |
|---|---|---|---|
| `document` | `dict` | (obrigatorio) | Documento com chaves `text`, `tipo`, `available_time`, `numero_reuniao` |
| `model_id` | `str \| None` | `None` | Identificador do modelo (slug OpenRouter ou caminho GGUF) |
| `seed` | `int` | `42` | Semente aleatoria para reprodutibilidade |
| `n_runs` | `int` | `1` | Numero de chamadas identicas (CLI usa `n_runs=3`) |
| `prompt_path` | `str \| Path \| None` | `None` | Template markdown. Padrao: `prompts/copom_v3.md` |
| `debug` | `bool` | `False` | Logs detalhados (latencia, tokens, resposta) |
| `provider` | `str \| None` | `None` | Backend: `local` ou `openrouter`. Fallback: `LLM_PROVIDER` |
| `openrouter_api_key` | `str \| None` | `None` | Chave API OpenRouter |
| `openrouter_provider` | `str \| None` | `None` | Provider upstream forcado (ex.: `Groq`) |

## Retorno

Dict JSON-serializavel com scores, metadados e estabilidade:

```json
{
  "stance": 0.5,
  "stance_label": "moderadamente_hawkish",
  "forward_guidance": "aperto",
  "incerteza": 0.25,
  "conviccao": 0.75,
  "justificativa": "O Copom decidiu aumentar a taxa Selic...",
  "model_id": "Qwen2.5-14B-Instruct-Q5_K_M.gguf",
  "seed": 42,
  "prompt_version": "copom_v3",
  "numero_reuniao": 117,
  "tipo": "ata",
  "available_time": "2006-03-16",
  "stability": {
    "stance":     {"mean": 0.5, "std": 0.0, "values": [0.5, 0.5, 0.5]},
    "incerteza":  {"mean": 0.25, "std": 0.0, "values": [0.25, 0.25, 0.25]},
    "conviccao":  {"mean": 0.75, "std": 0.0, "values": [0.75, 0.75, 0.75]}
  }
}
```

### Mapeamento `stance_label` → `stance`

O LLM retorna um rotulo categorico (`"moderadamente_hawkish"`)
em vez de um float. A funcao importa `STANCE_MAP` de
`promptExec.py` e deriva `stance` como:

```python
result["stance"] = STANCE_MAP.get(result["stance_label"], 0.0)
```

O `stance_label` original e preservado no output para
rastreabilidade.

### Em caso de erro (todas as runs falham)

```json
{
  "error": "All runs failed",
  "numero_reuniao": 180,
  "tipo": "ata",
  "available_time": "2012-07-05",
  "model_id": "...",
  "seed": 42,
  "prompt_version": "copom_v3"
}
```

### Campos de score

| Campo | Tipo | Faixa | Descricao |
|---|---|---|---|
| `stance` | `float` | `[-1.0, 1.0]` | Derivado de `stance_label` via `STANCE_MAP` |
| `stance_label` | `str` | 15 rotulos PT | Classificacao categorica do tom |
| `forward_guidance` | `str` | `aperto \| manutencao \| afrouxamento \| neutro` | Sinalizacao de politica monetaria |
| `incerteza` | `float` | `[0.0, 1.0]` | Nivel de incerteza expresso |
| `conviccao` | `float` | `[0.0, 1.0]` | Nivel de conviccao na decisao |
| `justificativa` | `str` | — | Texto livre do LLM justificando os scores |

### Estabilidade (`stability`)

Para cada campo numerico, a funcao calcula:

| Sub-campo | Descricao |
|---|---|
| `mean` | Media aritmetica das `n_runs` execucoes |
| `std` | Desvio padrao (0.0 se saidas identicas) |
| `values` | Lista com o valor de cada execucao |

Com `temperature=0` + semente fixa, `std` deve ser `0.0`
(saidas identicas). `std=0.0` com `n_runs=3` comprova
reprodutibilidade.

### Metadados

| Campo | Fonte | Descricao |
|---|---|---|
| `model_id` | `LLMClient.model` | Modelo efetivamente resolvido |
| `seed` | parametro | Semente utilizada |
| `prompt_version` | `prompt_path.stem` | Nome do template (ex.: `copom_v3`) |
| `numero_reuniao` | `document["numero_reuniao"]` | Numero da ata/comunicado |
| `tipo` | `document["tipo"]` | `"ata"` ou `"comunicado"` |
| `available_time` | `document["available_time"]` | Data de publicacao |

## Exemplos de uso

### Basico (local)

```python
from copom.features.extract_tone import extract_tone

document = {
    "numero_reuniao": 117,
    "tipo": "ata",
    "available_time": "2006-03-16",
    "text": "O Comite de Politica Monetaria decidiu..."
}

result = extract_tone(document, provider="local")
print(result["stance"])              # ex.: 0.5
print(result["stance_label"])        # ex.: "moderadamente_hawkish"
print(result["forward_guidance"])    # ex.: "aperto"
```

### OpenRouter com Qwen3-32B

```python
result = extract_tone(
    document,
    provider="openrouter",
    model_id="qwen/qwen-3-32b",
    n_runs=1,
)
```

### Via CLI

```bash
python -m copom.models --ata-range 116:227 --debug
```

O CLI chama `extract_tone()` com `n_runs=3` para cada documento e
mapeia `stance_label` → `stance`. O instrumento de tom da camada 4 nao
e o `stance` bruto (dominado pela decisao de juros), e sim o pareado
`stance(ata) − stance(comunicado)` da mesma reuniao, emitido por
`python -m copom.features.pareamento` (ver `src/copom/features/pareamento.py`).

## Dependencias

| Modulo | Uso |
|---|---|
| `copom.models.llm_client.LLMClient` | Cliente LLM unificado (local + openrouter) |
| `copom.models.promptExec.execute` | Pipeline de prompt unico (template → LLM → JSON → validacao) |
| `copom.models.promptExec.STANCE_MAP` | Mapeamento label → float (15 valores) |

## Variaveis de ambiente

| Variavel | Uso |
|---|---|
| `LLM_PROVIDER` | Backend padrao (`local` ou `openrouter`) |
| `LLM_MODEL_LOCAL` | Modelo GGUF local |
| `LLM_MODEL_OPENROUTER` | Slug do modelo OpenRouter |
| `OPENROUTER_API_KEY` | Chave de API OpenRouter |
| `OPENROUTER_PROVIDER` | Provider upstream forcado |
| `PROMPT_PATH` | Template de prompt padrao |
| `SEED` | Semente padrao |
