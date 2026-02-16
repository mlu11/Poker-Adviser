
import requests
import os

# 测试豆包API连接
api_key = os.getenv("DOUBAO_API_KEY")
endpoint = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
model = "doubao-seed-2-0-lite-260215"

payload = {
    "model": model,
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ],
    "max_tokens": 10
}

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

print(f"Testing connection to: {endpoint}")
print(f"Model: {model}")
print(f"API Key: {api_key[:10]}...{api_key[-5:]}")

try:
    response = requests.post(endpoint, json=payload, headers=headers, timeout=30)
    print(f"\nStatus: {response.status_code}")
    if response.ok:
        result = response.json()
        print(f"\nSuccess! Response: {result}")
    else:
        print(f"\nError: {response.text}")
except Exception as e:
    print(f"\nException: {str(e)}")
