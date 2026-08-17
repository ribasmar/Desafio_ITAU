"""
Deterministic LLM client for CopomLens.
Backends: llama.cpp (local via /completion) and OpenRouter (API).
"""

import logging
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Substrings de IDs de modelo cujo modo de raciocínio precisa ser desligado na
# extração de JSON (se deixado ativo, consome o teto de tokens e devolve
# content=null). Não-reasoning não recebem o campo (rejeitariam no Groq).
_REASONING_MODEL_HINTS = (
    "qwen3",
    "deepseek-r1",
    "deepseek-reasoner",
    "o1",
    "o3",
    "o4",
    "gpt-5",
    "grok",
    "llama-4",
    "gemini-2.5",
    "kimi",
    "thinking",
    "reasoning",
)


class LLMClient:
    """Deterministic LLM interface for llama.cpp and OpenRouter.

    Parameters
    ----------
    provider : str, optional
        ``"local"`` (llama.cpp) or ``"openrouter"``.
        Falls back to ``LLM_PROVIDER`` env var, then ``"local"``.
    server_url : str, optional
        URL of a running ``llama-server`` instance (provider=local).
        Falls back to ``LLAMA_SERVER_URL`` env var, then ``http://127.0.0.1:8080``.
    model : str, optional
        Model identifier. Falls back to provider-specific env var.
    seed : int, optional
        Random seed for reproducible output. Falls back to ``SEED`` env var, then ``42``.
    temperature : float
        Sampling temperature. ``0.0`` = greedy / deterministic.
    max_tokens : int
        Maximum tokens in the response.
    max_retries : int
        Number of connection retries on transient failures.
    openrouter_api_key : str, optional
        API key for OpenRouter. Falls back to ``OPENROUTER_API_KEY`` env var.
    debug : bool
        Enable debug logging (latency, token counts, response preview).
    """

    def __init__(
        self,
        provider: str | None = None,
        server_url: str | None = None,
        model: str | None = None,
        seed: int | None = None,
        temperature: float = 0.0,
        max_tokens: int = 800,
        max_retries: int = 3,
        openrouter_api_key: str | None = None,
        openrouter_provider: str | None = None,
        json_schema: dict | None = None,
        debug: bool = False,
    ) -> None:
        self.provider = provider or os.getenv("LLM_PROVIDER", "local")

        self.server_url = (
            server_url
            or os.getenv("LLAMA_SERVER_URL")
            or "http://127.0.0.1:8080"
        )

        if self.provider == "openrouter":
            self.model = (
                model
                or os.getenv("LLM_MODEL_OPENROUTER")
                or "qwen/qwen-3-32b"
            )
        else:
            self.model = (
                model
                or os.getenv("LLM_MODEL_LOCAL")
                or os.getenv("LLAMA_MODEL_PATH")
                or ""
            )

        self.seed = seed if seed is not None else int(os.getenv("SEED", "42"))
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.openrouter_api_key = (
            openrouter_api_key or os.getenv("OPENROUTER_API_KEY", "")
        )
        self.openrouter_provider = (
            openrouter_provider or os.getenv("OPENROUTER_PROVIDER", "")
        )
        self.json_schema = json_schema
        self.debug = debug

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        model: str | None = None,
        seed: int | None = None,
    ) -> str:
        """Send *prompt* to the configured provider."""
        model = model or self.model
        seed_val = seed if seed is not None else self.seed

        if self.provider == "local":
            return self._generate_local(prompt, model, seed_val)
        if self.provider == "openrouter":
            return self._generate_openrouter(prompt, model, seed_val)
        raise ValueError(f"Unknown provider: {self.provider}")

    # ------------------------------------------------------------------
    # Local (llama.cpp /completion)
    # ------------------------------------------------------------------

    def _generate_local(self, prompt: str, _model: str, seed_val: int) -> str:
        payload = {
            "prompt": prompt,
            "temperature": self.temperature,
            "seed": seed_val,
            "n_predict": self.max_tokens,
            "cache_prompt": False,
            "n_keep": -1,
        }
        if self.json_schema is not None:
            # O schema deixa de ser pedido no prompt e passa a ser imposto
            # pelo decoder (gramática GBNF do llama-server).
            payload["json_schema"] = self.json_schema

        url = f"{self.server_url}/completion"
        t0 = time.perf_counter()

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=180.0) as client:
                    resp = client.post(url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    elapsed = time.perf_counter() - t0

                    content = data.get("content", "")
                    if not isinstance(content, str):
                        content = str(content)

                    if self.debug:
                        tokens_in = data.get("tokens_evaluated", 0)
                        tokens_out = data.get("tokens_predicted", 0)
                        logger.debug(
                            "LLM call: %.2fs, %d tokens in, %d tokens out, seed=%d",
                            elapsed, tokens_in, tokens_out, seed_val,
                        )
                        logger.debug(
                            "LLM response (first 300 chars): %s", content[:300]
                        )

                    return content.strip()

            except httpx.ConnectError:
                last_error = (
                    f"Could not connect to llama-server at {self.server_url}. "
                    "Make sure llama-server is running."
                )
                if attempt < self.max_retries:
                    time.sleep(2 ** (attempt + 1))
                    continue
                break

            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries:
                    time.sleep(2 ** (attempt + 1))
                    continue
                break

        raise RuntimeError(
            f"llama-server error after {self.max_retries} retries: {last_error}"
        )

    # ------------------------------------------------------------------
    # OpenRouter (API)
    # ------------------------------------------------------------------

    def _generate_openrouter(
        self, prompt: str, model: str, seed_val: int
    ) -> str:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "seed": seed_val,
            "top_p": 1.0,
            "max_tokens": self.max_tokens,
        }
        if self.json_schema is not None:
            # Groq (único provedor sem quantização) não suporta "json_schema"
            # strict no roteamento (404 "No endpoints found"). "json_object"
            # garante JSON válido; o schema em si é imposto pelo prompt +
            # validação no código (promptExec._validate / divergencia).
            payload["response_format"] = {"type": "json_object"}
        # Modelos com modo de raciocínio híbrido (ex.: Qwen3) precisam do
        # thinking desligado, senão os tokens vão para o "reasoning" e o
        # "content" sai vazio. Modelos não-reasoning (ex.: Llama 3.3) não
        # suportam o campo e rejeitariam — por isso é condicional.
        if any(h in model for h in _REASONING_MODEL_HINTS):
            payload["reasoning"] = {"enabled": False}
        if self.openrouter_provider:
            payload["provider"] = {
                "order": [self.openrouter_provider],
                "allow_fallbacks": False,
            }

        t0 = time.perf_counter()

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=120.0) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    if resp.status_code == 429:
                        if attempt < self.max_retries:
                            retry_after = int(
                                resp.headers.get("Retry-After", 2 ** (attempt + 1))
                            )
                            time.sleep(retry_after)
                            continue
                        resp.raise_for_status()
                    if self.debug and resp.status_code >= 400:
                        logger.debug("OpenRouter error body: %s", resp.text[:500])
                    resp.raise_for_status()
                    data = resp.json()
                    elapsed = time.perf_counter() - t0

                    content = data["choices"][0]["message"]["content"]
                    if content is None:
                        # Qwen3-32B pode consumir todo o teto com reasoning e
                        # devolver content=null; trata como falha transiente
                        # para cair no retry (com seed diferente).
                        raise RuntimeError(
                            "OpenRouter returned empty content (reasoning overflow)"
                        )
                    if not isinstance(content, str):
                        content = str(content)

                    if self.debug:
                        usage = data.get("usage", {})
                        tokens_in = usage.get("prompt_tokens", 0)
                        tokens_out = usage.get("completion_tokens", 0)
                        logger.debug(
                            "LLM call: %.2fs, %d tokens in, %d tokens out, seed=%d",
                            elapsed, tokens_in, tokens_out, seed_val,
                        )
                        logger.debug(
                            "LLM response (first 300 chars): %s", content[:300]
                        )

                    return content.strip()

            except httpx.ConnectError:
                last_error = "Could not connect to OpenRouter API."
                if attempt < self.max_retries:
                    time.sleep(2 ** (attempt + 1))
                    continue
                break

            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries:
                    time.sleep(2 ** (attempt + 1))
                    continue
                break

        raise RuntimeError(
            f"OpenRouter error after {self.max_retries} retries: {last_error}"
        )
