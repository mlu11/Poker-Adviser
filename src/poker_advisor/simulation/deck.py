"""Deck management for poker simulation."""

import random
from typing import List

from poker_advisor.models.card import Card, Rank, Suit


class Deck:
    """A standard 52-card deck."""

    def __init__(self):
        """Initialize a new deck with all 52 cards."""
        self.cards: List[Card] = []
        self._reset()

    def _reset(self):
        """Reset the deck to all 52 cards."""
        self.cards = []
        for suit in Suit:
            for rank in Rank:
                self.cards.append(Card(rank, suit))

    def shuffle(self):
        """Shuffle the deck in place."""
        random.shuffle(self.cards)

    def deal(self, count: int = 1) -> List[Card]:
        """Deal cards from the top of the deck.

        Args:
            count: Number of cards to deal.

        Returns:
            List of dealt cards.
        """
        if count > len(self.cards):
            raise ValueError(f"Not enough cards in deck. Need {count}, have {len(self.cards)}")

        dealt = self.cards[:count]
        self.cards = self.cards[count:]
        return dealt

    def deal_one(self) -> Card:
        """Deal a single card from the top of the deck.

        Returns:
            The dealt card.
        """
        return self.deal(1)[0]

    def reset(self):
        """Reset and shuffle the deck."""
        self._reset()
        self.shuffle()

    @property
    def remaining(self) -> int:
        """Get the number of remaining cards."""
        return len(self.cards)

    def __len__(self) -> int:
        return len(self.cards)

    def __repr__(self) -> str:
        return f"Deck(remaining={len(self.cards)})"
