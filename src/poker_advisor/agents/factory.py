"""Agent factory for creating poker agents."""

from typing import Dict, List, Optional
import random

from poker_advisor.models.simulation import (
    AgentConfig, PlayStyle, AgentLevel, SimulationConfig
)
from poker_advisor.agents.base import RuleBasedAgent, BaseAgent


# Default agent names for different styles
AGENT_NAMES = {
    PlayStyle.LOOSE_AGGRESSIVE: [
        "Loosey Goosey", "Wild Bill", "Action Dan", "Mad Marty",
    ],
    PlayStyle.LOOSE_PASSIVE: [
        "Calling Station", "Fishy Phil", "Just Caller", "Easy Mark",
    ],
    PlayStyle.TIGHT_AGGRESSIVE: [
        "TAG Tony", "Solid Sam", "Nitro Nick", "Professor",
    ],
    PlayStyle.TIGHT_PASSIVE: [
        "Rock Roger", "Nit Nancy", "Weak Willie", "Safe Sally",
    ],
}


class AgentFactory:
    """Factory for creating poker agents."""

    def __init__(self):
        """Initialize the agent factory."""
        self._used_names: Dict[PlayStyle, List[str]] = {
            style: [] for style in PlayStyle
        }

    def create_agent(
        self,
        style: PlayStyle,
        level: AgentLevel,
        seat: int,
        name: Optional[str] = None,
    ) -> RuleBasedAgent:
        """Create an agent with the specified style.

        Args:
            style: The play style.
            level: The skill level.
            seat: The seat number.
            name: Optional name for the agent. If not provided, one will be generated.

        Returns:
            A new RuleBasedAgent instance.
        """
        if name is None:
            name = self._generate_name(style)

        return RuleBasedAgent(
            name=name,
            style=style,
            level=level,
            seat=seat,
        )

    def create_agents_for_simulation(
        self,
        config: SimulationConfig,
    ) -> Dict[int, BaseAgent]:
        """Create agents for a simulation based on the configuration.

        Args:
            config: The simulation configuration.

        Returns:
            Dictionary mapping seat numbers to agents.
        """
        agents: Dict[int, BaseAgent] = {}
        used_seats = set()

        # Reset used names
        self._used_names = {style: [] for style in PlayStyle}

        # If hero seat is specified, reserve it
        if config.hero_seat is not None:
            used_seats.add(config.hero_seat)

        # Create agents from config
        for agent_config in config.agent_configs:
            if agent_config.seat in used_seats:
                continue  # Skip duplicate seats

            agent = self.create_agent(
                style=agent_config.style,
                level=agent_config.level,
                seat=agent_config.seat,
                name=agent_config.name,
            )
            agents[agent_config.seat] = agent
            used_seats.add(agent_config.seat)

        # Create random agents for remaining seats
        seats_needed = config.player_count - len(used_seats)
        available_seats = [s for s in range(1, 10) if s not in used_seats]

        for i in range(seats_needed):
            if i >= len(available_seats):
                break

            seat = available_seats[i]
            style = self._random_style()
            level = AgentLevel.ADVANCED

            agent = self.create_agent(style, level, seat)
            agents[seat] = agent

        return agents

    def _generate_name(self, style: PlayStyle) -> str:
        """Generate a unique name for an agent of the given style."""
        available_names = [
            n for n in AGENT_NAMES.get(style, ["Player"])
            if n not in self._used_names[style]
        ]

        if not available_names:
            # All names used, reset
            self._used_names[style] = []
            available_names = AGENT_NAMES.get(style, ["Player"])

        name = random.choice(available_names)
        self._used_names[style].append(name)
        return name

    def _random_style(self) -> PlayStyle:
        """Get a random play style."""
        # Weighted towards TAG and LAG for more interesting games
        styles = list(PlayStyle)
        weights = [0.30, 0.20, 0.35, 0.15]  # LAG, LP, TAG, TP
        return random.choices(styles, weights=weights)[0]

    def create_random_configs(
        self,
        player_count: int,
        hero_seat: Optional[int] = None,
        exclude_hero: bool = True,
    ) -> List[AgentConfig]:
        """Create random agent configurations.

        Args:
            player_count: Total number of players.
            hero_seat: The hero's seat (if any).
            exclude_hero: Whether to exclude the hero seat from agent configs.

        Returns:
            List of agent configurations.
        """
        configs = []
        used_seats = set()

        if exclude_hero and hero_seat is not None:
            used_seats.add(hero_seat)

        seats_needed = player_count - len(used_seats)
        available_seats = [s for s in range(1, 10) if s not in used_seats]

        for i in range(min(seats_needed, len(available_seats))):
            seat = available_seats[i]
            style = self._random_style()
            level = AgentLevel.ADVANCED
            name = self._generate_name(style)

            style_config = get_style_config(style)

            configs.append(AgentConfig(
                name=name,
                style=style,
                level=level,
                seat=seat,
                stack=0.0,  # Will be set later
                vpip_pct=style_config.sample_vpip(),
                pfr_pct=style_config.sample_pfr(),
                af=style_config.sample_af(),
            ))

        return configs


# Singleton factory instance
_factory: Optional[AgentFactory] = None


def get_factory() -> AgentFactory:
    """Get the singleton agent factory instance."""
    global _factory
    if _factory is None:
        _factory = AgentFactory()
    return _factory


# Import here to avoid circular import
from poker_advisor.agents.styles import get_style_config
