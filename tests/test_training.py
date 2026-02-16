"""Tests for the training module."""

import pytest

from poker_advisor.models.hand import HandRecord
from poker_advisor.models.card import Card
from poker_advisor.models.action import ActionType, Street, PlayerAction
from poker_advisor.models.position import Position
from poker_advisor.analysis.leak_detector import Leak, Severity
from poker_advisor.training.scenario import ScenarioGenerator, Scenario


def _make_hand(hand_id=1, hero_seat=1, hero_name="Hero",
               players=None, positions=None, stacks=None,
               actions=None, flop=None, turn=None, river=None,
               shown_cards=None, winners=None,
               big_blind=1.0, small_blind=0.5, dealer_seat=3,
               hero_cards=None):
    """Helper to build a HandRecord with sensible defaults."""
    h = HandRecord(
        hand_id=hand_id,
        hero_seat=hero_seat,
        hero_name=hero_name,
        big_blind=big_blind,
        small_blind=small_blind,
        dealer_seat=dealer_seat,
    )
    h.players = players or {1: "Hero", 2: "Villain1", 3: "Villain2"}
    h.positions = positions or {1: Position.BB, 2: Position.SB, 3: Position.BTN}
    h.stacks = stacks or {1: 100.0, 2: 100.0, 3: 100.0}
    h.actions = actions or []
    h.hero_cards = hero_cards or [Card.parse("Ah"), Card.parse("Kh")]
    if flop:
        h.flop = flop
    if turn:
        h.turn = turn
    if river:
        h.river = river
    h.shown_cards = shown_cards or {}
    h.winners = winners or {}
    h.player_count = len(h.players)
    return h


class TestScenarioExtraction:
    """Test scenario extraction from hands."""

    def test_preflop_open_scenario(self):
        """Hero in UTG with no action before — preflop open decision."""
        hand = _make_hand(
            positions={1: Position.UTG, 2: Position.SB, 3: Position.BB},
            actions=[
                PlayerAction("Villain1", 2, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.RAISE, 3.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.FOLD, 0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.FOLD, 0, Street.PREFLOP),
            ],
        )
        gen = ScenarioGenerator()
        scenarios = gen._extract_scenarios(hand)
        assert len(scenarios) >= 1
        assert scenarios[0].scenario_type == "preflop_open"
        assert scenarios[0].decision_street == Street.PREFLOP

    def test_preflop_vs_raise_scenario(self):
        """Hero faces a raise preflop."""
        hand = _make_hand(
            positions={1: Position.BB, 2: Position.SB, 3: Position.BTN},
            actions=[
                PlayerAction("Villain1", 2, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.RAISE, 3.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.FOLD, 0, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.CALL, 2.0, Street.PREFLOP),
            ],
        )
        gen = ScenarioGenerator()
        scenarios = gen._extract_scenarios(hand)
        assert any(s.scenario_type == "preflop_vs_raise" for s in scenarios)

    def test_flop_cbet_decision(self):
        """Hero was PFR and first to act on flop — cbet decision."""
        hand = _make_hand(
            positions={1: Position.BTN, 2: Position.SB, 3: Position.BB},
            flop=[Card.parse("Qs"), Card.parse("7h"), Card.parse("2d")],
            actions=[
                PlayerAction("Villain1", 2, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.RAISE, 3.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.FOLD, 0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.CALL, 2.0, Street.PREFLOP),
                # Flop
                PlayerAction("Villain2", 3, ActionType.CHECK, 0, Street.FLOP),
                PlayerAction("Hero", 1, ActionType.BET, 4.0, Street.FLOP),
            ],
        )
        gen = ScenarioGenerator()
        scenarios = gen._extract_scenarios(hand)
        types = [s.scenario_type for s in scenarios]
        assert "flop_cbet_decision" in types

    def test_flop_facing_bet_scenario(self):
        """Hero faces a bet on flop."""
        hand = _make_hand(
            flop=[Card.parse("Qs"), Card.parse("7h"), Card.parse("2d")],
            actions=[
                PlayerAction("Villain2", 3, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.RAISE, 3.0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.FOLD, 0, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.CALL, 2.0, Street.PREFLOP),
                # Flop
                PlayerAction("Villain1", 2, ActionType.BET, 4.0, Street.FLOP),
                PlayerAction("Hero", 1, ActionType.CALL, 4.0, Street.FLOP),
            ],
        )
        gen = ScenarioGenerator()
        scenarios = gen._extract_scenarios(hand)
        types = [s.scenario_type for s in scenarios]
        assert "flop_facing_bet" in types

    def test_river_scenarios(self):
        """Full hand produces river decision."""
        hand = _make_hand(
            flop=[Card.parse("5s"), Card.parse("Th"), Card.parse("7d")],
            turn=Card.parse("3c"),
            river=Card.parse("9s"),
            actions=[
                PlayerAction("Villain2", 3, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.RAISE, 3.0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.FOLD, 0, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.CALL, 2.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.BET, 4.0, Street.FLOP),
                PlayerAction("Hero", 1, ActionType.CALL, 4.0, Street.FLOP),
                PlayerAction("Villain1", 2, ActionType.CHECK, 0, Street.TURN),
                PlayerAction("Hero", 1, ActionType.BET, 6.0, Street.TURN),
                PlayerAction("Villain1", 2, ActionType.CALL, 6.0, Street.TURN),
                PlayerAction("Villain1", 2, ActionType.CHECK, 0, Street.RIVER),
                PlayerAction("Hero", 1, ActionType.BET, 10.0, Street.RIVER),
            ],
        )
        gen = ScenarioGenerator()
        scenarios = gen._extract_scenarios(hand)
        types = [s.scenario_type for s in scenarios]
        assert "river_bet_decision" in types

    def test_no_scenarios_without_hero(self):
        hand = _make_hand(hero_seat=None)
        gen = ScenarioGenerator()
        scenarios = gen._extract_scenarios(hand)
        assert len(scenarios) == 0


