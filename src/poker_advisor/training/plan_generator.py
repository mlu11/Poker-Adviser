"""Training Plan Generator - Creates personalized training plans based on detected leaks."""

from dataclasses import dataclass
from typing import List, Dict
from enum import Enum
from datetime import datetime

from poker_advisor.models.stats import PlayerStats
from poker_advisor.analysis.leak_detector import Leak, Severity


class Difficulty(Enum):
    """Training difficulty levels."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


@dataclass
class TrainingModule:
    """Single training module."""
    name: str
    focus_area: str
    focus_leak: str
    description: str
    duration_minutes: int = 30
    difficulty: Difficulty = Difficulty.BEGINNER
    scenario_count: int = 10


@dataclass
class TrainingPlan:
    """Complete training plan."""
    plan_name: str
    created_at: datetime
    modules: List[TrainingModule]
    duration_days: int = 7
    daily_minutes: int = 30
    start_difficulty: Difficulty = Difficulty.BEGINNER


class TrainingPlanGenerator:
    """Generates personalized training plans based on leaks."""

    # Leak → training module mapping
    LEAK_MODULES = {
        "VPIP太高": TrainingModule(
            name="翻前起手牌范围收紧训练",
            focus_area="preflop",
            focus_leak="VPIP",
            description="学习标准起手牌范围，只在有利位置玩强牌，降低VPIP",
            duration_minutes=30,
            difficulty=Difficulty.BEGINNER,
            scenario_count=10
        ),
        "VPIP-PFR差距过大": TrainingModule(
            name="翻前加注训练",
            focus_area="preflop",
            focus_leak="VPIP-PFR",
            description="学习在有利位置积极加注，减少冷跟注",
            duration_minutes=35,
            difficulty=Difficulty.INTERMEDIATE,
            scenario_count=12
        ),
        "WTSD过高": TrainingModule(
            name="翻后弃牌训练",
            focus_area="postflop",
            focus_leak="WTSD",
            description="学习在翻后面对对手进攻时及时弃牌，设定弃牌即胜利",
            duration_minutes=40,
            difficulty=Difficulty.INTERMEDIATE,
            scenario_count=15
        ),
        "W$SD过低": TrainingModule(
            name="摊牌范围优化训练",
            focus_area="showdown",
            focus_leak="W$SD",
            description="只在有强牌时才跟注到摊牌，提升摊牌胜率",
            duration_minutes=45,
            difficulty=Difficulty.ADVANCED,
            scenario_count=12
        ),
        "WWSF过低": TrainingModule(
            name="不摊牌赢训练",
            focus_area="postflop",
            focus_leak="WWSF",
            description="学习在翻后积极进攻，争取不摊牌就赢底池",
            duration_minutes=40,
            difficulty=Difficulty.ADVANCED,
            scenario_count=15
        ),
        "C-Bet过低": TrainingModule(
            name="翻前进攻者持续下注训练",
            focus_area="cbet",
            focus_leak="C-Bet",
            description="学习作为翻前进攻者在不同翻牌结构持续下注",
            duration_minutes=35,
            difficulty=Difficulty.INTERMEDIATE,
            scenario_count=12
        ),
        "AF过低": TrainingModule(
            name="翻后攻击性训练",
            focus_area="postflop",
            focus_leak="AF",
            description="提升翻后攻击性，学习在有利位置主动下注和加注",
            duration_minutes=45,
            difficulty=Difficulty.ADVANCED,
            scenario_count=15
        ),
        "3-Bet过低": TrainingModule(
            name="3-Bet策略训练",
            focus_area="3bet",
            focus_leak="3-Bet",
            description="学习在有利位置对对手开池进行3-Bet",
            duration_minutes=30,
            difficulty=Difficulty.INTERMEDIATE,
            scenario_count=10
        )
    }

    def generate_plan(self, leaks: List[Leak],
                     player_stats: PlayerStats) -> TrainingPlan:
        """Generate personalized training plan from leaks."""
        modules: List[TrainingModule] = []

        # Take top 3-5 most severe leaks by EV loss
        sorted_leaks = sorted(leaks, key=lambda l: (-l.ev_loss_bb100, l.severity))
        top_leaks = sorted_leaks[:5]

        # Map each leak to training module
        for leak in top_leaks:
            module = self._leak_to_module(leak)
            if module:
                modules.append(module)

        # If no modules found, add default beginner modules
        if not modules:
            modules.extend([
                self.LEAK_MODULES.get("VPIP太高", TrainingModule(
                    name="基础翻前策略",
                    focus_area="preflop",
                    focus_leak="basics",
                    description="学习基础翻前策略和起手牌范围",
                    duration_minutes=30
                ))
            ])

        # Determine overall difficulty based on leak severity
        overall_diff = self._calculate_overall_difficulty(top_leaks)

        return TrainingPlan(
            plan_name=f"个性化训练方案 ({datetime.now().strftime('%Y-%m-%d')})",
            created_at=datetime.now(),
            modules=modules,
            duration_days=len(modules)*2,
            daily_minutes=sum(m.duration_minutes for m in modules) // len(modules) if modules else 30,
            start_difficulty=overall_diff
        )

    def _leak_to_module(self, leak: Leak) -> TrainingModule:
        """Map a leak to corresponding training module."""
        # Find best matching module based on leak description
        for key, module in self.LEAK_MODULES.items():
            if key in leak.description:
                return module

        # Fallback: match by severity
        if leak.severity in [Severity.S, Severity.A]:
            return TrainingModule(
                name="核心短板强化",
                focus_area="general",
                focus_leak="general",
                description="针对核心短板的综合训练",
                duration_minutes=45,
                difficulty=Difficulty.INTERMEDIATE,
                scenario_count=15
            )
        else:
            return TrainingModule(
                name="德州扑克基础",
                focus_area="general",
                focus_leak="general",
                description="德州扑克基础训练",
                duration_minutes=30,
                difficulty=Difficulty.BEGINNER,
                scenario_count=10
            )

    def _calculate_overall_difficulty(self, leaks: List[Leak]) -> Difficulty:
        """Calculate overall difficulty level based on leaks."""
        if not leaks:
            return Difficulty.BEGINNER

        s_count = sum(1 for l in leaks if l.severity == Severity.S)
        a_count = sum(1 for l in leaks if l.severity == Severity.A)

        if s_count > 0:
            return Difficulty.ADVANCED
        elif a_count > 2:
            return Difficulty.INTERMEDIATE
        elif a_count > 0:
            return Difficulty.INTERMEDIATE
        else:
            return Difficulty.BEGINNER

    def format_plan(self, plan: TrainingPlan) -> str:
        """Format training plan as markdown."""
        lines = [
            f"# {plan.plan_name}",
            "",
            f"**创建日期**: {plan.created_at.strftime('%Y-%m-%d')}",
            f"**建议周期**: {plan.duration_days} 天",
            f"**每日建议**: {plan.daily_minutes} 分钟",
            f"**起始难度**: {plan.start_difficulty.value}",
            "",
            "## 训练模块",
            ""
        ]

        for i, module in enumerate(plan.modules, 1):
            lines.extend([
                f"### {i}. {module.name}",
                f"- **针对**: {module.focus_leak}",
                f"- **时长**: {module.duration_minutes} 分钟",
                f"- **难度**: {module.difficulty.value}",
                f"- **场景数**: {module.scenario_count}",
                f"- **描述**: {module.description}",
                ""
            ])

        lines.extend([
            "---",
            "",
            "## 建议",
            "- 按顺序完成训练模块",
            "- 每个模块完成后进行效果验证",
            "- 根据正确率动态调整难度"
        ])

        return "\n".join(lines)
