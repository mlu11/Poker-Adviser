"""Pot management for poker simulation."""

from dataclasses import dataclass, field
from typing import Dict, List, Set


@dataclass
class SidePot:
    """A side pot in the game."""
    amount: float = 0.0
    eligible_seats: Set[int] = field(default_factory=set)


class PotManager:
    """Manages the main pot and side pots."""

    def __init__(self):
        """Initialize an empty pot manager."""
        self.main_pot: float = 0.0
        self.side_pots: List[SidePot] = []
        # Track bets per player for current street
        self.current_bets: Dict[int, float] = {}
        # Track total invested per player
        self.total_invested: Dict[int, float] = {}

    def add_bet(self, seat: int, amount: float):
        """Add a bet from a player.

        Args:
            seat: The player's seat number.
            amount: The amount to add to the pot.
        """
        self.current_bets[seat] = self.current_bets.get(seat, 0.0) + amount
        self.total_invested[seat] = self.total_invested.get(seat, 0.0) + amount
        self.main_pot += amount

    def get_player_bet(self, seat: int) -> float:
        """Get the current bet amount for a player in this street.

        Args:
            seat: The player's seat number.

        Returns:
            The current bet amount.
        """
        return self.current_bets.get(seat, 0.0)

    def get_total_invested(self, seat: int) -> float:
        """Get the total amount a player has invested in the hand.

        Args:
            seat: The player's seat number.

        Returns:
            The total invested amount.
        """
        return self.total_invested.get(seat, 0.0)

    def reset_street(self):
        """Reset current bets for a new street."""
        self.current_bets.clear()

    def reset_hand(self):
        """Reset everything for a new hand."""
        self.main_pot = 0.0
        self.side_pots.clear()
        self.current_bets.clear()
        self.total_invested.clear()

    @property
    def total_pot(self) -> float:
        """Get the total pot amount including all side pots."""
        total = self.main_pot
        for pot in self.side_pots:
            total += pot.amount
        return total

    def calculate_side_pots(self, all_in_seats: Set[int], folded_seats: Set[int],
                             active_seats: Set[int]):
        """Calculate side pots based on all-in players.

        Args:
            all_in_seats: Set of seats that are all-in.
            folded_seats: Set of seats that have folded.
            active_seats: Set of seats that are still active.
        """
        # This is a simplified side pot calculation
        # For a full implementation, we'd need to track each bet level
        pass

    def get_winners(self, hand_strengths: Dict[int, int]) -> Dict[int, float]:
        """Calculate pot distribution based on hand strengths.

        Args:
            hand_strengths: Mapping from seat to hand strength (higher is better).

        Returns:
            Mapping from seat to amount won.
        """
        # Simple implementation - just split main pot among best hand(s)
        if not hand_strengths:
            return {}

        best_strength = max(hand_strengths.values())
        winners = [seat for seat, strength in hand_strengths.items()
                   if strength == best_strength]

        if not winners:
            return {}

        split_amount = self.total_pot / len(winners)
        return {seat: split_amount for seat in winners}

    def return_uncalled_bets(self, last_aggressor_seat: int,
                             active_seats: Set[int]) -> Dict[int, float]:
        """Return uncalled bets to the last aggressor.

        Args:
            last_aggressor_seat: The seat of the last aggressor.
            active_seats: Set of active (not folded) seats.

        Returns:
            Mapping from seat to amount returned.
        """
        returns: Dict[int, float] = {}

        if not active_seats or len(active_seats) < 2:
            return returns

        # Find the highest bet
        bets = {seat: self.current_bets.get(seat, 0.0) for seat in active_seats}
        if not bets:
            return returns

        max_bet = max(bets.values())
        min_bet = min(bets.values())

        # If only one player made the max bet and others called less,
        # return the difference
        if max_bet > min_bet:
            # Count how many players made the max bet
            max_bettors = [seat for seat, bet in bets.items() if bet == max_bet]
            if len(max_bettors) == 1:
                seat = max_bettors[0]
                return_amount = max_bet - min_bet
                returns[seat] = return_amount
                self.main_pot -= return_amount

        return returns

    def __repr__(self) -> str:
        return f"PotManager(main={self.main_pot:.2f}, side_pots={len(self.side_pots)})"
