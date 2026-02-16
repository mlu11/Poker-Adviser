"""Card, Rank, and Suit models."""

from enum import Enum
from typing import Optional


class Suit(str, Enum):
    HEARTS = "h"
    DIAMONDS = "d"
    CLUBS = "c"
    SPADES = "s"

    @classmethod
    def from_symbol(cls, s: str) -> "Suit":
        mapping = {
            "h": cls.HEARTS, "Hearts": cls.HEARTS, "♥": cls.HEARTS,
            "d": cls.DIAMONDS, "Diamonds": cls.DIAMONDS, "♦": cls.DIAMONDS,
            "c": cls.CLUBS, "Clubs": cls.CLUBS, "♣": cls.CLUBS,
            "s": cls.SPADES, "Spades": cls.SPADES, "♠": cls.SPADES,
        }
        if s in mapping:
            return mapping[s]
        raise ValueError(f"Unknown suit: {s}")

    @property
    def symbol(self) -> str:
        return {"h": "♥", "d": "♦", "c": "♣", "s": "♠"}[self.value]


class Rank(str, Enum):
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "T"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    ACE = "A"

    @property
    def numeric_value(self) -> int:
        values = {
            "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8,
            "9": 9, "T": 10, "J": 11, "Q": 12, "K": 13, "A": 14,
        }
        return values[self.value]

    @classmethod
    def from_char(cls, c: str) -> "Rank":
        for r in cls:
            if r.value == c.upper():
                return r
        if c == "10":
            return cls.TEN
        raise ValueError(f"Unknown rank: {c}")


class Card:
    """A single playing card."""

    def __init__(self, rank: Rank, suit: Suit):
        self.rank = rank
        self.suit = suit

    @classmethod
    def parse(cls, s: str) -> "Card":
        """Parse a card string like 'Ah', 'Ts', '2c'."""
        s = s.strip()
        if len(s) == 2:
            return cls(Rank.from_char(s[0]), Suit.from_symbol(s[1]))
        elif len(s) == 3 and s[:2] == "10":
            return cls(Rank.TEN, Suit.from_symbol(s[2]))
        raise ValueError(f"Cannot parse card: {s}")

    @classmethod
    def from_name_and_suit(cls, rank_name: str, suit_name: str) -> "Card":
        """Parse from show pattern like rank_name='A' suit_name='Spades'."""
        return cls(Rank.from_char(rank_name), Suit.from_symbol(suit_name))

    def __repr__(self) -> str:
        return f"{self.rank.value}{self.suit.value}"

    def __str__(self) -> str:
        return f"{self.rank.value}{self.suit.symbol}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Card):
            return NotImplemented
        return self.rank == other.rank and self.suit == other.suit

    def __hash__(self) -> int:
        return hash((self.rank, self.suit))

    def to_short(self) -> str:
        """Return short string like 'Ah'."""
        return f"{self.rank.value}{self.suit.value}"
