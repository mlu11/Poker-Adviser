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
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY", os.getenv("DEEPSEEK_API_KEY", ""))
DOUBAO_API_ENDPOINT = os.getenv("DOUBAO_API_ENDPOINT", "https://ark.cn-beijing.volces.com/api/v3")
DEFAULT_MODEL = os.getenv("POKER_AI_MODEL", "doubao-seed-2-0-lite")
DEEP_ANALYSIS_MODEL = os.getenv("POKER_AI_DEEP_MODEL", "doubao-seed-2-0-pro")
MAX_TOKENS = int(os.getenv("POKER_AI_MAX_TOKENS", "4096"))

# Training
DEFAULT_TRAINING_SCENARIOS = int(os.getenv("POKER_TRAINING_COUNT", "10"))

# Blinds default
DEFAULT_SMALL_BLIND = float(os.getenv("POKER_DEFAULT_SB", "10"))
DEFAULT_BIG_BLIND = float(os.getenv("POKER_DEFAULT_BB", "20"))
