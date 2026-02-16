
"""Test the doubao code model with correct configuration."""

import requests
import os

# Code model configuration from user
api_key = "2564603b-a6fc-4983-8b00-c932d78ea969"
base_url = "https://ark.cn-beijing.volces.com/api/coding/v3"
model = "ark-code-latest"

prompt = """Write a simple Python program that:
1. Prints "Hello World! I'm doubao-seed-2-0-code."
2. Calculates the first 10 Fibonacci numbers and prints them
3. Add a comment explaining what each part does

Just give me the complete working code.
"""

payload = {
    "model": model,
    "messages": [
        {"role": "user", "content": prompt}
    ],
    "max_tokens": 500
}

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# Build URL correctly
if base_url.endswith('/chat/completions'):
    url = base_url
elif base_url.endswith('/'):
    url = f"{base_url}chat/completions"
else:
    url = f"{base_url}/chat/completions"

print(f"Testing doubao code model:")
print(f"  URL: {url}")
print(f"  Model: {model}")
print(f"  API Key: {api_key[:10]}...{api_key[-5:]}")
print(f"\nPrompt: {prompt}\n")

response = requests.post(url, json=payload, headers=headers, timeout=60)
if not response.ok:
    print(f"\n❌ Error {response.status_code}: {response.text}")
else:
    result = response.json()
    content = result["choices"][0]["message"]["content"]
    print("\n✅ Success! Generated Code:\n")
    print(content)
