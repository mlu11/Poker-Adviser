"""Hand evaluation for poker simulation."""

from enum import Enum, IntEnum
from typing import Dict, List, Optional, Tuple

from poker_advisor.models.card import Card, Rank, Suit


class HandRank(IntEnum):
    """Hand rankings from worst to best."""
    HIGH_CARD = 0
    ONE_PAIR = 1
    TWO_PAIR = 2
    THREE_OF_A_KIND = 3
    STRAIGHT = 4
    FLUSH = 5
    FULL_HOUSE = 6
    FOUR_OF_A_KIND = 7
    STRAIGHT_FLUSH = 8
    ROYAL_FLUSH = 9


class HandEvaluator:
    """Evaluates poker hands."""

    @staticmethod
    def evaluate(cards: List[Card]) -> Tuple[HandRank, List[int]]:
        """Evaluate a poker hand and return its rank and key values.

        Args:
            cards: List of cards (2-7 cards).

        Returns:
            Tuple of (HandRank, list of key values for tie-breaking).
        """
        if len(cards) < 2:
            return HandRank.HIGH_CARD, [0]

        # Get all 5-card combinations if we have more than 5 cards
        if len(cards) > 5:
            best_rank = HandRank.HIGH_CARD
            best_keys: List[int] = []
            # Generate all 5-card combinations
            from itertools import combinations
            for combo in combinations(cards, 5):
                rank, keys = HandEvaluator._evaluate_five(list(combo))
                if rank > best_rank or (rank == best_rank and keys > best_keys):
                    best_rank = rank
                    best_keys = keys
            return best_rank, best_keys

        if len(cards) == 5:
            return HandEvaluator._evaluate_five(cards)

        # For 2-4 cards, just evaluate what we have (simplified)
        return HandEvaluator._evaluate_partial(cards)

    @staticmethod
    def _evaluate_five(cards: List[Card]) -> Tuple[HandRank, List[int]]:
        """Evaluate exactly 5 cards."""
        # Get sorted ranks (descending) and suits
        ranks = sorted([c.rank.numeric_value for c in cards], reverse=True)
        suits = [c.suit for c in cards]

        # Count rank frequencies
        rank_counts: Dict[int, int] = {}
        for r in ranks:
            rank_counts[r] = rank_counts.get(r, 0) + 1

        # Check for flush
        is_flush = len(set(suits)) == 1

        # Check for straight
        is_straight, high_card = HandEvaluator._check_straight(ranks)

        # Count pairs, triples, etc.
        counts = sorted(rank_counts.values(), reverse=True)
        sorted_unique_ranks = sorted(rank_counts.keys(),
                                      key=lambda r: (-rank_counts[r], -r))

        # Royal Flush
        if is_flush and is_straight and high_card == 14:
            return HandRank.ROYAL_FLUSH, [14]

        # Straight Flush
        if is_flush and is_straight:
            return HandRank.STRAIGHT_FLUSH, [high_card]

        # Four of a Kind
        if counts[0] == 4:
            four_rank = sorted_unique_ranks[0]
            kicker = sorted_unique_ranks[1]
            return HandRank.FOUR_OF_A_KIND, [four_rank, kicker]

        # Full House
        if counts[0] == 3 and counts[1] == 2:
            three_rank = sorted_unique_ranks[0]
            pair_rank = sorted_unique_ranks[1]
            return HandRank.FULL_HOUSE, [three_rank, pair_rank]

        # Flush
        if is_flush:
            return HandRank.FLUSH, ranks

        # Straight
        if is_straight:
            return HandRank.STRAIGHT, [high_card]

        # Three of a Kind
        if counts[0] == 3:
            three_rank = sorted_unique_ranks[0]
            kickers = [r for r in ranks if r != three_rank][:2]
            return HandRank.THREE_OF_A_KIND, [three_rank] + kickers

        # Two Pair
        if counts[0] == 2 and counts[1] == 2:
            high_pair = max(sorted_unique_ranks[0], sorted_unique_ranks[1])
            low_pair = min(sorted_unique_ranks[0], sorted_unique_ranks[1])
            kicker = sorted_unique_ranks[2]
            return HandRank.TWO_PAIR, [high_pair, low_pair, kicker]

        # One Pair
        if counts[0] == 2:
            pair_rank = sorted_unique_ranks[0]
            kickers = [r for r in ranks if r != pair_rank][:3]
            return HandRank.ONE_PAIR, [pair_rank] + kickers

        # High Card
        return HandRank.HIGH_CARD, ranks

    @staticmethod
    def _evaluate_partial(cards: List[Card]) -> Tuple[HandRank, List[int]]:
        """Evaluate a partial hand (less than 5 cards)."""
        ranks = sorted([c.rank.numeric_value for c in cards], reverse=True)
        rank_counts: Dict[int, int] = {}
        for r in ranks:
            rank_counts[r] = rank_counts.get(r, 0) + 1

        counts = sorted(rank_counts.values(), reverse=True)
        sorted_unique_ranks = sorted(rank_counts.keys(),
                                      key=lambda r: (-rank_counts[r], -r))

        if counts[0] == 4:
            return HandRank.FOUR_OF_A_KIND, [sorted_unique_ranks[0]]
        if counts[0] == 3:
            return HandRank.THREE_OF_A_KIND, [sorted_unique_ranks[0]]
        if counts[0] == 2 and len(counts) > 1 and counts[1] == 2:
            return HandRank.TWO_PAIR, [sorted_unique_ranks[0], sorted_unique_ranks[1]]
        if counts[0] == 2:
            return HandRank.ONE_PAIR, [sorted_unique_ranks[0]]

        return HandRank.HIGH_CARD, ranks

    @staticmethod
    def _check_straight(ranks: List[int]) -> Tuple[bool, int]:
        """Check if ranks form a straight.

        Returns:
            Tuple of (is_straight, high_card).
        """
        unique_ranks = sorted(list(set(ranks)), reverse=True)

        # Check for normal straight
        if len(unique_ranks) >= 5:
            for i in range(len(unique_ranks) - 4):
                if unique_ranks[i] - unique_ranks[i + 4] == 4:
                    return True, unique_ranks[i]

        # Check for Ace-low straight (A-2-3-4-5)
        if 14 in unique_ranks and 2 in unique_ranks and 3 in unique_ranks and 4 in unique_ranks and 5 in unique_ranks:
            return True, 5

        return False, 0

    @staticmethod
    def compare(cards1: List[Card], cards2: List[Card]) -> int:
        """Compare two hands.

        Args:
            cards1: First hand.
            cards2: Second hand.

        Returns:
            1 if cards1 wins, -1 if cards2 wins, 0 if tie.
        """
        rank1, keys1 = HandEvaluator.evaluate(cards1)
        rank2, keys2 = HandEvaluator.evaluate(cards2)

        if rank1 > rank2:
            return 1
        if rank1 < rank2:
            return -1

        # Compare keys
        for k1, k2 in zip(keys1, keys2):
            if k1 > k2:
                return 1
            if k1 < k2:
                return -1

        return 0

    @staticmethod
    def get_winners(board: List[Card],
                   player_cards: Dict[int, List[Card]]) -> List[int]:
        """Get the winning seat(s) from a group of players.

        Args:
            board: Community cards.
            player_cards: Mapping from seat to player's hole cards.

        Returns:
            List of winning seat numbers (may be multiple for ties).
        """
        if not player_cards:
            return []

        # Evaluate each player's hand
        evaluations: Dict[int, Tuple[HandRank, List[int]]] = {}
        for seat, cards in player_cards.items():
            full_hand = cards + board
            evaluations[seat] = HandEvaluator.evaluate(full_hand)

        # Find the best hand
        best_rank = HandRank.HIGH_CARD
        best_keys: List[int] = []

        for (rank, keys) in evaluations.values():
            if rank > best_rank or (rank == best_rank and keys > best_keys):
                best_rank = rank
                best_keys = keys

        # Collect all winners
        winners = []
        for seat, (rank, keys) in evaluations.items():
            if rank == best_rank and keys == best_keys:
                winners.append(seat)

        return winners

    @staticmethod
    def get_rank_name(rank: HandRank) -> str:
        """Get a human-readable name for a hand rank."""
        names = {
            HandRank.HIGH_CARD: "高牌",
            HandRank.ONE_PAIR: "一对",
            HandRank.TWO_PAIR: "两对",
            HandRank.THREE_OF_A_KIND: "三条",
            HandRank.STRAIGHT: "顺子",
            HandRank.FLUSH: "同花",
            HandRank.FULL_HOUSE: "葫芦",
            HandRank.FOUR_OF_A_KIND: "四条",
            HandRank.STRAIGHT_FLUSH: "同花顺",
            HandRank.ROYAL_FLUSH: "皇家同花顺",
        }
        return names.get(rank, "未知")
