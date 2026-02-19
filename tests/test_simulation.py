"""Tests for the poker simulation module."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from poker_advisor.models.card import Card, Rank, Suit
from poker_advisor.models.action import ActionType, Street
from poker_advisor.models.simulation import (
    GamePhase, PlayStyle, AgentLevel,
    AgentConfig, SimulationConfig, PlayerState, GameState
)
from poker_advisor.simulation.deck import Deck
from poker_advisor.simulation.pot import PotManager
from poker_advisor.simulation.evaluator import HandEvaluator, HandRank
from poker_advisor.simulation.engine import SimulationEngine, ActionValidator


class TestDeck:
    """Tests for the Deck class."""

    def test_deck_initialization(self):
        """Test that a new deck has 52 cards."""
        deck = Deck()
        assert len(deck) == 52

    def test_deck_shuffle(self):
        """Test that shuffling changes the order."""
        deck1 = Deck()
        deck2 = Deck()
        deck1.shuffle()

        # It's possible but extremely unlikely for two shuffled decks to be the same
        # Check that at least some cards are in different positions
        different = False
        for c1, c2 in zip(deck1.cards, deck2.cards):
            if c1 != c2:
                different = True
                break
        assert different

    def test_deal_cards(self):
        """Test dealing cards from the deck."""
        deck = Deck()
        dealt = deck.deal(5)
        assert len(dealt) == 5
        assert len(deck) == 47

    def test_deal_one(self):
        """Test dealing a single card."""
        deck = Deck()
        card = deck.deal_one()
        assert card is not None
        assert len(deck) == 51

    def test_deal_too_many(self):
        """Test dealing more cards than available."""
        deck = Deck()
        deck.deal(52)
        with pytest.raises(ValueError):
            deck.deal(1)

    def test_reset(self):
        """Test resetting the deck."""
        deck = Deck()
        deck.deal(10)
        assert len(deck) == 42
        deck.reset()
        assert len(deck) == 52


class TestHandEvaluator:
    """Tests for the HandEvaluator class."""

    def test_high_card(self):
        """Test evaluating a high card hand."""
        cards = [
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.TEN, Suit.HEARTS),
            Card(Rank.EIGHT, Suit.DIAMONDS),
            Card(Rank.FIVE, Suit.CLUBS),
            Card(Rank.TWO, Suit.SPADES),
        ]
        rank, keys = HandEvaluator.evaluate(cards)
        assert rank == HandRank.HIGH_CARD

    def test_one_pair(self):
        """Test evaluating a pair."""
        cards = [
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.EIGHT, Suit.DIAMONDS),
            Card(Rank.FIVE, Suit.CLUBS),
            Card(Rank.TWO, Suit.SPADES),
        ]
        rank, keys = HandEvaluator.evaluate(cards)
        assert rank == HandRank.ONE_PAIR

    def test_two_pair(self):
        """Test evaluating two pair."""
        cards = [
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.EIGHT, Suit.DIAMONDS),
            Card(Rank.EIGHT, Suit.CLUBS),
            Card(Rank.TWO, Suit.SPADES),
        ]
        rank, keys = HandEvaluator.evaluate(cards)
        assert rank == HandRank.TWO_PAIR

    def test_three_of_a_kind(self):
        """Test evaluating three of a kind."""
        cards = [
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.ACE, Suit.DIAMONDS),
            Card(Rank.FIVE, Suit.CLUBS),
            Card(Rank.TWO, Suit.SPADES),
        ]
        rank, keys = HandEvaluator.evaluate(cards)
        assert rank == HandRank.THREE_OF_A_KIND

    def test_straight(self):
        """Test evaluating a straight."""
        cards = [
            Card(Rank.SIX, Suit.SPADES),
            Card(Rank.FIVE, Suit.HEARTS),
            Card(Rank.FOUR, Suit.DIAMONDS),
            Card(Rank.THREE, Suit.CLUBS),
            Card(Rank.TWO, Suit.SPADES),
        ]
        rank, keys = HandEvaluator.evaluate(cards)
        assert rank == HandRank.STRAIGHT

    def test_flush(self):
        """Test evaluating a flush."""
        cards = [
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.TEN, Suit.SPADES),
            Card(Rank.EIGHT, Suit.SPADES),
            Card(Rank.FIVE, Suit.SPADES),
            Card(Rank.TWO, Suit.SPADES),
        ]
        rank, keys = HandEvaluator.evaluate(cards)
        assert rank == HandRank.FLUSH

    def test_full_house(self):
        """Test evaluating a full house."""
        cards = [
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.ACE, Suit.DIAMONDS),
            Card(Rank.EIGHT, Suit.CLUBS),
            Card(Rank.EIGHT, Suit.SPADES),
        ]
        rank, keys = HandEvaluator.evaluate(cards)
        assert rank == HandRank.FULL_HOUSE

    def test_four_of_a_kind(self):
        """Test evaluating four of a kind."""
        cards = [
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.ACE, Suit.DIAMONDS),
            Card(Rank.ACE, Suit.CLUBS),
            Card(Rank.TWO, Suit.SPADES),
        ]
        rank, keys = HandEvaluator.evaluate(cards)
        assert rank == HandRank.FOUR_OF_A_KIND

    def test_straight_flush(self):
        """Test evaluating a straight flush."""
        cards = [
            Card(Rank.SIX, Suit.SPADES),
            Card(Rank.FIVE, Suit.SPADES),
            Card(Rank.FOUR, Suit.SPADES),
            Card(Rank.THREE, Suit.SPADES),
            Card(Rank.TWO, Suit.SPADES),
        ]
        rank, keys = HandEvaluator.evaluate(cards)
        assert rank == HandRank.STRAIGHT_FLUSH

    def test_royal_flush(self):
        """Test evaluating a royal flush."""
        cards = [
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.KING, Suit.SPADES),
            Card(Rank.QUEEN, Suit.SPADES),
            Card(Rank.JACK, Suit.SPADES),
            Card(Rank.TEN, Suit.SPADES),
        ]
        rank, keys = HandEvaluator.evaluate(cards)
        assert rank == HandRank.ROYAL_FLUSH

    def test_compare_hands(self):
        """Test comparing two hands."""
        # Pair vs high card
        pair = [
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.EIGHT, Suit.DIAMONDS),
            Card(Rank.FIVE, Suit.CLUBS),
            Card(Rank.TWO, Suit.SPADES),
        ]
        high_card = [
            Card(Rank.KING, Suit.SPADES),
            Card(Rank.QUEEN, Suit.HEARTS),
            Card(Rank.JACK, Suit.DIAMONDS),
            Card(Rank.TEN, Suit.CLUBS),
            Card(Rank.EIGHT, Suit.SPADES),
        ]
        assert HandEvaluator.compare(pair, high_card) == 1
        assert HandEvaluator.compare(high_card, pair) == -1


class TestPotManager:
    """Tests for the PotManager class."""

    def test_initialization(self):
        """Test pot manager initialization."""
        pot = PotManager()
        assert pot.total_pot == 0

    def test_add_bet(self):
        """Test adding bets to the pot."""
        pot = PotManager()
        pot.add_bet(1, 100)
        assert pot.total_pot == 100

    def test_multiple_bets(self):
        """Test adding multiple bets."""
        pot = PotManager()
        pot.add_bet(1, 100)
        pot.add_bet(2, 100)
        pot.add_bet(3, 100)
        assert pot.total_pot == 300

    def test_get_player_bet(self):
        """Test getting a player's current bet."""
        pot = PotManager()
        pot.add_bet(1, 50)
        pot.add_bet(1, 50)  # Add more
        assert pot.get_player_bet(1) == 100

    def test_reset_street(self):
        """Test resetting for a new street."""
        pot = PotManager()
        pot.add_bet(1, 100)
        pot.reset_street()
        assert pot.get_player_bet(1) == 0
        assert pot.total_pot == 100  # Total should remain

    def test_reset_hand(self):
        """Test resetting for a new hand."""
        pot = PotManager()
        pot.add_bet(1, 100)
        pot.reset_hand()
        assert pot.total_pot == 0


class TestSimulationEngine:
    """Tests for the SimulationEngine class."""

    def test_config_creation(self):
        """Test creating a simulation config."""
        config = SimulationConfig(
            player_count=6,
            small_blind=10,
            big_blind=20,
            hero_stack=1000,
            hero_seat=1,
            hero_name="TestHero",
        )
        assert config.player_count == 6
        assert config.small_blind == 10
        assert config.big_blind == 20

    def test_engine_initialization(self):
        """Test creating a simulation engine."""
        config = SimulationConfig(
            player_count=6,
            small_blind=10,
            big_blind=20,
            hero_stack=1000,
            hero_seat=1,
        )
        engine = SimulationEngine(config)
        assert engine.config == config

    def test_start_new_hand(self):
        """Test starting a new hand."""
        config = SimulationConfig(
            player_count=6,
            small_blind=10,
            big_blind=20,
            hero_stack=1000,
            hero_seat=1,
        )
        engine = SimulationEngine(config)
        state = engine.start_new_hand()
        assert state is not None
        assert state.phase == GamePhase.PREFLOP
        assert state.hand_number == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