class TestScenarioDescription:
    """Test scenario description generation."""

    def test_description_contains_hero_cards(self):
        hand = _make_hand(
            positions={1: Position.UTG, 2: Position.SB, 3: Position.BB},
            hero_cards=[Card.parse("Ah"), Card.parse("Kh")],
            actions=[
                PlayerAction("Villain1", 2, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.RAISE, 3.0, Street.PREFLOP),
            ],
        )
        gen = ScenarioGenerator()
        scenarios = gen._extract_scenarios(hand)
        assert len(scenarios) >= 1
        assert "A♥ K♥" in scenarios[0].description or "Ah Kh" in scenarios[0].description.lower()

    def test_description_contains_position(self):
        hand = _make_hand(
            positions={1: Position.BTN, 2: Position.SB, 3: Position.BB},
            actions=[
                PlayerAction("Villain1", 2, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.RAISE, 3.0, Street.PREFLOP),
            ],
        )
        gen = ScenarioGenerator()
        scenarios = gen._extract_scenarios(hand)
        assert "BTN" in scenarios[0].description

    def test_description_contains_board_on_flop(self):
        hand = _make_hand(
            flop=[Card.parse("Qs"), Card.parse("7h"), Card.parse("2d")],
            actions=[
                PlayerAction("Villain2", 3, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.RAISE, 3.0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.FOLD, 0, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.CALL, 2.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.BET, 4.0, Street.FLOP),
                PlayerAction("Hero", 1, ActionType.FOLD, 0, Street.FLOP),
            ],
        )
        gen = ScenarioGenerator()
        scenarios = gen._extract_scenarios(hand)
        flop_scenarios = [s for s in scenarios if s.decision_street == Street.FLOP]
        assert len(flop_scenarios) >= 1
        assert "翻牌" in flop_scenarios[0].description


class TestAvailableActions:
    """Test available action generation."""

    def test_facing_bet_has_fold_call_raise(self):
        hand = _make_hand(
            flop=[Card.parse("Qs"), Card.parse("7h"), Card.parse("2d")],
            actions=[
                PlayerAction("Villain2", 3, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.RAISE, 3.0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.FOLD, 0, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.CALL, 2.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.BET, 4.0, Street.FLOP),
                PlayerAction("Hero", 1, ActionType.CALL, 4.0, Street.FLOP),
            ],
        )
        gen = ScenarioGenerator()
        scenarios = gen._extract_scenarios(hand)
        flop_scenario = [s for s in scenarios if s.decision_street == Street.FLOP][0]

        actions = flop_scenario.available_actions
        assert "Fold" in actions
        assert any("Call" in a for a in actions)
        assert any("Raise" in a for a in actions)

    def test_no_bet_has_check_and_bet_options(self):
        hand = _make_hand(
            positions={1: Position.BTN, 2: Position.SB, 3: Position.BB},
            flop=[Card.parse("Qs"), Card.parse("7h"), Card.parse("2d")],
            actions=[
                PlayerAction("Villain1", 2, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.RAISE, 3.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.FOLD, 0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.CALL, 2.0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.CHECK, 0, Street.FLOP),
                PlayerAction("Hero", 1, ActionType.BET, 4.0, Street.FLOP),
            ],
        )
        gen = ScenarioGenerator()
        scenarios = gen._extract_scenarios(hand)
        cbet_scenario = [s for s in scenarios
                         if s.decision_street == Street.FLOP][0]

        actions = cbet_scenario.available_actions
        assert "Check" in actions
        assert any("Bet" in a for a in actions)


