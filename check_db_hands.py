#!/usr/bin/env python3
"""Check what's in the database vs fresh parse."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from poker_advisor.storage import Database, HandRepository
from poker_advisor.parser.pokernow_parser import PokerNowParser
from poker_advisor.analysis.calculator import StatsCalculator


def main():
    project_dir = Path(__file__).parent
    hand_history_csv = project_dir / "2:15 手牌记录.csv"

    print("=" * 80)
    print("COMPARING DB DATA vs FRESH PARSE")
    print("=" * 80)

    # Check DB
    print("\n--- Step 1: Reading from Database ---")
    db = Database()
    repo = HandRepository(db)
    sessions = repo.get_sessions()
    print(f"Found {len(sessions)} sessions:")
    for s in sessions:
        print(f"  {s['id']}: {s['filename']} ({s['hand_count']} hands)")

    if sessions:
        latest_session = sessions[-1]
        print(f"\nUsing latest session: {latest_session['id']}")
        db_hands = repo.get_all_hands(session_id=latest_session['id'])
        print(f"Loaded {len(db_hands)} hands from DB")

        # Check if DB hands have uncalled_bets
        print("\n--- Checking DB hands for uncalled_bets ---")
        count_with_uncalled = 0
        for h in db_hands[:20]:
            if h.uncalled_bets:
                count_with_uncalled += 1
                print(f"  Hand {h.hand_id}: uncalled_bets = {h.uncalled_bets}")
        print(f"Total DB hands with uncalled_bets (first 20): {count_with_uncalled}")

        # Calculate stats from DB
        print("\n--- Calculating stats from DB hands ---")
        target_name = "女神异闻录"
        for hand in db_hands:
            for seat, name in hand.players.items():
                if target_name in name:
                    hand.hero_seat = seat
                    hand.hero_name = name
                    break

        calc = StatsCalculator()
        db_stats = calc.calculate(db_hands)
        print(f"DB - Profit: ${db_stats.total_profit:.2f}, BB/100: {db_stats.bb_per_100:.1f}, BB size: {db_stats.big_blind_size}")

    # Fresh parse
    print("\n--- Step 2: Fresh parsing from CSV ---")
    parser = PokerNowParser()
    fresh_hands = parser.parse_file(str(hand_history_csv))
    print(f"Fresh parsed {len(fresh_hands)} hands")

    print("\n--- Checking fresh hands for uncalled_bets ---")
    count_with_uncalled = 0
    for h in fresh_hands[:20]:
        if h.uncalled_bets:
            count_with_uncalled += 1
            print(f"  Hand {h.hand_id}: uncalled_bets = {h.uncalled_bets}")
    print(f"Total fresh hands with uncalled_bets (first 20): {count_with_uncalled}")

    # Calculate stats from fresh
    target_name = "女神异闻录"
    for hand in fresh_hands:
        for seat, name in hand.players.items():
            if target_name in name:
                hand.hero_seat = seat
                hand.hero_name = name
                break

    calc = StatsCalculator()
    fresh_stats = calc.calculate(fresh_hands)
    print(f"\nFresh - Profit: ${fresh_stats.total_profit:.2f}, BB/100: {fresh_stats.bb_per_100:.1f}, BB size: {fresh_stats.big_blind_size}")

    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    if sessions:
        print(f"DB data is OLD - needs to be re-imported!")
    print("\nTo fix:")
    print("1. Restart Streamlit (Ctrl+C then re-run)")
    print("2. Re-import the hand history CSV in the web UI")


if __name__ == "__main__":
    main()
