"""Rich table formatting for terminal output."""

from typing import Dict, List

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from poker_advisor.models.hand import HandRecord
from poker_advisor.models.stats import PlayerStats
from poker_advisor.analysis.leak_detector import Leak, Severity
from poker_advisor.analysis.positional import PositionalAnalyzer


class TableFormatter:
    """Format poker data as Rich tables for terminal display."""

    def __init__(self, console: Console | None = None):
        self.console = console or Console()

    def print_stats(self, stats: PlayerStats) -> None:
        """Print overall stats as a Rich table."""
        table = Table(title=f"Player Stats: {stats.player_name}")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="green")

        d = stats.summary_dict()
        table.add_row("Hands", str(int(d["Hands"])))
        table.add_row("Profit", f"${stats.total_profit:+.2f}")
        table.add_row("BB/100", f"{stats.bb_per_100:+.1f}")
        table.add_row("", "")
        table.add_row("VPIP", f"{d['VPIP']:.1f}%")
        table.add_row("PFR", f"{d['PFR']:.1f}%")
        table.add_row("3-Bet%", f"{d['3-Bet%']:.1f}%")
        table.add_row("AF", f"{d['AF']:.2f}")
        table.add_row("C-Bet%", f"{d['C-Bet%']:.1f}%")
        table.add_row("Fold to C-Bet%", f"{d['Fold to C-Bet%']:.1f}%")
        table.add_row("WTSD%", f"{d['WTSD%']:.1f}%")
        table.add_row("W$SD%", f"{d['W$SD%']:.1f}%")
        table.add_row("WWSF%", f"{d['WWSF%']:.1f}%")
        table.add_row("ROI%", f"{d['ROI%']:.1f}%")

        self.console.print(table)

    def print_positional_stats(self, stats: PlayerStats) -> None:
        """Print per-position stats as a Rich table."""
        analyzer = PositionalAnalyzer()
        rows = analyzer.position_summary(stats)

        if not rows:
            self.console.print("[dim]No positional data available.[/dim]")
            return

        table = Table(title="Stats by Position")
        table.add_column("Position", style="cyan")
        table.add_column("Hands", justify="right")
        table.add_column("VPIP%", justify="right")
        table.add_column("PFR%", justify="right")
        table.add_column("3Bet%", justify="right")
        table.add_column("AF", justify="right")
        table.add_column("CBet%", justify="right")
        table.add_column("FoldCB%", justify="right")
        table.add_column("WTSD%", justify="right")

        for row in rows:
            table.add_row(
                row["position"],
                str(row["hands"]),
                f"{row['vpip']:.1f}",
                f"{row['pfr']:.1f}",
                f"{row['3bet']:.1f}",
                f"{row['af']:.2f}",
                f"{row['cbet']:.1f}",
                f"{row['fold_to_cbet']:.1f}",
                f"{row['wtsd']:.1f}",
            )

        self.console.print(table)

    def print_leaks(self, leaks: List[Leak]) -> None:
        """Print detected leaks as Rich panels."""
        if not leaks:
            self.console.print(Panel(
                "No significant leaks detected.",
                title="Leak Analysis",
                style="green",
            ))
            return

        self.console.print(f"\n[bold]Leak Analysis[/bold] — {len(leaks)} issue(s) found\n")

        severity_styles = {
            Severity.S: "bright_red",
            Severity.A: "red",
            Severity.B: "yellow",
            Severity.C: "blue",
        }
        severity_labels = {
            Severity.S: "CRITICAL",
            Severity.A: "MAJOR",
            Severity.B: "MODERATE",
            Severity.C: "MINOR",
        }

        for i, leak in enumerate(leaks, 1):
            style = severity_styles[leak.severity]
            label = severity_labels[leak.severity]

            content = Text()
            content.append(f"Value: {leak.actual_value:.1f}  ", style="bold")
            content.append(f"EV Loss: [bold]{leak.ev_loss_bb100:.2f}[/bold] BB/100\n")
            content.append(f"Baseline: {leak.baseline_low:.1f}-{leak.baseline_high:.1f}\n")
            if leak.advice:
                content.append(f"\n{leak.advice}")

            self.console.print(Panel(
                content,
                title=f"[{style}][{label}][/{style}] {leak.description}",
                border_style=style,
            ))

    def print_sessions(self, sessions: List[Dict]) -> None:
        """Print import sessions as a Rich table."""
        if not sessions:
            self.console.print("[dim]No sessions found. Import a log file first.[/dim]")
            return

        table = Table(title="Import Sessions")
        table.add_column("Session ID", style="cyan")
        table.add_column("Filename")
        table.add_column("Hands", justify="right")
        table.add_column("Imported", style="dim")
        table.add_column("Notes")

        for s in sessions:
            table.add_row(
                s.get("id", ""),
                s.get("filename", ""),
                str(s.get("hand_count", 0)),
                s.get("import_date", ""),
                s.get("notes", "") or "",
            )

        self.console.print(table)

    def print_hand(self, hand: HandRecord) -> None:
        """Print a single hand as a Rich panel."""
        from poker_advisor.formatters.text import TextFormatter
        text_fmt = TextFormatter()
        content = text_fmt.format_hand(hand)
        result = "Won" if hand.hero_won else "Lost" if hand.winners else ""
        style = "green" if hand.hero_won else "red" if hand.winners else "dim"
        self.console.print(Panel(content, title=f"Hand #{hand.hand_id}",
                                 subtitle=result, border_style=style))

    def print_hands_list(self, hands: List[HandRecord]) -> None:
        """Print a compact list of hands."""
        if not hands:
            self.console.print("[dim]No hands found.[/dim]")
            return

        table = Table(title=f"Hand History ({len(hands)} hands)")
        table.add_column("#", justify="right", style="dim")
        table.add_column("Hand ID", style="cyan")
        table.add_column("Position")
        table.add_column("Cards")
        table.add_column("Board")
        table.add_column("Pot", justify="right")
        table.add_column("Result", justify="right")

        for i, hand in enumerate(hands, 1):
            pos = hand.hero_position.value if hand.hero_position else ""
            result = ""
            if hand.hero_won:
                won_amt = hand.winners.get(hand.hero_seat, 0)
                result = f"[green]+${won_amt:.2f}[/green]"
            elif hand.winners:
                result = "[red]Lost[/red]"

            table.add_row(
                str(i),
                str(hand.hand_id),
                pos,
                hand.hero_cards_str or "-",
                hand.board_str or "-",
                f"${hand.pot_total:.2f}",
                result,
            )

        self.console.print(table)

    def print_training_progress(self, results: List[Dict]) -> None:
        """Print training results as a Rich table."""
        if not results:
            self.console.print("[dim]No training results yet. Start a training session![/dim]")
            return

        table = Table(title="Training Progress")
        table.add_column("Date", style="dim")
        table.add_column("Scenario")
        table.add_column("Your Action")
        table.add_column("Optimal")
        table.add_column("Score", justify="right")

        total_score = 0
        for r in results:
            score = r.get("score", 0)
            total_score += score
            score_style = "green" if score >= 7 else "yellow" if score >= 4 else "red"

            table.add_row(
                r.get("session_date", "")[:16],
                r.get("scenario_type", ""),
                r.get("user_action", ""),
                r.get("optimal_action", ""),
                f"[{score_style}]{score}/10[/{score_style}]",
            )

        self.console.print(table)
        if results:
            avg = total_score / len(results)
            self.console.print(f"\nAverage score: {avg:.1f}/10  |  "
                               f"Sessions: {len(results)}")
