"""Poker game simulation engine."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime
import random

from poker_advisor.models.card import Card
from poker_advisor.models.action import PlayerAction, ActionType, Street
from poker_advisor.models.position import Position, assign_positions
from poker_advisor.models.hand import HandRecord
from poker_advisor.models.simulation import (
    GamePhase, PlayStyle, AgentLevel,
    AgentConfig, SimulationConfig, PlayerState, GameState
)
from poker_advisor.simulation.deck import Deck
from poker_advisor.simulation.pot import PotManager
from poker_advisor.simulation.evaluator import HandEvaluator
from poker_advisor.agents.base import BaseAgent
from poker_advisor.agents.factory import AgentFactory, get_factory
from poker_advisor.agents.decision import DecisionType


class ActionValidator:
    """Validates player actions."""

    @staticmethod
    def get_available_actions(
        player: PlayerState,
        current_bet: float,
        min_raise: float,
    ) -> List[ActionType]:
        """Get the list of available actions for a player.

        Args:
            player: The player state.
            current_bet: The current bet amount to call.
            min_raise: The minimum raise amount.

        Returns:
            List of available action types.
        """
        actions: List[ActionType] = []

        if player.is_folded or player.is_all_in:
            return actions

        player_bet = player.current_bet
        to_call = current_bet - player_bet

        # Fold is always available (except when checking is free)
        if to_call > 0:
            actions.append(ActionType.FOLD)

        # Check or Call
        if to_call == 0:
            actions.append(ActionType.CHECK)
        else:
            if player.stack >= to_call:
                actions.append(ActionType.CALL)

        # Bet/Raise
        if to_call == 0:
            # Can bet
            if player.stack > 0:
                actions.append(ActionType.BET)
        else:
            # Can raise
            if player.stack >= to_call + min_raise:
                actions.append(ActionType.RAISE)

        # All-in is always an option if we have chips left
        if player.stack > 0 and to_call > 0:
            actions.append(ActionType.ALL_IN)

        return actions

    @staticmethod
    def validate_action(
        action_type: ActionType,
        amount: float,
        player: PlayerState,
        current_bet: float,
        min_raise: float,
        big_blind: float,
    ) -> Tuple[bool, str, float]:
        """Validate an action and adjust the amount if needed.

        Amount Semantics (IMPORTANT):
        - FOLD/CHECK: amount ignored (0)
        - CALL: amount = INCREMENT needed (to_call), but returns TOTAL (current_bet + to_call)
        - BET: amount = TOTAL bet (from 0)
        - RAISE: amount = TOTAL bet (player.current_bet + to_call + raise_increment)
        - ALL_IN: amount = TOTAL bet (player.current_bet + player.stack)

        Args:
            action_type: The action type to validate.
            amount: The proposed amount (see semantics above).
            player: The player making the action.
            current_bet: The current bet to call.
            min_raise: The minimum raise amount.
            big_blind: The big blind amount.

        Returns:
            Tuple of (is_valid, error_message, adjusted_amount).
            adjusted_amount is ALWAYS the TOTAL amount the player will have in the pot after this action.
        """
        player_bet = player.current_bet
        to_call = current_bet - player_bet

        if action_type == ActionType.FOLD:
            return True, "", 0.0

        if action_type == ActionType.CHECK:
            if to_call != 0:
                return False, "Cannot check - there's a bet to call", 0.0
            return True, "", 0.0

        if action_type == ActionType.CALL:
            if to_call <= 0:
                return False, "Nothing to call", 0.0
            if player.stack < to_call:
                # Call all-in - return total bet (current + stack)
                return True, "", player_bet + player.stack
            # Return total bet (current + to_call)
            return True, "", player_bet + to_call

        if action_type == ActionType.BET:
            if to_call != 0:
                return False, "Cannot bet - use raise instead", 0.0
            if player.stack <= 0:
                return False, "No chips left to bet", 0.0

            min_bet = big_blind
            bet_amount = max(min_bet, amount)
            bet_amount = min(bet_amount, player.stack)
            return True, "", bet_amount

        if action_type == ActionType.RAISE:
            if to_call < 0:
                return False, "Invalid state", 0.0
            if to_call == 0:
                return False, "No bet to raise - use bet instead", 0.0

            total_needed = to_call + min_raise
            if player.stack < to_call:
                # Just call all-in - return total bet (current + stack)
                return True, "", player_bet + player.stack
            if player.stack < total_needed:
                # Raise all-in - return total bet (current + stack)
                return True, "", player_bet + player.stack

            raise_amount = max(to_call + min_raise, amount)
            raise_amount = min(raise_amount, player.stack + player_bet)
            return True, "", raise_amount

        if action_type == ActionType.ALL_IN:
            # ALL_IN returns total bet (current + stack)
            return True, "", player_bet + player.stack

        return False, "Unknown action type", 0.0


@dataclass
class StreetState:
    """State for a single street."""
    street: Street
    current_bet: float = 0.0
    min_raise: float = 0.0
    last_aggressor: Optional[int] = None
    action_count: int = 0
    completed: bool = False
    acted_seats: Set[int] = None

    def __post_init__(self):
        if self.acted_seats is None:
            self.acted_seats = set()


class SimulationEngine:
    """Main poker game simulation engine."""

    def __init__(self, config: SimulationConfig):
        """Initialize the simulation engine.

        Args:
            config: The simulation configuration.
        """
        self.config = config
        self.db = None  # Will be set later if needed

        # Initialize components
        self.deck = Deck()
        self.pot = PotManager()
        self.evaluator = HandEvaluator()
        self.validator = ActionValidator()
        self.factory = get_factory()

        # Create agents
        self.agents: Dict[int, BaseAgent] = {}
        self._create_agents()

        # Game state
        self.hand_number = 0
        self.game_state: Optional[GameState] = None
        self.street_state: Optional[StreetState] = None
        self.action_history: List[str] = []
        self.hand_actions: List[PlayerAction] = []

        # Dealership tracking
        self.dealer_seat = self._select_initial_dealer()

        # Session tracking
        self.session_id = f"sim_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.completed_hands: List[HandRecord] = []

    def _create_agents(self):
        """Create agents based on configuration."""
        self.agents = self.factory.create_agents_for_simulation(self.config)

    def _select_initial_dealer(self) -> int:
        """Select the initial dealer seat."""
        available_seats = sorted(self._get_all_seats())
        if available_seats:
            return random.choice(available_seats)
        return 1

    def _get_all_seats(self) -> Set[int]:
        """Get all occupied seats."""
        seats = set(self.agents.keys())
        if self.config.hero_seat is not None:
            seats.add(self.config.hero_seat)
        return seats

    def start_new_hand(self) -> GameState:
        """Start a new hand.

        Returns:
            The initial game state for the new hand.
        """
        self.hand_number += 1
        self.action_history = []
        self.hand_actions = []

        # Reset deck
        self.deck.reset()
        self.pot.reset_hand()

        # Rotate dealer button
        self.dealer_seat = self._next_seat(self.dealer_seat)

        # Create player states
        players = self._create_player_states()

        # Deal hole cards
        self._deal_hole_cards(players)

        # Post blinds
        sb_seat = self._next_seat(self.dealer_seat)
        bb_seat = self._next_seat(sb_seat)

        self._post_blind(sb_seat, players, self.config.small_blind, is_small_blind=True)
        self._post_blind(bb_seat, players, self.config.big_blind, is_small_blind=False)

        # Initialize street state
        self.street_state = StreetState(
            street=Street.PREFLOP,
            current_bet=self.config.big_blind,
            min_raise=self.config.big_blind,
            acted_seats=set(),
        )

        # Set initial player to act (UTG)
        first_to_act = self._next_seat(bb_seat)

        # Create game state
        self.game_state = GameState(
            phase=GamePhase.PREFLOP,
            pot=self.pot.total_pot,
            current_bet=self.street_state.current_bet,
            min_raise=self.street_state.min_raise,
            community_cards=[],
            players=players,
            dealer_seat=self.dealer_seat,
            current_player_seat=first_to_act,
            action_history=self.action_history.copy(),
            hand_number=self.hand_number,
            small_blind=self.config.small_blind,
            big_blind=self.config.big_blind,
        )

        self._add_action_log(f"--- Hand #{self.hand_number} starting ---")

        return self.game_state

    def _create_player_states(self) -> Dict[int, PlayerState]:
        """Create player state objects for all players."""
        players: Dict[int, PlayerState] = {}
        all_seats = self._get_all_seats()

        # Assign positions
        sorted_seats = sorted(all_seats)
        position_map = assign_positions(sorted_seats, self.dealer_seat)

        # Create hero
        if self.config.hero_seat is not None:
            seat = self.config.hero_seat
            players[seat] = PlayerState(
                seat=seat,
                name=self.config.hero_name,
                stack=self.config.hero_stack,
                position=position_map.get(seat),
                cards=[],
                is_hero=True,
                is_folded=False,
                is_all_in=False,
                current_bet=0.0,
                total_invested=0.0,
                agent_config=None,
            )

        # Create agents
        for seat, agent in self.agents.items():
            if seat in players:
                continue  # Skip if already created as hero

            agent_config = AgentConfig(
                name=agent.name,
                style=agent.style,
                level=agent.level,
                seat=seat,
                stack=0.0,
                vpip_pct=agent.vpip_pct,
                pfr_pct=agent.pfr_pct,
                af=agent.aggression_factor,
            )

            players[seat] = PlayerState(
                seat=seat,
                name=agent.name,
                stack=self.config.hero_stack,  # Same stack for everyone
                position=position_map.get(seat),
                cards=[],
                is_hero=False,
                is_folded=False,
                is_all_in=False,
                current_bet=0.0,
                total_invested=0.0,
                agent_config=agent_config,
            )

        return players

    def _deal_hole_cards(self, players: Dict[int, PlayerState]):
        """Deal hole cards to all active players."""
        active_seats = [s for s, p in players.items() if not p.is_folded]

        # Deal one card at a time to each player
        for _ in range(2):
            for seat in active_seats:
                card = self.deck.deal_one()
                players[seat].cards.append(card)

    def _post_blind(
        self,
        seat: int,
        players: Dict[int, PlayerState],
        amount: float,
        is_small_blind: bool,
    ):
        """Post a blind for a player."""
        if seat not in players:
            return

        player = players[seat]
        actual_amount = min(amount, player.stack)

        player.stack -= actual_amount
        player.current_bet = actual_amount
        player.total_invested = actual_amount

        self.pot.add_bet(seat, actual_amount)

        blind_type = "small blind" if is_small_blind else "big blind"
        self._add_action_log(f"{player.name} posts {blind_type}: ${actual_amount:.0f}")

        # Record action
        self.hand_actions.append(PlayerAction(
            player_name=player.name,
            seat=seat,
            action_type=ActionType.POST_BLIND,
            amount=actual_amount,
            street=Street.PREFLOP,
            is_all_in=player.stack <= 0,
        ))

        if player.stack <= 0:
            player.is_all_in = True

        # Mark as having acted if street state exists
        if self.street_state:
            self.street_state.acted_seats.add(seat)

    def _next_seat(self, seat: int) -> int:
        """Get the next active seat after the given seat."""
        all_seats = sorted(self._get_all_seats())
        if not all_seats:
            return seat

        try:
            idx = all_seats.index(seat)
            next_idx = (idx + 1) % len(all_seats)
            return all_seats[next_idx]
        except ValueError:
            return all_seats[0]

    def _next_player_to_act(
        self,
        current_seat: int,
        players: Dict[int, PlayerState],
    ) -> Optional[int]:
        """Find the next player who needs to act."""
        # First check if street is already complete
        if self._is_street_complete():
            return None

        # Get all active, non-all-in seats in order
        all_seats = sorted(self._get_all_seats())
        if not all_seats:
            return None

        # Find starting index
        try:
            start_idx = all_seats.index(current_seat)
        except ValueError:
            start_idx = 0

        # Search for next player that needs to act
        num_players = len(all_seats)
        for i in range(1, num_players + 1):
            idx = (start_idx + i) % num_players
            seat = all_seats[idx]
            player = players.get(seat)

            if player and not player.is_folded and not player.is_all_in:
                # Player needs to act if they haven't matched the current bet
                if player.current_bet < self.street_state.current_bet:
                    return seat

        # If everyone has matched, check if street is actually complete
        if self._is_street_complete():
            return None

        # Fallback: find first active non-all-in player
        for seat in all_seats:
            player = players.get(seat)
            if player and not player.is_folded and not player.is_all_in:
                return seat

        return None

    def player_action(
        self,
        action_type: ActionType,
        amount: float = 0.0,
    ) -> GameState:
        """Process a player action.

        Args:
            action_type: The type of action.
            amount: The amount for bets/raises.

        Returns:
            The updated game state.
        """
        if not self.game_state or not self.street_state:
            raise ValueError("No hand in progress")

        seat = self.game_state.current_player_seat
        if seat is None:
            raise ValueError("No current player")

        player = self.game_state.players.get(seat)
        if not player:
            raise ValueError(f"Player not found at seat {seat}")

        # Validate action
        is_valid, error, adjusted_amount = self.validator.validate_action(
            action_type, amount, player,
            self.street_state.current_bet,
            self.street_state.min_raise,
            self.config.big_blind,
        )

        if not is_valid:
            raise ValueError(f"Invalid action: {error}")

        # Process the action
        self._process_action(seat, player, action_type, adjusted_amount)

        # Check if street is complete
        if self._is_street_complete():
            self._complete_street()

        # Update game state
        self._update_game_state()

        return self.game_state

    def _process_action(
        self,
        seat: int,
        player: PlayerState,
        action_type: ActionType,
        amount: float,
    ):
        """Process a validated action."""
        street = self.street_state.street

        if action_type == ActionType.FOLD:
            player.is_folded = True
            self._add_action_log(f"{player.name} folds")

        elif action_type == ActionType.CHECK:
            self._add_action_log(f"{player.name} checks")

        elif action_type in (ActionType.CALL, ActionType.BET, ActionType.RAISE, ActionType.ALL_IN):
            previous_bet = player.current_bet
            # Amount is total bet (already validated)
            increment = max(0.0, amount - previous_bet)

            # Take from player's stack
            player.stack -= increment
            player.current_bet = amount
            player.total_invested += increment

            # Add to pot
            self.pot.add_bet(seat, increment)

            # Track raises
            if action_type in (ActionType.BET, ActionType.RAISE, ActionType.ALL_IN):
                if amount > self.street_state.current_bet:
                    raise_amount = amount - self.street_state.current_bet
                    self.street_state.min_raise = max(self.street_state.min_raise, raise_amount)
                    self.street_state.current_bet = amount
                    self.street_state.last_aggressor = seat

            # Log
            if action_type == ActionType.CALL:
                self._add_action_log(f"{player.name} calls ${increment:.0f}")
            elif action_type == ActionType.BET:
                self._add_action_log(f"{player.name} bets ${amount:.0f}")
            elif action_type == ActionType.RAISE:
                self._add_action_log(f"{player.name} raises to ${amount:.0f}")
            elif action_type == ActionType.ALL_IN:
                self._add_action_log(f"{player.name} goes all-in for ${amount:.0f}")
                player.is_all_in = True

        # Record action
        self.hand_actions.append(PlayerAction(
            player_name=player.name,
            seat=seat,
            action_type=action_type,
            amount=amount,
            street=street,
            is_all_in=player.is_all_in,
        ))

        # Record for agent stats
        if not player.is_hero and seat in self.agents:
            agent = self.agents[seat]
            is_voluntary = action_type != ActionType.POST_BLIND
            agent.record_action(action_type, is_voluntary)

        self.street_state.action_count += 1
        self.street_state.acted_seats.add(seat)

    def _is_street_complete(self) -> bool:
        """Check if the current street is complete."""
        if not self.game_state or not self.street_state:
            return True

        players = self.game_state.players
        active = [p for p in players.values() if not p.is_folded]
        active_not_allin = [p for p in active if not p.is_all_in]
        active_seats = {s for s, p in players.items() if not p.is_folded and not p.is_all_in}

        if len(active) <= 1:
            return True

        # If everyone is all-in, street is complete
        if len(active_not_allin) == 0:
            return True

        # Check if all active, non-all-in players have matched the bet
        all_matched = True
        for player in active_not_allin:
            if player.current_bet < self.street_state.current_bet:
                all_matched = False
                break

        if not all_matched:
            return False

        # Check if all active non-all-in players have acted at least once
        # OR if the current bet is still at the minimum and everyone has acted
        all_acted = active_seats.issubset(self.street_state.acted_seats)

        # Special case for preflop: blinds count as bets, so after blinds, UTG acts first
        # Everyone needs to have a chance to respond to the current bet
        if self.street_state.last_aggressor is not None:
            # If there was an aggressor, check if everyone else has acted
            # For simplicity, if all_matched is True and we've had at least len(active) actions,
            # the street is complete
            return all_matched and (all_acted or self.street_state.action_count >= len(active))

        # No aggressor - everyone has checked
        return all_matched and all_acted

    def _complete_street(self):
        """Complete the current street and move to the next."""
        if not self.game_state:
            return

        # Return uncalled bets
        if self.street_state.last_aggressor is not None:
            active_seats = {
                s for s, p in self.game_state.players.items()
                if not p.is_folded
            }
            returns = self.pot.return_uncalled_bets(
                self.street_state.last_aggressor, active_seats
            )
            for seat, amount in returns.items():
                if seat in self.game_state.players:
                    player = self.game_state.players[seat]
                    player.stack += amount
                    player.current_bet -= amount
                    self._add_action_log(f"{player.name} gets ${amount:.0f} uncalled bet returned")

        # Reset for next street
        self.pot.reset_street()
        for player in self.game_state.players.values():
            player.current_bet = 0.0

        # Check if hand is complete
        active = [p for p in self.game_state.players.values() if not p.is_folded]
        if len(active) <= 1:
            self._complete_hand()
            return

        # Move to next street
        current_street = self.street_state.street

        if current_street == Street.PREFLOP:
            next_street = Street.FLOP
            # Deal flop
            self.game_state.community_cards.extend(self.deck.deal(3))
            self.game_state.phase = GamePhase.FLOP
            self._add_action_log(f"Flop: {self._format_cards(self.game_state.community_cards)}")

        elif current_street == Street.FLOP:
            next_street = Street.TURN
            card = self.deck.deal_one()
            self.game_state.community_cards.append(card)
            self.game_state.phase = GamePhase.TURN
            self._add_action_log(f"Turn: {self._format_cards([card])}")

        elif current_street == Street.TURN:
            next_street = Street.RIVER
            card = self.deck.deal_one()
            self.game_state.community_cards.append(card)
            self.game_state.phase = GamePhase.RIVER
            self._add_action_log(f"River: {self._format_cards([card])}")

        else:
            # River complete - showdown
            self._complete_hand()
            return

        # Initialize new street state
        self.street_state = StreetState(
            street=next_street,
            current_bet=0.0,
            min_raise=self.config.big_blind,
            acted_seats=set(),
        )

        # First to act is SB (or first after dealer)
        self.game_state.current_player_seat = self._first_to_act_postflop()

    def _first_to_act_postflop(self) -> Optional[int]:
        """Find the first player to act post-flop."""
        if not self.game_state:
            return None

        sb_seat = self._next_seat(self.dealer_seat)
        seat = sb_seat

        for _ in range(10):
            player = self.game_state.players.get(seat)
            if player and not player.is_folded and not player.is_all_in:
                return seat
            seat = self._next_seat(seat)

        return None

    def _complete_hand(self):
        """Complete the hand and award the pot."""
        if not self.game_state:
            return

        self.game_state.phase = GamePhase.COMPLETE

        active = {s: p for s, p in self.game_state.players.items() if not p.is_folded}

        if len(active) == 1:
            # Winner by default
            winner_seat = list(active.keys())[0]
            winner = active[winner_seat]
            amount = self.pot.total_pot
            winner.stack += amount
            self._add_action_log(f"{winner.name} wins ${amount:.0f} (everyone folded)")

            winners = {winner_seat: amount}

            # Update agent stats
            if not winner.is_hero and winner_seat in self.agents:
                self.agents[winner_seat].record_hand_result(amount, True)

        else:
            # Showdown - evaluate hands
            player_cards = {
                s: p.cards for s, p in active.items()
                if len(p.cards) >= 2
            }

            if player_cards:
                winner_seats = self.evaluator.get_winners(
                    self.game_state.community_cards, player_cards
                )

                # Split pot among winners
                split_amount = self.pot.total_pot / len(winner_seats)
                winners = {}

                for seat in winner_seats:
                    player = self.game_state.players[seat]
                    player.stack += split_amount
                    winners[seat] = split_amount
                    self._add_action_log(f"{player.name} wins ${split_amount:.0f}")

                    # Show cards
                    self._add_action_log(f"{player.name} shows: {self._format_cards(player.cards)}")

                    # Update agent stats
                    if not player.is_hero and seat in self.agents:
                        self.agents[seat].record_hand_result(split_amount, True)

                # Log losers' results
                for seat, player in active.items():
                    if seat not in winner_seats and not player.is_hero and seat in self.agents:
                        self.agents[seat].record_hand_result(-player.total_invested, False)
            else:
                winners = {}

        # Create HandRecord
        hand_record = self._create_hand_record(winners)
        self.completed_hands.append(hand_record)

        self._add_action_log(f"--- Hand #{self.hand_number} complete ---")

    def _create_hand_record(self, winners: Dict[int, float]) -> HandRecord:
        """Create a HandRecord from the current game state."""
        if not self.game_state:
            return HandRecord()

        players = {s: p.name for s, p in self.game_state.players.items()}
        positions = {s: p.position for s, p in self.game_state.players.items()
                    if p.position is not None}
        stacks = {s: (self.config.hero_stack - p.total_invested + winners.get(s, 0))
                 for s, p in self.game_state.players.items()}

        hero_seat = self.config.hero_seat
        hero_cards = []
        hero_name = None
        if hero_seat is not None and hero_seat in self.game_state.players:
            hero = self.game_state.players[hero_seat]
            hero_cards = hero.cards
            hero_name = hero.name

        flop = self.game_state.community_cards[:3] if len(self.game_state.community_cards) >= 3 else []
        turn = self.game_state.community_cards[3] if len(self.game_state.community_cards) >= 4 else None
        river = self.game_state.community_cards[4] if len(self.game_state.community_cards) >= 5 else None

        return HandRecord(
            hand_id=self.hand_number,
            timestamp=datetime.now().isoformat(),
            session_id=self.session_id,
            player_count=len(players),
            dealer_seat=self.dealer_seat,
            small_blind=self.config.small_blind,
            big_blind=self.config.big_blind,
            players=players,
            positions=positions,
            stacks=stacks,
            hero_seat=hero_seat,
            hero_cards=hero_cards,
            hero_name=hero_name,
            flop=flop,
            turn=turn,
            river=river,
            actions=self.hand_actions.copy(),
            shown_cards={},
            pot_total=self.pot.total_pot,
            winners=winners,
            uncalled_bets={},
        )

    def _update_game_state(self):
        """Update the game state after processing actions."""
        if not self.game_state or not self.street_state:
            return

        # Find next player
        if self.game_state.phase != GamePhase.COMPLETE:
            next_seat = self._next_player_to_act(
                self.game_state.current_player_seat or self.dealer_seat,
                self.game_state.players,
            )

            # If no next player, check if street is complete
            if next_seat is None and not self._is_street_complete():
                # Just cycle to next
                next_seat = self._next_seat(self.game_state.current_player_seat or self.dealer_seat)

            self.game_state.current_player_seat = next_seat
        else:
            self.game_state.current_player_seat = None

        # Update pot and bets
        self.game_state.pot = self.pot.total_pot
        self.game_state.current_bet = self.street_state.current_bet
        self.game_state.min_raise = self.street_state.min_raise
        self.game_state.action_history = self.action_history.copy()

    def _add_action_log(self, message: str):
        """Add a message to the action history."""
        self.action_history.append(message)

    def _format_cards(self, cards: List[Card]) -> str:
        """Format a list of cards as a string."""
        return " ".join(str(c) for c in cards)

    def get_state(self) -> Optional[GameState]:
        """Get the current game state."""
        return self.game_state

    def is_complete(self) -> bool:
        """Check if the current hand is complete."""
        return self.game_state is None or self.game_state.phase == GamePhase.COMPLETE

    def is_hero_turn(self) -> bool:
        """Check if it's the hero's turn to act."""
        if not self.game_state:
            return False
        if self.game_state.current_player_seat is None:
            return False
        if self.config.hero_seat is None:
            return False
        return self.game_state.current_player_seat == self.config.hero_seat

    def get_available_actions(self) -> List[ActionType]:
        """Get the available actions for the current player."""
        if not self.game_state or not self.street_state:
            return []

        seat = self.game_state.current_player_seat
        if seat is None:
            return []

        player = self.game_state.players.get(seat)
        if not player:
            return []

        return self.validator.get_available_actions(
            player, self.street_state.current_bet, self.street_state.min_raise
        )

    def agent_action(self) -> GameState:
        """Let the current agent take an action.

        Returns:
            The updated game state.
        """
        if not self.game_state or not self.street_state:
            raise ValueError("No hand in progress")

        if self.is_hero_turn():
            raise ValueError("It's the hero's turn - use player_action instead")

        seat = self.game_state.current_player_seat
        if seat is None:
            raise ValueError("No current player")

        if seat not in self.agents:
            raise ValueError(f"No agent at seat {seat}")

        agent = self.agents[seat]
        player = self.game_state.players[seat]

        # Get available actions
        available_actions = self.get_available_actions()
        if not available_actions:
            # No actions available - check/fold
            if ActionType.CHECK in available_actions:
                return self.player_action(ActionType.CHECK, 0.0)
            return self.player_action(ActionType.FOLD, 0.0)

        # Calculate call amount
        to_call = self.street_state.current_bet - player.current_bet
        min_raise = self.street_state.min_raise
        max_raise = player.stack + player.current_bet

        # Let agent decide
        decision = agent.make_decision(
            player=player,
            game_state=self.game_state,
            available_actions=available_actions,
            call_amount=to_call,
            min_raise=min_raise,
            max_raise=max_raise,
            pot=self.game_state.pot,
        )

        # Map decision type to action type
        action_map = {
            DecisionType.FOLD: ActionType.FOLD,
            DecisionType.CHECK: ActionType.CHECK,
            DecisionType.CALL: ActionType.CALL,
            DecisionType.BET: ActionType.BET,
            DecisionType.RAISE: ActionType.RAISE,
            DecisionType.ALL_IN: ActionType.ALL_IN,
        }

        action_type = action_map.get(decision.decision_type, ActionType.FOLD)

        # Ensure action is available
        if action_type not in available_actions:
            # Fall back to safe action
            if ActionType.CHECK in available_actions:
                action_type = ActionType.CHECK
            elif ActionType.CALL in available_actions:
                action_type = ActionType.CALL
            elif ActionType.FOLD in available_actions:
                action_type = ActionType.FOLD
            else:
                action_type = available_actions[0] if available_actions else ActionType.FOLD

        return self.player_action(action_type, decision.amount)

    def to_hand_record(self) -> Optional[HandRecord]:
        """Get the current hand as a HandRecord (if complete)."""
        if self.completed_hands:
            return self.completed_hands[-1]
        return None
