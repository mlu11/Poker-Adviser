"""Scenario generator — extract decision points from real hands."""

import random
from dataclasses import dataclass
from typing import List, Optional

from poker_advisor.models.hand import HandRecord
from poker_advisor.models.action import ActionType, Street, PlayerAction
from poker_advisor.models.stats import PlayerStats
from poker_advisor.analysis.leak_detector import Leak, Severity
from poker_advisor.formatters.text import TextFormatter


@dataclass
class Scenario:
    """A training scenario extracted from a real hand."""
    hand: HandRecord
    decision_street: Street
    decision_index: int  # index into hand.actions where hero must decide
    scenario_type: str   # e.g. "preflop_open", "facing_cbet", "river_bet"
    description: str     # human-readable scenario text
    available_actions: List[str]  # e.g. ["Fold", "Call $3.00", "Raise $9.00"]

    @property
    def hand_record_id(self) -> int:
        return self.hand.hand_id


class ScenarioGenerator:
    """Generate training scenarios from real hand histories.

    Extracts key decision points from hands and presents them as
    training exercises. Can focus on specific leak areas.
    """

    def __init__(self):
        self.formatter = TextFormatter()

    def generate(self, hands: List[HandRecord], count: int = 10,
                 leaks: Optional[List[Leak]] = None,
                 focus: Optional[str] = None) -> List[Scenario]:
        """Generate training scenarios from hands.

        Args:
            hands: Pool of hands to draw from.
            count: Number of scenarios to generate.
            leaks: Detected leaks to focus training on.
            focus: Optional focus area (e.g. "preflop", "cbet", "river").

        Returns:
            List of Scenario objects.
        """
        candidates = []
        for hand in hands:
            candidates.extend(self._extract_scenarios(hand))

        if not candidates:
            return []

        # Filter by focus area
        if focus:
            focused = [s for s in candidates if focus.lower() in s.scenario_type]
            if focused:
                candidates = focused

        # Prioritize scenarios matching detected leaks
        if leaks:
            candidates = self._prioritize_by_leaks(candidates, leaks)

        # Deduplicate by scenario type variety
        selected = self._select_diverse(candidates, count)
        return selected

    def _extract_scenarios(self, hand: HandRecord) -> List[Scenario]:
        """Extract all decision points from a single hand."""
        if hand.hero_seat is None:
            return []

        scenarios = []
        hero_seat = hand.hero_seat

        for i, action in enumerate(hand.actions):
            if action.seat != hero_seat:
                continue
            if action.action_type == ActionType.POST_BLIND:
                continue

            scenario_type = self._classify_decision(hand, action, i)
            if not scenario_type:
                continue

            description = self._build_description(hand, action.street, i)
            available = self._get_available_actions(hand, action, i)

            scenarios.append(Scenario(
                hand=hand,
                decision_street=action.street,
                decision_index=i,
                scenario_type=scenario_type,
                description=description,
                available_actions=available,
            ))

        return scenarios

    def _classify_decision(self, hand: HandRecord,
                           action: PlayerAction, index: int) -> Optional[str]:
        """Classify the type of decision point."""
        street = action.street
        preceding = hand.actions[:index]
        street_actions = [a for a in preceding if a.street == street
                          and a.action_type != ActionType.POST_BLIND]

        if street == Street.PREFLOP:
            # Check if there was a raise before hero
            raises_before = [a for a in street_actions
                             if a.action_type in (ActionType.RAISE, ActionType.BET)]
            if not raises_before:
                limpers = [a for a in street_actions
                           if a.action_type == ActionType.CALL]
                if limpers:
                    return "preflop_vs_limpers"
                return "preflop_open"
            elif len(raises_before) == 1:
                return "preflop_vs_raise"
            else:
                return "preflop_vs_3bet"

        if street == Street.FLOP:
            # Was hero the preflop raiser?
            hero_pfr = any(
                a.seat == hand.hero_seat and a.action_type in (ActionType.RAISE, ActionType.BET)
                for a in hand.actions_on_street(Street.PREFLOP)
            )
            bets_on_flop = [a for a in street_actions
                            if a.action_type in (ActionType.BET, ActionType.RAISE)]
            if not bets_on_flop and hero_pfr:
                return "flop_cbet_decision"
            elif bets_on_flop:
                return "flop_facing_bet"
            else:
                return "flop_check_decision"

        if street == Street.TURN:
            bets_on_turn = [a for a in street_actions
                            if a.action_type in (ActionType.BET, ActionType.RAISE)]
            if bets_on_turn:
                return "turn_facing_bet"
            else:
                return "turn_bet_decision"

        if street == Street.RIVER:
            bets_on_river = [a for a in street_actions
                             if a.action_type in (ActionType.BET, ActionType.RAISE)]
            if bets_on_river:
                return "river_facing_bet"
            else:
                return "river_bet_decision"

        return None

    def _build_description(self, hand: HandRecord,
                           up_to_street: Street, up_to_index: int) -> str:
        """Build a text description of the scenario up to the decision point."""
        lines = []

        # Table info
        pos = hand.hero_position
        pos_str = pos.value if pos else "?"
        lines.append(f"位置: {pos_str}  |  "
                     f"玩家数: {hand.player_count}  |  "
                     f"盲注: ${hand.small_blind:.2f}/${hand.big_blind:.2f}")

        # Hero cards
        if hand.hero_cards:
            lines.append(f"手牌: {hand.hero_cards_str}")

        # Stack
        if hand.hero_seat and hand.hero_seat in hand.stacks:
            stack = hand.stacks[hand.hero_seat]
            bb = hand.big_blind or 1.0
            lines.append(f"筹码: ${stack:.2f} ({stack/bb:.0f} BB)")

        # Board up to this street
        if up_to_street.order >= Street.FLOP.order and hand.flop:
            lines.append(f"翻牌: {' '.join(str(c) for c in hand.flop)}")
        if up_to_street.order >= Street.TURN.order and hand.turn:
            lines.append(f"转牌: {hand.turn}")
        if up_to_street.order >= Street.RIVER.order and hand.river:
            lines.append(f"河牌: {hand.river}")

        # Actions before this decision
        lines.append("")
        lines.append("行动记录:")
        for a in hand.actions[:up_to_index]:
            if a.action_type == ActionType.POST_BLIND:
                continue
            name = "你" if a.seat == hand.hero_seat else a.player_name
            lines.append(f"  [{a.street.value.upper()}] {name} {a.action_type.value}s"
                         + (f" ${a.amount:.2f}" if a.amount > 0 else ""))

        # Current pot estimate
        pot = sum(a.amount for a in hand.actions[:up_to_index] if a.amount > 0)
        lines.append(f"\n底池: ~${pot:.2f}")
        lines.append("\n你的行动是？")

        return "\n".join(lines)

    def _get_available_actions(self, hand: HandRecord,
                               action: PlayerAction,
                               index: int) -> List[str]:
        """Determine available actions at this decision point."""
        # Get the last bet/raise amount on this street before hero
        preceding_street = [a for a in hand.actions[:index]
                            if a.street == action.street
                            and a.action_type != ActionType.POST_BLIND]
        last_bet = 0.0
        for a in preceding_street:
            if a.action_type in (ActionType.BET, ActionType.RAISE):
                last_bet = a.amount

        actions = ["Fold"]

        if last_bet > 0:
            actions.append(f"Call ${last_bet:.2f}")
            raise_amt = last_bet * 2.5
            actions.append(f"Raise ${raise_amt:.2f}")
        else:
            actions.append("Check")
            # Suggest a bet size based on pot
            pot = sum(a.amount for a in hand.actions[:index] if a.amount > 0)
            if pot > 0:
                bet_sizes = [
                    f"Bet ${pot * 0.33:.2f} (1/3 pot)",
                    f"Bet ${pot * 0.67:.2f} (2/3 pot)",
                    f"Bet ${pot:.2f} (pot)",
                ]
                actions.extend(bet_sizes)
            else:
                actions.append(f"Bet ${hand.big_blind * 2.5:.2f}")

        actions.append("All-in")
        return actions

    def _prioritize_by_leaks(self, candidates: List[Scenario],
                              leaks: List[Leak]) -> List[Scenario]:
        """Sort scenarios so those related to detected leaks come first."""
        leak_types = set()
        for leak in leaks:
            m = leak.metric
            if m in ("vpip", "pfr", "vpip_pfr_gap"):
                leak_types.add("preflop")
            if m in ("three_bet_pct",):
                leak_types.add("3bet")
            if m in ("cbet_pct",):
                leak_types.add("cbet")
            if m in ("fold_to_cbet",):
                leak_types.add("facing")
            if m in ("af",):
                leak_types.add("bet_decision")
            if m in ("wtsd", "wsd"):
                leak_types.add("river")

        def score(s: Scenario) -> int:
            return sum(1 for lt in leak_types if lt in s.scenario_type)

        candidates.sort(key=score, reverse=True)
        return candidates

    def _select_diverse(self, candidates: List[Scenario],
                        count: int) -> List[Scenario]:
        """Select a diverse set of scenarios covering different types."""
        if len(candidates) <= count:
            return candidates

        # Group by type
        by_type = {}
        for s in candidates:
            by_type.setdefault(s.scenario_type, []).append(s)

        selected = []
        types = list(by_type.keys())

        # Round-robin across types
        while len(selected) < count and types:
            for t in list(types):
                if not by_type[t]:
                    types.remove(t)
                    continue
                s = by_type[t].pop(0)
                selected.append(s)
                if len(selected) >= count:
                    break

        return selected
