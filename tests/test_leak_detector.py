"""Tests for the leak detector."""

import pytest

from poker_advisor.models.stats import PlayerStats, PositionalStats
from poker_advisor.models.position import Position
from poker_advisor.analysis.leak_detector import (
    LeakDetector, Leak, Severity, MIN_HANDS_OVERALL, MIN_HANDS_POSITION,
)


def _make_stats(total_hands=100, vpip_count=25, pfr_count=20,
                three_bet_opp=20, three_bet_made=2,
                bets=30, raises=10, calls=20, folds=15,
                cbet_opp=15, cbet_made=10,
                faced_cbet=10, folded_to_cbet=4,
                saw_flop=50, went_to_showdown=15, won_at_showdown=8,
                **kwargs) -> PlayerStats:
    """Create a PlayerStats with controllable values."""
    overall = PositionalStats(
        total_hands=total_hands,
        voluntarily_put_in_pot=vpip_count,
        preflop_raise=pfr_count,
        three_bet_opportunities=three_bet_opp,
        three_bet_made=three_bet_made,
        bets=bets,
        raises=raises,
        calls=calls,
        folds=folds,
        cbet_opportunities=cbet_opp,
        cbet_made=cbet_made,
        faced_cbet=faced_cbet,
        folded_to_cbet=folded_to_cbet,
        saw_flop=saw_flop,
        went_to_showdown=went_to_showdown,
        won_at_showdown=won_at_showdown,
    )
    stats = PlayerStats(player_name="Hero", overall=overall)
    return stats


class TestLeakDetectorBasic:
    """Basic leak detection tests."""

    def test_no_leaks_for_balanced_player(self):
        # Values within GTO baselines
        stats = _make_stats(
            vpip_count=25,   # 25% VPIP
            pfr_count=20,    # 20% PFR
            three_bet_opp=20, three_bet_made=2,  # 10% 3bet (in range)
            bets=30, raises=10, calls=15,  # AF = 2.67 (in range)
            cbet_opp=15, cbet_made=10,  # 66.7% cbet (in range)
            faced_cbet=10, folded_to_cbet=4,  # 40% fold to cbet (in range)
            saw_flop=50, went_to_showdown=15, won_at_showdown=8,  # WTSD 30%, WSD 53%
        )
        detector = LeakDetector()
        leaks = detector.detect(stats)
        assert len(leaks) == 0

    def test_too_few_hands_returns_no_leaks(self):
        stats = _make_stats(total_hands=10)
        detector = LeakDetector()
        leaks = detector.detect(stats)
        assert len(leaks) == 0

    def test_high_vpip_detected(self):
        stats = _make_stats(vpip_count=45)  # 45% VPIP — way too high
        detector = LeakDetector()
        leaks = detector.detect(stats)
        vpip_leaks = [l for l in leaks if l.metric == "vpip"]
        assert len(vpip_leaks) >= 1
        assert vpip_leaks[0].actual_value == 45.0
        assert "过高" in vpip_leaks[0].description

    def test_low_vpip_detected(self):
        stats = _make_stats(vpip_count=12)  # 12% VPIP — too tight
        detector = LeakDetector()
        leaks = detector.detect(stats)
        vpip_leaks = [l for l in leaks if l.metric == "vpip"]
        assert len(vpip_leaks) >= 1
        assert "过低" in vpip_leaks[0].description

    def test_high_pfr_detected(self):
        stats = _make_stats(pfr_count=35)  # 35% PFR
        detector = LeakDetector()
        leaks = detector.detect(stats)
        pfr_leaks = [l for l in leaks if l.metric == "pfr"]
        assert len(pfr_leaks) >= 1

    def test_low_af_detected(self):
        stats = _make_stats(bets=5, raises=2, calls=30)  # AF = 0.23
        detector = LeakDetector()
        leaks = detector.detect(stats)
        af_leaks = [l for l in leaks if l.metric == "af"]
        assert len(af_leaks) >= 1
        assert "不足" in af_leaks[0].description

    def test_vpip_pfr_gap_detected(self):
        stats = _make_stats(vpip_count=30, pfr_count=10)  # gap = 20%
        detector = LeakDetector()
        leaks = detector.detect(stats)
        gap_leaks = [l for l in leaks if l.metric == "vpip_pfr_gap"]
        assert len(gap_leaks) == 1
        assert gap_leaks[0].severity == Severity.MAJOR

    def test_vpip_pfr_gap_not_triggered_when_small(self):
        stats = _make_stats(vpip_count=25, pfr_count=20)  # gap = 5%
        detector = LeakDetector()
        leaks = detector.detect(stats)
        gap_leaks = [l for l in leaks if l.metric == "vpip_pfr_gap"]
        assert len(gap_leaks) == 0


