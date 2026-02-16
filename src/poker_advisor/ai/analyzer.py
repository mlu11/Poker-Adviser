"""AI-powered strategy analysis using Claude."""

from typing import List, Optional

from poker_advisor.models.hand import HandRecord
from poker_advisor.models.stats import PlayerStats
from poker_advisor.analysis.calculator import StatsCalculator
from poker_advisor.analysis.leak_detector import LeakDetector, Leak
from poker_advisor.analysis.positional import PositionalAnalyzer
from poker_advisor.formatters.text import TextFormatter
from poker_advisor.ai.client import ClaudeClient
from poker_advisor.ai.prompts import (
    STRATEGY_ANALYST_SYSTEM,
    build_analysis_prompt,
    build_hand_review_prompt,
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

        prompt = build_analysis_prompt(stats_text, leaks_text, position_text)
        model = config.DEEP_ANALYSIS_MODEL if deep else None

        return self.client.ask(
            prompt=prompt,
            system=STRATEGY_ANALYST_SYSTEM,
            model=model,
        )

    def review_hand(self, hand: HandRecord,
                    hands: Optional[List[HandRecord]] = None,
                    deep: bool = False) -> str:
        """Get AI analysis of a specific hand.

        Args:
            hand: The hand to review.
            hands: Optional full hand history for context stats.
            deep: Use deep analysis model.

        Returns:
            Claude's hand review as markdown text.
        """
        hand_text = self.formatter.format_hand(hand)

        stats_text = ""
        if hands:
            stats = self.calculator.calculate(hands)
            stats_text = self.formatter.format_stats_summary(stats)

        prompt = build_hand_review_prompt(hand_text, stats_text)
        model = config.DEEP_ANALYSIS_MODEL if deep else None

        return self.client.ask(
            prompt=prompt,
            system=STRATEGY_ANALYST_SYSTEM,
            model=model,
        )
