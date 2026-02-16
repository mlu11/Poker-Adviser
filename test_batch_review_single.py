#!/usr/bin/env python3
"""Test that batch review is using correct API key and endpoint for deep analysis."""

import sys
sys.path.insert(0, './src')

from poker_advisor import config
from poker_advisor.storage.database import Database
from poker_advisor.storage.repository import HandRepository
from poker_advisor.ai.analyzer import StrategyAnalyzer
from poker_advisor.analysis.batch_reviewer import BatchReviewer

print("=== Testing deep model configuration ===")
print(f"DOUBAO_CODE_API_KEY: {config.DOUBAO_CODE_API_KEY}")
print(f"DOUBAO_CODE_API_ENDPOINT: {config.DOUBAO_CODE_API_ENDPOINT}")
print(f"DOUBAO_CODE_MODEL: {config.DOUBAO_CODE_MODEL}")
print(f"DEEP_ANALYSIS_MODEL: {config.DEEP_ANALYSIS_MODEL}")
print()

# Get one hand from the session
db = Database()
repo = HandRepository(db)
hands = repo.get_all_hands(session_id="635d83d4")
print(f"Found {len(hands)} hands in session 635d83d4")

if hands:
    hand = hands[0]
    print(f"\nFirst hand: hand_id={hand.hand_id}, session_id={hand.session_id}")
    print(f"Hero cards: {hand.hero_cards_str if hasattr(hand, 'hero_cards_str') else '?'}")

    # Test direct review_hand with deep=True
    analyzer = StrategyAnalyzer()
    print("\n=== Testing review_hand with deep=True ===")
    print("Expected: uses DOUBAO_CODE_API_KEY + https://ark.cn-beijing.volces.com/api/coding/v3\n")
    
    import traceback
    try:
        result = analyzer.review_hand(hand, hands, deep=True, use_cache=False)
        print("\n✅ SUCCESS! Got response:")
        print(result[:300] + "..." if len(result) > 300 else result)
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        traceback.print_exc()
