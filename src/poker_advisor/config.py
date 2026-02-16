"""Configuration loading from environment variables and defaults."""

import os
from pathlib import Path

# Database
DB_PATH = Path(os.getenv("POKER_DB_PATH", "poker_advisor.db"))

# AI Provider: deepseek or doubao
AI_PROVIDER = os.getenv("POKER_AI_PROVIDER", "doubao")

# DeepSeek API (fallback)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_ENDPOINT = os.getenv("DEEPSEEK_API_ENDPOINT", "https://api.deepseek.com/v1")

# Doubao API (OpenAI compatible)
# For Volcano Engine:
# - Lite model (general chat): endpoint_id in model, API key = DOUBAO_API_KEY
# - Code model (coding/deep analysis): separate API key and endpoint
DOUBAO_LITE_API_KEY = os.getenv("DOUBAO_LITE_API_KEY", "5a1871c0-875c-4c0d-b987-5125a0508823")
DOUBAO_LITE_API_ENDPOINT = os.getenv("DOUBAO_LITE_API_ENDPOINT", "https://ark.cn-beijing.volces.com/api/v3/chat/completions")
DOUBAO_LITE_MODEL = os.getenv("DOUBAO_LITE_MODEL", "5a1871c0-875c-4c0d-b987-5125a0508823")

DOUBAO_CODE_API_KEY = os.getenv("DOUBAO_CODE_API_KEY", "2564603b-a6fc-4983-8b00-c932d78ea969")
DOUBAO_CODE_API_ENDPOINT = os.getenv("DOUBAO_CODE_API_ENDPOINT", "https://ark.cn-beijing.volces.com/api/coding/v3")
DOUBAO_CODE_MODEL = os.getenv("DOUBAO_CODE_MODEL", "ark-code-latest")

# Defaults
AI_PROVIDER = os.getenv("POKER_AI_PROVIDER", "doubao")
DOUBAO_API_KEY = DOUBAO_LITE_API_KEY  # backward compatibility
DOUBAO_API_ENDPOINT = DOUBAO_LITE_API_ENDPOINT
DEFAULT_MODEL = DOUBAO_LITE_MODEL
DEEP_ANALYSIS_MODEL = DOUBAO_CODE_MODEL
MAX_TOKENS = int(os.getenv("POKER_AI_MAX_TOKENS", "4096"))

# Training
DEFAULT_TRAINING_SCENARIOS = int(os.getenv("POKER_TRAINING_COUNT", "10"))

# Blinds default
DEFAULT_SMALL_BLIND = float(os.getenv("POKER_DEFAULT_SB", "10"))
DEFAULT_BIG_BLIND = float(os.getenv("POKER_DEFAULT_BB", "20"))
