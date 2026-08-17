# `LLMClient` (`src/copom/models/llm_client.py`)

Interface LLM deterministica para o CopomLens. Suporta dois
backends:

| Provider | Motor | Indicacao |
|---|---|---|
| `local` | llama-server (`/completion`) | Offline; arquivo GGUF local. Sem chat template |
| `openrouter` | httpx → API OpenRouter | API remota (requer internet + chave de API) |

## Variaveis de ambiente

Copie o template e edite:

```bash
cp .env.example .env
```

### Gerais

| Variavel | Padrao | Descricao |
|---|---|---|
| `LLM_PROVIDER` | `local` | Backend ativo: `local` ou `openrouter` |
| `SEED` | `42` | Semente do amostrador (reprodutibilidade) |
| `TEMPERATURE` | `0.0` | Temperatura de amostragem (0 = guloso / deterministico) |

### Local (llama.cpp)

Usa o endpoint nativo `/completion` (nao o wrapper OpenAI-compativel)
para garantir que `cache_prompt` e `n_keep` sejam respeitados.

| Variavel | Padrao | Descricao |
|---|---|---|
| `LLAMA_SERVER_URL` | `http://127.0.0.1:8080` | URL do llama-server |
| `LLM_MODEL_LOCAL` | `Qwen2.5-14B-Instruct-Q5_K_M.gguf` | Arquivo GGUF |

**Payload enviado:**
```json
{
  "prompt": "<texto completo>",
  "temperature": 0.0,
  "seed": 42,
  "n_predict": 2048,
  "cache_prompt": false,
  "n_keep": -1
}
```

`cache_prompt: false` + `n_keep: -1` instruem o servidor a nao
salvar nem reusar KV cache entre requisicoes.

**Inicializacao do servidor:**
```bash
LD_LIBRARY_PATH=./llama.cpp/bin ./llama.cpp/bin/llama-server \
  -m ./Qwen2.5-14B-Instruct-Q5_K_M.gguf \
  --host 127.0.0.1 --port 8080 \
  -c 32768 --cache-ram 0 -sps 0.0 -np 1 -ngl 99
```

A flag `--cache-ram 0` desabilita o prompt cache no nivel do
servidor — nenhum `prompt_save` ou `alloc` e executado.

### OpenRouter

| Variavel | Padrao | Descricao |
|---|---|---|
| `LLM_MODEL_OPENROUTER` | `qwen/qwen-3-32b` | Slug do modelo (ex.: `qwen/qwen-3-32b`) |
| `OPENROUTER_API_KEY` | — | Chave de API em https://openrouter.ai/keys |
| `OPENROUTER_PROVIDER` | — | Forcar provider upstream (ex.: `Groq`). Se vazio, roteamento automatico |

Quando `OPENROUTER_PROVIDER` e definido, o payload inclui:
```json
{
  "provider": {
    "order": ["Groq"],
    "allow_fallbacks": false
  }
}
```

## Resolucao de modelo

Ordem de prioridade:

1. Parametro `model` passado ao construtor
2. `LLM_MODEL_OPENROUTER` (provider=openrouter) ou `LLM_MODEL_LOCAL` (provider=local)
3. Default: `qwen/qwen-3-32b` (openrouter) ou string vazia (local)

## Retry

Ambos os backends implementam retry com backoff exponencial
(2s → 4s → 8s) para erros transientes. O OpenRouter tambem
trata HTTP 429 (rate limit) lendo o header `Retry-After`.

## Debug logging

Com `debug=True`, sao registrados:

- Latencia da chamada
- Tokens de entrada e saida
- Primeiros 300 caracteres da resposta do LLM
- Corpo do erro em respostas HTTP >= 400 (apenas OpenRouter)

## Construtor

```python
LLMClient(
    provider: str | None = None,            # "local" | "openrouter"
    server_url: str | None = None,           # URL do llama-server
    model: str | None = None,                # slug ou caminho GGUF
    seed: int | None = None,                 # semente (default: 42)
    temperature: float = 0.0,                # temperatura
    max_tokens: int = 30000,                 # tokens maximos na resposta
    max_retries: int = 3,                    # tentativas de retry
    openrouter_api_key: str | None = None,   # chave API OpenRouter
    openrouter_provider: str | None = None,  # provider upstream forcado
    debug: bool = False,                     # logs detalhados
)
```

## Metodos

| Metodo | Retorno | Descricao |
|---|---|---|
| `generate(prompt, model, seed)` | `str` | Envia prompt para o LLM configurado e retorna texto cru |

## Uso

### Local (llama.cpp)

```python
from copom.models import LLMClient

llm = LLMClient(provider="local")
print(llm.generate("Responda em JSON: {\"msg\": \"ola\"}"))
```

### OpenRouter

```python
llm = LLMClient(provider="openrouter", model="qwen/qwen-3-32b")
print(llm.generate("Responda em JSON: {\"msg\": \"ola\"}"))
```

### CLI

```bash
# Local (default)
python -m copom.models --ata-range 116:227 --debug

# OpenRouter com provider forcado
python -m copom.models --provider openrouter \
    --model qwen/qwen-3-32b \
    --openrouter-provider Groq \
    --ata-range 116:120 --debug
```

## Reprodutibilidade

Todo provider opera com `temperature=0.0` + semente deterministica.
O mesmo prompt sempre produz a mesma saida. Tanto `model_id` quanto
`seed` sao registrados junto a cada score extraido.

## Arquivos do modulo

| Arquivo | Papel |
|---|---|
| `llm_client.py` | Classe `LLMClient`: wrapper deterministico para 2 backends |
| `__main__.py` | Ponto de entrada CLI para extracao em lote |
| `promptExec.py` | Execucao de prompt unico (template → LLM → parse JSON → validacao) |
| `__init__.py` | Inicializador do pacote; exporta `LLMClient` |
