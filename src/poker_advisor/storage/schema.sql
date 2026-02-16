-- Poker Advisor Database Schema

CREATE TABLE IF NOT EXISTS hands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hand_id INTEGER NOT NULL,
    session_id TEXT,
    timestamp TEXT,
    player_count INTEGER,
    dealer_seat INTEGER,
    small_blind REAL,
    big_blind REAL,
    hero_seat INTEGER,
    hero_name TEXT,
    hero_card1 TEXT,
    hero_card2 TEXT,
    flop1 TEXT,
    flop2 TEXT,
    flop3 TEXT,
    turn TEXT,
    river TEXT,
    pot_total REAL,
    hero_won INTEGER DEFAULT 0,
    went_to_showdown INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, hand_id)
);

CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hand_record_id INTEGER NOT NULL,
    seat INTEGER NOT NULL,
    name TEXT NOT NULL,
    position TEXT,
    stack REAL,
    FOREIGN KEY (hand_record_id) REFERENCES hands(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hand_record_id INTEGER NOT NULL,
    seq INTEGER NOT NULL,
    player_name TEXT NOT NULL,
    seat INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    amount REAL DEFAULT 0,
    street TEXT NOT NULL,
    is_all_in INTEGER DEFAULT 0,
    FOREIGN KEY (hand_record_id) REFERENCES hands(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS shown_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hand_record_id INTEGER NOT NULL,
    seat INTEGER NOT NULL,
    card TEXT NOT NULL,
    FOREIGN KEY (hand_record_id) REFERENCES hands(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS winners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hand_record_id INTEGER NOT NULL,
    seat INTEGER NOT NULL,
    amount REAL NOT NULL,
    FOREIGN KEY (hand_record_id) REFERENCES hands(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    filename TEXT,
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    hand_count INTEGER DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS training_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    hand_record_id INTEGER,
    scenario_type TEXT,
    user_action TEXT,
    optimal_action TEXT,
    score INTEGER,
    feedback TEXT,
    focus_area TEXT,
    FOREIGN KEY (hand_record_id) REFERENCES hands(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hand_id INTEGER NOT NULL,
    session_id TEXT,
    analysis_type TEXT NOT NULL, -- 'full_session' | 'single_hand'
    ai_explanation TEXT,
    ev_loss REAL,
    error_grade TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(hand_id, session_id, analysis_type)
);

CREATE TABLE IF NOT EXISTS bookmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hand_id INTEGER NOT NULL,
    session_id TEXT,
    bookmark_type TEXT NOT NULL DEFAULT 'mistake', -- 'mistake' | 'great_hand' | 'review'
    notes TEXT,
    tags TEXT, -- comma-separated
    error_grade TEXT, -- S/A/B/C
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS review_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hand_id INTEGER NOT NULL,
    session_id TEXT,
    decision_point TEXT, -- street or decision
    note_content TEXT,
    tags TEXT, -- comma-separated
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS training_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_name TEXT,
    focus_areas TEXT, -- comma-separated
    difficulty TEXT,
    duration_days INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_hands_session ON hands(session_id);
CREATE INDEX IF NOT EXISTS idx_hands_hand_id ON hands(hand_id);
CREATE INDEX IF NOT EXISTS idx_actions_hand ON actions(hand_record_id);
CREATE INDEX IF NOT EXISTS idx_players_hand ON players(hand_record_id);
CREATE INDEX IF NOT EXISTS idx_training_date ON training_results(session_date);
CREATE INDEX IF NOT EXISTS idx_analysis_cache ON analysis_results(hand_id, analysis_type);
CREATE INDEX IF NOT EXISTS idx_bookmarks_hand ON bookmarks(hand_id, session_id);
CREATE INDEX IF NOT EXISTS idx_review_notes_hand ON review_notes(hand_id, session_id);
