"""Statistics models for player analysis."""

from dataclasses import dataclass, field
from typing import Dict, Optional

from poker_advisor.models.position import Position


@dataclass
class PositionalStats:
    """Stats for a specific position."""
    position: Optional[Position] = None

    total_hands: int = 0
    voluntarily_put_in_pot: int = 0
    preflop_raise: int = 0

    # 3-bet
    three_bet_opportunities: int = 0
    three_bet_made: int = 0

    # Aggression
    bets: int = 0
    raises: int = 0
    calls: int = 0
    folds: int = 0

    # C-Bet
    cbet_opportunities: int = 0
    cbet_made: int = 0
    faced_cbet: int = 0
    folded_to_cbet: int = 0

    # Showdown
    saw_flop: int = 0
    went_to_showdown: int = 0
    won_at_showdown: int = 0
    won_without_showdown: int = 0  # Won when opponent folded before showdown

    # Money
    total_won: float = 0.0
    total_invested: float = 0.0

    @property
    def vpip(self) -> float:
        return self.voluntarily_put_in_pot / self.total_hands * 100 if self.total_hands else 0.0

    @property
    def pfr(self) -> float:
        return self.preflop_raise / self.total_hands * 100 if self.total_hands else 0.0

    @property
    def three_bet_pct(self) -> float:
        return self.three_bet_made / self.three_bet_opportunities * 100 if self.three_bet_opportunities else 0.0

    @property
    def aggression_factor(self) -> float:
        return (self.bets + self.raises) / self.calls if self.calls else float('inf') if (self.bets + self.raises) else 0.0

    @property
    def cbet_pct(self) -> float:
        return self.cbet_made / self.cbet_opportunities * 100 if self.cbet_opportunities else 0.0

    @property
    def fold_to_cbet_pct(self) -> float:
        return self.folded_to_cbet / self.faced_cbet * 100 if self.faced_cbet else 0.0

    @property
    def wtsd(self) -> float:
        return self.went_to_showdown / self.saw_flop * 100 if self.saw_flop else 0.0

    @property
    def wsd(self) -> float:
        return self.won_at_showdown / self.went_to_showdown * 100 if self.went_to_showdown else 0.0

    @property
    def wwsf(self) -> float:
        """Won Without Showdown Frequency: % of flops seen that you win without going to showdown."""
        return self.won_without_showdown / self.saw_flop * 100 if self.saw_flop else 0.0

    @property
    def roi(self) -> float:
        """Return on Investment: (total profit / total invested) * 100."""
        if self.total_invested == 0:
            return 0.0
        profit = self.total_won - self.total_invested
        return profit / self.total_invested * 100

    @property
    def bb_per_100(self) -> float:
        return 0.0  # Computed at a higher level with big blind info


@dataclass
class PlayerStats:
    """Aggregate stats for a player across all hands."""
    player_name: str = ""
    overall: PositionalStats = field(default_factory=PositionalStats)
    by_position: Dict[Position, PositionalStats] = field(default_factory=dict)

    # Session info
    total_sessions: int = 0
    total_profit: float = 0.0
    big_blind_size: float = 1.0

    @property
    def bb_per_100(self) -> float:
        if self.overall.total_hands == 0 or self.big_blind_size == 0:
            return 0.0
        return (self.total_profit / self.big_blind_size) / self.overall.total_hands * 100

    def get_position_stats(self, position: Position) -> PositionalStats:
        if position not in self.by_position:
            self.by_position[position] = PositionalStats(position=position)
        return self.by_position[position]

    def summary_dict(self) -> Dict[str, float]:
        return {
            "VPIP": self.overall.vpip,
            "PFR": self.overall.pfr,
            "3-Bet%": self.overall.three_bet_pct,
            "AF": self.overall.aggression_factor,
            "C-Bet%": self.overall.cbet_pct,
            "Fold to C-Bet%": self.overall.fold_to_cbet_pct,
            "WTSD%": self.overall.wtsd,
            "W$SD%": self.overall.wsd,
            "WWSF%": self.overall.wwsf,
            "ROI%": self.overall.roi,
            "BB/100": self.bb_per_100,
            "Hands": self.overall.total_hands,
        }
