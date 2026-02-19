"""Play style configurations for poker agents."""

from dataclasses import dataclass
from typing import Dict, Tuple
import json
import random
import os

from poker_advisor.models.simulation import PlayStyle


@dataclass
class PlayStyleConfig:
    """Configuration for a specific play style."""
    name: str
    description: str
    vpip_range: Tuple[float, float]
    pfr_range: Tuple[float, float]
    three_bet_pct: Tuple[float, float]
    af_range: Tuple[float, float]
    cbet_pct: Tuple[float, float]
    fold_to_cbet_pct: Tuple[float, float]
    wtsd_range: Tuple[float, float]

    def sample_vpip(self) -> float:
        """Sample a random VPIP value within the range."""
        return random.uniform(*self.vpip_range)

    def sample_pfr(self) -> float:
        """Sample a random PFR value within the range."""
        return random.uniform(*self.pfr_range)

    def sample_three_bet(self) -> float:
        """Sample a random 3-bet percentage."""
        return random.uniform(*self.three_bet_pct)

    def sample_af(self) -> float:
        """Sample a random aggression factor."""
        return random.uniform(*self.af_range)

    def sample_cbet(self) -> float:
        """Sample a random continuation bet percentage."""
        return random.uniform(*self.cbet_pct)

    def sample_fold_to_cbet(self) -> float:
        """Sample a random fold to c-bet percentage."""
        return random.uniform(*self.fold_to_cbet_pct)

    def sample_wtsd(self) -> float:
        """Sample a random went to showdown percentage."""
        return random.uniform(*self.wtsd_range)


# Default configurations if JSON file not found
DEFAULT_STYLES: Dict[PlayStyle, Dict] = {
    PlayStyle.LOOSE_AGGRESSIVE: {
        "name": "Loose Aggressive",
        "description": "Plays many hands, bets and raises frequently",
        "vpip_range": [0.35, 0.50],
        "pfr_range": [0.25, 0.40],
        "three_bet_pct": [0.08, 0.15],
        "af_range": [2.5, 4.0],
        "cbet_pct": [0.60, 0.70],
        "fold_to_cbet_pct": [0.30, 0.45],
        "wtsd_range": [0.30, 0.40]
    },
    PlayStyle.LOOSE_PASSIVE: {
        "name": "Loose Passive",
        "description": "Plays many hands, but calls more than raises",
        "vpip_range": [0.35, 0.55],
        "pfr_range": [0.10, 0.20],
        "three_bet_pct": [0.03, 0.08],
        "af_range": [1.0, 1.8],
        "cbet_pct": [0.40, 0.55],
        "fold_to_cbet_pct": [0.45, 0.60],
        "wtsd_range": [0.40, 0.55]
    },
    PlayStyle.TIGHT_AGGRESSIVE: {
        "name": "Tight Aggressive",
        "description": "Plays few hands, but bets and raises when in the pot",
        "vpip_range": [0.18, 0.28],
        "pfr_range": [0.14, 0.22],
        "three_bet_pct": [0.06, 0.12],
        "af_range": [2.0, 3.5],
        "cbet_pct": [0.55, 0.70],
        "fold_to_cbet_pct": [0.40, 0.55],
        "wtsd_range": [0.25, 0.35]
    },
    PlayStyle.TIGHT_PASSIVE: {
        "name": "Tight Passive",
        "description": "Plays few hands, calls down when in the pot",
        "vpip_range": [0.14, 0.24],
        "pfr_range": [0.08, 0.15],
        "three_bet_pct": [0.02, 0.06],
        "af_range": [0.8, 1.5],
        "cbet_pct": [0.35, 0.50],
        "fold_to_cbet_pct": [0.45, 0.60],
        "wtsd_range": [0.35, 0.50]
    }
}


def _load_styles_from_file() -> Dict[PlayStyle, PlayStyleConfig]:
    """Load style configurations from JSON file."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "config",
        "agent_styles.json"
    )

    styles: Dict[PlayStyle, PlayStyleConfig] = {}

    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for style_key, style_data in data.items():
                try:
                    style = PlayStyle(style_key)
                    styles[style] = PlayStyleConfig(
                        name=style_data["name"],
                        description=style_data["description"],
                        vpip_range=tuple(style_data["vpip_range"]),
                        pfr_range=tuple(style_data["pfr_range"]),
                        three_bet_pct=tuple(style_data["three_bet_pct"]),
                        af_range=tuple(style_data["af_range"]),
                        cbet_pct=tuple(style_data["cbet_pct"]),
                        fold_to_cbet_pct=tuple(style_data["fold_to_cbet_pct"]),
                        wtsd_range=tuple(style_data["wtsd_range"])
                    )
                except (ValueError, KeyError):
                    continue
    except Exception:
        pass

    # Fill in any missing styles with defaults
    for style, default_data in DEFAULT_STYLES.items():
        if style not in styles:
            styles[style] = PlayStyleConfig(
                name=default_data["name"],
                description=default_data["description"],
                vpip_range=tuple(default_data["vpip_range"]),
                pfr_range=tuple(default_data["pfr_range"]),
                three_bet_pct=tuple(default_data["three_bet_pct"]),
                af_range=tuple(default_data["af_range"]),
                cbet_pct=tuple(default_data["cbet_pct"]),
                fold_to_cbet_pct=tuple(default_data["fold_to_cbet_pct"]),
                wtsd_range=tuple(default_data["wtsd_range"])
            )

    return styles


# Global style cache
_STYLE_CACHE: Dict[PlayStyle, PlayStyleConfig] = {}


def get_style_config(style: PlayStyle) -> PlayStyleConfig:
    """Get the configuration for a play style.

    Args:
        style: The play style to get config for.

    Returns:
        The PlayStyleConfig for the given style.
    """
    global _STYLE_CACHE

    if not _STYLE_CACHE:
        _STYLE_CACHE = _load_styles_from_file()

    return _STYLE_CACHE.get(style, _STYLE_CACHE[PlayStyle.TIGHT_AGGRESSIVE])
