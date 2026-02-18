"""Interactive training session manager."""

from typing import List, Optional
from enum import Enum

from poker_advisor.models.hand import HandRecord
from poker_advisor.models.stats import PlayerStats
from poker_advisor.analysis.calculator import StatsCalculator
from poker_advisor.analysis.leak_detector import LeakDetector, Leak
from poker_advisor.ai.trainer import TrainingCoach, TrainingEvaluation
from poker_advisor.storage.repository import HandRepository
from poker_advisor.training.scenario import ScenarioGenerator, Scenario


class Difficulty(Enum):
    """Training difficulty levels."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class TrainingSession:
    """Manages an interactive training session with dynamic difficulty adjustment.

    Workflow:
    1. Generate scenarios from the player's hand history
    2. Present each scenario to the player
    3. Get the player's decision
    4. Use AI to evaluate the decision
    5. Adjust difficulty based on performance
    6. Save results for progress tracking
    """

    def __init__(self, repo: HandRepository,
                 coach: Optional[TrainingCoach] = None,
                 initial_difficulty: Difficulty = Difficulty.BEGINNER):
        self.repo = repo
        self.coach = coach or TrainingCoach()
        self.calculator = StatsCalculator()
        self.leak_detector = LeakDetector()
        self.generator = ScenarioGenerator()
        self.current_difficulty = initial_difficulty
        self.correct_count = 0
        self.total_count = 0

    def prepare(self, session_id: Optional[str] = None,
                count: int = 10,
                focus: Optional[str] = None,
                difficulty: Optional[Difficulty] = None) -> List[Scenario]:
        """Prepare training scenarios from hand history.

        Args:
            session_id: Optional session filter.
            count: Number of scenarios.
            focus: Focus area filter (e.g. "preflop", "river").
            difficulty: Difficulty level (overrides current difficulty).

        Returns:
            List of prepared scenarios.
        """
        if difficulty:
            self.current_difficulty = difficulty

        hands = self.repo.get_all_hands(session_id=session_id)
        if not hands:
            return []

        # Detect leaks to prioritize training
        stats = self.calculator.calculate(hands)
        leaks = self.leak_detector.detect(stats)

        # Filter scenarios by difficulty
        scenarios = self.generator.generate(
            hands=hands,
            count=count,
            leaks=leaks,
            focus=focus,
        )

        # Apply difficulty-based filtering/sorting
        scenarios = self._filter_by_difficulty(scenarios, self.current_difficulty)

        return scenarios

    def evaluate(self, scenario: Scenario, user_action: str,
                 user_reasoning: str = "") -> TrainingEvaluation:
        """Evaluate a player's decision on a scenario and adjust difficulty.

        Args:
            scenario: The training scenario.
            user_action: The player's chosen action.
            user_reasoning: Optional reasoning.

        Returns:
            TrainingEvaluation with score and feedback.
        """
        evaluation = self.coach.evaluate(
            scenario_text=scenario.description,
            user_action=user_action,
            user_reasoning=user_reasoning,
        )

        # Update counters and adjust difficulty
        self.total_count += 1
        if evaluation.score >= 7:
            self.correct_count += 1
        self._adjust_difficulty()

        return evaluation

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

        # Auto-add low-scoring hands to bookmarks (错题本)
        if evaluation.score < 5:
            self._add_to_bookmarks(scenario, evaluation)

    def _filter_by_difficulty(self, scenarios: List[Scenario],
                              difficulty: Difficulty) -> List[Scenario]:
        """Filter scenarios based on difficulty level."""
        if not scenarios:
            return []

        # Sort/filter based on difficulty
        difficulty_ranking = {
            Difficulty.BEGINNER: ["preflop", "check"],
            Difficulty.INTERMEDIATE: ["preflop", "cbet", "flop"],
            Difficulty.ADVANCED: ["flop", "turn", "river", "3bet"],
            Difficulty.EXPERT: ["river", "3bet", "facing"],
        }

        preferred_types = difficulty_ranking.get(difficulty, [])

        # Prioritize preferred types
        def score(s: Scenario) -> int:
            return sum(1 for t in preferred_types if t in s.scenario_type)

        scenarios.sort(key=score, reverse=True)
        return scenarios

    def _adjust_difficulty(self):
        """Adjust difficulty based on recent performance."""
        if self.total_count < 5:
            return

        accuracy = self.correct_count / self.total_count

        # Increase difficulty if >80% accuracy in current level
        if accuracy > 0.8:
            if self.current_difficulty == Difficulty.BEGINNER:
                self.current_difficulty = Difficulty.INTERMEDIATE
                self._reset_counters()
            elif self.current_difficulty == Difficulty.INTERMEDIATE:
                self.current_difficulty = Difficulty.ADVANCED
                self._reset_counters()
            elif self.current_difficulty == Difficulty.ADVANCED:
                self.current_difficulty = Difficulty.EXPERT
                self._reset_counters()

        # Decrease difficulty if <40% accuracy
        elif accuracy < 0.4:
            if self.current_difficulty == Difficulty.EXPERT:
                self.current_difficulty = Difficulty.ADVANCED
                self._reset_counters()
            elif self.current_difficulty == Difficulty.ADVANCED:
                self.current_difficulty = Difficulty.INTERMEDIATE
                self._reset_counters()
            elif self.current_difficulty == Difficulty.INTERMEDIATE:
                self.current_difficulty = Difficulty.BEGINNER
                self._reset_counters()

    def _reset_counters(self):
        """Reset counters after difficulty change."""
        self.correct_count = 0
        self.total_count = 0

    def _add_to_bookmarks(self, scenario: Scenario, evaluation: TrainingEvaluation):
        """Auto-add low-scoring hands to bookmarks."""
        try:
            self.repo.add_bookmark(
                hand_id=scenario.hand.hand_id,
                session_id=scenario.hand.session_id or "",
                bookmark_type="mistake",
                notes=f"训练错题: 得分 {evaluation.score}/10\n{evaluation.feedback}",
                tags="training,mistake",
                error_grade="B" if evaluation.score >= 3 else "A",
            )
        except Exception:
            pass

    @property
    def current_accuracy(self) -> float:
        """Get current accuracy rate."""
        if self.total_count == 0:
            return 0.0
        return self.correct_count / self.total_count
