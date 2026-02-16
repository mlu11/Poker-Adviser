"""Main parser for Poker Now Club log files."""

from typing import Dict, List, Optional, Tuple
import csv
import io
import re

from poker_advisor.models.card import Card, Rank, Suit
from poker_advisor.models.action import ActionType, Street, PlayerAction
from poker_advisor.models.position import Position, assign_positions
from poker_advisor.models.hand import HandRecord
from poker_advisor.parser import patterns


def _parse_amount(s: str) -> float:
    """Parse a money amount string, removing commas.

    Some Poker Now logs use whole units (not cents), so return as-is.
    """
    raw = float(s.replace(",", ""))
    return raw


def _parse_board_cards(text: str) -> List[Card]:
    """Parse board card text into Card objects.

    Handles formats like:
    - '5♠, J♥, 2♦'
    - '5s, Jh, 2d'
    - '10♣, J♥'
    - '5 of Spades, J of Hearts'
    """
    cards = []
    # Try short notation first: Ah, Ts, 2c, 10♣, etc.
    short_matches = re.findall(r'(10|[2-9TJQKA])[♥♦♣♠hdcs]', text, re.IGNORECASE)
    suit_matches = re.findall(r'(?:10|[2-9TJQKA])([♥♦♣♠hdcs])', text, re.IGNORECASE)

    if short_matches and len(short_matches) == len(suit_matches):
        for rank_ch, suit_ch in zip(short_matches, suit_matches):
            try:
                cards.append(Card(Rank.from_char(rank_ch), Suit.from_symbol(suit_ch)))
            except ValueError:
                continue
        return cards

    # Try "X of Suit" notation
    named_matches = re.findall(r'(10|[2-9TJQKA]+)\s+of\s+(Hearts|Diamonds|Clubs|Spades)', text, re.IGNORECASE)
    for rank_s, suit_s in named_matches:
        try:
            cards.append(Card.from_name_and_suit(rank_s, suit_s))
        except ValueError:
            continue

    return cards


