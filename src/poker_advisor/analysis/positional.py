"""Positional analysis — break down stats by position category."""

from dataclasses import dataclass, field
from typing import Dict, List

from poker_advisor.models.position import Position
from poker_advisor.models.stats import PlayerStats, PositionalStats


@dataclass
class PositionGroupStats:
    """Aggregated stats for a position group (Early/Middle/Late/Blinds)."""
    group_name: str
    positions: List[Position] = field(default_factory=list)
    stats: PositionalStats = field(default_factory=PositionalStats)


class PositionalAnalyzer:
    """Analyze player stats broken down by position groups."""

    GROUPS = {
        "Early": [Position.UTG, Position.UTG1],
        "Middle": [Position.MP, Position.MP1, Position.HJ],
        "Late": [Position.CO, Position.BTN],
        "Blinds": [Position.SB, Position.BB],
    }

    def analyze(self, player_stats: PlayerStats) -> Dict[str, PositionGroupStats]:
        """Create position group summaries from player stats.

        Returns dict mapping group name to aggregated stats.
        """
        result = {}
        for group_name, positions in self.GROUPS.items():
            group = PositionGroupStats(group_name=group_name, positions=positions)
            agg = group.stats
            for pos in positions:
                if pos in player_stats.by_position:
                    ps = player_stats.by_position[pos]
                    self._merge_stats(agg, ps)
            result[group_name] = group
        return result

    def position_summary(self, player_stats: PlayerStats) -> List[Dict]:
        """Generate a summary table of stats per individual position.

        Returns a list of dicts suitable for tabular display.
        """
        rows = []
        position_order = [
            Position.UTG, Position.UTG1, Position.MP, Position.MP1,
            Position.HJ, Position.CO, Position.BTN, Position.SB, Position.BB,
        ]
        for pos in position_order:
            if pos not in player_stats.by_position:
                continue
            ps = player_stats.by_position[pos]
            if ps.total_hands == 0:
                continue
            rows.append({
                "position": pos.value,
                "hands": ps.total_hands,
                "vpip": round(ps.vpip, 1),
                "pfr": round(ps.pfr, 1),
                "3bet": round(ps.three_bet_pct, 1),
                "af": round(ps.aggression_factor, 2),
                "cbet": round(ps.cbet_pct, 1),
                "fold_to_cbet": round(ps.fold_to_cbet_pct, 1),
                "wtsd": round(ps.wtsd, 1),
            })
        return rows

    def group_summary(self, player_stats: PlayerStats) -> List[Dict]:
        """Generate a summary table of stats per position group."""
        groups = self.analyze(player_stats)
        rows = []
        for group_name in ["Early", "Middle", "Late", "Blinds"]:
            g = groups[group_name]
            s = g.stats
            if s.total_hands == 0:
                continue
            rows.append({
                "group": group_name,
                "hands": s.total_hands,
                "vpip": round(s.vpip, 1),
                "pfr": round(s.pfr, 1),
                "3bet": round(s.three_bet_pct, 1),
                "af": round(s.aggression_factor, 2),
                "cbet": round(s.cbet_pct, 1),
                "fold_to_cbet": round(s.fold_to_cbet_pct, 1),
                "wtsd": round(s.wtsd, 1),
            })
        return rows

    def _merge_stats(self, target: PositionalStats,
                     source: PositionalStats) -> None:
        """Merge source stats into target (additive)."""
        target.total_hands += source.total_hands
        target.voluntarily_put_in_pot += source.voluntarily_put_in_pot
        target.preflop_raise += source.preflop_raise
        target.three_bet_opportunities += source.three_bet_opportunities
        target.three_bet_made += source.three_bet_made
        target.bets += source.bets
        target.raises += source.raises
        target.calls += source.calls
        target.folds += source.folds
        target.cbet_opportunities += source.cbet_opportunities
        target.cbet_made += source.cbet_made
        target.faced_cbet += source.faced_cbet
        target.folded_to_cbet += source.folded_to_cbet
        target.saw_flop += source.saw_flop
        target.went_to_showdown += source.went_to_showdown
        target.won_at_showdown += source.won_at_showdown
        target.total_won += source.total_won
        target.total_invested += source.total_invested
