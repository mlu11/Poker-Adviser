"""Tests for the statistics calculator."""

import pytest

from poker_advisor.models.hand import HandRecord
from poker_advisor.models.card import Card
from poker_advisor.models.action import ActionType, Street, PlayerAction
from poker_advisor.models.position import Position
from poker_advisor.analysis.calculator import StatsCalculator


def _make_hand(hand_id=1, hero_seat=1, hero_name="Hero",
               players=None, positions=None, stacks=None,
               actions=None, flop=None, turn=None, river=None,
               shown_cards=None, winners=None,
               big_blind=1.0, small_blind=0.5, dealer_seat=3):
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
    if flop:
        h.flop = flop
    if turn:
        h.turn = turn
    if river:
        h.river = river
    h.shown_cards = shown_cards or {}
    h.winners = winners or {}
    return h


class TestVPIP:
    """Test VPIP calculation."""

    def test_call_counts_as_vpip(self):
        hand = _make_hand(actions=[
            PlayerAction("Villain2", 3, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
            PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
            PlayerAction("Villain1", 2, ActionType.CALL, 1.0, Street.PREFLOP),
            PlayerAction("Villain2", 3, ActionType.CALL, 0.5, Street.PREFLOP),
            PlayerAction("Hero", 1, ActionType.CALL, 0.0, Street.PREFLOP),  # check option
        ])
        calc = StatsCalculator()
        stats = calc.calculate([hand])
        # Hero only checked (the big blind check is not voluntary)
        assert stats.overall.vpip == 0.0

    def test_raise_counts_as_vpip(self):
        hand = _make_hand(actions=[
            PlayerAction("Villain2", 3, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
            PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
            PlayerAction("Villain1", 2, ActionType.FOLD, 0, Street.PREFLOP),
            PlayerAction("Villain2", 3, ActionType.CALL, 0.5, Street.PREFLOP),
            PlayerAction("Hero", 1, ActionType.RAISE, 3.0, Street.PREFLOP),
        ])
        calc = StatsCalculator()
        stats = calc.calculate([hand])
        assert stats.overall.voluntarily_put_in_pot == 1
        assert stats.overall.vpip == 100.0

    def test_fold_not_vpip(self):
        hand = _make_hand(
            positions={1: Position.UTG, 2: Position.SB, 3: Position.BB},
            actions=[
                PlayerAction("Villain1", 2, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.FOLD, 0, Street.PREFLOP),
            ],
        )
        calc = StatsCalculator()
        stats = calc.calculate([hand])
        assert stats.overall.voluntarily_put_in_pot == 0
        assert stats.overall.vpip == 0.0

    def test_vpip_over_multiple_hands(self):
        hand1 = _make_hand(hand_id=1, actions=[
            PlayerAction("Villain2", 3, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
            PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
            PlayerAction("Villain1", 2, ActionType.FOLD, 0, Street.PREFLOP),
            PlayerAction("Villain2", 3, ActionType.CALL, 0.5, Street.PREFLOP),
            PlayerAction("Hero", 1, ActionType.RAISE, 3.0, Street.PREFLOP),
        ])
        hand2 = _make_hand(hand_id=2, positions={1: Position.UTG, 2: Position.SB, 3: Position.BB},
                           actions=[
            PlayerAction("Villain1", 2, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
            PlayerAction("Villain2", 3, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
            PlayerAction("Hero", 1, ActionType.FOLD, 0, Street.PREFLOP),
        ])
        calc = StatsCalculator()
        stats = calc.calculate([hand1, hand2])
        assert stats.overall.total_hands == 2
        assert stats.overall.voluntarily_put_in_pot == 1
        assert stats.overall.vpip == 50.0


class TestPFR:
    """Test PFR calculation."""

    def test_raise_is_pfr(self):
        hand = _make_hand(actions=[
            PlayerAction("Villain2", 3, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
            PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
            PlayerAction("Villain1", 2, ActionType.FOLD, 0, Street.PREFLOP),
            PlayerAction("Villain2", 3, ActionType.FOLD, 0, Street.PREFLOP),
            PlayerAction("Hero", 1, ActionType.RAISE, 3.0, Street.PREFLOP),
        ])
        calc = StatsCalculator()
        stats = calc.calculate([hand])
        assert stats.overall.preflop_raise == 1
        assert stats.overall.pfr == 100.0

    def test_call_is_not_pfr(self):
        hand = _make_hand(actions=[
            PlayerAction("Villain2", 3, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
            PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
            PlayerAction("Villain1", 2, ActionType.RAISE, 3.0, Street.PREFLOP),
            PlayerAction("Villain2", 3, ActionType.FOLD, 0, Street.PREFLOP),
            PlayerAction("Hero", 1, ActionType.CALL, 2.0, Street.PREFLOP),
        ])
        calc = StatsCalculator()
        stats = calc.calculate([hand])
        assert stats.overall.preflop_raise == 0
        assert stats.overall.pfr == 0.0


class TestThreeBet:
    """Test 3-bet calculation."""

    def test_3bet_opportunity_and_taken(self):
        hand = _make_hand(
            positions={1: Position.BB, 2: Position.SB, 3: Position.BTN},
            actions=[
                PlayerAction("Villain1", 2, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.RAISE, 3.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.FOLD, 0, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.RAISE, 9.0, Street.PREFLOP),
            ],
        )
        calc = StatsCalculator()
        stats = calc.calculate([hand])
        assert stats.overall.three_bet_opportunities == 1
        assert stats.overall.three_bet_made == 1
        assert stats.overall.three_bet_pct == 100.0

    def test_3bet_opportunity_declined(self):
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
        calc = StatsCalculator()
        stats = calc.calculate([hand])
        assert stats.overall.three_bet_opportunities == 1
        assert stats.overall.three_bet_made == 0

    def test_no_3bet_opportunity_when_no_raise(self):
        hand = _make_hand(actions=[
            PlayerAction("Villain2", 3, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
            PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
            PlayerAction("Villain1", 2, ActionType.CALL, 1.0, Street.PREFLOP),
            PlayerAction("Villain2", 3, ActionType.CALL, 0.5, Street.PREFLOP),
            PlayerAction("Hero", 1, ActionType.RAISE, 4.0, Street.PREFLOP),
        ])
        calc = StatsCalculator()
        stats = calc.calculate([hand])
        # Hero's raise here is a raise, not a 3-bet (no prior raise)
        assert stats.overall.three_bet_opportunities == 0


class TestAggression:
    """Test aggression factor calculation."""

    def test_aggression_factor(self):
        hand = _make_hand(
            flop=[Card.parse("Ah"), Card.parse("Kd"), Card.parse("5c")],
            actions=[
                PlayerAction("Villain2", 3, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.RAISE, 3.0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.FOLD, 0, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.CALL, 2.0, Street.PREFLOP),
                # Flop
                PlayerAction("Hero", 1, ActionType.BET, 4.0, Street.FLOP),
                PlayerAction("Villain1", 2, ActionType.CALL, 4.0, Street.FLOP),
            ],
        )
        calc = StatsCalculator()
        stats = calc.calculate([hand])
        # Hero: 1 bet, 0 raises, 0 calls postflop => AF = (1+0)/0 = inf
        # But preflop actions don't count for AF
        assert stats.overall.bets == 1
        assert stats.overall.calls == 0
        assert stats.overall.aggression_factor == float('inf')

    def test_af_with_calls(self):
        hand = _make_hand(
            flop=[Card.parse("Ah"), Card.parse("Kd"), Card.parse("5c")],
            turn=Card.parse("2s"),
            actions=[
                PlayerAction("Villain2", 3, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.RAISE, 3.0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.FOLD, 0, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.CALL, 2.0, Street.PREFLOP),
                # Flop
                PlayerAction("Villain1", 2, ActionType.BET, 4.0, Street.FLOP),
                PlayerAction("Hero", 1, ActionType.CALL, 4.0, Street.FLOP),
                # Turn
                PlayerAction("Villain1", 2, ActionType.BET, 8.0, Street.TURN),
                PlayerAction("Hero", 1, ActionType.RAISE, 20.0, Street.TURN),
            ],
        )
        calc = StatsCalculator()
        stats = calc.calculate([hand])
        # Postflop: 0 bets + 1 raise = 1 aggressive, 1 call => AF = 1/1 = 1.0
        assert stats.overall.bets == 0
        assert stats.overall.raises == 1
        assert stats.overall.calls == 1
        assert stats.overall.aggression_factor == 1.0


class TestCBet:
    """Test continuation bet calculations."""

    def test_cbet_made(self):
        hand = _make_hand(
            flop=[Card.parse("Ah"), Card.parse("Kd"), Card.parse("5c")],
            actions=[
                PlayerAction("Villain2", 3, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.FOLD, 0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.CALL, 0.5, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.RAISE, 3.0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.CALL, 2.0, Street.PREFLOP),
                # Flop — hero raised preflop, now bets = c-bet
                PlayerAction("Villain2", 3, ActionType.CHECK, 0, Street.FLOP),
                PlayerAction("Hero", 1, ActionType.BET, 4.0, Street.FLOP),
            ],
        )
        calc = StatsCalculator()
        stats = calc.calculate([hand])
        assert stats.overall.cbet_opportunities == 1
        assert stats.overall.cbet_made == 1
        assert stats.overall.cbet_pct == 100.0

    def test_cbet_missed(self):
        hand = _make_hand(
            flop=[Card.parse("Ah"), Card.parse("Kd"), Card.parse("5c")],
            actions=[
                PlayerAction("Villain2", 3, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.FOLD, 0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.CALL, 0.5, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.RAISE, 3.0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.CALL, 2.0, Street.PREFLOP),
                # Flop — hero checks instead of c-betting
                PlayerAction("Villain2", 3, ActionType.CHECK, 0, Street.FLOP),
                PlayerAction("Hero", 1, ActionType.CHECK, 0, Street.FLOP),
            ],
        )
        calc = StatsCalculator()
        stats = calc.calculate([hand])
        assert stats.overall.cbet_opportunities == 1
        assert stats.overall.cbet_made == 0
        assert stats.overall.cbet_pct == 0.0

    def test_no_cbet_opportunity_when_not_pfr(self):
        hand = _make_hand(
            flop=[Card.parse("Ah"), Card.parse("Kd"), Card.parse("5c")],
            actions=[
                PlayerAction("Villain2", 3, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.RAISE, 3.0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.FOLD, 0, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.CALL, 2.0, Street.PREFLOP),
                # Flop
                PlayerAction("Hero", 1, ActionType.CHECK, 0, Street.FLOP),
                PlayerAction("Villain1", 2, ActionType.BET, 4.0, Street.FLOP),
            ],
        )
        calc = StatsCalculator()
        stats = calc.calculate([hand])
        assert stats.overall.cbet_opportunities == 0


class TestFoldToCBet:
    """Test fold to c-bet calculations."""

    def test_fold_to_cbet(self):
        hand = _make_hand(
            flop=[Card.parse("Ah"), Card.parse("Kd"), Card.parse("5c")],
            actions=[
                PlayerAction("Villain2", 3, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.RAISE, 3.0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.FOLD, 0, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.CALL, 2.0, Street.PREFLOP),
                # Flop — villain (PFR) c-bets, hero folds
                PlayerAction("Hero", 1, ActionType.CHECK, 0, Street.FLOP),
                PlayerAction("Villain1", 2, ActionType.BET, 4.0, Street.FLOP),
                PlayerAction("Hero", 1, ActionType.FOLD, 0, Street.FLOP),
            ],
        )
        calc = StatsCalculator()
        stats = calc.calculate([hand])
        assert stats.overall.faced_cbet == 1
        assert stats.overall.folded_to_cbet == 1

    def test_call_cbet(self):
        hand = _make_hand(
            flop=[Card.parse("Ah"), Card.parse("Kd"), Card.parse("5c")],
            actions=[
                PlayerAction("Villain2", 3, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.RAISE, 3.0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.FOLD, 0, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.CALL, 2.0, Street.PREFLOP),
                # Flop — villain (PFR) c-bets, hero calls
                PlayerAction("Hero", 1, ActionType.CHECK, 0, Street.FLOP),
                PlayerAction("Villain1", 2, ActionType.BET, 4.0, Street.FLOP),
                PlayerAction("Hero", 1, ActionType.CALL, 4.0, Street.FLOP),
            ],
        )
        calc = StatsCalculator()
        stats = calc.calculate([hand])
        assert stats.overall.faced_cbet == 1
        assert stats.overall.folded_to_cbet == 0


class TestShowdown:
    """Test showdown stats."""

    def test_went_to_showdown(self):
        hand = _make_hand(
            flop=[Card.parse("5s"), Card.parse("Th"), Card.parse("7d")],
            turn=Card.parse("3c"),
            river=Card.parse("9s"),
            shown_cards={1: [Card.parse("Jh"), Card.parse("Js")],
                         2: [Card.parse("Ah"), Card.parse("Kh")]},
            winners={2: 10.0},
            actions=[
                PlayerAction("Villain2", 3, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.RAISE, 3.0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.FOLD, 0, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.CALL, 2.0, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.BET, 2.0, Street.FLOP),
                PlayerAction("Villain1", 2, ActionType.CALL, 2.0, Street.FLOP),
                PlayerAction("Hero", 1, ActionType.BET, 2.0, Street.TURN),
                PlayerAction("Villain1", 2, ActionType.CALL, 2.0, Street.TURN),
                PlayerAction("Hero", 1, ActionType.BET, 2.0, Street.RIVER),
                PlayerAction("Villain1", 2, ActionType.CALL, 2.0, Street.RIVER),
            ],
        )
        calc = StatsCalculator()
        stats = calc.calculate([hand])
        assert stats.overall.saw_flop == 1
        assert stats.overall.went_to_showdown == 1
        assert stats.overall.won_at_showdown == 0  # hero lost
        assert stats.overall.wtsd == 100.0
        assert stats.overall.wsd == 0.0

    def test_won_at_showdown(self):
        hand = _make_hand(
            flop=[Card.parse("5s"), Card.parse("Th"), Card.parse("7d")],
            turn=Card.parse("3c"),
            river=Card.parse("9s"),
            shown_cards={1: [Card.parse("Ah"), Card.parse("As")],
                         2: [Card.parse("Kh"), Card.parse("Ks")]},
            winners={1: 10.0},
            actions=[
                PlayerAction("Villain2", 3, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.RAISE, 3.0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.FOLD, 0, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.CALL, 2.0, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.CHECK, 0, Street.FLOP),
                PlayerAction("Villain1", 2, ActionType.CHECK, 0, Street.FLOP),
                PlayerAction("Hero", 1, ActionType.CHECK, 0, Street.TURN),
                PlayerAction("Villain1", 2, ActionType.CHECK, 0, Street.TURN),
                PlayerAction("Hero", 1, ActionType.CHECK, 0, Street.RIVER),
                PlayerAction("Villain1", 2, ActionType.CHECK, 0, Street.RIVER),
            ],
        )
        calc = StatsCalculator()
        stats = calc.calculate([hand])
        assert stats.overall.went_to_showdown == 1
        assert stats.overall.won_at_showdown == 1
        assert stats.overall.wsd == 100.0


class TestPositionalBreakdown:
    """Test that stats are tracked per position."""

    def test_stats_by_position(self):
        hand_btn = _make_hand(
            hand_id=1,
            positions={1: Position.BTN, 2: Position.SB, 3: Position.BB},
            actions=[
                PlayerAction("Villain1", 2, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.RAISE, 3.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.FOLD, 0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.FOLD, 0, Street.PREFLOP),
            ],
            winners={1: 1.5},
        )
        hand_bb = _make_hand(
            hand_id=2,
            positions={1: Position.BB, 2: Position.SB, 3: Position.BTN},
            actions=[
                PlayerAction("Villain1", 2, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.FOLD, 0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.FOLD, 0, Street.PREFLOP),
            ],
        )

        calc = StatsCalculator()
        stats = calc.calculate([hand_btn, hand_bb])

        assert stats.overall.total_hands == 2
        assert Position.BTN in stats.by_position
        assert Position.BB in stats.by_position
        assert stats.by_position[Position.BTN].total_hands == 1
        assert stats.by_position[Position.BTN].pfr == 100.0
        assert stats.by_position[Position.BB].total_hands == 1
        assert stats.by_position[Position.BB].pfr == 0.0


class TestProfit:
    """Test profit/loss tracking."""

    def test_profit_calculation(self):
        hand = _make_hand(
            winners={1: 10.0},
            actions=[
                PlayerAction("Villain2", 3, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.FOLD, 0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.CALL, 0.5, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.RAISE, 3.0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.CALL, 2.0, Street.PREFLOP),
            ],
        )
        calc = StatsCalculator()
        stats = calc.calculate([hand])
        # Hero invested: 1.0 (blind) + 3.0 (raise) = 4.0, won 10.0
        assert stats.total_profit == pytest.approx(6.0)

    def test_loss_calculation(self):
        hand = _make_hand(
            winners={2: 10.0},
            actions=[
                PlayerAction("Villain2", 3, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.RAISE, 3.0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.FOLD, 0, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.CALL, 2.0, Street.PREFLOP),
            ],
        )
        calc = StatsCalculator()
        stats = calc.calculate([hand])
        # Hero invested: 1.0 (blind) + 2.0 (call) = 3.0, won 0
        assert stats.total_profit == pytest.approx(-3.0)

    def test_bb_per_100(self):
        hands = []
        for i in range(100):
            w = {1: 2.0} if i % 2 == 0 else {2: 2.0}
            hands.append(_make_hand(
                hand_id=i,
                winners=w,
                actions=[
                    PlayerAction("Villain2", 3, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                    PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                    PlayerAction("Villain1", 2, ActionType.FOLD, 0, Street.PREFLOP),
                    PlayerAction("Villain2", 3, ActionType.FOLD, 0, Street.PREFLOP),
                ],
            ))
        calc = StatsCalculator()
        stats = calc.calculate(hands)
        # Half the time win 2.0 (invested 1.0 = +1.0), half lose 1.0
        # Net = 50 * 1.0 - 50 * 1.0 = 0
        assert stats.bb_per_100 == pytest.approx(0.0)


class TestHeroNameResolution:
    """Test hero name-based resolution."""

    def test_by_hero_name(self):
        hand = _make_hand(
            hero_seat=None,  # no hero seat set
            hero_name=None,
            actions=[
                PlayerAction("Villain2", 3, ActionType.POST_BLIND, 0.5, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.POST_BLIND, 1.0, Street.PREFLOP),
                PlayerAction("Villain1", 2, ActionType.RAISE, 3.0, Street.PREFLOP),
                PlayerAction("Villain2", 3, ActionType.FOLD, 0, Street.PREFLOP),
                PlayerAction("Hero", 1, ActionType.CALL, 2.0, Street.PREFLOP),
            ],
        )
        calc = StatsCalculator()
        stats = calc.calculate([hand], hero_name="Hero")
        assert stats.player_name == "Hero"
        assert stats.overall.total_hands == 1
        assert stats.overall.vpip == 100.0

    def test_empty_hands(self):
        calc = StatsCalculator()
        stats = calc.calculate([])
        assert stats.overall.total_hands == 0


class TestWithSampleLog:
    """Integration test using the parsed sample log."""

    @pytest.fixture
    def parsed_hands(self):
        from poker_advisor.parser.pokernow_parser import PokerNowParser
        parser = PokerNowParser()
        return parser.parse_file("tests/fixtures/sample_log.txt")

    def test_calculate_from_parsed(self, parsed_hands):
        calc = StatsCalculator()
        stats = calc.calculate(parsed_hands)
        assert stats.overall.total_hands == 3
        # The hero has cards in all 3 hands, so should process all 3
        assert stats.player_name != ""
