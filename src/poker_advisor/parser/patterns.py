"""All regex patterns for Poker Now log parsing."""

import re

# Hand boundaries
# Old: -- starting hand #1 (dealer: "Player2") --
# New: -- starting hand #358 (id: xxx)  No Limit Texas Hold'em (dealer: "Name @ ID") --
HAND_START = re.compile(
    r'-- starting hand #(\d+)'
    r'(?:\s*\(id:\s*\w+\))?'
    r'(?:\s+[^(]*)?'
    r'(?:\(dealer:\s*"([^"]+)"\))?',
    re.IGNORECASE,
)
HAND_END = re.compile(r'-- ending hand #(\d+)', re.IGNORECASE)

# Player joining / seating
PLAYER_SEAT = re.compile(
    r'"([^"]+)"\s*@\s*seat\s*#?(\d+)'
)

# Player stacks at start of hand
# Old: "Player1" @ seat #1 ($100.00)
# New: #1 "Wesley @ 4KT6D07Q4u" (10789)
PLAYER_STACKS_OLD = re.compile(
    r'"([^"]+)"\s*@\s*seat\s*#?(\d+)\s*\(\s*\$?([\d,]+\.?\d*)\s*\)'
)
PLAYER_STACKS_NEW = re.compile(
    r'#(\d+)\s*"([^"]+)"\s*\(\s*\$?([\d,]+\.?\d*)\s*\)'
)
# Keep PLAYER_STACKS as alias for backward compat in case anything references it
PLAYER_STACKS = PLAYER_STACKS_OLD

# Hero hand
HERO_HAND = re.compile(
    r'Your\s+hand\s+is\s+((?:10|[2-9TJQKA])[hdcs♥♦♣♠]),?\s*((?:10|[2-9TJQKA])[hdcs♥♦♣♠])',
    re.IGNORECASE,
)

# Blinds posting
# Old: "Player1" @ seat #1 posts a big blind of $1.00
# New: "Name @ ID" posts a big blind of 20
POST_BLIND = re.compile(
    r'"([^"]+)"(?:\s*@\s*seat\s*#?(\d+))?\s+'
    r'(posts\s+a\s+small\s+blind|posts\s+a\s+big\s+blind|posts\s+a\s+missing\s+small\s+blind|posts\s+a\s+missing\s+big\s+blind|posts\s+a\s+straddle)\s+of\s+\$?([\d,]+\.?\d*)',
    re.IGNORECASE,
)

# Player actions — seat is optional for new format
PLAYER_FOLD = re.compile(
    r'"([^"]+)"(?:\s*@\s*seat\s*#?(\d+))?\s+folds',
    re.IGNORECASE,
)
PLAYER_CHECK = re.compile(
    r'"([^"]+)"(?:\s*@\s*seat\s*#?(\d+))?\s+checks',
    re.IGNORECASE,
)
PLAYER_CALL = re.compile(
    r'"([^"]+)"(?:\s*@\s*seat\s*#?(\d+))?\s+calls\s+\$?([\d,]+\.?\d*)',
    re.IGNORECASE,
)
PLAYER_BET = re.compile(
    r'"([^"]+)"(?:\s*@\s*seat\s*#?(\d+))?\s+bets\s+\$?([\d,]+\.?\d*)',
    re.IGNORECASE,
)
PLAYER_RAISE = re.compile(
    r'"([^"]+)"(?:\s*@\s*seat\s*#?(\d+))?\s+raises\s+(?:to\s+)?\$?([\d,]+\.?\d*)',
    re.IGNORECASE,
)

# All-in detection (can appear in combination with above)
ALL_IN = re.compile(r'all\s*in', re.IGNORECASE)

