"""End-to-end integration tests.

Tests the full pipeline: parse → store → retrieve → analyze → detect leaks → generate scenarios.
"""

import os
import tempfile
import pytest

from poker_advisor.parser.pokernow_parser import PokerNowParser
from poker_advisor.storage.database import Database
from poker_advisor.storage.repository import HandRepository
from poker_advisor.analysis.calculator import StatsCalculator
from poker_advisor.analysis.positional import PositionalAnalyzer
from poker_advisor.analysis.leak_detector import LeakDetector
from poker_advisor.training.scenario import ScenarioGenerator
from poker_advisor.formatters.text import TextFormatter
from poker_advisor.formatters.table import TableFormatter


@pytest.fixture
def db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["POKER_DB_PATH"] = path
    database = Database(path)
    yield database
    os.unlink(path)


@pytest.fixture
def repo(db):
    return HandRepository(db)


@pytest.fixture
def parsed_hands():
    parser = PokerNowParser()
    return parser.parse_file("tests/fixtures/sample_log.txt")


class TestFullPipeline:
    """Test the complete data flow from parse to analysis."""

    def test_parse_store_retrieve(self, repo, parsed_hands):
        """Parse → Store → Retrieve roundtrip."""
        assert len(parsed_hands) == 3

        session_id = repo.save_session(parsed_hands, filename="test.txt",
                                        notes="integration test")
        assert len(session_id) == 8

        # Retrieve all
        retrieved = repo.get_all_hands()
        assert len(retrieved) == 3

        # Retrieve by session
        by_session = repo.get_all_hands(session_id=session_id)
        assert len(by_session) == 3

        # Retrieve single hand
        hand = repo.get_hand_by_hand_id(1, session_id=session_id)
        assert hand is not None
        assert hand.hand_id == 1

    def test_parse_to_stats(self, parsed_hands):
        """Parse → Calculate stats."""
        calc = StatsCalculator()
        stats = calc.calculate(parsed_hands)

        assert stats.overall.total_hands == 3
        assert stats.player_name != ""
        assert stats.overall.vpip >= 0
        assert stats.overall.pfr >= 0

        # Summary dict has all expected keys
        d = stats.summary_dict()
        expected_keys = {"VPIP", "PFR", "3-Bet%", "AF", "C-Bet%",
                         "Fold to C-Bet%", "WTSD%", "W$SD%", "BB/100", "Hands"}
        assert set(d.keys()) == expected_keys

    def test_parse_to_positional(self, parsed_hands):
        """Parse → Stats → Positional analysis."""
        calc = StatsCalculator()
        stats = calc.calculate(parsed_hands)

        analyzer = PositionalAnalyzer()
        pos_rows = analyzer.position_summary(stats)
        assert isinstance(pos_rows, list)

        group_rows = analyzer.group_summary(stats)
        assert isinstance(group_rows, list)

    def test_parse_to_leaks(self, parsed_hands):
        """Parse → Stats → Leak detection."""
        calc = StatsCalculator()
        stats = calc.calculate(parsed_hands)

        detector = LeakDetector()
        leaks = detector.detect(stats)
        # With only 3 hands, should return no leaks (below min threshold)
        assert isinstance(leaks, list)
        assert len(leaks) == 0  # too few hands

    def test_parse_to_training(self, parsed_hands):
        """Parse → Generate training scenarios."""
        gen = ScenarioGenerator()
        scenarios = gen.generate(parsed_hands, count=10)

        assert len(scenarios) >= 1
        for s in scenarios:
            assert s.description
            assert s.available_actions
            assert s.scenario_type
            assert s.decision_street

    def test_store_retrieve_sessions(self, repo, parsed_hands):
        """Store hands and retrieve session list."""
        sid = repo.save_session(parsed_hands, filename="test.txt")

        sessions = repo.get_sessions()
        assert len(sessions) >= 1
        assert any(s["id"] == sid for s in sessions)

    def test_store_training_results(self, repo):
        """Save and retrieve training results."""
        repo.save_training_result(
            hand_record_id=None,
            scenario_type="preflop_open",
            user_action="Raise $3.00",
            optimal_action="Raise $3.00",
            score=8,
            feedback="Good play",
            focus_area="preflop",
        )

        results = repo.get_training_results()
        assert len(results) == 1
        assert results[0]["score"] == 8
        assert results[0]["scenario_type"] == "preflop_open"

    def test_multiple_sessions(self, repo, parsed_hands):
        """Import multiple sessions and filter by session."""
        sid1 = repo.save_session(parsed_hands, filename="session1.txt")
        sid2 = repo.save_session(parsed_hands, filename="session2.txt")

        all_hands = repo.get_all_hands()
        assert len(all_hands) == 6

        s1_hands = repo.get_all_hands(session_id=sid1)
        assert len(s1_hands) == 3

        s2_hands = repo.get_all_hands(session_id=sid2)
        assert len(s2_hands) == 3


class TestFormatters:
    """Test formatters don't crash on real data."""

    def test_text_formatter(self, parsed_hands):
        fmt = TextFormatter()

        # Format hand
        text = fmt.format_hand(parsed_hands[0])
        assert "Hand #" in text
        assert "$" in text

        # Format stats
        calc = StatsCalculator()
        stats = calc.calculate(parsed_hands)
        stats_text = fmt.format_stats_summary(stats)
        assert "VPIP" in stats_text
        assert "PFR" in stats_text

        # Format leaks (empty list)
        leak_text = fmt.format_leaks([])
        assert "No significant leaks" in leak_text

    def test_table_formatter_no_crash(self, parsed_hands):
        """TableFormatter methods should not raise on real data."""
        from io import StringIO
        from rich.console import Console

        buf = StringIO()
        console = Console(file=buf)
        fmt = TableFormatter(console)

        calc = StatsCalculator()
        stats = calc.calculate(parsed_hands)

        # These should not raise
        fmt.print_stats(stats)
        fmt.print_positional_stats(stats)
        fmt.print_leaks([])
        fmt.print_hands_list(parsed_hands)
        fmt.print_hand(parsed_hands[0])
        fmt.print_training_progress([])

        output = buf.getvalue()
        assert len(output) > 0


class TestCLIEntryPoint:
    """Test CLI module can be loaded."""

    def test_app_import(self):
        from cli.main import app
        assert app is not None

    def test_commands_registered(self):
        from cli.main import app
        # Typer stores commands in registered_commands or similar
        info = app.info
        assert info.name == "poker-advisor"
