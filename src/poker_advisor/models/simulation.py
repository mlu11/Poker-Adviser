"""Simulation data models for poker game simulation."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from poker_advisor.models.card import Card
from poker_advisor.models.position import Position


class GamePhase(str, Enum):
    """Game phase enumeration."""
    WAITING = "waiting"
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"
    COMPLETE = "complete"


class PlayStyle(str, Enum):
    """Agent play style enumeration."""
    LOOSE_AGGRESSIVE = "LAG"
    LOOSE_PASSIVE = "LP"
    TIGHT_AGGRESSIVE = "TAG"
    TIGHT_PASSIVE = "TP"


class AgentLevel(str, Enum):
    """Agent skill level enumeration."""
    BEGINNER = "beginner"
    ADVANCED = "advanced"
    EXPERT = "expert"


@dataclass
class AgentConfig:
    """Agent configuration."""
    name: str
    style: PlayStyle
    level: AgentLevel
    seat: int
    stack: float
    # Statistical metrics (for display)
    vpip_pct: float = 0.0
    pfr_pct: float = 0.0
    af: float = 0.0


@dataclass
class SimulationConfig:
    """Simulation session configuration."""
    player_count: int = 6
    small_blind: float = 10.0
    big_blind: float = 20.0
    hero_stack: float = 1000.0
    hero_seat: Optional[int] = None
    agent_configs: List[AgentConfig] = field(default_factory=list)
    hero_name: str = "Hero"


@dataclass
class PlayerState:
    """Player state during a hand."""
    seat: int
    name: str
    stack: float
    position: Optional[Position] = None
    cards: List[Card] = field(default_factory=list)
    is_hero: bool = False
    is_folded: bool = False
    is_all_in: bool = False
    current_bet: float = 0.0
    total_invested: float = 0.0
    agent_config: Optional[AgentConfig] = None


@dataclass
class GameState:
    """Complete game state."""
    phase: GamePhase
    pot: float
    current_bet: float
    min_raise: float
    community_cards: List[Card]
    players: Dict[int, PlayerState]
    dealer_seat: int
    current_player_seat: Optional[int]
    action_history: List[str]
    hand_number: int
    small_blind: float = 10.0
    big_blind: float = 20.0

    @property
    def active_players(self) -> List[PlayerState]:
        """Get list of players who haven't folded."""
        return [p for p in self.players.values() if not p.is_folded]

    @property
    def hero(self) -> Optional[PlayerState]:
        """Get the hero player if present."""
        for p in self.players.values():
            if p.is_hero:
                return p
        return None
