"""CRUD operations for hand records."""

import uuid
from typing import List, Optional

from poker_advisor.models.hand import HandRecord
from poker_advisor.models.card import Card
from poker_advisor.models.action import ActionType, Street, PlayerAction
from poker_advisor.models.position import Position
from poker_advisor.storage.database import Database


class HandRepository:
    """Repository for storing and retrieving hand records."""

    def __init__(self, db: Database):
        self.db = db

    def save_session(self, hands: List[HandRecord], filename: str = "",
                     notes: str = "") -> str:
        """Save a list of parsed hands as a session. Returns session_id."""
        session_id = str(uuid.uuid4())[:8]

        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO sessions (id, filename, hand_count, notes) VALUES (?, ?, ?, ?)",
                (session_id, filename, len(hands), notes),
            )

            for hand in hands:
                record_id = self._save_hand(conn, hand, session_id)

        return session_id

    def _save_hand(self, conn, hand: HandRecord, session_id: str) -> int:
        """Save a single hand record and return its db id."""
        hero_c1 = hand.hero_cards[0].to_short() if len(hand.hero_cards) > 0 else None
        hero_c2 = hand.hero_cards[1].to_short() if len(hand.hero_cards) > 1 else None
        flop1 = hand.flop[0].to_short() if len(hand.flop) > 0 else None
        flop2 = hand.flop[1].to_short() if len(hand.flop) > 1 else None
        flop3 = hand.flop[2].to_short() if len(hand.flop) > 2 else None
        turn = hand.turn.to_short() if hand.turn else None
        river = hand.river.to_short() if hand.river else None

        cursor = conn.execute(
            """INSERT INTO hands
            (hand_id, session_id, timestamp, player_count, dealer_seat,
             small_blind, big_blind, hero_seat, hero_name,
             hero_card1, hero_card2, flop1, flop2, flop3, turn, river,
             pot_total, hero_won, went_to_showdown)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (hand.hand_id, session_id, hand.timestamp, hand.player_count,
             hand.dealer_seat, hand.small_blind, hand.big_blind,
             hand.hero_seat, hand.hero_name, hero_c1, hero_c2,
             flop1, flop2, flop3, turn, river,
             hand.pot_total, int(hand.hero_won), int(hand.went_to_showdown)),
        )
        record_id = cursor.lastrowid

        # Save players
        for seat, name in hand.players.items():
            pos = hand.positions.get(seat)
            stack = hand.stacks.get(seat, 0.0)
            conn.execute(
                "INSERT INTO players (hand_record_id, seat, name, position, stack) VALUES (?, ?, ?, ?, ?)",
                (record_id, seat, name, pos.value if pos else None, stack),
            )

        # Save actions
        for seq, action in enumerate(hand.actions):
            conn.execute(
                """INSERT INTO actions
                (hand_record_id, seq, player_name, seat, action_type, amount, street, is_all_in)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (record_id, seq, action.player_name, action.seat,
                 action.action_type.value, action.amount,
                 action.street.value, int(action.is_all_in)),
            )

        # Save shown cards
        for seat, cards in hand.shown_cards.items():
            for card in cards:
                conn.execute(
                    "INSERT INTO shown_cards (hand_record_id, seat, card) VALUES (?, ?, ?)",
                    (record_id, seat, card.to_short()),
                )

        # Save winners
        for seat, amount in hand.winners.items():
            conn.execute(
                "INSERT INTO winners (hand_record_id, seat, amount) VALUES (?, ?, ?)",
                (record_id, seat, amount),
            )

        # Save uncalled bets
        for seat, amount in hand.uncalled_bets.items():
            conn.execute(
                "INSERT INTO uncalled_bets (hand_record_id, seat, amount) VALUES (?, ?, ?)",
                (record_id, seat, amount),
            )

        return record_id

    def get_all_hands(self, session_id: Optional[str] = None) -> List[HandRecord]:
        """Retrieve all hands, optionally filtered by session."""
        with self.db.connect() as conn:
            if session_id:
                rows = conn.execute(
                    "SELECT id, * FROM hands WHERE session_id = ? ORDER BY hand_id",
                    (session_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, * FROM hands ORDER BY hand_id"
                ).fetchall()

            return [self._row_to_hand(conn, row) for row in rows]

    def get_hand(self, record_id: int) -> Optional[HandRecord]:
        """Retrieve a single hand by its database id."""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT id, * FROM hands WHERE id = ?", (record_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_hand(conn, row)

    def get_hand_by_hand_id(self, hand_id: int,
                            session_id: Optional[str] = None) -> Optional[HandRecord]:
        """Retrieve a hand by its original hand_id."""
        with self.db.connect() as conn:
            if session_id:
                row = conn.execute(
                    "SELECT id, * FROM hands WHERE hand_id = ? AND session_id = ?",
                    (hand_id, session_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT id, * FROM hands WHERE hand_id = ? ORDER BY id DESC LIMIT 1",
                    (hand_id,),
                ).fetchone()
            if not row:
                return None
            return self._row_to_hand(conn, row)

    def _row_to_hand(self, conn, row) -> HandRecord:
        """Convert a database row back to a HandRecord."""
        record_id = row["id"]
        hand = HandRecord(
            hand_id=row["hand_id"],
            session_id=row["session_id"] or "",
            timestamp=row["timestamp"] or "",
            player_count=row["player_count"] or 0,
            dealer_seat=row["dealer_seat"] or 0,
            small_blind=row["small_blind"] or 0.0,
            big_blind=row["big_blind"] or 0.0,
            hero_seat=row["hero_seat"],
            hero_name=row["hero_name"],
            pot_total=row["pot_total"] or 0.0,
        )

        # Parse hero cards
        if row["hero_card1"]:
            hand.hero_cards.append(Card.parse(row["hero_card1"]))
        if row["hero_card2"]:
            hand.hero_cards.append(Card.parse(row["hero_card2"]))

        # Parse board
        if row["flop1"]:
            hand.flop = [
                Card.parse(row["flop1"]),
                Card.parse(row["flop2"]),
                Card.parse(row["flop3"]),
            ]
        if row["turn"]:
            hand.turn = Card.parse(row["turn"])
        if row["river"]:
            hand.river = Card.parse(row["river"])

        # Load players
        player_rows = conn.execute(
            "SELECT seat, name, position, stack FROM players WHERE hand_record_id = ?",
            (record_id,),
        ).fetchall()
        for pr in player_rows:
            hand.players[pr["seat"]] = pr["name"]
            hand.stacks[pr["seat"]] = pr["stack"] or 0.0
            if pr["position"]:
                try:
                    hand.positions[pr["seat"]] = Position(pr["position"])
                except ValueError:
                    pass

        # Load actions
        action_rows = conn.execute(
            "SELECT * FROM actions WHERE hand_record_id = ? ORDER BY seq",
            (record_id,),
        ).fetchall()
        for ar in action_rows:
            hand.actions.append(PlayerAction(
                player_name=ar["player_name"],
                seat=ar["seat"],
                action_type=ActionType(ar["action_type"]),
                amount=ar["amount"],
                street=Street(ar["street"]),
                is_all_in=bool(ar["is_all_in"]),
            ))

        # Load shown cards
        shown_rows = conn.execute(
            "SELECT seat, card FROM shown_cards WHERE hand_record_id = ?",
            (record_id,),
        ).fetchall()
        for sr in shown_rows:
            seat = sr["seat"]
            if seat not in hand.shown_cards:
                hand.shown_cards[seat] = []
            hand.shown_cards[seat].append(Card.parse(sr["card"]))

        # Load winners
        winner_rows = conn.execute(
            "SELECT seat, amount FROM winners WHERE hand_record_id = ?",
            (record_id,),
        ).fetchall()
        for wr in winner_rows:
            hand.winners[wr["seat"]] = wr["amount"]

        # Load uncalled bets
        uncalled_rows = conn.execute(
            "SELECT seat, amount FROM uncalled_bets WHERE hand_record_id = ?",
            (record_id,),
        ).fetchall()
        for ur in uncalled_rows:
            hand.uncalled_bets[ur["seat"]] = ur["amount"]

        return hand

    def get_sessions(self) -> list:
        """Get all import sessions."""
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY import_date DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_hand_count(self, session_id: Optional[str] = None) -> int:
        """Get total hand count."""
        with self.db.connect() as conn:
            if session_id:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM hands WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) as cnt FROM hands").fetchone()
            return row["cnt"]

    def save_training_result(self, hand_record_id: Optional[int],
                             scenario_type: str, user_action: str,
                             optimal_action: str, score: int,
                             feedback: str, focus_area: str = ""):
        """Save a training session result."""
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO training_results
                (hand_record_id, scenario_type, user_action, optimal_action,
                 score, feedback, focus_area)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (hand_record_id, scenario_type, user_action, optimal_action,
                 score, feedback, focus_area),
            )

    def get_training_results(self, limit: int = 50) -> list:
        """Get recent training results."""
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM training_results ORDER BY session_date DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    # === Analysis Result Cache ===
    def get_cached_analysis(self, hand_id: int, session_id: str,
                           analysis_type: str) -> Optional[dict]:
        """Get cached analysis result if exists."""
        with self.db.connect() as conn:
            row = conn.execute(
                """SELECT * FROM analysis_results
                WHERE hand_id = ? AND session_id = ? AND analysis_type = ?""",
                (hand_id, session_id, analysis_type),
            ).fetchone()
            if row:
                return dict(row)
            return None

    def save_analysis_result(self, hand_id: int, session_id: str,
                            analysis_type: str, ai_explanation: str,
                            ev_loss: Optional[float] = None,
                            error_grade: Optional[str] = None):
        """Save or update cached analysis result."""
        with self.db.connect() as conn:
            # Try update first
            existing = conn.execute(
                """SELECT id FROM analysis_results
                WHERE hand_id = ? AND session_id = ? AND analysis_type = ?""",
                (hand_id, session_id, analysis_type),
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE analysis_results
                    SET ai_explanation = ?, ev_loss = ?, error_grade = ?, created_at = CURRENT_TIMESTAMP
                    WHERE id = ?""",
                    (ai_explanation, ev_loss, error_grade, existing["id"]),
                )
            else:
                conn.execute(
                    """INSERT INTO analysis_results
                    (hand_id, session_id, analysis_type, ai_explanation, ev_loss, error_grade)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (hand_id, session_id, analysis_type, ai_explanation, ev_loss, error_grade),
                )

    def get_cached_analysis_count(self, session_id: Optional[str] = None) -> int:
        """Get number of cached analysis results."""
        with self.db.connect() as conn:
            if session_id:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM analysis_results WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM analysis_results"
                ).fetchone()
            return row["cnt"]

    # === Hand Filtering Methods ===
    def get_hands_by_filters(self,
                              session_id: Optional[str] = None,
                              position: Optional[str] = None,
                              min_blind: Optional[float] = None,
                              max_blind: Optional[float] = None,
                              hero_won: Optional[bool] = None,
                              went_to_showdown: Optional[bool] = None,
                              limit: Optional[int] = None,
                              sort_by: str = "hand_id",
                              descending: bool = True
                             ) -> list:
        """Get hands with multiple filter conditions."""
        with self.db.connect() as conn:
            query = "SELECT id, * FROM hands WHERE 1=1"
            params = []

            if session_id:
                query += " AND session_id = ?"
                params.append(session_id)

            if min_blind is not None:
                query += " AND big_blind >= ?"
                params.append(min_blind)

            if max_blind is not None:
                query += " AND big_blind <= ?"
                params.append(max_blind)

            if hero_won is not None:
                query += " AND hero_won = ?"
                params.append(int(hero_won))

            if went_to_showdown is not None:
                query += " AND went_to_showdown = ?"
                params.append(int(went_to_showdown))

            sort_columns = {"hand_id": "hand_id", "timestamp": "timestamp", "pot": "pot_total"}
            sort_col = sort_columns.get(sort_by, "hand_id")
            query += f" ORDER BY {sort_col} {'DESC' if descending else 'ASC'}"

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            rows = conn.execute(query, tuple(params)).fetchall()
            return [self._row_to_hand(conn, row) for row in rows]

    # === Bookmark Methods ===
    def add_bookmark(self, hand_id: int, session_id: str,
                   bookmark_type: str = "mistake",
                   notes: str = "", tags: str = "",
                   error_grade: str = ""):
        """Add a bookmark to a hand."""
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO bookmarks
                (hand_id, session_id, bookmark_type, notes, tags, error_grade)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (hand_id, session_id, bookmark_type, notes, tags, error_grade),
            )

    def remove_bookmark(self, bookmark_id: int):
        """Remove a bookmark."""
        with self.db.connect() as conn:
            conn.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))

    def get_bookmarks(self, session_id: Optional[str] = None,
                     bookmark_type: Optional[str] = None,
                     error_grade: Optional[str] = None) -> list:
        """Get all bookmarks, optionally filtered."""
        with self.db.connect() as conn:
            query = "SELECT * FROM bookmarks WHERE 1=1"
            params = []

            if session_id:
                query += " AND session_id = ?"
                params.append(session_id)

            if bookmark_type:
                query += " AND bookmark_type = ?"
                params.append(bookmark_type)

            if error_grade:
                query += " AND error_grade = ?"
                params.append(error_grade)

            query += " ORDER BY created_at DESC"
            rows = conn.execute(query, tuple(params)).fetchall()
            return [dict(r) for r in rows]

    # === Review Notes Methods ===
    def add_review_note(self, hand_id: int, session_id: str = "",
                      decision_point: str = "",
                      note_content: str = "",
                      tags: str = ""):
        """Add a note to a hand at a specific decision point."""
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO review_notes
                (hand_id, session_id, decision_point, note_content, tags)
                VALUES (?, ?, ?, ?, ?)""",
                (hand_id, session_id, decision_point, note_content, tags),
            )

    def get_review_notes(self, hand_id: Optional[int] = None,
                       session_id: Optional[str] = None) -> list:
        """Get review notes for a hand or session."""
        with self.db.connect() as conn:
            query = "SELECT * FROM review_notes WHERE 1=1"
            params = []

            if hand_id:
                query += " AND hand_id = ?"
                params.append(hand_id)

            if session_id:
                query += " AND session_id = ?"
                params.append(session_id)

            query += " ORDER BY created_at DESC"
            rows = conn.execute(query, tuple(params)).fetchall()
            return [dict(r) for r in rows]

    def remove_review_note(self, note_id: int):
        """Remove a review note by ID."""
        with self.db.connect() as conn:
            conn.execute("DELETE FROM review_notes WHERE id = ?", (note_id,))
