"""AI-powered strategy analysis using Claude."""

from typing import List, Optional
import threading

from poker_advisor.models.hand import HandRecord
from poker_advisor.models.stats import PlayerStats
from poker_advisor.analysis.calculator import StatsCalculator
from poker_advisor.analysis.leak_detector import LeakDetector, Leak
from poker_advisor.analysis.positional import PositionalAnalyzer
from poker_advisor.formatters.text import TextFormatter
from poker_advisor.ai.client import ClaudeClient
from poker_advisor.ai.prompts import (
    STRATEGY_ANALYST_SYSTEM,
    SKILL_SYSTEM_PROMPT,
    SkillManager,
    build_analysis_prompt,
    build_hand_review_prompt,
    build_quick_classification_prompt,
    build_deep_leak_analysis_prompt,
)
from poker_advisor import config


class StrategyAnalyzer:
    """AI strategy analyzer that combines stats with Claude analysis."""

    def __init__(self, client: Optional[ClaudeClient] = None):
        self.client = client or ClaudeClient()
        self.calculator = StatsCalculator()
        self.leak_detector = LeakDetector()
        self.positional = PositionalAnalyzer()
        self.formatter = TextFormatter()
        self.skill_manager = SkillManager()
        self._db_lock = threading.Lock()

    def _call_api(self, prompt: str, system_prompt: str,
                  max_tokens: int = 4096, deep: bool = False,
                  skill_name: str = "default") -> str:
        """Unified API call logic for both standard and deep analysis."""
        # Inject few-shot examples only for cache miss
        examples = self.skill_manager.get_few_shot_examples(skill_name)
        if examples:
            prompt = f"{examples}\n\n---\n\n{prompt}"

        if deep:
            from poker_advisor.ai.client import ClaudeClient
            client = ClaudeClient(
                api_key=config.DOUBAO_CODE_API_KEY,
                model=config.DEEP_ANALYSIS_MODEL,
                endpoint=config.DOUBAO_CODE_API_ENDPOINT
            )
            return client.ask(
                prompt=prompt,
                system=system_prompt,
                model=config.DEEP_ANALYSIS_MODEL,
            )
        else:
            model = config.DEEP_ANALYSIS_MODEL if deep else None
            return self.client.ask(
                prompt=prompt,
                system=system_prompt,
                model=model,
            )

    def _compute_hand_context(self, hand: HandRecord) -> dict:
        """Compute hand context including effective stack, SPR, and pot odds for each street."""
        context = {
            "effective_stack": min([stack for stack in hand.stacks.values()]) if hand.stacks else 0,
            "flop_spr": 0,
            "turn_spr": 0,
            "river_spr": 0,
            "street_odds": {},
        }

        # Calculate SPR for each street
        pot_after_flop = hand.pot_total  # Simplified
        if hand.flop:
            context["flop_spr"] = context["effective_stack"] / pot_after_flop if pot_after_flop > 0 else 0
        if hand.turn:
            context["turn_spr"] = context["effective_stack"] / (pot_after_flop * 2) if pot_after_flop > 0 else 0
        if hand.river:
            context["river_spr"] = context["effective_stack"] / (pot_after_flop * 3) if pot_after_flop > 0 else 0

        return context

    def _build_baseline_comparison(self, stats: PlayerStats) -> str:
        """Build GTO baseline comparison table from config/baselines.json."""
        from poker_advisor.analysis.leak_detector import GTO_BASELINES

        lines = []
        lines.append("| 指标 | 玩家值 | GTO范围 | 偏差 |")
        lines.append("|------|--------|---------|------|")

        overall_baseline = GTO_BASELINES.get("overall", {})
        for metric in ["vpip", "pfr", "three_bet_pct", "af", "cbet_pct", "fold_to_cbet", "wtsd", "wsd", "wwsf"]:
            if metric in overall_baseline:
                player_val = getattr(stats.overall, metric, 0)
                baseline_min, baseline_max = overall_baseline[metric]
                deviation = abs(player_val - (baseline_min + baseline_max) / 2)
                lines.append(f"| {metric.upper()} | {player_val:.1f}% | {baseline_min}-{baseline_max}% | {deviation:.1f}pp |")

        return "\n".join(lines)

    def _build_sample_warnings(self, stats: PlayerStats) -> str:
        """Build sample size warning text for positions with < 30 hands."""
        warnings = []
        for pos, pos_stats in stats.by_position.items():
            if pos_stats.total_hands < 30:
                warnings.append(f"⚠️ {pos}位置样本量不足：{pos_stats.total_hands}手（建议≥30手）")
        return "\n".join(warnings) if warnings else ""

    def analyze_full(self, hands: List[HandRecord],
                     deep: bool = False) -> str:
        """Run full strategy analysis on a set of hands.

        Args:
            hands: List of hand records to analyze.
            deep: Use the deep analysis model (Opus) for more thorough analysis.

        Returns:
            Claude's analysis as markdown text.
        """
        stats = self.calculator.calculate(hands)
        leaks = self.leak_detector.detect(stats)

        stats_text = self.formatter.format_stats_summary(stats)
        leaks_text = self.formatter.format_leaks(leaks)

        # Build positional summary
        pos_rows = self.positional.position_summary(stats)
        position_text = ""
        if pos_rows:
            lines = []
            for row in pos_rows:
                lines.append(
                    f"  {row['position']:6s}  "
                    f"Hands={row['hands']:3d}  "
                    f"VPIP={row['vpip']:5.1f}%  "
                    f"PFR={row['pfr']:5.1f}%  "
                    f"3Bet={row['3bet']:5.1f}%  "
                    f"AF={row['af']:5.2f}  "
                    f"CBet={row['cbet']:5.1f}%"
                )
            position_text = "\n".join(lines)

        # Step 1: Quick classification (max tokens: 1024)
        quick_prompt = build_quick_classification_prompt(stats_text, leaks_text)
        quick_result = self._call_api(quick_prompt, SKILL_SYSTEM_PROMPT,
                                      max_tokens=1024, deep=deep,
                                      skill_name="strategy_quick")

        # Step 2: Deep leak analysis (max tokens: 4096)
        deep_prompt = build_deep_leak_analysis_prompt(stats_text, leaks_text,
                                                      quick_result, quick_result)
        deep_result = self._call_api(deep_prompt, SKILL_SYSTEM_PROMPT,
                                     max_tokens=4096, deep=deep,
                                     skill_name="strategy_deep")

        return f"# 策略分析报告\n\n## 快速分析\n{quick_result}\n\n---\n\n## 深度分析\n{deep_result}"

    def review_hand(self, hand: HandRecord,
                    hands: Optional[List[HandRecord]] = None,
                    deep: bool = False,
                    use_cache: bool = True,
                    repo=None) -> str:
        """Get AI analysis of a specific hand.

        Args:
            hand: The hand to review.
            hands: Optional full hand history for context stats.
            deep: Use deep analysis model.
            use_cache: Use cached analysis if available
            repo: HandRepository for caching (required if use_cache=True)

        Returns:
            Claude's hand review as markdown text.
        """
        # Check cache first if repo provided
        if use_cache and repo and hand.session_id:
            cached = repo.get_cached_analysis(
                hand.hand_id, hand.session_id, "single_hand"
            )
            if cached:
                return cached["ai_explanation"]

        hand_text = self.formatter.format_hand(hand)

        stats_text = ""
        spr_info = ""
        pot_odds_info = ""
        leak_correlation = ""

        if hands:
            stats = self.calculator.calculate(hands)
            stats_text = self.formatter.format_stats_summary(stats)

        # Compute hand context
        context = self._compute_hand_context(hand)
        spr_info = f"有效筹码: ${context['effective_stack']:.2f}\n翻牌SPR: {context['flop_spr']:.2f}\n转牌SPR: {context['turn_spr']:.2f}\n河牌SPR: {context['river_spr']:.2f}"

        prompt = build_hand_review_prompt(hand_text, stats_text,
                                          spr_info, pot_odds_info,
                                          leak_correlation)

        result = self._call_api(prompt, SKILL_SYSTEM_PROMPT,
                               max_tokens=4096, deep=deep,
                               skill_name="hand_review")

        # Save to cache if repo provided
        if use_cache and repo and hand.session_id:
            # Rough estimate of EV loss from pot
            est_ev_loss = hand.pot_total * (0.5 if not hand.hero_won else 0)
            repo.save_analysis_result(
                hand_id=hand.hand_id,
                session_id=hand.session_id,
                analysis_type="single_hand",
                ai_explanation=result,
                ev_loss=est_ev_loss
            )

        return result