# Community cards
# Old: Flop:  [5♠, T♥, 7♦]
# New: Flop:  [Q♠, 2♣, J♦]  (same bracket format for flop)
FLOP = re.compile(
    r'Flop[:\s]*(?:\([^)]*\)\s*)?\[([^\]]+)\]',
    re.IGNORECASE,
)
# Old: Turn:  [5♠, T♥, 7♦, 3♣]  (all cards in brackets)
# New: Turn: Q♠, 2♣, J♦ [4♣]    (previous cards outside, new card in brackets)
# Pattern handles both: allows optional text before the bracket
TURN = re.compile(
    r'Turn[:\s]*[^[]*\[([^\]]+)\]',
    re.IGNORECASE,
)
RIVER = re.compile(
    r'River[:\s]*[^[]*\[([^\]]+)\]',
    re.IGNORECASE,
)

# Show cards — old format: one card per line with named suits
SHOW_CARDS = re.compile(
    r'"([^"]+)"(?:\s*@\s*seat\s*#?(\d+))?\s+shows\s+a\s+((?:10|[2-9TJQKA])+)\s+of\s+(Hearts|Diamonds|Clubs|Spades)',
    re.IGNORECASE,
)

# Show cards — new format with symbols: "Name" shows a 5♦, 9♦.
SHOW_CARDS_SYMBOL = re.compile(
    r'"([^"]+)"(?:\s*@\s*seat\s*#?(\d+))?\s+shows\s+a\s+((?:10|[2-9TJQKA])[♥♦♣♠]),?\s*((?:10|[2-9TJQKA])[♥♦♣♠])',
    re.IGNORECASE,
)

# Alternative show pattern (card notation with brackets)
SHOW_CARDS_ALT = re.compile(
    r'"([^"]+)"(?:\s*@\s*seat\s*#?(\d+))?\s+shows\s+\[([^\]]+)\]',
    re.IGNORECASE,
)

# Pot collection
# Old: "Player2" @ seat #3 collected $10.00 from pot
# New: "Wesley @ ID" collected 40 from pot
# New: "Wesley @ ID" collected 14690 from pot with Flush, A High (combination: ...)
POT_COLLECT = re.compile(
    r'"([^"]+)"(?:\s*@\s*seat\s*#?(\d+))?\s+collected\s+\$?([\d,]+\.?\d*)\s+from\s+(?:the\s+)?pot',
    re.IGNORECASE,
)

# Blinds change
BLINDS_CHANGE = re.compile(
    r'Blinds\s+(?:increased|changed)\s+to\s+\$?([\d,]+\.?\d*)\s*/\s*\$?([\d,]+\.?\d*)',
    re.IGNORECASE,
)

# Dealer button
DEALER_BUTTON = re.compile(
    r'(?:dealer|button):\s*"([^"]+)"',
    re.IGNORECASE,
)

# Card pattern for parsing board cards
CARD_PATTERN = re.compile(r'((?:10|[2-9TJQKA])+)\s*of\s*(Hearts|Diamonds|Clubs|Spades)|((?:10|[2-9TJQKA])[hdcs♥♦♣♠])', re.IGNORECASE)

# Timestamp in log lines (Poker Now format)
TIMESTAMP = re.compile(r'^(\d{4}-\d{2}-\d{2}T[\d:.]+Z?)\s*--\s*', re.IGNORECASE)

# Dead button / uncalled bet
UNCALLED_BET = re.compile(
    r'[Uu]ncalled\s+(?:portion\s+of\s+)?bet\s+\(?\$?([\d,]+\.?\d*)\)?\s+returned\s+to\s+"([^"]+)"',
    re.IGNORECASE,
)

# Pot info line
POT_INFO = re.compile(
    r'(?:main\s+)?pot:\s*\$?([\d,]+\.?\d*)',
    re.IGNORECASE,
)

# Hand result line
HAND_RESULT = re.compile(
    r'"([^"]+)"(?:\s*@\s*seat\s*#?(\d+))?\s+(?:wins|gained)\s+\$?([\d,]+\.?\d*)',
    re.IGNORECASE,
)