class PokerNowParser:
    """Parse Poker Now Club full log text into HandRecord objects."""

    def __init__(self):
        self._current_small_blind = 10
        self._current_big_blind = 20

    def parse_file(self, filepath: str) -> List[HandRecord]:
        """Parse a log file and return list of HandRecord."""
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
        return self.parse_text(text)

    def parse_text(self, text: str) -> List[HandRecord]:
        """Parse log text and return list of HandRecord.

        Poker Now logs have newest entries at the top.
        We reverse to process chronologically.
        Supports both plain text (old) and CSV (new) formats.
        """
        lines_raw = text.strip().split("\n")

        # Detect CSV format by checking first line
        if lines_raw and lines_raw[0].strip().startswith("entry,at,order"):
            lines = self._extract_csv_entries(text)
        else:
            lines = list(reversed(lines_raw))

        hands: List[HandRecord] = []
        current_lines: List[str] = []
        current_hand_id: Optional[int] = None
        # Track show card lines that appear after ending hand
        pending_show_lines: List[str] = []
        last_completed_hand: Optional[HandRecord] = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check for hand start
            start_match = patterns.HAND_START.search(line)
            if start_match:
                # Before starting new hand, attach any pending show lines to last hand
                if pending_show_lines and last_completed_hand is not None:
                    self._apply_show_lines(last_completed_hand, pending_show_lines)
                    pending_show_lines = []
                    last_completed_hand = None

                current_hand_id = int(start_match.group(1))
                current_lines = [line]
                continue

            # Check for hand end
            end_match = patterns.HAND_END.search(line)
            if end_match:
                if current_lines and current_hand_id is not None:
                    current_lines.append(line)
                    hand = self._parse_hand(current_hand_id, current_lines)
                    if hand:
                        hands.append(hand)
                        last_completed_hand = hand
                current_lines = []
                current_hand_id = None
                pending_show_lines = []
                continue

            # Check for blinds change outside of hand
            blinds_match = patterns.BLINDS_CHANGE.search(line)
            if blinds_match:
                self._current_small_blind = _parse_amount(blinds_match.group(1))
                self._current_big_blind = _parse_amount(blinds_match.group(2))

            if current_hand_id is not None:
                current_lines.append(line)
            elif last_completed_hand is not None:
                # Lines between ending and starting hand — check for show cards
                if 'shows' in line:
                    pending_show_lines.append(line)

        # Handle any remaining pending show lines
        if pending_show_lines and last_completed_hand is not None:
            self._apply_show_lines(last_completed_hand, pending_show_lines)

        return hands

    def _extract_csv_entries(self, text: str) -> List[str]:
        """Extract entry column from CSV format, reversed to chronological order."""
        reader = csv.DictReader(io.StringIO(text))
        entries = []
        for row in reader:
            entry = row.get("entry", "").strip()
            if entry:
                entries.append(entry)
        # CSV is reverse chronological (newest first), reverse it
        return list(reversed(entries))

    def _apply_show_lines(self, hand: HandRecord, show_lines: List[str]) -> None:
        """Apply show card lines that appeared after ending hand."""
        name_to_seat = {name: seat for seat, name in hand.players.items()}
        for line in show_lines:
            self._parse_show_line(line, hand, name_to_seat)

    def _parse_show_line(self, line: str, hand: HandRecord, name_to_seat: Dict[str, int]) -> None:
        """Parse a single show card line and add to hand."""
        # Try symbol format first: "Name" shows a 5♦, 9♦.
        show_sym = patterns.SHOW_CARDS_SYMBOL.search(line)
        if show_sym:
            name = show_sym.group(1)
            seat_s = show_sym.group(2)
            card1_s = show_sym.group(3)
            card2_s = show_sym.group(4)
            seat = int(seat_s) if seat_s else name_to_seat.get(name)
            if seat is not None:
                try:
                    cards = [Card.parse(card1_s), Card.parse(card2_s)]
                    hand.shown_cards[seat] = cards
                except ValueError:
                    pass
            return

        # Try named suit format: "Name" shows a A of Hearts
        show_named = patterns.SHOW_CARDS.search(line)
        if show_named:
            name = show_named.group(1)
            seat_s = show_named.group(2)
            rank_s = show_named.group(3)
            suit_s = show_named.group(4)
            seat = int(seat_s) if seat_s else name_to_seat.get(name)
            if seat is not None:
                try:
                    card = Card.from_name_and_suit(rank_s, suit_s)
                    if seat not in hand.shown_cards:
                        hand.shown_cards[seat] = []
                    hand.shown_cards[seat].append(card)
                except ValueError:
                    pass
            return

        # Try bracket format: "Name" shows [Ah Kh]
        show_alt = patterns.SHOW_CARDS_ALT.search(line)
        if show_alt:
            name = show_alt.group(1)
            seat_s = show_alt.group(2)
            cards_text = show_alt.group(3)
            seat = int(seat_s) if seat_s else name_to_seat.get(name)
            if seat is not None:
                parsed = _parse_board_cards(cards_text)
                if parsed:
                    hand.shown_cards[seat] = parsed

    def _resolve_seat(self, name: str, seat_s: Optional[str],
                      name_to_seat: Dict[str, int]) -> int:
        """Resolve seat number from match group or name lookup."""
        if seat_s:
            return int(seat_s)
        return name_to_seat.get(name, 0)

    def _parse_hand(self, hand_id: int, lines: List[str]) -> Optional[HandRecord]:
        """Parse lines belonging to a single hand into a HandRecord."""
        hand = HandRecord(hand_id=hand_id)
        hand.small_blind = self._current_small_blind
        hand.big_blind = self._current_big_blind

        current_street = Street.PREFLOP
        dealer_name: Optional[str] = None
        player_stacks_parsed = False
        name_to_seat: Dict[str, int] = {}

        # Track per-player cumulative amount for current street.
        # In Poker Now, "calls X" and "raises to X" mean the player's TOTAL
        # for this betting round is X (cumulative), not incremental.
        # We convert to incremental for accurate profit calculation.
        player_street_cumulative: Dict[int, float] = {}

        for line in lines:
            # Check for dealer in hand start line
            start_match = patterns.HAND_START.search(line)
            if start_match and start_match.group(2):
                dealer_name = start_match.group(2)

            # Player stacks — try old format first, then new format
            if not player_stacks_parsed:
                stack_matches = patterns.PLAYER_STACKS_OLD.findall(line)
                if stack_matches:
                    for name, seat_s, stack_s in stack_matches:
                        seat = int(seat_s)
                        hand.players[seat] = name
                        hand.stacks[seat] = _parse_amount(stack_s)
                        name_to_seat[name] = seat
                    player_stacks_parsed = True
                    hand.player_count = len(hand.players)
                else:
                    # Try new format: #1 "Name @ ID" (10789)
                    stack_matches_new = patterns.PLAYER_STACKS_NEW.findall(line)
                    if stack_matches_new:
                        for seat_s, name, stack_s in stack_matches_new:
                            seat = int(seat_s)
                            hand.players[seat] = name
                            hand.stacks[seat] = _parse_amount(stack_s)
                            name_to_seat[name] = seat
                        player_stacks_parsed = True
                        hand.player_count = len(hand.players)

            # Blinds change within hand
            blinds_match = patterns.BLINDS_CHANGE.search(line)
            if blinds_match:
                self._current_small_blind = _parse_amount(blinds_match.group(1))
                self._current_big_blind = _parse_amount(blinds_match.group(2))
                hand.small_blind = self._current_small_blind
                hand.big_blind = self._current_big_blind

            # Hero hand
            hero_match = patterns.HERO_HAND.search(line)
            if hero_match:
                try:
                    hand.hero_cards = [
                        Card.parse(hero_match.group(1)),
                        Card.parse(hero_match.group(2)),
                    ]
                except ValueError:
                    pass

            # Blind posts
            blind_match = patterns.POST_BLIND.match(line)
            if not blind_match:
                blind_match = patterns.POST_BLIND.search(line)
            if blind_match:
                name, seat_s, blind_type, amount_s = blind_match.groups()
                seat = self._resolve_seat(name, seat_s, name_to_seat)
                amount = _parse_amount(amount_s)
                if seat:
                    hand.players[seat] = name
                action = PlayerAction(
                    player_name=name,
                    seat=seat,
                    action_type=ActionType.POST_BLIND,
                    amount=amount,
                    street=Street.PREFLOP,
                )
                hand.actions.append(action)
                # Blinds are incremental, but add to cumulative tracking
                # so subsequent calls/raises compute correct incremental
                player_street_cumulative[seat] = player_street_cumulative.get(seat, 0.0) + amount
                continue

            # Fold
            fold_match = patterns.PLAYER_FOLD.search(line)
            if fold_match and not patterns.POST_BLIND.search(line):
                name, seat_s = fold_match.groups()
                seat = self._resolve_seat(name, seat_s, name_to_seat)
                hand.actions.append(PlayerAction(
                    player_name=name, seat=seat,
                    action_type=ActionType.FOLD, street=current_street,
                ))
                continue

            # Check
            check_match = patterns.PLAYER_CHECK.search(line)
            if check_match:
                name, seat_s = check_match.groups()
                seat = self._resolve_seat(name, seat_s, name_to_seat)
                hand.actions.append(PlayerAction(
                    player_name=name, seat=seat,
                    action_type=ActionType.CHECK, street=current_street,
                ))
                continue

            # Call — amount is cumulative total for this round
            call_match = patterns.PLAYER_CALL.search(line)
            if call_match:
                name, seat_s, amount_s = call_match.groups()
                seat = self._resolve_seat(name, seat_s, name_to_seat)
                is_allin = bool(patterns.ALL_IN.search(line))
                cumulative = _parse_amount(amount_s)
                prior = player_street_cumulative.get(seat, 0.0)
                incremental = max(cumulative - prior, 0.0)
                player_street_cumulative[seat] = cumulative
                hand.actions.append(PlayerAction(
                    player_name=name, seat=seat,
                    action_type=ActionType.CALL, amount=incremental,
                    street=current_street, is_all_in=is_allin,
                ))
                continue

            # Raise — amount is cumulative total for this round
            raise_match = patterns.PLAYER_RAISE.search(line)
            if raise_match:
                name, seat_s, amount_s = raise_match.groups()
                seat = self._resolve_seat(name, seat_s, name_to_seat)
                is_allin = bool(patterns.ALL_IN.search(line))
                cumulative = _parse_amount(amount_s)
                prior = player_street_cumulative.get(seat, 0.0)
                incremental = max(cumulative - prior, 0.0)
                player_street_cumulative[seat] = cumulative
                hand.actions.append(PlayerAction(
                    player_name=name, seat=seat,
                    action_type=ActionType.RAISE, amount=incremental,
                    street=current_street, is_all_in=is_allin,
                ))
                continue

            # Bet — amount is cumulative total for this round
            bet_match = patterns.PLAYER_BET.search(line)
            if bet_match:
                name, seat_s, amount_s = bet_match.groups()
                seat = self._resolve_seat(name, seat_s, name_to_seat)
                is_allin = bool(patterns.ALL_IN.search(line))
                cumulative = _parse_amount(amount_s)
                prior = player_street_cumulative.get(seat, 0.0)
                incremental = max(cumulative - prior, 0.0)
                player_street_cumulative[seat] = cumulative
                hand.actions.append(PlayerAction(
                    player_name=name, seat=seat,
                    action_type=ActionType.BET, amount=incremental,
                    street=current_street, is_all_in=is_allin,
                ))
                continue

            # Flop
            flop_match = patterns.FLOP.search(line)
            if flop_match:
                current_street = Street.FLOP
                player_street_cumulative.clear()  # Reset for new street
                hand.flop = _parse_board_cards(flop_match.group(1))
                continue

            # Turn — the new format has only the new card in brackets
            turn_match = patterns.TURN.search(line)
            if turn_match:
                current_street = Street.TURN
                player_street_cumulative.clear()  # Reset for new street
                turn_cards = _parse_board_cards(turn_match.group(1))
                if turn_cards:
                    hand.turn = turn_cards[-1]  # Last card is the turn card
                continue

            # River
            river_match = patterns.RIVER.search(line)
            if river_match:
                current_street = Street.RIVER
                player_street_cumulative.clear()  # Reset for new street
                river_cards = _parse_board_cards(river_match.group(1))
                if river_cards:
                    hand.river = river_cards[-1]
                continue

            # Show cards — symbol format (new): "Name" shows a 5♦, 9♦.
            show_sym = patterns.SHOW_CARDS_SYMBOL.search(line)
            if show_sym:
                name = show_sym.group(1)
                seat_s = show_sym.group(2)
                card1_s = show_sym.group(3)
                card2_s = show_sym.group(4)
                seat = self._resolve_seat(name, seat_s, name_to_seat)
                if seat:
                    try:
                        hand.shown_cards[seat] = [
                            Card.parse(card1_s), Card.parse(card2_s)
                        ]
                    except ValueError:
                        pass
                continue

            # Show cards — named suit format (old): "Name" shows a A of Hearts
            show_match = patterns.SHOW_CARDS.search(line)
            if show_match:
                name, seat_s, rank_s, suit_s = show_match.groups()
                seat = self._resolve_seat(name, seat_s, name_to_seat)
                if seat:
                    try:
                        card = Card.from_name_and_suit(rank_s, suit_s)
                        if seat not in hand.shown_cards:
                            hand.shown_cards[seat] = []
                        hand.shown_cards[seat].append(card)
                    except ValueError:
                        pass
                continue

            # Show cards — bracket format: "Name" shows [Ah Kh]
            show_alt_match = patterns.SHOW_CARDS_ALT.search(line)
            if show_alt_match:
                name, seat_s, cards_text = show_alt_match.groups()
                seat = self._resolve_seat(name, seat_s, name_to_seat)
                if seat:
                    parsed = _parse_board_cards(cards_text)
                    if parsed:
                        hand.shown_cards[seat] = parsed
                continue

            # Pot collection — accumulate for side pots
            pot_match = patterns.POT_COLLECT.search(line)
            if pot_match:
                name, seat_s, amount_s = pot_match.groups()
                seat = self._resolve_seat(name, seat_s, name_to_seat)
                if seat:
                    amount = _parse_amount(amount_s)
                    hand.winners[seat] = hand.winners.get(seat, 0.0) + amount
                    hand.pot_total += amount
                continue

            # Hand result (wins/gained) — accumulate for side pots
            result_match = patterns.HAND_RESULT.search(line)
            if result_match:
                name, seat_s, amount_s = result_match.groups()
                seat = self._resolve_seat(name, seat_s, name_to_seat)
                if seat and seat not in hand.winners:
                    hand.winners[seat] = hand.winners.get(seat, 0.0) + _parse_amount(amount_s)
                continue

            # Uncalled bet — track the returned amount
            uncalled_match = patterns.UNCALLED_BET.search(line)
            if uncalled_match:
                uncalled_amount = _parse_amount(uncalled_match.group(1))
                uncalled_name = uncalled_match.group(2)
                uncalled_seat = self._resolve_seat(uncalled_name, None, name_to_seat)
                if uncalled_seat:
                    hand.uncalled_bets[uncalled_seat] = hand.uncalled_bets.get(uncalled_seat, 0.0) + uncalled_amount
                continue

        # Post-processing: determine dealer and positions
        if dealer_name:
            for seat, name in hand.players.items():
                if name == dealer_name:
                    hand.dealer_seat = seat
                    break

        if hand.dealer_seat and hand.players:
            seats = sorted(hand.players.keys())
            hand.positions = assign_positions(seats, hand.dealer_seat)

        # Determine hero seat from hero cards or "Your hand" context
        if hand.hero_cards and not hand.hero_seat:
            # Try to find hero from shown cards
            for seat, cards in hand.shown_cards.items():
                if set(c.to_short() for c in cards) == set(c.to_short() for c in hand.hero_cards):
                    hand.hero_seat = seat
                    hand.hero_name = hand.players.get(seat)
                    break

        # Calculate pot total from all bets if not already set
        if hand.pot_total == 0:
            hand.pot_total = sum(a.amount for a in hand.actions)

        return hand if hand.players else None
