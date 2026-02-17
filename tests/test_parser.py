"""Tests for Poker Now log parser."""

import os
import pytest
from poker_advisor.parser.pokernow_parser import PokerNowParser
from poker_advisor.models.action import ActionType, Street
from poker_advisor.models.position import Position

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def parser():
    return PokerNowParser()


@pytest.fixture
def sample_hands(parser):
    filepath = os.path.join(FIXTURE_DIR, "sample_log.txt")
    return parser.parse_file(filepath)


class TestParserBasic:
    def test_parses_correct_number_of_hands(self, sample_hands):
        assert len(sample_hands) == 3

    def test_hand_ids_sequential(self, sample_hands):
        ids = [h.hand_id for h in sample_hands]
        assert ids == [1, 2, 3]

    def test_players_parsed(self, sample_hands):
        hand1 = sample_hands[0]
        assert len(hand1.players) == 3
        assert "Player1" in hand1.players.values()
        assert "Player2" in hand1.players.values()
        assert "Player3" in hand1.players.values()

    def test_stacks_parsed(self, sample_hands):
        hand1 = sample_hands[0]
        for seat, stack in hand1.stacks.items():
            assert stack == 100.00

    def test_hero_cards_parsed(self, sample_hands):
        hand1 = sample_hands[0]
        assert len(hand1.hero_cards) == 2
        card_strs = [c.to_short() for c in hand1.hero_cards]
        assert "Js" in card_strs
        assert "Jh" in card_strs

    def test_blinds_parsed(self, sample_hands):
        hand1 = sample_hands[0]
        blind_actions = [a for a in hand1.actions if a.action_type == ActionType.POST_BLIND]
        assert len(blind_actions) == 2
        amounts = sorted([a.amount for a in blind_actions])
        assert amounts == [0.50, 1.00]


class TestParserActions:
    def test_preflop_actions(self, sample_hands):
        hand1 = sample_hands[0]
        preflop = hand1.actions_on_street(Street.PREFLOP)
        # Blinds + player actions
        non_blind = [a for a in preflop if a.action_type != ActionType.POST_BLIND]
        assert len(non_blind) >= 2  # At least calls/raises/folds

    def test_flop_actions(self, sample_hands):
        hand1 = sample_hands[0]
        flop_actions = hand1.actions_on_street(Street.FLOP)
        assert len(flop_actions) >= 1

    def test_raise_parsed(self, sample_hands):
        hand1 = sample_hands[0]
        raises = [a for a in hand1.actions if a.action_type == ActionType.RAISE]
        assert len(raises) >= 1
        assert raises[0].amount == 2.00

    def test_fold_parsed(self, sample_hands):
        hand1 = sample_hands[0]
        folds = [a for a in hand1.actions if a.action_type == ActionType.FOLD]
        assert len(folds) >= 1


class TestParserCommunityCards:
    def test_flop_parsed(self, sample_hands):
        hand1 = sample_hands[0]
        assert len(hand1.flop) == 3
        flop_strs = [c.to_short() for c in hand1.flop]
        assert "5s" in flop_strs
        assert "Th" in flop_strs
        assert "7d" in flop_strs

    def test_turn_parsed(self, sample_hands):
        hand1 = sample_hands[0]
        assert hand1.turn is not None
        assert hand1.turn.to_short() == "3c"

    def test_river_parsed(self, sample_hands):
        hand1 = sample_hands[0]
        assert hand1.river is not None
        assert hand1.river.to_short() == "9s"

    def test_board_property(self, sample_hands):
        hand1 = sample_hands[0]
        assert len(hand1.board) == 5


class TestParserShowdown:
    def test_shown_cards_parsed(self, sample_hands):
        hand1 = sample_hands[0]
        assert len(hand1.shown_cards) >= 1

    def test_winner_parsed(self, sample_hands):
        hand1 = sample_hands[0]
        assert len(hand1.winners) >= 1
        # Player2 won hand #1
        winner_names = [hand1.players[s] for s in hand1.winners]
        assert "Player2" in winner_names


class TestParserPositions:
    def test_dealer_set(self, sample_hands):
        hand1 = sample_hands[0]
        assert hand1.dealer_seat > 0
        assert hand1.players[hand1.dealer_seat] == "Player2"

    def test_positions_assigned(self, sample_hands):
        hand1 = sample_hands[0]
        assert len(hand1.positions) == 3
        positions = set(hand1.positions.values())
        assert Position.BTN in positions
        assert Position.SB in positions
        assert Position.BB in positions


