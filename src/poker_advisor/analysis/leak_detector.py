"""Leak detector — compare player stats against GTO baselines."""

import json
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from poker_advisor.models.stats import PlayerStats, PositionalStats
from poker_advisor.models.position import Position


class Severity(str, Enum):
    """S/A/B/C four-level severity classification based on EV loss."""
    S = "S"       # Critical: > 5 BB/100 EV loss
    A = "A"       # Major: 3-5 BB/100 EV loss
    B = "B"       # Moderate: 1-3 BB/100 EV loss
    C = "C"       # Minor: < 1 BB/100 EV loss


@dataclass
class Leak:
    """A detected weakness in the player's game."""
    metric: str
    description: str
    severity: Severity
    actual_value: float
    baseline_low: float
    baseline_high: float
    position: Optional[str] = None
    advice: str = ""
    ev_loss_bb100: float = 0.0  # Estimated EV loss in BB per 100 hands


# Load baselines from config file
def _load_baselines() -> tuple[Dict[str, tuple], Dict[str, Dict[str, tuple]]]:
    """Load GTO baselines from config JSON file."""
    config_path = Path(__file__).parent.parent.parent / "config" / "baselines.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data["overall"], data["positions"]
    # Fallback to defaults if config file not found
    return {
        "vpip":           (22.0, 30.0),
        "pfr":            (17.0, 24.0),
        "three_bet_pct":  (6.0, 10.0),
        "af":             (2.0, 4.0),
        "cbet_pct":       (55.0, 75.0),
        "fold_to_cbet":   (35.0, 55.0),
        "wtsd":           (25.0, 35.0),
        "wsd":            (48.0, 56.0),
    }, {
        "Early": {
            "vpip": (14.0, 20.0),
            "pfr":  (12.0, 18.0),
        },
        "Middle": {
            "vpip": (18.0, 26.0),
            "pfr":  (15.0, 22.0),
        },
        "Late": {
            "vpip": (28.0, 40.0),
            "pfr":  (22.0, 32.0),
        },
        "Blinds": {
            "vpip": (20.0, 30.0),
            "pfr":  (12.0, 20.0),
        },
    }


# GTO baseline ranges loaded from config
GTO_BASELINES, POSITION_ADJUSTMENTS = _load_baselines()

# Minimum hands required for a metric to be considered reliable
MIN_HANDS_OVERALL = 30
MIN_HANDS_POSITION = 15

# Human-readable descriptions for detected leaks
LEAK_DESCRIPTIONS = {
    ("vpip", "high"): (
        "VPIP 过高 — 入池过于频繁",
        "收紧起手牌范围，尤其在前位。专注于只用优质起手牌入池。"
    ),
    ("vpip", "low"): (
        "VPIP 过低 — 打得过紧",
        "适当放宽入池范围，特别是在有利位置。过紧会让对手容易读出你的牌力范围。"
    ),
    ("pfr", "high"): (
        "PFR 过高 — 翻前加注过于频繁",
        "减少边缘牌的加注，尤其在前位。更多使用平跟来平衡范围。"
    ),
    ("pfr", "low"): (
        "PFR 过低 — 翻前不够主动",
        "用更多牌进行开池加注而非平跟。被动入池会让你在翻后处于信息劣势。"
    ),
    ("three_bet_pct", "high"): (
        "3-Bet 频率过高",
        "减少轻 3-Bet 的频率。过多的 3-Bet 会让你在被 4-Bet 时陷入困境。"
    ),
    ("three_bet_pct", "low"): (
        "3-Bet 频率过低",
        "增加 3-Bet 频率，特别是对后位开池者。加入一些诈唬 3-Bet（如同花 A5s）来平衡范围。"
    ),
    ("af", "high"): (
        "翻后攻击性过高",
        "减少无意义的翻后下注。不是所有翻面都适合持续施压，学会适时控池。"
    ),
    ("af", "low"): (
        "翻后攻击性不足",
        "在有利的翻面结构上更多下注和加注。被动的翻后打法会错失很多价值。"
    ),
    ("cbet_pct", "high"): (
        "持续下注频率过高",
        "不要在所有翻面都 C-Bet。在不利翻面（湿润、对手范围有利）时学会过牌。"
    ),
    ("cbet_pct", "low"): (
        "持续下注频率过低",
        "在有利翻面结构上更频繁地 C-Bet。作为翻前进攻者，你有范围优势。"
    ),
    ("fold_to_cbet", "high"): (
        "面对 C-Bet 弃牌过多",
        "增加防守频率：更多跟注甚至加注 C-Bet。对手可以通过频繁 C-Bet 来剥削你。"
    ),
    ("fold_to_cbet", "low"): (
        "面对 C-Bet 弃牌过少",
        "不要用过弱的牌防守 C-Bet。在不利翻面上学会放弃边缘牌。"
    ),
    ("wtsd", "high"): (
        "去摊牌频率过高 — 跟注站倾向",
        "学会在回合推进时放弃边缘牌。不要因为已经投入很多就不愿弃牌。"
    ),
    ("wtsd", "low"): (
        "去摊牌频率过低 — 弃牌过早",
        "增加中等牌力的跟注频率。过早弃牌会让对手用诈唬频繁获利。"
    ),
    ("wsd", "high"): (
        "摊牌胜率偏高 — 可能打得过紧",
        "摊牌胜率高说明你只在很强的时候才去摊牌。可以适当用更宽的范围去摊牌。"
    ),
    ("wsd", "low"): (
        "摊牌胜率偏低 — 跟注太宽",
        "减少用弱牌去摊牌的频率。如果经常在摊牌时输钱，说明跟注标准过低。"
    ),
    ("wwsf", "low"): (
        "未摊牌赢率偏低",
        "增加翻后进攻频率，更多用下注/加注拿下底池无需摊牌。"
    ),
    ("wwsf", "high"): (
        "未摊牌赢率偏高",
        "诈唬频率可能过高。适当减少不必要的bluff。"
    ),
}


