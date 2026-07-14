# CLI — `__main__.py` (`src/copom/models/__main__.py`)

Ponto de entrada CLI para extracao de tom em lote a partir de
documentos Copom. Executa `extract_tone()` com `n_runs=3` para cada
documento, validando determinismo e reportando estatisticas de
estabilidade.

## Uso

```bash
PYTHONPATH=src python -m copom.models [OPCOES]
```

## Opcoes

| Opcao | Padrao | Descricao |
|---|---|---|
| `--provider` | `openrouter` | Backend LLM: `local`, `ollama` ou `openrouter` |
| `--model` | (resolvido via env/default) | Slug do modelo, tag Ollama ou caminho GGUF |
| `--ata` | (todos) | Processar apenas a reuniao com este numero (ex.: `--ata 270`) |
| `--limit` | (todos) | Processar apenas os primeiros N documentos (ignorado se `--ata` for definido) |
| `--dataset` | `data/processed/copom_dataset.jsonl` | Caminho do dataset de entrada (JSONL) |
| `--output` | `data/processed/tone_results.jsonl` | Caminho do arquivo de saida (JSONL) |
| `--prompt` | `prompts/copom_v1.md` | Caminho do template de prompt (sobrescreve `PROMPT_PATH` do env) |

## Resolucao do modelo

O modelo e resolvido na seguinte ordem:

1. `--model` (argumento CLI)
2. `LLM_MODEL_<PROVIDER>` (variavel de ambiente)
3. `OPENROUTER_MODEL` (retrocompatibilidade, apenas para openrouter)
4. `LLAMA_MODEL_PATH` (apenas para local)
5. `_DEFAULT_MODELS[provider]` (fallback)

### Defaults por provider

| Provider | Modelo padrao |
|---|---|
| `openrouter` | `qwen/qwen-2.5-7b-instruct` |
| `ollama` | `qwen2.5:7b` |
| `local` | `Qwen2.5-7B-Instruct-Q8_0.gguf` |

## Exemplos

### Extrair tom de uma ata especifica

```bash
PYTHONPATH=src python -m copom.models --provider openrouter --ata 270
```

Saida esperada:

```
[1/2] Ata 270 (2025-05-13) ... OK  (stance=0.8, std=0.0)
[2/2] Comunicado 270 (2025-05-07) ... OK  (stance=0.5, std=0.0)

Done. 2 OK, 0 errors — saved to data/processed/tone_results.jsonl
```

### Processar os 5 primeiros documentos com Ollama

```bash
PYTHONPATH=src python -m copom.models --provider ollama --limit 5
```

### Usar modelo diferente via OpenRouter

```bash
PYTHONPATH=src python -m copom.models --provider openrouter \
    --model meta-llama/llama-3.1-8b-instruct --ata 260
```

### Dataset e saida customizados

```bash
PYTHONPATH=src python -m copom.models --provider openrouter \
    --dataset data/meu_dataset.jsonl \
    --output data/minha_saida.jsonl \
    --limit 10
```

## Formato de saida

Cada linha do arquivo de saida e um objeto JSON (JSONL) com:

```json
{
  "stance": 0.8,
  "stance_delta": 0.0,
  "forward_guidance": "aperto",
  "incerteza": 0.3,
  "conviccao": 0.7,
  "justificativa": "...",
  "model_id": "qwen/qwen-2.5-7b-instruct",
  "seed": 42,
  "prompt_version": "copom_v1",
  "numero_reuniao": 270,
  "tipo": "ata",
  "available_time": "2025-05-13",
  "stability": {
    "stance": {"mean": 0.8, "std": 0.0, "values": [0.8, 0.8, 0.8]},
    "stance_delta": {"mean": 0.0, "std": 0.0, "values": [0.0, 0.0, 0.0]},
    "incerteza": {"mean": 0.3, "std": 0.0, "values": [0.3, 0.3, 0.3]},
    "conviccao": {"mean": 0.7, "std": 0.0, "values": [0.7, 0.7, 0.7]}
  }
}
```

### Em caso de erro

```json
{
  "numero_reuniao": 266,
  "tipo": "ata",
  "available_time": "2024-11-14",
  "error": "OpenRouter API error: ..."
}
```

## Estabilidade

O CLI executa `n_runs=3` (tres chamadas identicas com mesma semente)
para cada documento. Com `temperature=0.0`, as respostas devem ser
identicas (`std=0.0`). Se `std > 0`, indica nao-determinismo no
provider.
