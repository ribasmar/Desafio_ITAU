# CLI — `__main__.py` (`src/copom/models/__main__.py`)

Ponto de entrada CLI para extracao de tom em lote a partir de
documentos Copom. Executa `extract_tone()` com `n_runs=3` para cada
documento, validando determinismo e reportando estatisticas de
estabilidade.

## Uso

```bash
python -m copom.models [OPCOES]
```

## Opcoes

| Opcao | Padrao | Descricao |
|---|---|---|
| `--provider` | `local` | Backend LLM: `local` (llama.cpp) ou `openrouter` |
| `--model` | (resolvido via env/default) | Slug OpenRouter ou caminho GGUF |
| `--api-key` | (env `OPENROUTER_API_KEY`) | Chave de API OpenRouter |
| `--openrouter-provider` | (env `OPENROUTER_PROVIDER`) | Forcar provider upstream (ex.: `Groq`) |
| `--ata` | (todos) | Apenas uma reuniao (ex.: `--ata 270`) |
| `--ata-range` | (todos) | Faixa de reunioes (ex.: `--ata-range 116:227`) |
| `--limit` | (todos) | Apenas os N primeiros documentos |
| `--dataset` | `data/processed/copom_dataset.jsonl` | Dataset de entrada (JSONL) |
| `--output` | `data/processed/tone_results.jsonl` | Arquivo de saida (JSONL) |
| `--prompt` | `prompts/cb_lens_v1.md` | Template de prompt |
| `--debug` | `False` | Logs detalhados em `data/processed/debug.log` e stderr |

### Formato de `--ata-range`

```bash
--ata-range 116:227   # reunioes 116 a 227 inclusive
--ata-range 116:      # da reuniao 116 ate o final
--ata-range :227      # do inicio ate a reuniao 227
```

## Resolucao do modelo

Provider-aware. Ordem de prioridade:

1. `--model` (argumento CLI)
2. `LLM_MODEL_OPENROUTER` (provider=openrouter) ou `LLM_MODEL_LOCAL` (provider=local)
3. `LLAMA_MODEL_PATH` (fallback legado)
4. `_DEFAULT_MODEL` = `Qwen2.5-14B-Instruct-Q5_K_M.gguf`

## Exemplos

### Extrair uma faixa de reunioes

```bash
python -m copom.models --ata-range 116:227 --debug
```

Saida esperada:

```
[1/174] Ata 116 (2006-01-26) ... OK  (stance=0.25)
[2/174] Ata 117 (2006-03-16) ... OK  (stance=0.5)
...
Done. 172 OK, 2 errors — saved to data/processed/tone_results.jsonl
```

### OpenRouter com Qwen3-32B

```bash
python -m copom.models --provider openrouter \
    --model qwen/qwen-3-32b \
    --ata-range 116:120 --debug
```

### Forcar provider Groq no OpenRouter

```bash
python -m copom.models --provider openrouter \
    --openrouter-provider Groq \
    --ata 270
```

## Pos-processamento: `stance_delta`

Apos a extracao de todos os documentos:

1. Resultados sao ordenados por `numero_reuniao`
2. `stance_delta[t] = stance[t] - stance[t-1]`
3. Documentos com erro quebram a cadeia: `stance_delta = None`
4. Primeiro documento da sequencia: `stance_delta = 0.0`

## Formato de saida

Cada linha do arquivo de saida e um objeto JSON (JSONL) com:

```json
{
  "stance": 0.5,
  "stance_label": "moderadamente_hawkish",
  "forward_guidance": "aperto",
  "incerteza": 0.25,
  "conviccao": 0.75,
  "justificativa": "...",
  "model_id": "Qwen2.5-14B-Instruct-Q5_K_M.gguf",
  "seed": 42,
  "prompt_version": "cb_lens_v1",
  "numero_reuniao": 117,
  "tipo": "ata",
  "available_time": "2006-03-16",
  "stance_delta": 0.25,
  "stability": {
    "stance": {"mean": 0.5, "std": 0.0, "values": [0.5, 0.5, 0.5]},
    "incerteza": {"mean": 0.25, "std": 0.0, "values": [0.25, 0.25, 0.25]},
    "conviccao": {"mean": 0.75, "std": 0.0, "values": [0.75, 0.75, 0.75]}
  }
}
```

### Em caso de erro

```json
{
  "numero_reuniao": 180,
  "tipo": "ata",
  "available_time": "2012-07-05",
  "error": "llama-server error after 3 retries: timed out",
  "stance_delta": null
}
```

## Estabilidade & Debug

O CLI executa `n_runs=3` (tres chamadas identicas com mesma semente)
para cada documento. Com `temperature=0.0`, as respostas devem ser
identicas (`std=0.0`). Se `std > 0`, indica nao-determinismo no
provider.

Com `--debug`, o sistema loga em `data/processed/debug.log`:
- Progresso por documento (meeting, tipo, data)
- Latencia e tokens por chamada LLM
- Primeiros 300 chars da resposta
- Erros detalhados
