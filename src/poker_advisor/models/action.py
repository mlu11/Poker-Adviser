"""Action and Street models."""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class Street(str, Enum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"

    @property
    def order(self) -> int:
        return ["preflop", "flop", "turn", "river"].index(self.value)


class ActionType(str, Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    POST_BLIND = "post_blind"
    ALL_IN = "all_in"

    @property
    def is_aggressive(self) -> bool:
        return self in (ActionType.BET, ActionType.RAISE, ActionType.ALL_IN)

    @property
    def is_voluntary(self) -> bool:
        return self not in (ActionType.POST_BLIND, ActionType.FOLD)


@dataclass
class PlayerAction:
    """A single player action in a hand."""
    player_name: str
    seat: int
    action_type: ActionType
    amount: float = 0.0
    street: Street = Street.PREFLOP
    is_all_in: bool = False

    def __str__(self) -> str:
        if self.action_type in (ActionType.FOLD, ActionType.CHECK):
            return f"{self.player_name} {self.action_type.value}s"
        suffix = " (all-in)" if self.is_all_in else ""
        return f"{self.player_name} {self.action_type.value}s ${self.amount:.2f}{suffix}"
