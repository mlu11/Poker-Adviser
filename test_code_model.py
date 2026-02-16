#!/usr/bin/env python3
"""Test the Doubao code model configuration."""

import sys
sys.path.insert(0, './src')

from poker_advisor import config
from poker_advisor.ai.client import ClaudeClient

print("=== Current Configuration ===")
print(f"DOUBAO_LITE_API_KEY: {config.DOUBAO_LITE_API_KEY}")
print(f"DOUBAO_LITE_ENDPOINT: {config.DOUBAO_LITE_API_ENDPOINT}")
print(f"DOUBAO_LITE_MODEL: {config.DOUBAO_LITE_MODEL}")
print()
print(f"DOUBAO_CODE_API_KEY: {config.DOUBAO_CODE_API_KEY}")
print(f"DOUBAO_CODE_ENDPOINT: {config.DOUBAO_CODE_API_ENDPOINT}")
print(f"DOUBAO_CODE_MODEL: {config.DOUBAO_CODE_MODEL}")
print()
print(f"DEEP_ANALYSIS_MODEL: {config.DEEP_ANALYSIS_MODEL}")
print()

# Test code model
print("=== Testing code model API call... ===")
try:
    client = ClaudeClient(
        api_key=config.DOUBAO_CODE_API_KEY,
        model=config.DOUBAO_CODE_MODEL,
        endpoint=config.DOUBAO_CODE_API_ENDPOINT,
    )
    response = client.ask("Hello! Please write a short Python function to add two numbers.", system="You are a helpful coding assistant.")
    print("\n✅ Success! Got response:\n")
    print(response[:500])
    if len(response) > 500:
        print("... (truncated)")
except Exception as e:
    print(f"\n❌ Failed: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
