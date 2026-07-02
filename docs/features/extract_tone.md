# `extract_tone()` (`src/copom/features/extract_tone.py`)

Funcao principal da camada 2 do pipeline Copom Quant AI. Recebe um
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
    n_runs: int = 3,
    prompt_path: str | Path | None = None,
    provider: str = "ollama",
) -> dict
```

## Parametros

| Parametro | Tipo | Padrao | Descricao |
|---|---|---|---|
| `document` | `dict` | (obrigatorio) | Documento Copom com chaves `text`, `tipo`, `available_time`, `numero_reuniao` |
| `model_id` | `str \| None` | `None` | Identificador do modelo. Se `None`, resolvido via `LLM_MODEL_<PROVIDER>` entao default do provider |
| `seed` | `int` | `42` | Semente aleatoria para reprodutibilidade |
| `n_runs` | `int` | `3` | Numero de chamadas identicas. Com `temperature=0`, resultados devem ser identicos |
| `prompt_path` | `str \| Path \| None` | `None` | Caminho do template markdown. Padrao: `prompts/copom_v1.md` |
| `provider` | `str` | `"ollama"` | Backend LLM: `local`, `ollama` ou `openrouter` |

## Retorno

Dict JSON-serializavel com scores de tom, metadados e estabilidade:

```json
{
  "stance": 0.30,
  "stance_delta": 0.0,
  "forward_guidance": "aperto",
  "incerteza": 0.40,
  "conviccao": 0.60,
  "justificativa": "O Comite de Politica Monetaria decidiu...",
  "model_id": "qwen/qwen-2.5-7b-instruct",
  "seed": 42,
  "prompt_version": "copom_v1",
  "numero_reuniao": 270,
  "tipo": "ata",
  "available_time": "2025-05-13",
  "stability": {
    "stance":       {"mean": 0.30, "std": 0.00, "values": [0.30, 0.30, 0.30]},
    "stance_delta": {"mean": 0.00, "std": 0.00, "values": [0.00, 0.00, 0.00]},
    "incerteza":    {"mean": 0.40, "std": 0.00, "values": [0.40, 0.40, 0.40]},
    "conviccao":    {"mean": 0.60, "std": 0.00, "values": [0.60, 0.60, 0.60]}
  }
}
```

### Campos de score

| Campo | Tipo | Faixa | Descricao |
|---|---|---|---|
| `stance` | `float` | `[-1.0, 1.0]` | Tom geral (-1 = pessimista, +1 = optimista) |
| `stance_delta` | `float` | `[-1.0, 1.0]` | Mudanca em relacao a reuniao anterior |
| `forward_guidance` | `str` | `aperto \| manutencao \| afrouxamento \| neutro` | Sinalizacao de politica monetaria |
| `incerteza` | `float` | `[0.0, 1.0]` | Nivel de incerteza expresso |
| `conviccao` | `float` | `[0.0, 1.0]` | Nivel de conviccao na decisao |
| `justificativa` | `str` | — | Texto livre do LLM justificando os scores |

### Estabilidade (`stability`)

Para cada campo numerico, a funcao calcula:

| Sub-campo | Descricao |
|---|---|
| `mean` | Media aritmetica das `n_runs` execucoes |
| `std` | Desvio padrao (0.0 se `n_runs=1` ou saidas identicas) |
| `values` | Lista com o valor bruto de cada execucao |

Com `temperature=0` + semente fixa, `std` deve ser `0.0` (saidas identicas).
Se `std > 0`, indica nao-determinismo no provider.

### Metadados

| Campo | Fonte | Descricao |
|---|---|---|
| `model_id` | `LLMClient.model` | Modelo efetivamente resolvido apos fallbacks |
| `seed` | parametro | Semente utilizada |
| `prompt_version` | `prompt_path.stem` | Nome do template (ex.: `copom_v1`) |
| `numero_reuniao` | `document["numero_reuniao"]` | Numero da ata/comunicado |
| `tipo` | `document["tipo"]` | `"ata"` ou `"comunicado"` |
| `available_time` | `document["available_time"]` | Data de publicacao |

## Exemplos de uso

### Basico

```python
from copom.features.extract_tone import extract_tone

document = {
    "numero_reuniao": 270,
    "tipo": "ata",
    "available_time": "2025-05-13",
    "text": "O Comite de Politica Monetaria decidiu..."
}

result = extract_tone(document, provider="openrouter")
print(result["stance"])           # ex.: 0.8
print(result["forward_guidance"]) # ex.: "aperto"
print(result["stability"]["stance"]["std"])  # 0.0 (deterministico)
```

### Com modelo customizado

```python
result = extract_tone(
    document,
    model_id="meta-llama/llama-3.1-8b-instruct",
    provider="openrouter",
    seed=123,
    n_runs=5,
)
```

### Via CLI

```bash
PYTHONPATH=src python -m copom.models --provider openrouter --ata 270
```

O CLI Internamente chama `extract_tone()` com `n_runs=3` para cada
documento do dataset.

## Dependencias

| Modulo | Uso |
|---|---|
| `copom.models.llm_client.LLMClient` | Cliente LLM unificado |
| `copom.models.promptExec.execute` | Pipeline de prompt unico (template → LLM → JSON → validacao) |

## Variaveis de ambiente

| Variavel | Uso |
|---|---|
| `LLM_PROVIDER` | Backend padrao (se `provider` nao for especificado) |
| `LLM_MODEL_OPENROUTER` | Modelo OpenRouter padrao |
| `OPENROUTER_API_KEY` | Chave de API OpenRouter |
| `PROMPT_PATH` | Template de prompt padrao |
| `SEED` | Semente padrao |
