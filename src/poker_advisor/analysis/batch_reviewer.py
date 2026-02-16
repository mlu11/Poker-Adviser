"""Batch Reviewer - Analyze multiple hands, filter top EV loss hands, generate batch report.

Uses analysis result caching to avoid repeated API calls.
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from poker_advisor.models.hand import HandRecord
from poker_advisor.models.stats import PlayerStats, PositionalStats
from poker_advisor.analysis.calculator import StatsCalculator
from poker_advisor.analysis.leak_detector import LeakDetector, Leak
from poker_advisor.ai.analyzer import StrategyAnalyzer
from poker_advisor.storage.repository import HandRepository
from poker_advisor import config


@dataclass
class BatchReviewResult:
    """Result from batch review."""
    total_hands: int
    analyzed_hands: int
    cached_hits: int
    top_leaks: List[Leak]
    top_ev_loss_hands: List[Tuple[HandRecord, float]]
    ai_analyses: Dict[int, str]  # hand_id -> analysis text
    overall_summary: str


class BatchReviewer:
    """Batch review processor with caching."""

    def __init__(self, repo: HandRepository, analyzer: StrategyAnalyzer):
        self.repo = repo
        self.analyzer = analyzer
        self.calc = StatsCalculator()
        self.leak_detector = LeakDetector()

    def review_top_ev_loss(
        self,
        hands: List[HandRecord],
        top_n: int = 10,
        deep_ai: bool = True,
        use_cache: bool = True,
        session_id: str = ""
    ) -> BatchReviewResult:
        """
        1. Calculate EV loss per hand (simplified: based on pot size and hero position)
        2. Sort by estimated EV loss descending
        3. Take top N hands for AI analysis
        4. Use cache when available
        5. Return consolidated report

        Args:
            hands: List of hands to review
            top_n: Number of top EV loss hands to analyze with AI
            deep_ai: Use deep analysis model
            use_cache: Use cached analysis results

        Returns:
            BatchReviewResult with all analysis data
        """
        from poker_advisor.ai.client import ClaudeClient

        total_hands = len(hands)
        cached_hits = 0
        ai_analyses: Dict[int, str] = {}

        # Calculate overall stats and leaks
        overall_stats = self.calc.calculate(hands)
        all_leaks = self.leak_detector.detect(overall_stats)
        # Sort leaks by EV loss descending
        sorted_leaks = sorted(all_leaks, key=lambda l: -l.ev_loss_bb100)

        # Estimate EV loss for each hand (heuristic)
        hand_ev_estimates: List[Tuple[HandRecord, float]] = []
        for hand in hands:
            # Heuristic EV loss estimation:
            # - If hero lost and went to showdown with weak range, higher loss
            # - Larger pot = higher EV swing
            # - Hero is out of position = higher potential mistake
            estimated_loss = self._estimate_hand_ev_loss(hand, overall_stats)
            hand_ev_estimates.append((hand, estimated_loss))

        # Sort by estimated EV loss descending, take top N
        sorted_hands = sorted(hand_ev_estimates, key=lambda x: -x[1])
        top_hands = sorted_hands[:top_n]

        # Analyze each top hand with caching
        for hand, est_loss in top_hands:
            # Check cache first
            if use_cache:
                cached = self.repo.get_cached_analysis(
                    hand.hand_id, session_id, "single_hand"
                )
                if cached:
                    ai_analyses[hand.hand_id] = cached["ai_explanation"]
                    cached_hits += 1
                    continue

            # No cache, run analysis
            analysis = self.analyzer.review_hand(hand, hands, deep=deep_ai, use_cache=use_cache, repo=self.repo)
            ai_analyses[hand.hand_id] = analysis

            # Save to cache
            self.repo.save_analysis_result(
                hand_id=hand.hand_id,
                session_id=session_id,
                analysis_type="single_hand",
                ai_explanation=analysis,
                ev_loss=est_loss,
                error_grade=self._grade_error(est_loss)
            )

        # Generate overall summary
        overall_summary = self._generate_summary(
            total_hands, len(top_hands), cached_hits, sorted_leaks
        )

        return BatchReviewResult(
            total_hands=total_hands,
            analyzed_hands=len(top_hands),
            cached_hits=cached_hits,
            top_leaks=sorted_leaks[:5],  # Top 5 leaks
            top_ev_loss_hands=top_hands,
            ai_analyses=ai_analyses,
            overall_summary=overall_summary
        )

    def _estimate_hand_ev_loss(self, hand: HandRecord, overall_stats: PlayerStats) -> float:
        """Heuristic estimation of EV loss for a single hand."""
        # Base estimation
        loss = 0.0

        # Hero lost this hand - higher potential mistake
        if not hand.hero_won:
            loss += hand.pot_total * 0.5

        # Went to showdown - if overall WTSD is very high, likely mistake
        if hand.went_to_showdown and overall_stats.overall.wtsd > 50:
            loss += hand.pot_total * 0.3

        # Larger pot = bigger impact
        loss += hand.pot_total * 0.2

        # Out of position (early position) - bigger mistakes cost more
        if hand.hero_position and hand.hero_position.value in ["utg", "hj"]:
            loss *= 1.2

        return loss

    def _grade_error(self, ev_loss: float) -> str:
        """Grade error based on estimated EV loss."""
        if ev_loss > 5:
            return "S"
        elif ev_loss > 3:
            return "A"
        elif ev_loss > 1:
            return "B"
        else:
            return "C"

    def _generate_summary(
        self,
        total_hands: int,
        analyzed_hands: int,
        cached_hits: int,
        top_leaks: List[Leak]
    ) -> str:
        """Generate overall batch review summary text."""
        lines = []
        lines.append(f"# Batch Review Summary")
        lines.append("")
        lines.append(f"- Total hands in batch: **{total_hands}**")
        lines.append(f"- Top EV loss hands selected for AI analysis: **{analyzed_hands}**")
        lines.append(f"- Cached analysis hits: **{cached_hits}** ({cached_hits/analyzed_hands*100:.0f}%)")
        lines.append("")

        if top_leaks:
            lines.append("## Top 5 Overall Leaks (by EV loss)")
            lines.append("")
            for i, leak in enumerate(top_leaks, 1):
                severity_icon = {
                    "S": "🔥", "A": "🔴", "B": "🟡", "C": "🟢"
                }.get(leak.severity.value, "●")
                lines.append(
                    f"{i}. {severity_icon} **{leak.description}**  \n"
                    f"  - Value: {leak.actual_value:.1f}%  \n"
                    f"  - EV Loss: {leak.ev_loss_bb100:.2f} BB/100  \n"
                    f"  - Advice: {leak.advice}"
                )
                lines.append("")

        lines.append("---")
        lines.append("*Generated by PokerMaster Pro Batch Reviewer*")

        return "\n".join(lines)

    def format_report(self, result: BatchReviewResult) -> str:
        """Format batch review result as markdown report."""
        lines = [result.overall_summary, ""]
        lines.append("## Top EV Loss Hands - Detailed AI Analysis")
        lines.append("")

        for i, (hand, est_loss) in enumerate(result.top_ev_loss_hands, 1):
            analysis = result.ai_analyses.get(hand.hand_id, "*No analysis available*")
            lines.append(f"---")
            lines.append(f"### Hand #{hand.hand_id}  |  Est. EV Loss: ${est_loss:.2f}")
            lines.append("")
            lines.append(f"**Board:** {hand.board_str}  \n")
            lines.append(f"**Hero hand:** {hand.hero_cards_str}  \n")
            lines.append(f"**Pot:** ${hand.pot_total:.2f}")
            lines.append("")
            lines.append("#### AI Analysis:")
            lines.append("")
            lines.append(analysis)
            lines.append("")

        return "\n".join(lines)
