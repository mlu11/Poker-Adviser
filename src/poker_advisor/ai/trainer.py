"""AI training coach — evaluates player decisions using Claude."""

import re
from dataclasses import dataclass
from typing import Optional

from poker_advisor.ai.client import ClaudeClient
from poker_advisor.ai.prompts import (
    TRAINING_COACH_SYSTEM,
    build_training_eval_prompt,
)
from poker_advisor import config


@dataclass
class TrainingEvaluation:
    """Result of an AI evaluation of a training decision."""
    score: int
    feedback: str
    optimal_action: str


class TrainingCoach:
    """AI coach that evaluates training decisions."""

    def __init__(self, client: Optional[ClaudeClient] = None):
        self.client = client or ClaudeClient()

    def evaluate(self, scenario_text: str, user_action: str,
                 user_reasoning: str = "") -> TrainingEvaluation:
        """Evaluate a player's decision in a training scenario.

        Args:
            scenario_text: Text description of the scenario.
            user_action: The action the user chose (e.g., "Fold", "Call $10").
            user_reasoning: Optional reasoning from the user.

        Returns:
            TrainingEvaluation with score, feedback, and optimal action.
        """
        prompt = build_training_eval_prompt(scenario_text, user_action,
                                            user_reasoning)

        response = self.client.ask(
            prompt=prompt,
            system=TRAINING_COACH_SYSTEM,
        )

        return self._parse_evaluation(response, user_action)

    def _parse_evaluation(self, response: str,
                          user_action: str) -> TrainingEvaluation:
        """Parse the structured response from Claude into a TrainingEvaluation."""
        # Try to extract score from "评分：X/10" or "## 评分：X/10"
        score = 5  # default
        score_match = re.search(r'评分[：:]\s*(\d+)\s*/\s*10', response)
        if score_match:
            score = min(10, max(1, int(score_match.group(1))))

        # Try to extract optimal action from "## 最优打法" section
        optimal_action = ""
        optimal_match = re.search(
            r'最优打法\s*\n+(.*?)(?=\n##|\Z)',
            response,
            re.DOTALL,
        )
        if optimal_match:
            # Take the first non-empty line as the action summary
            for line in optimal_match.group(1).strip().split('\n'):
                line = line.strip().lstrip('-').lstrip('*').strip()
                if line:
                    optimal_action = line[:100]
                    break

        if not optimal_action:
            optimal_action = user_action

        return TrainingEvaluation(
            score=score,
            feedback=response,
            optimal_action=optimal_action,
        )
