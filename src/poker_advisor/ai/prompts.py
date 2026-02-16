"""Prompt templates for Claude API interactions."""

STRATEGY_ANALYST_SYSTEM = """\
你是一位专业的德州扑克策略分析师。你的任务是分析玩家的统计数据和检测到的漏洞，\
提供深入、可操作的策略建议。

规则：
- 用中文回答
- 基于具体数据给出建议，不要泛泛而谈
- 对每个漏洞给出具体的修复步骤
- 考虑不同位置的策略差异
- 如果数据量不足，明确指出哪些结论可能不够可靠
- 使用 Markdown 格式组织回答
"""

TRAINING_COACH_SYSTEM = """\
你是一位德州扑克训练教练。你的任务是评估玩家在特定场景下的决策，\
并提供详细的教学反馈。

规则：
- 用中文回答
- 给出 1-10 分的评分（10 分为最优）
- 解释最优打法及其理由
- 讨论该场景下的范围分析
- 考虑筹码深度、位置、对手倾向等因素
- 如果玩家的决策合理但不是最优，也要肯定其合理性
- 使用 Markdown 格式组织回答

回答格式：
## 评分：X/10

## 分析
（你的分析）

## 最优打法
（最优打法及理由）

## 关键要点
（学习要点总结）
"""


def build_analysis_prompt(stats_text: str, leaks_text: str,
                          position_text: str = "") -> str:
    """Build the prompt for full strategy analysis."""
    parts = [
        "请分析以下玩家的扑克统计数据，提供深度策略分析报告。",
        "",
        "## 玩家统计数据",
        stats_text,
    ]

    if position_text:
        parts.extend(["", "## 位置统计", position_text])

    if leaks_text:
        parts.extend(["", "## 检测到的漏洞", leaks_text])

    parts.extend([
        "",
        "请按以下结构输出分析报告：",
        "1. **玩家风格评估** — 根据数据判断玩家类型（紧凶/松凶/紧弱/松弱等）",
        "2. **核心漏洞分析（Top 3）** — 详细分析最严重的漏洞，每个漏洞给出具体修复步骤",
        "3. **优势保持** — 玩家做得好的方面，如何继续保持",
        "4. **学习计划** — 按优先级排列的具体提升建议",
    ])

    return "\n".join(parts)


def build_hand_review_prompt(hand_text: str,
                             stats_text: str = "") -> str:
    """Build the prompt for single hand review."""
    parts = [
        "请分析以下这手牌，评估英雄（Hero）在每条街的决策。",
        "",
        "## 手牌记录",
        hand_text,
    ]

    if stats_text:
        parts.extend([
            "",
            "## 玩家整体统计（参考）",
            stats_text,
        ])

    parts.extend([
        "",
        "请分析：",
        "1. **翻前决策** — 起手牌选择和下注行为是否合理",
        "2. **翻后各街分析** — 每条街的决策评估",
        "3. **关键转折点** — 这手牌中最重要的决策点",
        "4. **改进建议** — 如何在类似场景中做出更好的决策",
    ])

    return "\n".join(parts)


def build_training_eval_prompt(scenario_text: str, user_action: str,
                               user_reasoning: str = "") -> str:
    """Build the prompt for evaluating a training decision."""
    parts = [
        "玩家正在进行训练，请评估他们在以下场景中的决策。",
        "",
        "## 场景",
        scenario_text,
        "",
        f"## 玩家决策：{user_action}",
    ]

    if user_reasoning:
        parts.extend([f"玩家理由：{user_reasoning}"])

    parts.extend([
        "",
        "请按照规定格式（评分/分析/最优打法/关键要点）给出评估。",
        "评分标准：",
        "- 10分：最优或接近最优的决策",
        "- 7-9分：合理的决策，但有更好的选择",
        "- 4-6分：可以理解但有明显问题",
        "- 1-3分：严重错误的决策",
    ])

    return "\n".join(parts)
