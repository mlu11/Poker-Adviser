# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

德州扑克策略顾问 — 解析 Poker Now Club 手牌历史日志，存储至 SQLite，计算玩家统计数据，检测漏洞，并通过 Doubao API（OpenAI 兼容接口）提供 AI 驱动的策略分析和交互式训练。双界面：Typer CLI 和 Streamlit Web UI。

## 构建与运行命令

```bash
# 以开发模式安装
pip install -e ".[dev]"

# 运行所有测试（121 个）
python3 -m pytest tests/

# 运行单个测试文件或类
python3 -m pytest tests/test_parser.py::TestParserBasic -v

# 运行并生成覆盖率报告
python3 -m pytest tests/ --cov=poker_advisor --cov-report=html

# CLI（入口：cli/main.py）
python3 -m cli.main import-log <日志文件>
python3 -m cli.main stats [--by-position] [--session ID] [--position BTN]
python3 -m cli.main leaks [--session ID]
python3 -m cli.main hands [--limit N]
python3 -m cli.main review-hand <id> [--ai] [--deep]
python3 -m cli.main analyze [--session ID] [--deep]
python3 -m cli.main sessions
python3 -m cli.main train [--count N] [--focus preflop|flop|turn|river|cbet]
python3 -m cli.main progress

# Web UI
streamlit run web/app.py
```

## 环境变量

- `DOUBAO_API_KEY` — AI 分析/训练功能必需（`analyze`、`review-hand --ai`、`train`）
- `DOUBAO_API_ENDPOINT` — Doubao API 端点（默认：`https://ark.cn-beijing.volces.com/api/v3`）
- `POKER_AI_PROVIDER` — AI 提供商，`doubao`（默认）或 `deepseek`
- `POKER_AI_MODEL` — 用于分析的模型（默认：`doubao-seed-2-0-lite`）
- `POKER_AI_DEEP_MODEL` — 深度分析模型（默认：`doubao-seed-2-0-pro`）
- `POKER_DB_PATH` — SQLite 数据库路径（默认：`poker_advisor.db`）

配置加载位于 `src/poker_advisor/config.py`。

## 架构

**数据流：** Poker Now 日志文件 → 解析器 → `List[HandRecord]` → 仓储层 → SQLite → 分析引擎 → AI 顾问 → CLI/Web 输出

### 核心层（均位于 `src/poker_advisor/` 下）

- **models/** — 纯数据类和枚举。`HandRecord` 是贯穿每一层的核心数据结构。`PlayerStats`/`PositionalStats` 存储计算指标（VPIP、PFR、AF、3-Bet%、C-Bet%、WTSD、W$SD）。
- **parser/** — `PokerNowParser` 将 Poker Now 日志转换为 `HandRecord` 对象。支持两种格式：旧版纯文本（`"Player" @ seat #N`）和新版 CSV（`entry,at,order` 三列，`"Name @ ID"` 标识）。所有正则表达式模式集中在 `patterns.py` 中。支持多种花色表示（Ah、A♥、"A of Hearts"）和 10/T 两种十点表示。解析器在处理前会反转日志行（Poker Now 输出为最新优先）。
- **storage/** — `Database` 管理 SQLite 连接，使用上下文管理器事务，并从 `schema.sql` 自动初始化表结构。`HandRepository` 提供基于会话组织的 CRUD 操作。数据库包含 7 张表：hands、players、actions、shown_cards、winners、sessions、training_results。
- **analysis/** — `StatsCalculator` 从 `List[HandRecord]` 计算所有指标（整体 + 按位置跟踪）。`PositionalAnalyzer` 按前位/中位/后位/盲注分组统计。`LeakDetector` 将指标与 GTO 基线对比，分 3 个严重级别；每个指标设有最小样本量要求以避免噪声。漏洞描述为中文。
- **ai/** — `ClaudeClient` 封装 AI API（OpenAI 兼容接口，使用 `requests` 直接调用），通过 `POKER_AI_PROVIDER` 环境变量切换 Doubao/DeepSeek。`StrategyAnalyzer` 编排完整分析流程（统计 + 漏洞 + 位置 → 提示词）及单手牌复盘。`TrainingCoach` 评估训练决策并解析结构化响应。所有提示词模板在 `prompts.py` 中。内置重试逻辑（超时 60s，最多 2 次重试）。
- **formatters/** — `TextFormatter` 用于纯文本输出。`TableFormatter` 用于 Rich 表格/面板（统计、位置分析、漏洞、手牌列表、会话、训练进度）。
- **training/** — `ScenarioGenerator` 从真实手牌中提取决策点，分类为 10+ 种场景类型（preflop_open、flop_cbet_decision、river_facing_bet 等）。根据漏洞优先排列场景，轮询选择保证多样性。`TrainingSession` 编排完整训练流程（准备场景 → AI 评估 → 保存结果）。

### CLI 层（`cli/main.py`）

基于 Typer 的应用，包含 9 个命令。所有模块延迟导入以加快启动速度。`_require_api_key()` 在 AI 命令执行前验证 API 密钥（根据当前 provider 检查对应的环境变量）。

### Web 层（`web/`）

基于 Streamlit 的多页应用。首页提供功能导航和日志导入。5 个子页面：统计分析（含 Plotly 雷达图）、漏洞检测、AI 分析（全局 + 单手牌复盘）、交互式训练、手牌历史浏览。

### 关键设计决策

- `models/position.py` 中的位置分配算法支持 2–10 人桌，包含单挑特殊逻辑。
- 英雄识别通过匹配 "Your hand" 行和亮牌记录实现。
- 数据库使用 `session_id`（8 字符 UUID 前缀）按文件分组导入的手牌。
- 大盲位过牌（CALL 金额为 $0）不计入 VPIP 统计。
- 漏洞检测器对每个指标设有最小样本量要求（整体 30 手，位置组 15 手，另有 3-bet/cbet/wtsd 等指标的专项最小样本量）。
- 新版 CSV 格式中，action 行不含 seat 号，解析器通过 stacks 行构建 `name_to_seat` 映射来关联座位。
- 新版 CSV 格式中，亮牌行出现在 `-- ending hand --` 之后，解析器使用 `pending_show_lines` 将其关联回已完成的手牌。

## 测试

- `tests/test_parser.py` — 解析器测试（51 个，含旧格式 26 个 + 新 CSV 格式 25 个）
- `tests/test_calculator.py` — 统计计算器测试（25 个）
- `tests/test_leak_detector.py` — 漏洞检测器测试（16 个）
- `tests/test_training.py` — 训练模块测试（17 个）
- `tests/test_integration.py` — 端到端集成测试（12 个）

测试夹具位于 `tests/fixtures/`：`sample_log.txt`（旧格式）和 `sample_log_csv.csv`（新 CSV 格式），各含 3 手牌。添加新功能时，请扩展这些夹具或在同一目录下创建新的夹具文件。
