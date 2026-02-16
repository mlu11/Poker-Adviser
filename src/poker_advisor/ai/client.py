"""AI Client wrapper for strategy analysis (OpenAI-compatible interface).
Supports both DeepSeek and Doubao providers.
"""

from typing import Optional
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

        Args:
            prompt: The user message.
            system: Optional system prompt.
            model: Override model for this request.
            max_tokens: Override max tokens.

        Returns:
            The assistant's text response.
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
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        # Increase timeout and add retry logic
        max_retries = 2
        timeout = 60  # 60 seconds (increased from 30)
        
        for attempt in range(max_retries + 1):
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=timeout)
                if not response.ok:
                    print(f"Response [{response.status_code}]: {response.text[:200]}")
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"]
            except requests.exceptions.Timeout:
                if attempt < max_retries:
                    print(f"⏱ 请求超时，重试 {attempt + 1}/{max_retries}...")
                    continue
                else:
                    raise
            except requests.exceptions.RequestException as e:
                if attempt < max_retries:
                    print(f"⚠️ 请求失败，重试 {attempt + 1}/{max_retries}: {str(e)[:100]}")
                    continue
                else:
                    raise
