"""Interactive training session manager."""

from typing import List, Optional

from poker_advisor.models.hand import HandRecord
from poker_advisor.models.stats import PlayerStats
from poker_advisor.analysis.calculator import StatsCalculator
from poker_advisor.analysis.leak_detector import LeakDetector, Leak
from poker_advisor.ai.trainer import TrainingCoach, TrainingEvaluation
from poker_advisor.storage.repository import HandRepository
from poker_advisor.training.scenario import ScenarioGenerator, Scenario


class TrainingSession:
    """Manages an interactive training session.

    Workflow:
    1. Generate scenarios from the player's hand history
    2. Present each scenario to the player
    3. Get the player's decision
    4. Use AI to evaluate the decision
    5. Save results for progress tracking
    """

    def __init__(self, repo: HandRepository,
                 coach: Optional[TrainingCoach] = None):
        self.repo = repo
        self.coach = coach or TrainingCoach()
        self.calculator = StatsCalculator()
        self.leak_detector = LeakDetector()
        self.generator = ScenarioGenerator()

    def prepare(self, session_id: Optional[str] = None,
                count: int = 10,
                focus: Optional[str] = None) -> List[Scenario]:
        """Prepare training scenarios from hand history.

        Args:
            session_id: Optional session filter.
            count: Number of scenarios.
            focus: Focus area filter (e.g. "preflop", "river").

        Returns:
            List of prepared scenarios.
        """
        hands = self.repo.get_all_hands(session_id=session_id)
        if not hands:
            return []

        # Detect leaks to prioritize training
        stats = self.calculator.calculate(hands)
        leaks = self.leak_detector.detect(stats)

        return self.generator.generate(
            hands=hands,
            count=count,
            leaks=leaks,
            focus=focus,
        )

    def evaluate(self, scenario: Scenario, user_action: str,
                 user_reasoning: str = "") -> TrainingEvaluation:
        """Evaluate a player's decision on a scenario.

        Args:
            scenario: The training scenario.
            user_action: The player's chosen action.
            user_reasoning: Optional reasoning.

        Returns:
            TrainingEvaluation with score and feedback.
        """
        return self.coach.evaluate(
            scenario_text=scenario.description,
            user_action=user_action,
            user_reasoning=user_reasoning,
        )

    def save_result(self, scenario: Scenario,
                    user_action: str,
                    evaluation: TrainingEvaluation,
                    focus_area: str = "") -> None:
        """Save a training result to the database."""
        self.repo.save_training_result(
            hand_record_id=scenario.hand_record_id,
            scenario_type=scenario.scenario_type,
            user_action=user_action,
            optimal_action=evaluation.optimal_action,
            score=evaluation.score,
            feedback=evaluation.feedback,
            focus_area=focus_area or scenario.scenario_type,
        )
