# `LLMClient` (`src/copom/models/llm_client.py`)

Interface LLM deterministica para o Copom Quant AI. Suporta tres
backends:

| Provider | Motor | Indicacao |
|---|---|---|
| `local` | llama-server (HTTP) | Offline; usa arquivo GGUF local via endpoint OpenAI-compativel |
| `ollama` | Cliente Python Ollama | Servidor local; modelo baixado via `ollama pull` |
| `openrouter` | httpx → API OpenRouter | API remota (requer internet + chave de API) |

## Variaveis de ambiente

Copie o template e edite:

```bash
cp .env.example .env
```

### Gerais

| Variavel | Padrao | Descricao |
|---|---|---|
| `LLM_PROVIDER` | `openrouter` | Backend ativo: `local`, `ollama` ou `openrouter` |
| `SEED` | `42` | Semente do amostrador (reprodutibilidade) |
| `TEMPERATURE` | `0.0` | Temperatura de amostragem (0 = guloso / deterministico) |

### Resolucao de modelo

O modelo e resolvido na seguinte ordem de prioridade:

1. Parametro `model` passado ao construtor
2. Variavel `LLM_MODEL_<PROVIDER>` (ex.: `LLM_MODEL_OPENROUTER`)
3. Variavel `OPENROUTER_MODEL` (retrocompatibilidade, apenas para openrouter)
4. Variavel `LLAMA_MODEL_PATH` (apenas para local)
5. Default do `DEFAULT_MODELS`

| Variavel | Provider | Descricao |
|---|---|---|
| `LLM_MODEL_OPENROUTER` | openrouter | Slug do modelo OpenRouter (ex.: `qwen/qwen-2.5-7b-instruct`) |
| `LLM_MODEL_OLLAMA` | ollama | Tag do modelo Ollama (ex.: `qwen2.5:7b`) |
| `LLM_MODEL_LOCAL` | local | Caminho do arquivo GGUF |

### Ollama

| Variavel | Padrao | Descricao |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | URL do servidor Ollama |

### Local (llama-server)

| Variavel | Padrao | Descricao |
|---|---|---|
| `LLAMA_SERVER_URL` | `http://127.0.0.1:8080` | URL do endpoint OpenAI-compativel do llama-server |

### OpenRouter

| Variavel | Padrao | Descricao |
|---|---|---|
| `OPENROUTER_API_KEY` | — | Chave de API em https://openrouter.ai/keys |
| `OPENROUTER_PROVIDER` | — | Provider upstream para roteamento (ex.: `together`, `phala`). Se vazio, o OpenRouter roteia automaticamente |

## Modelos padrao

| Provider | Modelo padrao |
|---|---|
| `openrouter` | `qwen/qwen-2.5-7b-instruct` |
| `ollama` | `qwen2.5:7b` |
| `local` | `Qwen2.5-7B-Instruct-Q8_0.gguf` |

### Modelos populares no OpenRouter

| Slug | Modelo |
|---|---|
| `qwen/qwen-2.5-7b-instruct` | Qwen 2.5 7B  |
| `meta-llama/llama-3.1-8b-instruct` | Llama 3.1 8B (padrao)|
| `mistralai/mistral-7b-instruct` | Mistral 7B |
| `anthropic/claude-3-haiku` | Claude 3 Haiku |

A slug e o path apos `openrouter.ai/` na pagina do modelo.
Exemplo: `https://openrouter.ai/qwen/qwen-2.5-7b-instruct` → `qwen/qwen-2.5-7b-instruct`.

## Retry para rate limiting (429)

O metodo `_generate_openrouter()` implementa retry com backoff exponencial
para erros HTTP 429 (Too Many Requests):

- Maximo de 3 tentativas
- Le o header `Retry-After` quando disponivel
- Caso contrario, usa backoff exponencial: 2s → 4s → 8s
- Erros diferentes de 429 sao propagados imediatamente (sem retry)

## Uso

### Python

```python
from copom.models import LLMClient

# OpenRouter (padrao via .env)
llm = LLMClient()
print(llm.generate("Responda em JSON: {\"msg\": \"ola\"}"))

# Ollama local
llm = LLMClient(provider="ollama")
print(llm.generate("Responda em JSON: {\"msg\": \"ola\"}"))

# Com modelo especifico
llm = LLMClient(provider="openrouter", model="meta-llama/llama-3.1-8b-instruct")
print(llm.generate("Responda em JSON: {\"msg\": \"ola\"}"))
```

### CLI

```bash
# OpenRouter com ata especifica
PYTHONPATH=src python -m copom.models --provider openrouter --ata 270

# Ollama com limite de documentos
PYTHONPATH=src python -m copom.models --provider ollama --limit 5

# Modelo especifico via CLI
PYTHONPATH=src python -m copom.models --provider openrouter \
    --model meta-llama/llama-3.1-8b-instruct --ata 270
```

## Reprodutibilidade

Todo provider opera com `temperature=0.0` + semente deterministica.
O mesmo prompt sempre produz a mesma saida. Tanto `model_id` quanto
`seed` sao registrados junto a cada score extraído (veja
[`extract_tone()`](../features/extract_tone)).

## Construtor

```python
LLMClient(
    provider: str | None = None,      # "local" | "ollama" | "openrouter"
    model: str | None = None,          # slug do modelo
    seed: int | None = None,           # semente (default: 42)
    temperature: float = 0.0,          # temperatura
    llama_server_url: str | None = None,  # URL do llama-server
    openrouter_api_key: str | None = None,  # chave API OpenRouter
    openrouter_provider: str | None = None, # provider upstream
    ollama_host: str | None = None,    # URL do servidor Ollama
)
```

## Metodos

| Metodo | Retorno | Descricao |
|---|---|---|
| `generate(prompt, model, seed)` | `str` | Envia prompt para o LLM configurado e retorna texto cru |
| `generate_from_file(path, model, seed)` | `str` | Le arquivo como prompt e chama `generate()` |

## Arquivos do modulo

| Arquivo | Papel |
|---|---|
| `llm_client.py` | Classe `LLMClient`: wrapper deterministico para 3 backends |
| `__main__.py` | Ponto de entrada CLI para extracao em lote |
| `promptExec.py` | Execucao de prompt unico (template → LLM → parse JSON → validacao) |
| `__init__.py` | Inicializador do pacote; exporta `LLMClient` |
