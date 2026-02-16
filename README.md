# ♠ Poker Advisor

德州扑克策略顾问 — AI 驱动的手牌分析与训练系统。

解析 [Poker Now Club](https://www.pokernow.club/) 手牌历史日志，计算玩家统计数据，检测打法漏洞，并通过 Claude API 提供深度策略分析和交互式训练。

## 功能

- **日志解析** — 导入 Poker Now Club CSV 日志，自动解析手牌、行动、公共牌、摊牌等信息
- **统计分析** — 计算 VPIP、PFR、AF、3-Bet%、C-Bet%、WTSD 等核心指标，支持按位置分组
- **漏洞检测** — 将统计数据与 GTO 基线对比，按严重程度标记漏洞并给出改进建议
- **AI 策略分析** — 使用 Claude 进行全局策略分析和单手牌深度复盘
- **交互式训练** — 从真实手牌中提取决策场景，AI 实时评估你的决策
- **双界面** — Typer CLI + Streamlit Web UI

## 快速开始

```bash
# 安装
pip install -e ".[dev]"

# 设置 API Key（AI 功能需要）
export DOUBAO_API_KEY=sk-...

# 导入日志
python3 -m cli.main import-log your_log.csv

# 查看统计
python3 -m cli.main stats --by-position

# 检测漏洞
python3 -m cli.main leaks

# AI 策略分析
python3 -m cli.main analyze

# 开始训练
python3 -m cli.main train --count 5

# 启动 Web UI
streamlit run web/app.py
```

## CLI 命令

| 命令 | 说明 |
|------|------|
| `import-log <file>` | 导入 Poker Now 日志文件 |
| `sessions` | 列出所有导入会话 |
| `stats` | 查看玩家统计数据 |
| `leaks` | 检测打法漏洞 |
| `hands` | 浏览手牌列表 |
| `review-hand <id>` | 查看手牌详情（`--ai` 启用 AI 复盘） |
| `analyze` | AI 全局策略分析（`--deep` 使用 Opus） |
| `train` | 交互式训练（`--focus` 聚焦领域） |
| `progress` | 查看训练进度 |

## 测试

```bash
python3 -m pytest tests/ -v
```

## 技术栈

- Python 3.10+
- Doubao API（ByteDance，策略分析 + 训练评估）
- SQLite（数据存储）
- Typer + Rich（CLI）
- Streamlit + Plotly（Web UI）
