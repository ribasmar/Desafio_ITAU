# Modulo `copom.models` — Visao Geral

Pacote responsavel pela camada de integracao com LLMs no pipeline
CopomLens. Fornece abstracao unificada para dois provedores
(local llama.cpp e OpenRouter) com foco em reprodutibilidade
(temperature=0 + semente fixa).

## Arquivos

| Arquivo | Descricao | Documentacao |
|---|---|---|
| `llm_client.py` | Classe `LLMClient`: wrapper deterministico para 2 backends | [llm_client.md](./llm_client.md) |
| `__main__.py` | Ponto de entrada CLI para extracao em lote | [__main__.py.md](./__main__.py.md) |
| `promptExec.py` | Pipeline de prompt unico: template → LLM → JSON → validacao | [promptExec.md](./promptExec.md) |
| `__init__.py` | Inicializador do pacote; exporta `LLMClient` | — |

## Fluxo do pipeline

```
                        ┌─────────────────────────────────┐
                        │      python -m copom.models     │
                        │      (--provider local/openr)   │
                        └───────────────┬─────────────────┘
                                        │
                                        ▼
                        ┌─────────────────────────────────┐
                        │       extract_tone()            │
                        │  (copom.features.extract_tone)  │
                        │   executa n_runs=3 vezes        │
                        │   STANCE_MAP[label → float]     │
                        └───────────────┬─────────────────┘
                                        │
                               ┌─────────┴─────────┐
                               ▼                   ▼
                 ┌──────────────────────┐ ┌──────────────────────┐
                 │   promptExec.py      │ │   promptExec.py      │
                 │   build_prompt()     │ │   (run 2, 3)         │
                 │   llm.generate()     │ │                      │
                 │   _validate()        │ │                      │
                 └──────────────────────┘ └──────────────────────┘
                                        │
                                        ▼
                        ┌─────────────────────────────────────┐
                        │  Pareamento (features/pareamento)  │
                        │  stance_pareado = ata − comunicado │
                        └─────────────────────────────────────┘
```

## Resolucao de modelo (provider-aware)

```
arg --model  →  LLM_MODEL_OPENROUTER (openrouter)  →  LLM_MODEL_LOCAL (local)
             →  LLAMA_MODEL_PATH  →  _DEFAULT_MODEL
```

| Prioridade | Fonte | Exemplo |
|---|---|---|
| 1 | `--model` (CLI) | `--model qwen/qwen-3-32b` |
| 2 | `LLM_MODEL_OPENROUTER` (provider=openrouter) | `qwen/qwen-3-32b` |
| 2 | `LLM_MODEL_LOCAL` (provider=local) | `Qwen2.5-14B-Instruct-Q5_K_M.gguf` |
| 3 | `LLAMA_MODEL_PATH` | fallback legado |
| 4 | `_DEFAULT_MODEL` | `Qwen2.5-14B-Instruct-Q5_K_M.gguf` |

## Variaveis de ambiente

| Variavel | Descricao |
|---|---|
| `LLM_PROVIDER` | Backend ativo: `local` ou `openrouter` |
| `LLM_MODEL_LOCAL` | Arquivo GGUF local |
| `LLM_MODEL_OPENROUTER` | Slug do modelo OpenRouter |
| `LLAMA_SERVER_URL` | URL do llama-server |
| `OPENROUTER_API_KEY` | Chave de API OpenRouter |
| `OPENROUTER_PROVIDER` | Provider upstream forcado (ex.: `Groq`) |
| `PROMPT_PATH` | Template de prompt (default: `copom_v3.md`) |
| `SEED` | Semente para reprodutibilidade |
| `TEMPERATURE` | Temperatura de amostragem |

## Configuracao padrao

O projeto vem configurado para usar **llama.cpp local** como provider padrao:

```bash
LLM_PROVIDER=local
LLM_MODEL_LOCAL=Qwen2.5-14B-Instruct-Q5_K_M.gguf
```

Para usar OpenRouter:

```bash
LLM_PROVIDER=openrouter
LLM_MODEL_OPENROUTER=qwen/qwen-3-32b
OPENROUTER_API_KEY=sk-or-v1-...
```
