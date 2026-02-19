"""PokerNow format exporter."""

from typing import List, TextIO, Optional
from datetime import datetime

from poker_advisor.models.hand import HandRecord
from poker_advisor.models.card import Card
from poker_advisor.models.action import ActionType, Street


class PokerNowExporter:
    """Exports hand records to PokerNow log format."""

    @staticmethod
    def export_hand(hand: HandRecord) -> str:
        """Export a single hand to PokerNow format.

        Args:
            hand: The hand record to export.

        Returns:
            The hand in PokerNow log format as a string.
        """
        lines = []

        # Hand header
        hand_id = hand.hand_id or 1
        timestamp = hand.timestamp or datetime.now().isoformat()
        lines.append(f"-- Hand #{hand_id}: NLHE ({hand.small_blind:.0f}/{hand.big_blind:.0f}) - {timestamp}")

        # Seat info
        for seat in sorted(hand.players.keys()):
            name = hand.players[seat]
            stack = hand.stacks.get(seat, 0)
            lines.append(f"-- Seat {seat}: {name} ({stack:.0f})")

        # Blinds
        # Find SB and BB positions
        sb_seat = None
        bb_seat = None
        for seat, pos in hand.positions.items():
            if pos and pos.value == "SB":
                sb_seat = seat
            elif pos and pos.value == "BB":
                bb_seat = seat

        if sb_seat and sb_seat in hand.players:
            lines.append(f"-- small blind: Seat {sb_seat} (${hand.small_blind:.0f})")
        if bb_seat and bb_seat in hand.players:
            lines.append(f"-- big blind: Seat {bb_seat} (${hand.big_blind:.0f})")

        # Hero cards
        if hand.hero_cards:
            cards_str = " ".join(PokerNowExporter._format_card(c) for c in hand.hero_cards)
            lines.append(f"-- ** Dealt to {hand.hero_name or 'Hero'}: {cards_str}")

        # Actions by street
        street_order = [Street.PREFLOP, Street.FLOP, Street.TURN, Street.RIVER]
        street_headers = {
            Street.FLOP: f"-- ** Flop: {' '.join(PokerNowExporter._format_card(c) for c in hand.flop)}",
            Street.TURN: f"-- ** Turn: {PokerNowExporter._format_card(hand.turn) if hand.turn else ''}",
            Street.RIVER: f"-- ** River: {PokerNowExporter._format_card(hand.river) if hand.river else ''}",
        }

        for street in street_order:
            if street in street_headers and street != Street.PREFLOP:
                if street == Street.FLOP and hand.flop:
                    lines.append(street_headers[street])
                elif street == Street.TURN and hand.turn:
                    lines.append(street_headers[street])
                elif street == Street.RIVER and hand.river:
                    lines.append(street_headers[street])

            actions = hand.actions_on_street(street)
            for action in actions:
                if action.action_type == ActionType.POST_BLIND:
                    continue  # Already posted
                lines.append(PokerNowExporter._format_action(action))

        # Showdown and winners
        if hand.went_to_showdown:
            for seat, cards in hand.shown_cards.items():
                name = hand.players.get(seat, f"Seat{seat}")
                cards_str = " ".join(PokerNowExporter._format_card(c) for c in cards)
                lines.append(f"-- {name} shows {cards_str}")

        if hand.winners:
            for seat, amount in hand.winners.items():
                name = hand.players.get(seat, f"Seat{seat}")
                lines.append(f"-- {name} wins ${amount:.2f}")

        # Uncalled bets
        for seat, amount in hand.uncalled_bets.items():
            name = hand.players.get(seat, f"Seat{seat}")
            lines.append(f"-- Uncalled bet (${amount:.2f}) returned to {name}")

        lines.append("")  # Empty line between hands

        return "\n".join(lines)

    @staticmethod
    def export_hands(hands: List[HandRecord], output_file: str):
        """Export multiple hands to a file.

        Args:
            hands: List of hand records to export.
            output_file: Path to the output file.
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            for hand in hands:
                f.write(PokerNowExporter.export_hand(hand))
                f.write("\n")

    @staticmethod
    def _format_card(card: Optional[Card]) -> str:
        """Format a card for PokerNow output."""
        if card is None:
            return ""
        rank = card.rank.value
        suit = {
            "h": "h", "d": "d", "c": "c", "s": "s"
        }.get(card.suit.value, card.suit.value)
        return f"{rank}{suit}"

    @staticmethod
    def _format_action(action) -> str:
        """Format an action for PokerNow output."""
        name = action.player_name

        if action.action_type == ActionType.FOLD:
            return f"{name}: folds"
        elif action.action_type == ActionType.CHECK:
            return f"{name}: checks"
        elif action.action_type == ActionType.CALL:
            return f"{name}: calls ${action.amount:.2f}"
        elif action.action_type == ActionType.BET:
            return f"{name}: bets ${action.amount:.2f}"
        elif action.action_type == ActionType.RAISE:
            return f"{name}: raises to ${action.amount:.2f}"
        elif action.action_type == ActionType.ALL_IN:
            return f"{name}: raises to ${action.amount:.2f} and is all-in"
        else:
            return f"{name}: {action.action_type.value}"