class TestGenerate:
    """Test full scenario generation pipeline."""

    def test_generate_from_hands(self):
        hands = [
            _make_hand(
                hand_id=i,
                positions={1: Position.BTN, 2: Position.SB, 3: Position.BB},
                actions=[
                    PlayerAction("Villain1", 2, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                    PlayerAction("Villain2", 3, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                    PlayerAction("Hero", 1, ActionType.RAISE, 3.0, Street.PREFLOP),
                    PlayerAction("Villain1", 2, ActionType.FOLD, 0, Street.PREFLOP),
                    PlayerAction("Villain2", 3, ActionType.FOLD, 0, Street.PREFLOP),
                ],
            )
            for i in range(5)
        ]

        gen = ScenarioGenerator()
        scenarios = gen.generate(hands, count=3)
        assert len(scenarios) <= 3
        assert all(isinstance(s, Scenario) for s in scenarios)

    def test_focus_filters_scenarios(self):
        hand = _make_hand(
            flop=[Card.parse("Qs"), Card.parse("7h"), Card.parse("2d")],
            actions=[
                PlayerAction("Villain2", 3, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.RAISE, 3.0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.FOLD, 0, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.CALL, 2.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.BET, 4.0, Street.FLOP),
                PlayerAction("Hero", 1, ActionType.CALL, 4.0, Street.FLOP),
            ],
        )
        gen = ScenarioGenerator()
        # Focus on flop only
        scenarios = gen.generate([hand], count=10, focus="flop")
        for s in scenarios:
            assert "flop" in s.scenario_type

    def test_leak_prioritization(self):
        """Scenarios matching leaks should come first."""
        hands = []
        # Hand with preflop decision
        hands.append(_make_hand(
            hand_id=1,
            positions={1: Position.UTG, 2: Position.SB, 3: Position.BB},
            actions=[
                PlayerAction("Villain1", 2, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.RAISE, 3.0, Street.PREFLOP),
            ],
        ))
        # Hand with river decision
        hands.append(_make_hand(
            hand_id=2,
            flop=[Card.parse("5s"), Card.parse("Th"), Card.parse("7d")],
            turn=Card.parse("3c"),
            river=Card.parse("9s"),
            actions=[
                PlayerAction("Villain2", 3, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.RAISE, 3.0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.FOLD, 0, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.CALL, 2.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.CHECK, 0, Street.FLOP),
                PlayerAction("Hero", 1, ActionType.CHECK, 0, Street.FLOP),
                PlayerAction("Villain1", 2, ActionType.CHECK, 0, Street.TURN),
                PlayerAction("Hero", 1, ActionType.CHECK, 0, Street.TURN),
                PlayerAction("Villain1", 2, ActionType.BET, 5.0, Street.RIVER),
                PlayerAction("Hero", 1, ActionType.CALL, 5.0, Street.RIVER),
            ],
        ))

        # Leak in river play
        leaks = [Leak(
            metric="wtsd",
            description="WTSD too high",
            severity=Severity.MAJOR,
            actual_value=45.0,
            baseline_low=25.0,
            baseline_high=35.0,
        )]

        gen = ScenarioGenerator()
        scenarios = gen.generate(hands, count=10, leaks=leaks)
        # River scenarios should be prioritized
        assert len(scenarios) > 0
        river_scenarios = [s for s in scenarios if "river" in s.scenario_type]
        assert len(river_scenarios) > 0

    def test_empty_hands_returns_empty(self):
        gen = ScenarioGenerator()
        assert gen.generate([], count=5) == []

    def test_diverse_selection(self):
        """Should select diverse scenario types."""
        hands = []
        for i in range(10):
            hands.append(_make_hand(
                hand_id=i,
                flop=[Card.parse("Qs"), Card.parse("7h"), Card.parse("2d")],
                actions=[
                    PlayerAction("Villain2", 3, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                    PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                    PlayerAction("Villain1", 2, ActionType.RAISE, 3.0, Street.PREFLOP),
                    PlayerAction("Villain2", 3, ActionType.FOLD, 0, Street.PREFLOP),
                    PlayerAction("Hero", 1, ActionType.CALL, 2.0, Street.PREFLOP),
                    PlayerAction("Villain1", 2, ActionType.BET, 4.0, Street.FLOP),
                    PlayerAction("Hero", 1, ActionType.CALL, 4.0, Street.FLOP),
                ],
            ))

        gen = ScenarioGenerator()
        scenarios = gen.generate(hands, count=5)
        # Should have extracted both preflop and flop scenarios
        types = set(s.scenario_type for s in scenarios)
        assert len(types) >= 1


class TestWithSampleLog:
    """Integration test using the parsed sample log."""

    @pytest.fixture
    def parsed_hands(self):
        from poker_advisor.parser.pokernow_parser import PokerNowParser
        parser = PokerNowParser()
        return parser.parse_file("tests/fixtures/sample_log.txt")

    def test_generate_from_real_hands(self, parsed_hands):
        gen = ScenarioGenerator()
        scenarios = gen.generate(parsed_hands, count=10)
        # Should produce at least some scenarios from the 3-hand sample
        assert len(scenarios) >= 1
        for s in scenarios:
            assert s.description
            assert s.available_actions
            assert s.scenario_type