class LeakDetector:
    """Detect leaks by comparing player stats against GTO baselines."""

    def detect(self, player_stats: PlayerStats) -> List[Leak]:
        """Analyze player stats and return detected leaks sorted by severity."""
        leaks = []

        if player_stats.overall.total_hands < MIN_HANDS_OVERALL:
            return leaks

        # Check overall stats
        overall = player_stats.overall
        leaks.extend(self._check_stats(overall, GTO_BASELINES, position=None))

        # Check position-specific stats
        group_positions = {
            "Early": [Position.UTG, Position.UTG1],
            "Middle": [Position.MP, Position.MP1, Position.HJ],
            "Late": [Position.CO, Position.BTN],
            "Blinds": [Position.SB, Position.BB],
        }

        for group_name, positions in group_positions.items():
            merged = self._merge_position_stats(player_stats, positions)
            if merged.total_hands < MIN_HANDS_POSITION:
                continue

            baselines = dict(GTO_BASELINES)
            if group_name in POSITION_ADJUSTMENTS:
                baselines.update(POSITION_ADJUSTMENTS[group_name])

            group_leaks = self._check_stats(merged, baselines, position=group_name)
            leaks.extend(group_leaks)

        # Sort by severity (S first, then A, B, C) and by EV loss
        severity_order = {Severity.S: 0, Severity.A: 1, Severity.B: 2, Severity.C: 3}
        leaks.sort(key=lambda l: (severity_order[l.severity], -l.ev_loss_bb100))
        return leaks

    def _check_stats(self, stats: PositionalStats,
                     baselines: Dict[str, tuple],
                     position: Optional[str]) -> List[Leak]:
        """Check a set of stats against baselines."""
        leaks = []

        metric_getters = {
            "vpip": stats.vpip,
            "pfr": stats.pfr,
            "three_bet_pct": stats.three_bet_pct,
            "af": stats.aggression_factor,
            "cbet_pct": stats.cbet_pct,
            "fold_to_cbet": stats.fold_to_cbet_pct,
            "wtsd": stats.wtsd,
            "wsd": stats.wsd,
            "wwsf": stats.wwsf,
        }

        # Skip metrics that need minimum sample sizes
        min_samples = {
            "three_bet_pct": stats.three_bet_opportunities >= 10,
            "cbet_pct": stats.cbet_opportunities >= 5,
            "fold_to_cbet": stats.faced_cbet >= 5,
            "wtsd": stats.saw_flop >= 10,
            "wsd": stats.went_to_showdown >= 5,
            "wwsf": stats.saw_flop >= 10,
        }

        for metric, value in metric_getters.items():
            if metric not in baselines:
                continue
            if metric in min_samples and not min_samples[metric]:
                continue

            low, high = baselines[metric]
            if value < low:
                leak = self._create_leak(metric, "low", value, low, high, position)
                if leak:
                    leaks.append(leak)
            elif value > high:
                leak = self._create_leak(metric, "high", value, low, high, position)
                if leak:
                    leaks.append(leak)

        # Check VPIP-PFR gap (should be small, ideally < 6)
        if "vpip" in baselines and "pfr" in baselines:
            gap = stats.vpip - stats.pfr
            if gap > 10 and stats.total_hands >= MIN_HANDS_OVERALL:
                # Severity based on gap size
                deviation_pp = gap - 6.0
                ev_loss = deviation_pp * 0.35
                if gap > 30:
                    severity = Severity.S
                elif gap > 20:
                    severity = Severity.A
                elif gap > 14:
                    severity = Severity.B
                else:
                    severity = Severity.C
                leaks.append(Leak(
                    metric="vpip_pfr_gap",
                    description="VPIP-PFR 差距过大 — 过多冷跟注",
                    severity=severity,
                    actual_value=round(gap, 1),
                    baseline_low=0.0,
                    baseline_high=6.0,
                    position=position,
                    advice="减少翻前平跟的频率。大部分你选择入池的牌应该通过加注入池，而非冷跟注。",
                    ev_loss_bb100=round(ev_loss, 2),
                ))

        return leaks

    def _create_leak(self, metric: str, direction: str,
                     value: float, low: float, high: float,
                     position: Optional[str]) -> Optional[Leak]:
        """Create a Leak object for a metric outside its baseline range.
        
        Calculates EV loss estimate and assigns S/A/B/C severity:
        - S: > 5 BB/100 EV loss (deviation > 15pp)
        - A: 3-5 BB/100 (deviation > 10pp)
        - B: 1-3 BB/100 (deviation > 5pp)
        - C: < 1 BB/100 (deviation < 5pp)
        """
        key = (metric, direction)
        if key not in LEAK_DESCRIPTIONS:
            return None

        description, advice = LEAK_DESCRIPTIONS[key]
        if position:
            description = f"[{position}] {description}"

        # Calculate absolute deviation in percentage points
        if direction == "low":
            deviation_pp = low - value
        else:
            deviation_pp = value - high

        # Estimate EV loss: ~0.35 BB/100 per percentage point deviation (empirical estimate)
        ev_loss = deviation_pp * 0.35

        # Determine severity based on EV loss
        if ev_loss > 5.0:
            severity = Severity.S
        elif ev_loss > 3.0:
            severity = Severity.A
        elif ev_loss > 1.0:
            severity = Severity.B
        else:
            severity = Severity.C

        return Leak(
            metric=metric,
            description=description,
            severity=severity,
            actual_value=round(value, 1),
            baseline_low=low,
            baseline_high=high,
            position=position,
            advice=advice,
            ev_loss_bb100=round(ev_loss, 2),
        )

    def _merge_position_stats(self, player_stats: PlayerStats,
                              positions: List[Position]) -> PositionalStats:
        """Merge stats from multiple positions into one."""
        merged = PositionalStats()
        for pos in positions:
            if pos in player_stats.by_position:
                ps = player_stats.by_position[pos]
                merged.total_hands += ps.total_hands
                merged.voluntarily_put_in_pot += ps.voluntarily_put_in_pot
                merged.preflop_raise += ps.preflop_raise
                merged.three_bet_opportunities += ps.three_bet_opportunities
                merged.three_bet_made += ps.three_bet_made
                merged.bets += ps.bets
                merged.raises += ps.raises
                merged.calls += ps.calls
                merged.folds += ps.folds
                merged.cbet_opportunities += ps.cbet_opportunities
                merged.cbet_made += ps.cbet_made
                merged.faced_cbet += ps.faced_cbet
                merged.folded_to_cbet += ps.folded_to_cbet
                merged.saw_flop += ps.saw_flop
                merged.went_to_showdown += ps.went_to_showdown
                merged.won_at_showdown += ps.won_at_showdown
                merged.won_without_showdown += ps.won_without_showdown
                merged.total_won += ps.total_won
                merged.total_invested += ps.total_invested
        return merged
