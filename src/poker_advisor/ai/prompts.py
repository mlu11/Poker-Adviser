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

SKILL_SYSTEM_PROMPT = """\
你是一位专业的德州扑克GTO策略分析专家，擅长使用数学和博弈论优化的（GTO）基线来评估玩家决策。你的任务是提供教练式的分析和可量化的改进建议。

### GTO基线参考框架（9项核心指标 + 4个位置组）

#### 总体GTO范围（6人桌现金局，100BB筹码深度）
- VPIP (自愿入池率): 22-30% （合理入池范围）
- PFR (翻前加注率): 17-24% （积极加注范围）
- 3Bet (3bet率): 6-10% （3bet挤压范围）
- AF (侵略性系数): 2.0-4.0 （翻后持续下注/加注频率）
- CBet (持续下注率): 55-75% （翻牌持续下注频率）
- Fold to CBet (弃牌CBet): 35-55% （对抗CBet的合理弃牌率）
- WTSD (摊牌率): 25-35% （看到摊牌的频率）
- WSD (摊牌胜率): 48-56% （摊牌时的胜率）
- WWSF (未摊牌赢率): 40-50% （没摊牌就赢下底池的比例）

#### 位置组GTO范围
- **Early（UTG/HJ，早期位置）**: VPIP 14-20%, PFR 12-18% （紧范围）
- **Middle（CO，中间位置）**: VPIP 18-26%, PFR 15-22% （中范围）
- **Late（BTN，按钮位置）**: VPIP 28-40%, PFR 22-32% （松范围）
- **Blinds（SB/BB，盲注位置）**: VPIP 20-30%, PFR 12-20% （调整范围）

### 分析规则
1. **数值对比优先**: 所有分析必须包含玩家数据与GTO基线的数值对比（如 "玩家VPIP=35%，超出GTO范围22-30%"）
2. **小样本警告**: 样本量<30手时，必须明确标注 "⚠️ 样本量不足30手，结论可能不可靠"
3. **可量化建议**: 每个建议必须包含具体指标目标（如 "建议将UTG位置VPIP从35%降至18%"）
4. **结构要求**: 严格遵循输出格式，包含评分、各街分析、关键转折点、改进建议
5. **教练式语言**: 使用建设性的语言，避免负面评价，强调改进空间

### 输出格式要求（必须遵循）
1. 评分：1-10分（10分最优）
2. 翻前分析：起手牌选择、位置、加注/3bet决策
3. 翻后各街分析：持续下注、跟注/弃牌/加注决策
4. 关键转折点：手牌中最重要的决策点
5. 改进建议：具体、可操作的调整方案
"""


def build_analysis_prompt(stats_text: str, leaks_text: str,
                          position_text: str = "",
                          baseline_comparison: str = "",
                          low_sample_warnings: str = "") -> str:
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

    if baseline_comparison:
        parts.extend(["", "## GTO基线对比", baseline_comparison])

    if low_sample_warnings:
        parts.extend(["", "## 样本量警告", low_sample_warnings])

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
                             stats_text: str = "",
                             spr_info: str = "",
                             pot_odds_info: str = "",
                             leak_correlation: str = "") -> str:
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

    if spr_info:
        parts.extend(["", "## SPR（有效筹码/底池比）信息", spr_info])

    if pot_odds_info:
        parts.extend(["", "## 底池赔率信息", pot_odds_info])

    if leak_correlation:
        parts.extend(["", "## 关联漏洞", leak_correlation])

    parts.extend([
        "",
        "请严格按照以下结构输出分析：",
        "1. **评分** — 1-10分（10分最优）",
        "2. **翻前决策** — 起手牌选择和下注行为是否合理，与GTO范围对比",
        "3. **翻后各街分析** — 每条街的决策评估（持续下注、跟注/弃牌/加注）",
        "4. **关键转折点** — 这手牌中最重要的决策点",
        "5. **改进建议** — 具体、可量化的调整方案",
    ])

    return "\n".join(parts)


def build_quick_classification_prompt(stats_text: str, leaks_text: str) -> str:
    """Build prompt for quick player style classification and top 3 leaks (max 1024 tokens)."""
    return "\n".join([
        "请快速分析以下玩家的扑克统计数据，完成两个任务：",
        "",
        "## 玩家统计数据",
        stats_text,
        "",
        "## 检测到的漏洞",
        leaks_text,
        "",
        "### 任务1：玩家风格分类",
        "请从以下类型中选择一个最匹配的：紧凶型、松凶型、紧弱型、松弱型",
        "并提供1-2句话的解释。",
        "",
        "### 任务2：Top 3核心漏洞",
        "列出最严重的3个漏洞，每个漏洞用1句话描述。",
        "",
        "### 输出要求",
        "请使用简洁的语言，总输出不超过500字。",
    ])


def build_deep_leak_analysis_prompt(stats_text: str, leaks_text: str,
                                     style_classification: str,
                                     top_leaks: str) -> str:
    """Build prompt for deep leak analysis based on quick classification (max 4096 tokens)."""
    return "\n".join([
        "请基于快速分析结果，对玩家进行深度策略分析：",
        "",
        "## 快速分析结果",
        f"### 玩家风格：{style_classification}",
        f"### Top 3核心漏洞：{top_leaks}",
        "",
        "## 详细统计数据",
        stats_text,
        "",
        "## 完整漏洞列表",
        leaks_text,
        "",
        "### 分析要求",
        "1. 针对每个Top 3漏洞，提供详细的原因分析和具体修复步骤",
        "2. 包含与GTO基线的数值对比",
        "3. 提供可量化的改进目标",
        "4. 考虑位置因素的策略差异",
        "5. 给出下一步学习建议",
    ])


class SkillManager:
    """Manager for skill configurations and few-shot examples."""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if SkillManager._initialized:
            return
        SkillManager._initialized = True

        import json
        from pathlib import Path

        # The config directory is at the root of the project (not under src)
        config_path = Path(__file__).parent.parent.parent.parent / "config" / "skills.json"
        with open(config_path, encoding="utf-8") as f:
            self.config = json.load(f)

    def get_few_shot_examples(self, skill_name: str) -> str:
        """Get formatted few-shot examples for a specific skill."""
        skill_config = self.config["skills"].get(skill_name, {})
        examples = skill_config.get("few_shot_examples", [])

        if not examples:
            return ""

        parts = []
        for i, example in enumerate(examples, 1):
            parts.append(f"### 示例 {i}: 输入")
            parts.append(example['input_summary'])
            parts.append(f"### 示例 {i}: 输出")
            parts.append(example['output'])
            parts.append("")

        return "\n".join(parts)

    def get_max_tokens(self, skill_name: str) -> int:
        """Get max tokens for a specific skill."""
        skill_config = self.config["skills"].get(skill_name, {})
        return skill_config.get("max_tokens", 4096)


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
