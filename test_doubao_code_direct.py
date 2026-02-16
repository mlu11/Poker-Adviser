#!/usr/bin/env python3
"""Test direct call to doubao code API to verify URL and auth."""

import sys
import requests

from poker_advisor import config

print("Testing direct call to doubao code API:")
print(f"API Key: {config.DOUBAO_CODE_API_KEY}")
print(f"Endpoint: {config.DOUBAO_CODE_API_ENDPOINT}")
print(f"Model: {config.DOUBAO_CODE_MODEL}")
print()

# Try with and without /chat/completions
url_candidate1 = f"{config.DOUBAO_CODE_API_ENDPOINT.rstrip('/')}/chat/completions"
url_candidate2 = config.DOUBAO_CODE_API_ENDPOINT

print(f"Candidate 1: {url_candidate1}")
print(f"Candidate 2: {url_candidate2}")
print()

headers = {
    "Authorization": f"Bearer {config.DOUBAO_CODE_API_KEY}",
    "Content-Type": "application/json",
}

payload = {
    "model": config.DOUBAO_CODE_MODEL,
    "messages": [
        {"role": "user", "content": "Hello! Write a Python function that adds two numbers."}
    ],
    "max_tokens": 100,
}

print("Trying candidate 1...")
try:
    resp = requests.post(url_candidate1, json=payload, headers=headers, timeout=30)
    print(f"Status: {resp.status_code}")
    if resp.ok:
        result = resp.json()
        print(f"✅ Success! Response:")
        print(result["choices"][0]["message"]["content"][:200])
    else:
        print(f"❌ Error: {resp.text}")
except Exception as e:
    print(f"❌ Exception: {e}")

print("\n---\n")

print("Trying candidate 2...")
try:
    resp = requests.post(url_candidate2, json=payload, headers=headers, timeout=30)
    print(f"Status: {resp.status_code}")
    if resp.ok:
        result = resp.json()
        print(f"✅ Success! Response:")
        print(result["choices"][0]["message"]["content"][:200])
    else:
        print(f"❌ Error: {resp.text}")
except Exception as e:
    print(f"❌ Exception: {e}")
