# Modulo `copom.models` — Visao Geral

Pacote responsavel pela camada de integracao com LLMs no pipeline
Copom Quant AI. Fornece abstracao unificada para tres provedores
(local, Ollama, OpenRouter) com foco em reprodutibilidade
(temperature=0 + semente fixa).

## Arquivos

| Arquivo | Descricao | Documentacao |
|---|---|---|
| `llm_client.py` | Classe `LLMClient`: wrapper deterministico para 3 backends | [llm_client.md](./llm_client.md) |
| `__main__.py` | Ponto de entrada CLI para extracao em lote | [__main__.py.md](./__main__.py.md) |
| `promptExec.py` | Pipeline de prompt unico: template → LLM → JSON → validacao | [promptExec.md](./promptExec.md) |
| `__init__.py` | Inicializador do pacote; exporta `LLMClient` | — |

## Fluxo do pipeline

```
                        ┌─────────────────────────────────┐
                        │      python -m copom.models     │
                        │         (--provider X)          │
                        └───────────────┬─────────────────┘
                                        │
                                        ▼
                        ┌─────────────────────────────────┐
                        │       extract_tone()            │
                        │  (copom.features.extract_tone)  │
                        │   executa n_runs=3 vezes        │
                        └───────────────┬─────────────────┘
                                        │
                              ┌─────────┴─────────┐
                              ▼                   ▼
                ┌──────────────────────┐ ┌──────────────────────┐
                │   promptExec.py      │ │   promptExec.py      │
                │   build_prompt()     │ │   build_prompt()     │
                │   (run 1)            │ │   (run 2, 3)         │
                └──────────┬───────────┘ └──────────┬───────────┘
                           │                        │
                           ▼                        ▼
                ┌──────────────────────┐ ┌──────────────────────┐
                │   LLMClient          │ │   LLMClient          │
                │   .generate()        │ │   .generate()        │
                └──────────┬───────────┘ └──────────┬───────────┘
                           │                        │
                           ▼                        ▼
                ┌──────────────────────┐ ┌──────────────────────┐
                │  _parse_llm_json()   │ │  _parse_llm_json()   │
                │  + validacao schema  │ │  + validacao schema  │
                └──────────┬───────────┘ └──────────┬───────────┘
                           │                        │
                           └───────────┬────────────┘
                                       ▼
                        ┌─────────────────────────────────┐
                        │    Agregacao de estabilidade    │
                        │    mean / std por campo         │
                        └─────────────────────────────────┘
```

## Resolucao de modelo

O modelo e resolvido em cascata:

```
arg --model  →  LLM_MODEL_<PROVIDER>  →  OPENROUTER_MODEL  →  DEFAULT_MODELS
```

| Prioridade | Fonte | Exemplo |
|---|---|---|
| 1 | Parametro `model` no construtor | `LLMClient(model="...")` |
| 2 | `LLM_MODEL_OPENROUTER` | `qwen/qwen-2.5-7b-instruct` |
| 3 | `OPENROUTER_MODEL` (retrocompat) | `qwen/qwen-2.5-7b-instruct` |
| 4 | `DEFAULT_MODELS[provider]` | `qwen/qwen-2.5-7b-instruct` |

## Variaveis de ambiente

| Variavel | Descricao |
|---|---|
| `LLM_PROVIDER` | Backend ativo: `local`, `ollama` ou `openrouter` |
| `LLM_MODEL_OPENROUTER` | Slug do modelo OpenRouter |
| `LLM_MODEL_OLLAMA` | Tag do modelo Ollama |
| `OPENROUTER_API_KEY` | Chave de API OpenRouter |
| `OPENROUTER_PROVIDER` | Provider upstream para roteamento |
| `OLLAMA_HOST` | URL do servidor Ollama |
| `LLAMA_SERVER_URL` | URL do llama-server |
| `SEED` | Semente para reprodutibilidade |
| `TEMPERATURE` | Temperatura de amostragem |

## Configuracao padrao

O projeto vem configurado para usar **OpenRouter** como provider padrao:

```bash
LLM_PROVIDER=openrouter
LLM_MODEL_OPENROUTER=qwen/qwen-2.5-7b-instruct
OPENROUTER_PROVIDER=together
```

Para usar Ollama ou local, altere `LLM_PROVIDER` no `.env` ou passe
`--provider ollama` / `--provider local` no CLI.
