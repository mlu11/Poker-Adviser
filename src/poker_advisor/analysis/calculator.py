"""Core statistics calculator for poker hand analysis."""

from typing import List, Optional

from poker_advisor.models.hand import HandRecord
from poker_advisor.models.action import ActionType, Street, PlayerAction
from poker_advisor.models.position import Position
from poker_advisor.models.stats import PlayerStats, PositionalStats


class StatsCalculator:
    """Calculate poker statistics from a list of hand records.

    All calculations are from the hero's perspective. The hero is identified
    by hero_seat on each HandRecord.
    """

    def calculate(self, hands: List[HandRecord],
                  hero_name: Optional[str] = None) -> PlayerStats:
        """Calculate aggregate stats for the hero across all hands.

        Args:
            hands: List of parsed hand records.
            hero_name: Optional hero name filter. If None, uses hero_seat
                       from each hand.

        Returns:
            PlayerStats with overall and positional breakdowns.
        """
        stats = PlayerStats()
        if not hands:
            return stats

        # Determine hero name from first hand if not provided
        if hero_name is None:
            for h in hands:
                if h.hero_name:
                    hero_name = h.hero_name
                    break
        stats.player_name = hero_name or ""

        # Track big blind for BB/100 calculation
        bb_sizes = []

        for hand in hands:
            seat = self._resolve_hero_seat(hand, hero_name)
            if seat is None:
                continue

            pos = hand.positions.get(seat)
            self._process_hand(hand, seat, stats.overall, pos)
            if pos:
                pos_stats = stats.get_position_stats(pos)
                self._process_hand(hand, seat, pos_stats, pos)

            # Track winnings
            won = hand.winners.get(seat, 0.0)
            invested = self._total_invested(hand, seat)
            net = won - invested
            stats.total_profit += net
            stats.overall.total_won += won
            stats.overall.total_invested += invested

            if pos:
                pos_stats = stats.get_position_stats(pos)
                pos_stats.total_won += won
                pos_stats.total_invested += invested

            if hand.big_blind > 0:
                bb_sizes.append(hand.big_blind)

        if bb_sizes:
            stats.big_blind_size = bb_sizes[-1]

        return stats

    def _resolve_hero_seat(self, hand: HandRecord,
                           hero_name: Optional[str]) -> Optional[int]:
        """Find the hero's seat in this hand."""
        if hero_name:
            for seat, name in hand.players.items():
                if name == hero_name:
                    return seat
        return hand.hero_seat

    def _process_hand(self, hand: HandRecord, hero_seat: int,
                      stats: PositionalStats,
                      position: Optional[Position]) -> None:
        """Process a single hand and update stats counters."""
        stats.total_hands += 1

        preflop_actions = hand.actions_on_street(Street.PREFLOP)
        hero_preflop = [a for a in preflop_actions if a.seat == hero_seat]
        all_hero = [a for a in hand.actions if a.seat == hero_seat]

        # VPIP: did hero voluntarily put money in preflop?
        if self._is_vpip(hero_preflop):
            stats.voluntarily_put_in_pot += 1

        # PFR: did hero raise preflop?
        if self._is_pfr(hero_preflop):
            stats.preflop_raise += 1

        # 3-Bet
        had_opportunity, did_3bet = self._check_3bet(preflop_actions, hero_seat)
        if had_opportunity:
            stats.three_bet_opportunities += 1
            if did_3bet:
                stats.three_bet_made += 1

        # Postflop aggression counts (flop/turn/river only)
        for action in all_hero:
            if action.street == Street.PREFLOP:
                continue
            if action.action_type in (ActionType.BET, ActionType.RAISE):
                if action.action_type == ActionType.BET:
                    stats.bets += 1
                else:
                    stats.raises += 1
            elif action.action_type == ActionType.CALL:
                stats.calls += 1
            elif action.action_type == ActionType.FOLD:
                stats.folds += 1

        # Saw flop?
        hero_saw_flop = self._hero_saw_flop(hand, hero_seat, hero_preflop)
        if hero_saw_flop:
            stats.saw_flop += 1

        # C-Bet (hero was preflop raiser and had opportunity on flop)
        if hero_saw_flop:
            was_pfr = self._is_pfr(hero_preflop)
            if was_pfr:
                stats.cbet_opportunities += 1
                if self._did_cbet(hand, hero_seat):
                    stats.cbet_made += 1

        # Faced C-Bet
        if hero_saw_flop:
            faced, folded = self._check_faced_cbet(hand, hero_seat, preflop_actions)
            if faced:
                stats.faced_cbet += 1
                if folded:
                    stats.folded_to_cbet += 1

        # Showdown
        if hand.went_to_showdown:
            stats.went_to_showdown += 1
            if hero_seat in hand.winners:
                stats.won_at_showdown += 1
        else:
            # Hand ended before showdown — did hero win without going to showdown?
            if hero_seat in hand.winners:
                stats.won_without_showdown += 1

    def _is_vpip(self, hero_preflop: List[PlayerAction]) -> bool:
        """Hero voluntarily put money in pot preflop (call, raise, bet — not blind).

        A call of $0 (BB checking the option) does not count as voluntary.
        """
        for a in hero_preflop:
            if a.action_type in (ActionType.BET, ActionType.RAISE, ActionType.ALL_IN):
                return True
            if a.action_type == ActionType.CALL and a.amount > 0:
                return True
        return False

    def _is_pfr(self, hero_preflop: List[PlayerAction]) -> bool:
        """Hero raised preflop."""
        for a in hero_preflop:
            if a.action_type in (ActionType.RAISE, ActionType.BET):
                return True
        return False

    def _check_3bet(self, preflop_actions: List[PlayerAction],
                    hero_seat: int) -> tuple:
        """Check if hero had a 3-bet opportunity and whether they took it.

        Returns (had_opportunity, did_3bet).

        A 3-bet opportunity exists when there has been a raise before hero acts,
        and hero hasn't acted aggressively yet. A 3-bet is the hero re-raising.
        """
        raise_count = 0
        hero_had_opportunity = False

        for action in preflop_actions:
            if action.action_type == ActionType.POST_BLIND:
                continue

            if action.seat != hero_seat:
                if action.action_type in (ActionType.RAISE, ActionType.BET):
                    raise_count += 1
            else:
                # Hero's turn to act
                if raise_count == 1:
                    # There was exactly one raise before hero — hero can 3-bet
                    hero_had_opportunity = True
                    if action.action_type in (ActionType.RAISE, ActionType.ALL_IN):
                        return (True, True)
                    return (True, False)

        return (hero_had_opportunity, False)

    def _hero_saw_flop(self, hand: HandRecord, hero_seat: int,
                       hero_preflop: List[PlayerAction]) -> bool:
        """Did the hero see the flop?"""
        if not hand.flop:
            return False
        # Hero saw flop if they didn't fold preflop
        for a in hero_preflop:
            if a.action_type == ActionType.FOLD:
                return False
        return True

    def _did_cbet(self, hand: HandRecord, hero_seat: int) -> bool:
        """Did hero continuation bet on the flop?

        A c-bet is a bet on the flop by the preflop raiser, being the first
        to bet (not a raise over someone else's bet).
        """
        flop_actions = hand.actions_on_street(Street.FLOP)
        for action in flop_actions:
            if action.action_type == ActionType.CHECK:
                if action.seat == hero_seat:
                    return False
                continue
            if action.action_type in (ActionType.BET, ActionType.ALL_IN):
                return action.seat == hero_seat
            if action.action_type in (ActionType.RAISE, ActionType.CALL, ActionType.FOLD):
                # Someone else acted aggressively first or hero folded/called
                return False
        return False

    def _check_faced_cbet(self, hand: HandRecord, hero_seat: int,
                          preflop_actions: List[PlayerAction]) -> tuple:
        """Check if hero faced a c-bet and whether they folded.

        Returns (faced_cbet, folded_to_cbet).

        Hero faces a c-bet when the preflop raiser (not hero) bets on the flop.
        """
        # Find the preflop raiser (last raiser who isn't hero)
        pfr_seat = None
        for a in preflop_actions:
            if a.action_type in (ActionType.RAISE, ActionType.BET) and a.seat != hero_seat:
                pfr_seat = a.seat

        if pfr_seat is None:
            return (False, False)

        flop_actions = hand.actions_on_street(Street.FLOP)
        cbet_happened = False
        for action in flop_actions:
            if not cbet_happened:
                if action.action_type in (ActionType.BET, ActionType.ALL_IN) and action.seat == pfr_seat:
                    cbet_happened = True
                elif action.action_type in (ActionType.BET, ActionType.RAISE):
                    break  # Someone else bet first — not a c-bet
            else:
                # C-bet happened, now look for hero's response
                if action.seat == hero_seat:
                    return (True, action.action_type == ActionType.FOLD)

        return (False, False)

    def _total_invested(self, hand: HandRecord, seat: int) -> float:
        """Calculate total amount invested by a player in this hand.

        Sums all action amounts and subtracts any uncalled bet returns.
        """
        total = 0.0
        for a in hand.actions:
            if a.seat == seat and a.amount > 0:
                total += a.amount
        # Subtract uncalled bet returns
        total -= hand.uncalled_bets.get(seat, 0.0)
        return max(total, 0.0)
