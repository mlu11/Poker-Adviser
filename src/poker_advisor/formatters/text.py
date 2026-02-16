"""Plain text formatting for terminal output."""

from typing import List, Optional

from poker_advisor.models.hand import HandRecord
from poker_advisor.models.action import Street
from poker_advisor.models.stats import PlayerStats
from poker_advisor.analysis.leak_detector import Leak, Severity


class TextFormatter:
    """Format poker data as plain text for terminal display."""

    def format_hand(self, hand: HandRecord) -> str:
        """Format a single hand for display."""
        lines = []
        lines.append(f"=== Hand #{hand.hand_id} ===")

        if hand.timestamp:
            lines.append(f"Time: {hand.timestamp}")

        lines.append(f"Players: {hand.player_count}  |  "
                     f"Blinds: ${hand.small_blind:.2f}/${hand.big_blind:.2f}  |  "
                     f"Pot: ${hand.pot_total:.2f}")

        # Hero info
        if hand.hero_cards:
            pos_str = f" ({hand.hero_position.value})" if hand.hero_position else ""
            lines.append(f"Hero: {hand.hero_cards_str}{pos_str}")

        # Board
        if hand.board:
            lines.append(f"Board: {hand.board_str}")

        # Actions by street
        for street in hand.streets_seen:
            street_actions = hand.actions_on_street(street)
            non_blind = [a for a in street_actions
                         if street != Street.PREFLOP or a.action_type.value != "post_blind"]
            if non_blind:
                lines.append(f"\n  [{street.value.upper()}]")
                for a in non_blind:
                    lines.append(f"    {a}")

        # Result
        if hand.winners:
            lines.append("")
            for seat, amount in hand.winners.items():
                name = hand.players.get(seat, f"Seat {seat}")
                lines.append(f"  Winner: {name} (${amount:.2f})")

        return "\n".join(lines)

    def format_stats_summary(self, stats: PlayerStats) -> str:
        """Format overall stats as text."""
        lines = []
        lines.append(f"=== Player Stats: {stats.player_name} ===")
        lines.append(f"Hands: {stats.overall.total_hands}")
        lines.append(f"Profit: ${stats.total_profit:+.2f}  "
                     f"({stats.bb_per_100:+.1f} BB/100)")
        lines.append("")

        d = stats.summary_dict()
        lines.append(f"  VPIP:           {d['VPIP']:5.1f}%")
        lines.append(f"  PFR:            {d['PFR']:5.1f}%")
        lines.append(f"  3-Bet%:         {d['3-Bet%']:5.1f}%")
        lines.append(f"  AF:             {d['AF']:5.2f}")
        lines.append(f"  C-Bet%:         {d['C-Bet%']:5.1f}%")
        lines.append(f"  Fold to C-Bet%: {d['Fold to C-Bet%']:5.1f}%")
        lines.append(f"  WTSD%:          {d['WTSD%']:5.1f}%")
        lines.append(f"  W$SD%:          {d['W$SD%']:5.1f}%")

        return "\n".join(lines)

    def format_leaks(self, leaks: List[Leak]) -> str:
        """Format detected leaks as text."""
        if not leaks:
            return "No significant leaks detected. Keep playing solid poker!"

        severity_icons = {
            Severity.MAJOR: "[!!!]",
            Severity.MODERATE: "[!!]",
            Severity.MINOR: "[!]",
        }

        lines = ["=== Leak Analysis ===", ""]
        for i, leak in enumerate(leaks, 1):
            icon = severity_icons[leak.severity]
            lines.append(f"{i}. {icon} {leak.description}")
            lines.append(f"   Value: {leak.actual_value:.1f}  "
                         f"(baseline: {leak.baseline_low:.1f}-{leak.baseline_high:.1f})")
            lines.append(f"   Severity: {leak.severity.value}")
            if leak.advice:
                lines.append(f"   Advice: {leak.advice}")
            lines.append("")

        return "\n".join(lines)
