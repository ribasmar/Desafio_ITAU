"""
Deterministic LLM client for Copom Quant AI.
Supports local (llama.cpp), Ollama, and OpenRouter providers.
"""

import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()


class LLMClient:
    """Deterministic LLM interface with pluggable backends.

    Parameters
    ----------
    provider : str, optional
        One of ``"local"``, ``"ollama"``, ``"openrouter"``.
        Falls back to ``LLM_PROVIDER`` env var, then ``"local"``.
    model : str, optional
        Model name / path. Default depends on provider (see ``DEFAULT_MODELS``).
    seed : int, optional
        Random seed for reproducible output. Falls back to ``SEED`` env var, then ``42``.
    temperature : float
        Sampling temperature. ``0.0`` = greedy / deterministic.
    llama_server_url : str, optional
        URL of a running ``llama-server`` instance (OpenAI-compatible endpoint).
        Falls back to ``LLAMA_SERVER_URL`` env var, then ``http://127.0.0.1:8080``.
    openrouter_api_key : str, optional
        API key for OpenRouter. Falls back to ``OPENROUTER_API_KEY`` env var.
    ollama_host : str, optional
        Ollama server URL. Falls back to ``OLLAMA_HOST`` env var, then
        ``http://localhost:11434``.

    Reproducibility
    ----------------
    Every provider uses ``temperature=0.0`` + a fixed ``seed``, so the same
    prompt always yields the same output.  The ``model_id`` and ``seed`` are
    recorded alongside every score.
    """

    DEFAULT_MODELS: dict[str, str] = {
        "local": "Meta-Llama-3.1-8B-Instruct-Q8_0.gguf",
        "ollama": "llama3.1:8B",
        "openrouter": "meta-llama/llama-3.1-8b-instruct",
    }

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        seed: int | None = None,
        temperature: float = 0.0,
        llama_server_url: str | None = None,
        openrouter_api_key: str | None = None,
        openrouter_provider:str | None = None, 
        ollama_host: str | None = None,
    ) -> None:
        self.provider = provider or os.getenv("LLM_PROVIDER", "local")
        self.seed = seed if seed is not None else int(os.getenv("SEED", "42"))
        self.temperature = temperature

        model_env_key = f"LLM_MODEL_{self.provider.upper()}"
        self.model = (
            model
            or os.getenv(model_env_key)
            or os.getenv("OPENROUTER_MODEL")  # backward-compat fallback
            or self.DEFAULT_MODELS.get(self.provider, "")
        )

        self.llama_server_url = (
            llama_server_url
            or os.getenv("LLAMA_SERVER_URL")
            or "http://127.0.0.1:8080"
        )
        self.openrouter_api_key = (
            openrouter_api_key
            or os.getenv("OPENROUTER_API_KEY", "")
        )
        self.openrouter_provider = (
            openrouter_provider
            or os.getenv("OPENROUTER_PROVIDER","")
        )
        self.ollama_host = (
            ollama_host
            or os.getenv("OLLAMA_HOST")
            or "http://localhost:11434"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        model: str | None = None,
        seed: int | None = None,
    ) -> str:
        """Send *prompt* to the configured LLM and return the raw response."""
        model = model or self.model
        seed = seed if seed is not None else self.seed

        dispatch = {
            "local": self._generate_llama_server,
            "ollama": self._generate_ollama,
            "openrouter": self._generate_openrouter,
        }
        handler = dispatch.get(self.provider)
        if handler is None:
            raise ValueError(f"Unknown provider: {self.provider}")

        return handler(prompt, model, seed)

    def generate_from_file(
        self,
        path: str,
        model: str | None = None,
        seed: int | None = None,
    ) -> str:
        """Read *path* as a prompt and send it to the LLM."""
        if not os.path.exists(path):
            return f"Error: file not found '{path}'"

        with open(path, "r", encoding="utf-8") as f:
            return self.generate(f.read(), model=model, seed=seed)

    # ------------------------------------------------------------------
    # Local (llama-server via HTTP)
    # ------------------------------------------------------------------

    def _generate_llama_server(self, prompt: str, model: str, seed: int) -> str:
        url = f"{self.llama_server_url}/v1/chat/completions"

        system = self._extract_system(prompt)
        user = self._extract_user(prompt)

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": self.temperature,
            "seed": seed,
            "max_tokens": 512,
        }

        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"].strip()
        except httpx.ConnectError:
            return (
                f"Could not connect to llama-server at {self.llama_server_url}. "
                "Make sure llama-server is running (see docs/src/models/llm_client.md)."
            )
        except Exception as e:
            return f"llama-server error: {e}"

    # ------------------------------------------------------------------
    # Ollama (local server via Python client)
    # ------------------------------------------------------------------

    def _generate_ollama(self, prompt: str, model: str, seed: int) -> str:
        import ollama

        system = self._extract_system(prompt)
        user = self._extract_user(prompt)

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        client = ollama.Client(host=self.ollama_host)
        response = client.chat(
            model=model,
            messages=messages,
            options={
                "temperature": self.temperature,
                "seed": seed,
            },
        )
        return response["message"]["content"].strip()

    # ------------------------------------------------------------------
    # OpenRouter (remote API via httpx)
    # ------------------------------------------------------------------

    def _generate_openrouter(self, prompt: str, model: str, seed: int) -> str:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        payload: dict = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "seed": seed,
            "top_p": 1.0,
            "top_k": 1,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
            "provider": {
                "order": self.openrouter_provider,
                "allow_fallbacks": "false"
                }
        }
        if self.openrouter_provider:
            payload["provider"] = {"only": [self.openrouter_provider]}

        max_retries = 3
        for attempt in range(max_retries + 1):
            try:
                with httpx.Client(timeout=60.0) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    if resp.status_code == 429:
                        if attempt < max_retries:
                            retry_after = int(resp.headers.get("Retry-After", 2 ** (attempt + 1)))
                            time.sleep(retry_after)
                            continue
                    resp.raise_for_status()
                    return resp.json()["choices"][0]["message"]["content"].strip()
            except Exception as e:
                if attempt < max_retries and "429" in str(e):
                    time.sleep(2 ** (attempt + 1))
                    continue
                return f"OpenRouter API error: {e}"
        return "OpenRouter API error: max retries exceeded"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_system(full_prompt: str) -> str:
        """Extract the ``## System`` section from a copom markdown prompt."""
        lines = full_prompt.splitlines()
        in_system = False
        parts: list[str] = []
        for line in lines:
            if line.strip().startswith("## System"):
                in_system = True
                continue
            if line.strip().startswith("## User"):
                break
            if in_system:
                parts.append(line)
        return "\n".join(parts).strip()

    @staticmethod
    def _extract_user(full_prompt: str) -> str:
        """Extract the ``## User`` section from a copom markdown prompt."""
        lines = full_prompt.splitlines()
        in_user = False
        parts: list[str] = []
        for line in lines:
            if line.strip().startswith("## User"):
                in_user = True
                continue
            if in_user:
                parts.append(line)
        return "\n".join(parts).strip()