class TestParserMultipleHands:
    def test_hand2_preflop_only(self, sample_hands):
        hand2 = sample_hands[1]
        assert len(hand2.flop) == 0
        assert hand2.turn is None
        assert hand2.river is None

    def test_hand2_hero_cards(self, sample_hands):
        hand2 = sample_hands[1]
        card_strs = [c.to_short() for c in hand2.hero_cards]
        assert "Ks" in card_strs
        assert "Qs" in card_strs

    def test_hand3_flop_only(self, sample_hands):
        hand3 = sample_hands[2]
        assert len(hand3.flop) == 3
        assert hand3.turn is None

    def test_hand3_hero_cards(self, sample_hands):
        hand3 = sample_hands[2]
        card_strs = [c.to_short() for c in hand3.hero_cards]
        assert "Ah" in card_strs
        assert "Ad" in card_strs


@pytest.fixture
def csv_hands(parser):
    filepath = os.path.join(FIXTURE_DIR, "sample_log_csv.csv")
    return parser.parse_file(filepath)


class TestParserNewFormatBasic:
    """Tests for the new CSV format parsing."""

    def test_csv_parses_correct_number_of_hands(self, csv_hands):
        assert len(csv_hands) == 3

    def test_csv_hand_ids_sequential(self, csv_hands):
        ids = [h.hand_id for h in csv_hands]
        assert ids == [1, 2, 3]

    def test_csv_players_parsed(self, csv_hands):
        hand1 = csv_hands[0]
        assert len(hand1.players) == 3
        assert "PlayerA @ ID_A" in hand1.players.values()
        assert "PlayerB @ ID_B" in hand1.players.values()
        assert "PlayerC @ ID_C" in hand1.players.values()

    def test_csv_stacks_parsed(self, csv_hands):
        hand1 = csv_hands[0]
        # New format: integer amounts without $
        assert hand1.stacks[1] == 10000.0
        assert hand1.stacks[5] == 8000.0
        assert hand1.stacks[9] == 12000.0

    def test_csv_seat_mapping(self, csv_hands):
        hand1 = csv_hands[0]
        assert hand1.players[1] == "PlayerA @ ID_A"
        assert hand1.players[5] == "PlayerB @ ID_B"
        assert hand1.players[9] == "PlayerC @ ID_C"


class TestParserNewFormatHeroCards:
    def test_csv_hero_cards_hand1(self, csv_hands):
        hand1 = csv_hands[0]
        assert len(hand1.hero_cards) == 2
        card_strs = [c.to_short() for c in hand1.hero_cards]
        assert "As" in card_strs
        assert "Tc" in card_strs  # 10♣ should parse to Tc

    def test_csv_hero_cards_hand2(self, csv_hands):
        hand2 = csv_hands[1]
        card_strs = [c.to_short() for c in hand2.hero_cards]
        assert "5s" in card_strs
        assert "9d" in card_strs

    def test_csv_hero_cards_hand3(self, csv_hands):
        hand3 = csv_hands[2]
        card_strs = [c.to_short() for c in hand3.hero_cards]
        assert "Qd" in card_strs
        assert "Jc" in card_strs


class TestParserNewFormatActions:
    def test_csv_blinds_parsed(self, csv_hands):
        hand1 = csv_hands[0]
        blind_actions = [a for a in hand1.actions if a.action_type == ActionType.POST_BLIND]
        assert len(blind_actions) == 2
        amounts = sorted([a.amount for a in blind_actions])
        assert amounts == [10.0, 20.0]

    def test_csv_fold_parsed(self, csv_hands):
        hand1 = csv_hands[0]
        folds = [a for a in hand1.actions if a.action_type == ActionType.FOLD]
        assert len(folds) >= 1

    def test_csv_raise_parsed(self, csv_hands):
        hand1 = csv_hands[0]
        raises = [a for a in hand1.actions if a.action_type == ActionType.RAISE]
        assert len(raises) >= 1

    def test_csv_all_in_detected(self, csv_hands):
        hand1 = csv_hands[0]
        allin_actions = [a for a in hand1.actions if a.is_all_in]
        assert len(allin_actions) >= 1
        assert allin_actions[0].amount == 2299.0

    def test_csv_actions_have_correct_seats(self, csv_hands):
        hand1 = csv_hands[0]
        for action in hand1.actions:
            assert action.seat in hand1.players, f"Action seat {action.seat} not in players"

    def test_csv_call_parsed(self, csv_hands):
        hand2 = csv_hands[1]
        calls = [a for a in hand2.actions if a.action_type == ActionType.CALL]
        assert len(calls) >= 1


