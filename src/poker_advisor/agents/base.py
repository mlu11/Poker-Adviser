"""Base agent class for poker agents."""

from abc import ABC, abstractmethod
from typing import List, Optional

from poker_advisor.models.card import Card
from poker_advisor.models.action import ActionType
from poker_advisor.models.simulation import (
    GameState, PlayerState, PlayStyle, AgentLevel
)
from poker_advisor.agents.styles import PlayStyleConfig, get_style_config
from poker_advisor.agents.decision import DecisionEngine, Decision


class BaseAgent(ABC):
    """Abstract base class for poker agents."""

    def __init__(
        self,
        name: str,
        style: PlayStyle,
        level: AgentLevel,
        seat: int,
    ):
        """Initialize the agent.

        Args:
            name: The agent's name.
            style: The play style.
            level: The skill level.
            seat: The seat number.
        """
        self.name = name
        self.style = style
        self.level = level
        self.seat = seat
        self.style_config = get_style_config(style)
        self.decision_engine = DecisionEngine(self.style_config)

        # Track statistics
        self.hands_played = 0
        self.hands_won = 0
        self.total_profit = 0.0
        self.vpip_count = 0
        self.pfr_count = 0
        self.aggressive_actions = 0
        self.passive_actions = 0

    @abstractmethod
    def make_decision(
        self,
        player: PlayerState,
        game_state: GameState,
        available_actions: List[ActionType],
        call_amount: float,
        min_raise: float,
        max_raise: float,
        pot: float,
    ) -> Decision:
        """Make a decision for the current situation.

        Args:
            player: The player's current state.
            game_state: The current game state.
            available_actions: List of available action types.
            call_amount: Amount needed to call.
            min_raise: Minimum raise amount.
            max_raise: Maximum raise amount (stack size).
            pot: Current pot size.

        Returns:
            The agent's decision.
        """
        pass

    def record_action(self, action_type: ActionType, is_voluntary: bool):
        """Record an action for statistics.

        Args:
            action_type: The type of action taken.
            is_voluntary: Whether the action was voluntary (not posting blinds).
        """
        if not is_voluntary:
            return

        if action_type in (ActionType.CALL, ActionType.CHECK):
            self.passive_actions += 1
        elif action_type in (ActionType.BET, ActionType.RAISE, ActionType.ALL_IN):
            self.aggressive_actions += 1
            self.pfr_count += 1
            self.vpip_count += 1
        elif action_type == ActionType.FOLD:
            pass
        else:
            self.vpip_count += 1

    def record_hand_result(self, profit: float, won: bool):
        """Record the result of a hand.

        Args:
            profit: The profit/loss for the hand.
            won: Whether the hand was won.
        """
        self.hands_played += 1
        if won:
            self.hands_won += 1
        self.total_profit += profit

    @property
    def vpip_pct(self) -> float:
        """Calculate VPIP percentage."""
        if self.hands_played == 0:
            return 0.0
        return self.vpip_count / max(1, self.hands_played)

    @property
    def pfr_pct(self) -> float:
        """Calculate PFR percentage."""
        if self.hands_played == 0:
            return 0.0
        return self.pfr_count / max(1, self.hands_played)

    @property
    def aggression_factor(self) -> float:
        """Calculate aggression factor (aggressive / passive)."""
        if self.passive_actions == 0:
            return float(self.aggressive_actions) if self.aggressive_actions > 0 else 1.0
        return self.aggressive_actions / max(1, self.passive_actions)

    def reset_stats(self):
        """Reset all statistics."""
        self.hands_played = 0
        self.hands_won = 0
        self.total_profit = 0.0
        self.vpip_count = 0
        self.pfr_count = 0
        self.aggressive_actions = 0
        self.passive_actions = 0


class RuleBasedAgent(BaseAgent):
    """A rule-based poker agent that uses simple heuristics."""

    def make_decision(
        self,
        player: PlayerState,
        game_state: GameState,
        available_actions: List[ActionType],
        call_amount: float,
        min_raise: float,
        max_raise: float,
        pot: float,
    ) -> Decision:
        """Make a decision using rule-based logic."""
        is_preflop = game_state.phase.value == "preflop"
        can_check = ActionType.CHECK in available_actions

        decision = self.decision_engine.make_decision(
            player=player,
            game_state=game_state,
            is_preflop=is_preflop,
            can_check=can_check,
            call_amount=call_amount,
            min_raise=min_raise,
            max_raise=max_raise,
            pot_before_action=pot
        )

        return decision
