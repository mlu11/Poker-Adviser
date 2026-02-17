"""Test cases for hand type recognition."""

import pytest

from poker_advisor.models.card import Card
from poker_advisor.models.hand import HandRecord
from poker_advisor.models.position import Position


class TestHandTypeRecognition:
    """Test cases for hand type recognition."""

    @pytest.fixture
    def hand_with_one_pair(self):
        """Hand with one pair."""
        hand = HandRecord(hand_id=1)
        hand.hero_cards = [Card.parse("Ah"), Card.parse("Ad")]
        hand.flop = [Card.parse("2c"), Card.parse("3d"), Card.parse("4h")]
        hand.turn = Card.parse("5s")
        hand.river = Card.parse("6d")
        return hand

    @pytest.fixture
    def hand_with_two_pairs(self):
        """Hand with two pairs."""
        hand = HandRecord(hand_id=2)
        hand.hero_cards = [Card.parse("Ah"), Card.parse("Ad")]
        hand.flop = [Card.parse("2c"), Card.parse("2d"), Card.parse("4h")]
        hand.turn = Card.parse("5s")
        hand.river = Card.parse("6d")
        return hand

    @pytest.fixture
    def hand_with_three_of_a_kind(self):
        """Hand with three of a kind."""
        hand = HandRecord(hand_id=3)
        hand.hero_cards = [Card.parse("Ah"), Card.parse("Ad")]
        hand.flop = [Card.parse("Ac"), Card.parse("3d"), Card.parse("4h")]
        hand.turn = Card.parse("5s")
        hand.river = Card.parse("6d")
        return hand

    @pytest.fixture
    def hand_with_straight(self):
        """Hand with a straight."""
        hand = HandRecord(hand_id=4)
        hand.hero_cards = [Card.parse("2h"), Card.parse("3d")]
        hand.flop = [Card.parse("4c"), Card.parse("5d"), Card.parse("6h")]
        hand.turn = Card.parse("7s")
        hand.river = Card.parse("8d")
        return hand

    @pytest.fixture
    def hand_with_flush(self):
        """Hand with a flush."""
        hand = HandRecord(hand_id=5)
        hand.hero_cards = [Card.parse("2h"), Card.parse("3h")]
        hand.flop = [Card.parse("4h"), Card.parse("5d"), Card.parse("6h")]
        hand.turn = Card.parse("7h")
        hand.river = Card.parse("8d")
        return hand

    @pytest.fixture
    def hand_with_full_house(self):
        """Hand with a full house."""
        hand = HandRecord(hand_id=6)
        hand.hero_cards = [Card.parse("Ah"), Card.parse("Ad")]
        hand.flop = [Card.parse("Ac"), Card.parse("2d"), Card.parse("2h")]
        hand.turn = Card.parse("5s")
        hand.river = Card.parse("6d")
        return hand

    @pytest.fixture
    def hand_with_four_of_a_kind(self):
        """Hand with four of a kind."""
        hand = HandRecord(hand_id=7)
        hand.hero_cards = [Card.parse("Ah"), Card.parse("Ad")]
        hand.flop = [Card.parse("Ac"), Card.parse("As"), Card.parse("4h")]
        hand.turn = Card.parse("5s")
        hand.river = Card.parse("6d")
        return hand

    @pytest.fixture
    def hand_with_straight_flush(self):
        """Hand with a straight flush."""
        hand = HandRecord(hand_id=8)
        hand.hero_cards = [Card.parse("2h"), Card.parse("3h")]
        hand.flop = [Card.parse("4h"), Card.parse("5h"), Card.parse("6h")]
        hand.turn = Card.parse("7h")
        hand.river = Card.parse("8d")
        return hand

    @pytest.fixture
    def hand_with_royal_flush(self):
        """Hand with a royal flush."""
        hand = HandRecord(hand_id=9)
        hand.hero_cards = [Card.parse("Ah"), Card.parse("Kh")]
        hand.flop = [Card.parse("Qh"), Card.parse("Jh"), Card.parse("Th")]
        hand.turn = Card.parse("9h")
        hand.river = Card.parse("8d")
        return hand

    def test_unknown_hand_type(self):
        """Test that an empty hand returns '未知牌型'."""
        hand = HandRecord(hand_id=0)
        assert hand.hand_type == "未知牌型"
        assert hand.get_hand_strength() == 0

    def test_high_card(self):
        """Test high card hand type."""
        hand = HandRecord(hand_id=8)
        hand.hero_cards = [Card.parse("2h"), Card.parse("7d")]
        hand.flop = [Card.parse("4c"), Card.parse("5d"), Card.parse("9h")]
        hand.turn = Card.parse("Ts")
        hand.river = Card.parse("Qh")
        assert hand.hand_type == "高牌"
        assert hand.get_hand_strength() == 0

    def test_one_pair(self, hand_with_one_pair):
        """Test one pair hand type."""
        assert hand_with_one_pair.hand_type == "一对"
        assert hand_with_one_pair.get_hand_strength() == 1

    def test_two_pairs(self, hand_with_two_pairs):
        """Test two pairs hand type."""
        assert hand_with_two_pairs.hand_type == "两对"
        assert hand_with_two_pairs.get_hand_strength() == 2

    def test_three_of_a_kind(self, hand_with_three_of_a_kind):
        """Test three of a kind hand type."""
        assert hand_with_three_of_a_kind.hand_type == "三条"
        assert hand_with_three_of_a_kind.get_hand_strength() == 3

    def test_straight(self, hand_with_straight):
        """Test straight hand type."""
        assert hand_with_straight.hand_type == "顺子"
        assert hand_with_straight.get_hand_strength() == 4

    def test_flush(self, hand_with_flush):
        """Test flush hand type."""
        assert hand_with_flush.hand_type == "同花"
        assert hand_with_flush.get_hand_strength() == 5

    def test_full_house(self, hand_with_full_house):
        """Test full house hand type."""
        assert hand_with_full_house.hand_type == "葫芦"
        assert hand_with_full_house.get_hand_strength() == 6

    def test_four_of_a_kind(self, hand_with_four_of_a_kind):
        """Test four of a kind hand type."""
        assert hand_with_four_of_a_kind.hand_type == "四条"
        assert hand_with_four_of_a_kind.get_hand_strength() == 7

    def test_straight_flush(self, hand_with_straight_flush):
        """Test straight flush hand type."""
        assert hand_with_straight_flush.hand_type == "同花顺"
        assert hand_with_straight_flush.get_hand_strength() == 8

    def test_royal_flush(self, hand_with_royal_flush):
        """Test royal flush hand type."""
        assert hand_with_royal_flush.hand_type == "皇家同花顺"
        assert hand_with_royal_flush.get_hand_strength() == 9