class TestSeverity:
    """Test severity classification."""

    def test_minor_severity(self):
        # Slightly outside range
        stats = _make_stats(vpip_count=31)  # 31% — just above 30% ceiling
        detector = LeakDetector()
        leaks = detector.detect(stats)
        vpip_leaks = [l for l in leaks if l.metric == "vpip"]
        assert len(vpip_leaks) >= 1
        assert vpip_leaks[0].severity == Severity.MINOR

    def test_major_severity(self):
        # Far outside range
        stats = _make_stats(vpip_count=50)  # 50% — way above 30% ceiling
        detector = LeakDetector()
        leaks = detector.detect(stats)
        vpip_leaks = [l for l in leaks if l.metric == "vpip"]
        assert len(vpip_leaks) >= 1
        assert vpip_leaks[0].severity == Severity.MAJOR

    def test_leaks_sorted_by_severity(self):
        # Create a player with multiple leaks of different severity
        stats = _make_stats(
            vpip_count=50,  # major
            pfr_count=25,   # minor (just above 24)
            bets=2, raises=1, calls=30,  # AF 0.1 — major
        )
        detector = LeakDetector()
        leaks = detector.detect(stats)
        severities = [l.severity for l in leaks]
        # Major should come first
        for i in range(len(severities) - 1):
            severity_order = {Severity.MAJOR: 0, Severity.MODERATE: 1, Severity.MINOR: 2}
            assert severity_order[severities[i]] <= severity_order[severities[i + 1]]


class TestPositionalLeaks:
    """Test position-specific leak detection."""

    def test_position_specific_leak(self):
        stats = _make_stats(vpip_count=25, pfr_count=20)

        # Add position stats with a leak in early position
        early_stats = PositionalStats(
            position=Position.UTG,
            total_hands=20,
            voluntarily_put_in_pot=10,  # 50% VPIP from UTG — way too loose
            preflop_raise=8,
        )
        stats.by_position[Position.UTG] = early_stats

        detector = LeakDetector()
        leaks = detector.detect(stats)

        early_leaks = [l for l in leaks if l.position == "Early"]
        assert len(early_leaks) >= 1
        assert any("Early" in l.description for l in early_leaks)

    def test_position_group_too_few_hands_skipped(self):
        stats = _make_stats()
        # Only 5 hands from UTG — below MIN_HANDS_POSITION
        early_stats = PositionalStats(
            position=Position.UTG,
            total_hands=5,
            voluntarily_put_in_pot=5,  # 100% VPIP — would be a huge leak
        )
        stats.by_position[Position.UTG] = early_stats

        detector = LeakDetector()
        leaks = detector.detect(stats)
        early_leaks = [l for l in leaks if l.position == "Early"]
        assert len(early_leaks) == 0  # Skipped due to sample size


class TestMinSampleSizes:
    """Test that metrics with insufficient samples are skipped."""

    def test_cbet_skipped_with_few_opportunities(self):
        stats = _make_stats(cbet_opp=2, cbet_made=0)  # Too few opportunities
        detector = LeakDetector()
        leaks = detector.detect(stats)
        cbet_leaks = [l for l in leaks if l.metric == "cbet_pct"]
        assert len(cbet_leaks) == 0

    def test_fold_to_cbet_skipped_with_few_samples(self):
        stats = _make_stats(faced_cbet=2, folded_to_cbet=2)
        detector = LeakDetector()
        leaks = detector.detect(stats)
        ftc_leaks = [l for l in leaks if l.metric == "fold_to_cbet"]
        assert len(ftc_leaks) == 0

    def test_wtsd_skipped_with_few_flops(self):
        stats = _make_stats(saw_flop=3, went_to_showdown=3)
        detector = LeakDetector()
        leaks = detector.detect(stats)
        wtsd_leaks = [l for l in leaks if l.metric == "wtsd"]
        assert len(wtsd_leaks) == 0