class TestParserNewFormatCommunityCards:
    def test_csv_flop_parsed(self, csv_hands):
        hand2 = csv_hands[1]
        assert len(hand2.flop) == 3
        flop_strs = [c.to_short() for c in hand2.flop]
        assert "Qs" in flop_strs
        assert "2c" in flop_strs
        assert "Jd" in flop_strs

    def test_csv_turn_parsed(self, csv_hands):
        """Turn in new format: Q♠, 2♣, J♦ [4♣] — only 4♣ is the turn card."""
        hand2 = csv_hands[1]
        assert hand2.turn is not None
        assert hand2.turn.to_short() == "4c"

    def test_csv_river_parsed(self, csv_hands):
        """River in new format: Q♠, 2♣, J♦, 4♣ [8♠] — only 8♠ is the river card."""
        hand2 = csv_hands[1]
        assert hand2.river is not None
        assert hand2.river.to_short() == "8s"

    def test_csv_flop_with_10(self, csv_hands):
        """Hand 3 has 10♣ on the flop — should parse as T♣."""
        hand3 = csv_hands[2]
        assert len(hand3.flop) == 3
        flop_strs = [c.to_short() for c in hand3.flop]
        assert "Tc" in flop_strs
        assert "5h" in flop_strs
        assert "Jh" in flop_strs

    def test_csv_board_complete(self, csv_hands):
        hand2 = csv_hands[1]
        assert len(hand2.board) == 5


class TestParserNewFormatShowdown:
    def test_csv_winner_parsed(self, csv_hands):
        hand1 = csv_hands[0]
        assert len(hand1.winners) >= 1
        winner_names = [hand1.players[s] for s in hand1.winners]
        assert "PlayerA @ ID_A" in winner_names

    def test_csv_pot_amount(self, csv_hands):
        hand1 = csv_hands[0]
        assert hand1.pot_total == 60.0

    def test_csv_winner_with_hand_description(self, csv_hands):
        """New format: collected X from pot with Two Pair, ..."""
        hand2 = csv_hands[1]
        winner_names = [hand2.players[s] for s in hand2.winners]
        assert "PlayerA @ ID_A" in winner_names
        assert hand2.winners[1] == 50.0

    def test_csv_shown_cards_after_ending(self, csv_hands):
        """Show cards appear after ending hand in new format."""
        hand2 = csv_hands[1]
        assert len(hand2.shown_cards) >= 1
        # PlayerA showed 4♥, 8♥
        if 1 in hand2.shown_cards:
            card_strs = [c.to_short() for c in hand2.shown_cards[1]]
            assert "4h" in card_strs
            assert "8h" in card_strs


class TestParserNewFormatPositions:
    def test_csv_dealer_set(self, csv_hands):
        hand1 = csv_hands[0]
        assert hand1.dealer_seat > 0
        assert hand1.players[hand1.dealer_seat] == "PlayerC @ ID_C"

    def test_csv_positions_assigned(self, csv_hands):
        hand1 = csv_hands[0]
        assert len(hand1.positions) == 3
        positions = set(hand1.positions.values())
        assert Position.BTN in positions
        assert Position.SB in positions
        assert Position.BB in positions


class TestHandRecord:
    def test_streets_seen(self, sample_hands):
        hand1 = sample_hands[0]
        assert Street.PREFLOP in hand1.streets_seen
        assert Street.FLOP in hand1.streets_seen
        assert Street.TURN in hand1.streets_seen
        assert Street.RIVER in hand1.streets_seen

    def test_summary(self, sample_hands):
        hand1 = sample_hands[0]
        summary = hand1.summary()
        assert "Hand #1" in summary

    def test_went_to_showdown(self, sample_hands):
        hand1 = sample_hands[0]
        assert hand1.went_to_showdown

    def test_hand2_no_showdown(self, sample_hands):
        hand2 = sample_hands[1]
        assert not hand2.went_to_showdown
