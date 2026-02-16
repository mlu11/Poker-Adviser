"""HandRecord - the core data structure for a single poker hand."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from poker_advisor.models.card import Card
from poker_advisor.models.action import PlayerAction, Street
from poker_advisor.models.position import Position


@dataclass
class HandRecord:
    """Complete record of a single poker hand."""

    hand_id: int = 0
    timestamp: str = ""
    session_id: str = ""

    # Table info
    player_count: int = 0
    dealer_seat: int = 0
    small_blind: float = 0.0
    big_blind: float = 0.0

    # Player info: seat -> name
    players: Dict[int, str] = field(default_factory=dict)
    # seat -> position
    positions: Dict[int, Position] = field(default_factory=dict)
    # seat -> stack at start
    stacks: Dict[int, float] = field(default_factory=dict)

    # Hero info
    hero_seat: Optional[int] = None
    hero_cards: List[Card] = field(default_factory=list)
    hero_name: Optional[str] = None

    # Community cards
    flop: List[Card] = field(default_factory=list)
    turn: Optional[Card] = None
    river: Optional[Card] = None

    # Actions per street
    actions: List[PlayerAction] = field(default_factory=list)

    # Showdown
    shown_cards: Dict[int, List[Card]] = field(default_factory=dict)

    # Results: seat -> net amount won/lost
    pot_total: float = 0.0
    winners: Dict[int, float] = field(default_factory=dict)

    @property
    def board(self) -> List[Card]:
        cards = list(self.flop)
        if self.turn:
            cards.append(self.turn)
        if self.river:
            cards.append(self.river)
        return cards

    @property
    def board_str(self) -> str:
        return " ".join(str(c) for c in self.board) if self.board else ""

    @property
    def hero_cards_str(self) -> str:
        return " ".join(str(c) for c in self.hero_cards) if self.hero_cards else ""

    def actions_on_street(self, street: Street) -> List[PlayerAction]:
        return [a for a in self.actions if a.street == street]

    @property
    def streets_seen(self) -> List[Street]:
        streets = [Street.PREFLOP]
        if self.flop:
            streets.append(Street.FLOP)
        if self.turn:
            streets.append(Street.TURN)
        if self.river:
            streets.append(Street.RIVER)
        return streets

    def hero_actions(self) -> List[PlayerAction]:
        if self.hero_seat is None:
            return []
        return [a for a in self.actions if a.seat == self.hero_seat]

    def hero_actions_on_street(self, street: Street) -> List[PlayerAction]:
        return [a for a in self.hero_actions() if a.street == street]

    @property
    def hero_position(self) -> Optional[Position]:
        if self.hero_seat is None:
            return None
        return self.positions.get(self.hero_seat)

    @property
    def went_to_showdown(self) -> bool:
        return len(self.shown_cards) > 0

    @property
    def hero_won(self) -> bool:
        return self.hero_seat is not None and self.hero_seat in self.winners

    def summary(self) -> str:
        parts = [f"Hand #{self.hand_id}"]
        if self.hero_cards:
            parts.append(f"Hero: {self.hero_cards_str}")
        if self.hero_position:
            parts.append(f"Pos: {self.hero_position.value}")
        if self.board:
            parts.append(f"Board: {self.board_str}")
        parts.append(f"Pot: ${self.pot_total:.2f}")
        if self.hero_won:
            parts.append("(Won)")
        return " | ".join(parts)
