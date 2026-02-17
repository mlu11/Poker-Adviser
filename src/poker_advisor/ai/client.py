"""AI Client wrapper for strategy analysis (OpenAI-compatible interface).
Supports both DeepSeek and Doubao providers.
Uses streaming to avoid read timeout on slow LLM responses.
"""

from typing import Optional
import json
import time
import requests

from poker_advisor import config


class ClaudeClient:
    """Wrapper around AI API (OpenAI-compatible interface).
    Supports DeepSeek and Doubao.
    """

    def __init__(self, api_key: Optional[str] = None,
                 model: Optional[str] = None,
                 endpoint: Optional[str] = None):
        # Select provider config
        if config.AI_PROVIDER == "doubao":
            self.api_key = api_key or config.DOUBAO_API_KEY
            self.endpoint = endpoint or config.DOUBAO_API_ENDPOINT
        else:  # deepseek
            self.api_key = api_key or config.DEEPSEEK_API_KEY
            self.endpoint = endpoint or config.DEEPSEEK_API_ENDPOINT

        if not self.api_key:
            raise ValueError(
                f"{config.AI_PROVIDER.upper()}_API_KEY not set. "
                "Set it via environment variable or pass api_key=."
            )
        self.model = model or config.DEFAULT_MODEL
        self.endpoint = self.endpoint

    def ask(self, prompt: str, system: str = "",
            model: Optional[str] = None,
            max_tokens: Optional[int] = None) -> str:
        """Send a prompt to the AI provider and return the text response.

        Uses streaming (SSE) so the connection stays alive as long as tokens
        are being generated, avoiding read-timeout on slow responses.
        """
        # Build URL
        if self.endpoint.endswith('/chat/completions'):
            url = self.endpoint
        else:
            url = f"{self.endpoint.rstrip('/')}/chat/completions"

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model or self.model,
            "messages": messages,
            "max_tokens": max_tokens or config.MAX_TOKENS,
            "stream": True,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        max_retries = 3
        connect_timeout = 30
        # Per-chunk read timeout — only needs to cover the gap between
        # successive SSE chunks, not the entire generation time.
        chunk_timeout = 120

        for attempt in range(max_retries + 1):
            try:
                response = requests.post(
                    url, json=payload, headers=headers,
                    timeout=(connect_timeout, chunk_timeout),
                    stream=True,
                )
                if not response.ok:
                    error_text = response.text[:300]
                    print(f"Response [{response.status_code}]: {error_text}")
                    response.raise_for_status()

                # Collect streamed SSE chunks into full content
                content = self._read_stream(response)
                if content:
                    return content

                raise RuntimeError("Streaming response returned empty content")

            except requests.exceptions.Timeout:
                if attempt < max_retries:
                    wait = 2 ** attempt
                    print(f"⏱ 请求超时，{wait}秒后重试 {attempt + 1}/{max_retries}...")
                    time.sleep(wait)
                    continue
                else:
                    raise
            except requests.exceptions.RequestException as e:
                if attempt < max_retries:
                    wait = 2 ** attempt
                    print(f"⚠️ 请求失败，{wait}秒后重试 {attempt + 1}/{max_retries}: {str(e)[:100]}")
                    time.sleep(wait)
                    continue
                else:
                    raise

    @staticmethod
    def _read_stream(response: requests.Response) -> str:
        """Read an SSE stream and return the concatenated content."""
        # Force UTF-8 decoding — Doubao API may not declare charset in headers
        response.encoding = "utf-8"
        collected = []
        for raw_line in response.iter_lines():
            if not raw_line:
                continue
            # Decode bytes to str with UTF-8 explicitly
            line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
            # SSE format: "data: {...}" or "data: [DONE]"
            if line.startswith("data: "):
                data = line[6:]
                if data.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0].get("delta", {})
                    text = delta.get("content", "")
                    if text:
                        collected.append(text)
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
        return "".join(collected)
