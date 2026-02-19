"""Decision engine for poker agents."""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple
import random

from poker_advisor.models.card import Card
from poker_advisor.models.action import ActionType
from poker_advisor.models.simulation import GameState, PlayerState, PlayStyle
from poker_advisor.agents.styles import PlayStyleConfig, get_style_config


class DecisionType(str, Enum):
    """Types of decisions an agent can make."""
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "all_in"


@dataclass
class Decision:
    """A decision made by an agent."""
    decision_type: DecisionType
    amount: float = 0.0
    reasoning: str = ""


class HandStrengthCategory(str, Enum):
    """Categories of hand strength."""
    MONSTER = "monster"
    STRONG = "strong"
    GOOD = "good"
    MEDIUM = "medium"
    WEAK = "weak"
    TRASH = "trash"


class DecisionEngine:
    """Engine for making poker decisions based on hand strength and play style."""

    # Pre-flop hand rankings (simplified)
    PREFLOP_RANKS = {
        # Premium hands
        "AA": 100, "KK": 95, "QQ": 90, "AK": 88, "JJ": 85,
        "AQ": 80, "TT": 78, "AKs": 85, "AQs": 77,
        # Strong hands
        "AJ": 70, "KQ": 68, "99": 67, "AJs": 72, "KQs": 70,
        "AT": 60, "KJ": 62, "88": 61, "ATs": 63, "KJs": 65,
        # Good hands
        "77": 55, "QJ": 54, "KT": 53, "QTs": 56, "A9s": 52,
        "66": 48, "55": 46, "A8s": 47, "JT": 50, "JTs": 52,
        # Medium hands
        "44": 42, "33": 40, "22": 38, "T9s": 41, "98s": 39,
        "A5s": 35, "A2s": 32, "K9s": 36, "Q9s": 34,
        # Drawing hands
        "87s": 33, "76s": 31, "65s": 29, "54s": 27,
    }

    def __init__(self, style_config: PlayStyleConfig):
        """Initialize the decision engine.

        Args:
            style_config: The play style configuration to use.
        """
        self.style_config = style_config
        self.vpip = style_config.sample_vpip()
        self.pfr = style_config.sample_pfr()
        self.three_bet_pct = style_config.sample_three_bet()
        self.cbet_pct = style_config.sample_cbet()
        self.fold_to_cbet = style_config.sample_fold_to_cbet()

    def evaluate_preflop_hand(self, cards: List[Card]) -> Tuple[int, HandStrengthCategory]:
        """Evaluate the strength of a pre-flop hand.

        Args:
            cards: The player's hole cards (2 cards).

        Returns:
            Tuple of (strength_score 0-100, category).
        """
        if len(cards) != 2:
            return 0, HandStrengthCategory.TRASH

        c1, c2 = cards
        r1, r2 = c1.rank.numeric_value, c2.rank.numeric_value
        suited = c1.suit == c2.suit

        high = max(r1, r2)
        low = min(r1, r2)

        # Create key for lookup
        high_char = self._rank_to_char(high)
        low_char = self._rank_to_char(low)

        if high == low:
            key = high_char + high_char
        elif suited:
            key = high_char + low_char + "s"
        else:
            key = high_char + low_char

        base_score = self.PREFLOP_RANKS.get(key, 20)

        # Adjust based on play style - looser styles rate hands higher
        if self.vpip > 0.40:
            base_score = min(100, base_score + 10)
        elif self.vpip < 0.25:
            base_score = max(0, base_score - 10)

        category = self._score_to_category(base_score)
        return base_score, category

    def _rank_to_char(self, rank: int) -> str:
        """Convert a numeric rank to a character."""
        if rank == 14:
            return "A"
        elif rank == 13:
            return "K"
        elif rank == 12:
            return "Q"
        elif rank == 11:
            return "J"
        elif rank == 10:
            return "T"
        else:
            return str(rank)

    def _score_to_category(self, score: int) -> HandStrengthCategory:
        """Convert a score to a hand strength category."""
        if score >= 85:
            return HandStrengthCategory.MONSTER
        elif score >= 70:
            return HandStrengthCategory.STRONG
        elif score >= 55:
            return HandStrengthCategory.GOOD
        elif score >= 35:
            return HandStrengthCategory.MEDIUM
        elif score >= 20:
            return HandStrengthCategory.WEAK
        else:
            return HandStrengthCategory.TRASH

    def make_decision(
        self,
        player: PlayerState,
        game_state: GameState,
        is_preflop: bool,
        can_check: bool,
        call_amount: float,
        min_raise: float,
        max_raise: float,
        pot_before_action: float,
    ) -> Decision:
        """Make a poker decision based on the current state.

        Args:
            player: The player making the decision.
            game_state: Current game state.
            is_preflop: Whether we're pre-flop.
            can_check: Whether checking is an option.
            call_amount: The amount needed to call.
            min_raise: Minimum raise amount.
            max_raise: Maximum raise amount (player's stack).
            pot_before_action: Pot size before this action.

        Returns:
            The agent's Decision.
        """
        # Evaluate hand strength
        if is_preflop:
            score, category = self.evaluate_preflop_hand(player.cards)
        else:
            # Simplified post-flop evaluation
            score, category = self._evaluate_postflop(player.cards, game_state.community_cards)

        # Calculate pot odds
        pot_odds = self._calculate_pot_odds(call_amount, pot_before_action)

        # Make decision based on hand strength, style, and pot odds
        decision = self._select_action(
            score, category, can_check, call_amount,
            min_raise, max_raise, pot_before_action,
            is_preflop, pot_odds, player.current_bet
        )

        return decision

    def _evaluate_postflop(
        self,
        hole_cards: List[Card],
        community_cards: List[Card]
    ) -> Tuple[int, HandStrengthCategory]:
        """Simplified post-flop hand evaluation."""
        all_cards = hole_cards + community_cards

        if len(all_cards) < 2:
            return 0, HandStrengthCategory.TRASH

        # Count pairs
        ranks = [c.rank.numeric_value for c in all_cards]
        rank_counts = {}
        for r in ranks:
            rank_counts[r] = rank_counts.get(r, 0) + 1

        counts = sorted(rank_counts.values(), reverse=True)

        # Simple scoring
        if counts[0] == 4:
            score = 90
        elif counts[0] == 3 and len(counts) > 1 and counts[1] >= 2:
            score = 80
        elif len(set([c.suit for c in all_cards])) == 1 and len(all_cards) >= 5:
            score = 75
        elif counts[0] == 3:
            score = 65
        elif counts[0] == 2 and len(counts) > 1 and counts[1] == 2:
            score = 55
        elif counts[0] == 2:
            score = 40
        else:
            # High card only
            high = max(ranks)
            score = max(10, high - 5)

        category = self._score_to_category(score)
        return score, category

    def _calculate_pot_odds(self, call_amount: float, pot: float) -> float:
        """Calculate pot odds (call / (pot + call))."""
        if call_amount <= 0:
            return 1.0
        total = pot + call_amount
        return call_amount / total if total > 0 else 1.0

    def _select_action(
        self,
        score: int,
        category: HandStrengthCategory,
        can_check: bool,
        call_amount: float,
        min_raise: float,
        max_raise: float,
        pot: float,
        is_preflop: bool,
        pot_odds: float,
        player_current_bet: float = 0.0
    ) -> Decision:
        """Select an action based on hand strength and style.

        Args:
            player_current_bet: The amount the player already has in the pot.
                This is needed to calculate the TOTAL bet amount for raises.
        """
        # Base aggression from style
        af = self.style_config.sample_af()

        # Decision thresholds
        if is_preflop:
            fold_threshold = 25
            call_threshold = 45
            raise_threshold = 65
        else:
            fold_threshold = 20
            call_threshold = 40
            raise_threshold = 60

        # Adjust thresholds based on aggression
        if af > 2.5:
            fold_threshold += 5
            call_threshold -= 5
            raise_threshold -= 10
        elif af < 1.5:
            fold_threshold -= 5
            call_threshold += 5
            raise_threshold += 10

        # Add some randomness
        random_factor = random.uniform(-15, 15)
        adjusted_score = score + random_factor

        # Make decision
        if adjusted_score < fold_threshold:
            if can_check and call_amount == 0:
                return Decision(DecisionType.CHECK, 0.0, "Checking with weak hand")
            else:
                # Consider bluffing with some probability
                bluff_chance = 0.05 if af > 2.5 else 0.02
                if random.random() < bluff_chance and max_raise >= min_raise:
                    # Bluff raise - calculate total amount including current bet
                    raise_increment = self._calculate_raise_size(pot, min_raise, max_raise - player_current_bet - call_amount)
                    total_raise = player_current_bet + call_amount + raise_increment
                    return Decision(DecisionType.RAISE, total_raise, "Bluff raise")
                return Decision(DecisionType.FOLD, 0.0, "Folding weak hand")

        elif adjusted_score < raise_threshold:
            if can_check and call_amount == 0:
                # Check with medium strength
                return Decision(DecisionType.CHECK, 0.0, "Checking with medium hand")
            elif call_amount > 0:
                # Calculate implied odds consideration
                if score > call_threshold or pot_odds < 0.3:
                    return Decision(DecisionType.CALL, call_amount, "Calling with decent hand")
                else:
                    return Decision(DecisionType.FOLD, 0.0, "Pot odds not good enough")
            else:
                return Decision(DecisionType.CHECK, 0.0, "Checking")

        else:
            # Strong hand - bet/raise
            if can_check and call_amount == 0:
                # Value bet
                bet_size = self._calculate_bet_size(pot, min_raise, max_raise)
                return Decision(DecisionType.BET, bet_size, "Value betting strong hand")
            elif max_raise >= min_raise + call_amount + player_current_bet:
                # Raise - return TOTAL amount (player_current_bet + call_amount + raise_increment)
                # max_raise is player.stack + player_current_bet (from engine.py)
                available_for_raise = max_raise - player_current_bet - call_amount
                raise_increment = self._calculate_raise_size(pot + call_amount, min_raise, available_for_raise)
                total_raise = player_current_bet + call_amount + raise_increment
                return Decision(DecisionType.RAISE, total_raise, "Raising with strong hand")
            elif call_amount > 0:
                return Decision(DecisionType.CALL, call_amount, "Calling with strong hand")
            else:
                return Decision(DecisionType.CHECK, 0.0, "Slow playing")

    def _calculate_bet_size(self, pot: float, min_bet: float, max_bet: float) -> float:
        """Calculate a bet size based on pot and style."""
        # Default bet sizes - 50-75% of pot
        min_pct = 0.4
        max_pct = 0.7

        # More aggressive = bigger bets
        af = self.style_config.sample_af()
        if af > 2.5:
            min_pct = 0.5
            max_pct = 0.8

        target = pot * random.uniform(min_pct, max_pct)
        bet = max(min_bet, min(target, max_bet))
        return round(bet, -1)  # Round to nearest 10

    def _calculate_raise_size(self, pot: float, min_raise: float, max_raise: float) -> float:
        """Calculate a raise size based on pot and style."""
        # Default raise sizes - 2.5x to 3.5x
        min_mult = 2.0
        max_mult = 3.0

        af = self.style_config.sample_af()
        if af > 2.5:
            min_mult = 2.5
            max_mult = 3.5

        target = min_raise * random.uniform(min_mult, max_mult)
        raise_amount = max(min_raise, min(target, max_raise))
        return round(raise_amount, -1)
