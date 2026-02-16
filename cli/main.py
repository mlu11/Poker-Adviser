"""Poker Advisor CLI — Typer-based command line interface."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

app = typer.Typer(
    name="poker-advisor",
    help="Texas Hold'em Poker Strategy Advisor",
    no_args_is_help=True,
)
console = Console()


def _get_db():
    from poker_advisor.storage import Database
    return Database()


def _get_repo(db=None):
    from poker_advisor.storage import HandRepository
    if db is None:
        db = _get_db()
    return HandRepository(db)


def _require_api_key():
    from poker_advisor import config
    key = config.DOUBAO_API_KEY if config.AI_PROVIDER == "doubao" else config.DEEPSEEK_API_KEY
    env_var = "DOUBAO_API_KEY" if config.AI_PROVIDER == "doubao" else "DEEPSEEK_API_KEY"
    if not key:
        console.print(f"[red]{env_var} not set.[/red]")
        console.print(f"Set it via: export {env_var}=your-key-here")
        raise typer.Exit(1)


@app.command()
def import_log(
    file: Path = typer.Argument(..., help="Path to Poker Now log file",
                                exists=True, readable=True),
    notes: str = typer.Option("", help="Notes for this import session"),
):
    """Import a Poker Now Club log file."""
    from poker_advisor.parser.pokernow_parser import PokerNowParser

    console.print(f"Parsing [cyan]{file.name}[/cyan]...")

    parser = PokerNowParser()
    try:
        hands = parser.parse_file(str(file))
    except Exception as e:
        console.print(f"[red]Error parsing file:[/red] {e}")
        raise typer.Exit(1)

    if not hands:
        console.print("[yellow]No hands found in the log file.[/yellow]")
        raise typer.Exit(1)

    repo = _get_repo()
    session_id = repo.save_session(hands, filename=file.name, notes=notes)

    console.print(f"[green]Imported {len(hands)} hands.[/green]")
    console.print(f"Session ID: [cyan]{session_id}[/cyan]")


@app.command()
def sessions():
    """List all import sessions."""
    from poker_advisor.formatters.table import TableFormatter

    repo = _get_repo()
    session_list = repo.get_sessions()
    fmt = TableFormatter(console)
    fmt.print_sessions(session_list)


@app.command()
def stats(
    session: Optional[str] = typer.Option(None, "--session", "-s",
                                          help="Filter by session ID"),
    position: Optional[str] = typer.Option(None, "--position", "-p",
                                           help="Filter by position (e.g., BTN, BB, UTG)"),
    by_position: bool = typer.Option(False, "--by-position",
                                     help="Show breakdown by position"),
):
    """View player statistics."""
    from poker_advisor.analysis.calculator import StatsCalculator
    from poker_advisor.formatters.table import TableFormatter

    repo = _get_repo()
    hands = repo.get_all_hands(session_id=session)

    if not hands:
        console.print("[yellow]No hands found. Import a log file first.[/yellow]")
        raise typer.Exit(1)

    calc = StatsCalculator()
    player_stats = calc.calculate(hands)

    fmt = TableFormatter(console)

    if position:
        from poker_advisor.models.position import Position
        try:
            pos = Position(position.upper())
        except ValueError:
            console.print(f"[red]Unknown position: {position}[/red]")
            console.print(f"Valid positions: {', '.join(p.value for p in Position)}")
            raise typer.Exit(1)

        if pos not in player_stats.by_position:
            console.print(f"[yellow]No data for position {pos.value}.[/yellow]")
            raise typer.Exit(1)

        pos_stats = player_stats.by_position[pos]
        from poker_advisor.models.stats import PlayerStats
        filtered = PlayerStats(
            player_name=f"{player_stats.player_name} ({pos.value})",
            overall=pos_stats,
        )
        fmt.print_stats(filtered)
    else:
        fmt.print_stats(player_stats)

    if by_position:
        console.print()
        fmt.print_positional_stats(player_stats)


@app.command()
def leaks(
    session: Optional[str] = typer.Option(None, "--session", "-s",
                                          help="Filter by session ID"),
):
    """Detect leaks in your play compared to GTO baselines."""
    from poker_advisor.analysis.calculator import StatsCalculator
    from poker_advisor.analysis.leak_detector import LeakDetector
    from poker_advisor.formatters.table import TableFormatter

    repo = _get_repo()
    hands = repo.get_all_hands(session_id=session)

    if not hands:
        console.print("[yellow]No hands found. Import a log file first.[/yellow]")
        raise typer.Exit(1)

    calc = StatsCalculator()
    player_stats = calc.calculate(hands)

    detector = LeakDetector()
    detected_leaks = detector.detect(player_stats)

    fmt = TableFormatter(console)
    fmt.print_leaks(detected_leaks)


@app.command()
def hands(
    session: Optional[str] = typer.Option(None, "--session", "-s",
                                          help="Filter by session ID"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max hands to show"),
):
    """List imported hands."""
    from poker_advisor.formatters.table import TableFormatter

    repo = _get_repo()
    all_hands = repo.get_all_hands(session_id=session)

    if not all_hands:
        console.print("[yellow]No hands found.[/yellow]")
        raise typer.Exit(1)

    display = all_hands[:limit]
    fmt = TableFormatter(console)
    fmt.print_hands_list(display)

    if len(all_hands) > limit:
        console.print(f"\n[dim]Showing {limit} of {len(all_hands)} hands. "
                      f"Use --limit to see more.[/dim]")


@app.command()
def review_hand(
    hand_id: int = typer.Argument(..., help="Hand ID to review"),
    session: Optional[str] = typer.Option(None, "--session", "-s",
                                          help="Session ID (disambiguate duplicate hand IDs)"),
    ai: bool = typer.Option(False, "--ai", help="Get AI analysis of the hand"),
    deep: bool = typer.Option(False, "--deep", help="Use deep analysis model (Opus)"),
):
    """Review a specific hand in detail."""
    from poker_advisor.formatters.table import TableFormatter

    repo = _get_repo()
    hand = repo.get_hand_by_hand_id(hand_id, session_id=session)

    if not hand:
        console.print(f"[red]Hand #{hand_id} not found.[/red]")
        raise typer.Exit(1)

    fmt = TableFormatter(console)
    fmt.print_hand(hand)

    if ai:
        _require_api_key()
        from poker_advisor.ai.analyzer import StrategyAnalyzer
        from rich.markdown import Markdown

        console.print("\n[dim]Requesting AI analysis...[/dim]\n")
        all_hands = repo.get_all_hands(session_id=session)
        analyzer = StrategyAnalyzer()
        result = analyzer.review_hand(hand, hands=all_hands, deep=deep)
        console.print(Markdown(result))


@app.command()
def analyze(
    session: Optional[str] = typer.Option(None, "--session", "-s",
                                          help="Filter by session ID"),
    deep: bool = typer.Option(False, "--deep",
                              help="Use deep analysis model (Opus)"),
):
    """Get AI-powered strategy analysis of your play."""
    from rich.markdown import Markdown

    _require_api_key()

    repo = _get_repo()
    hands = repo.get_all_hands(session_id=session)

    if not hands:
        console.print("[yellow]No hands found. Import a log file first.[/yellow]")
        raise typer.Exit(1)

    model_name = "Opus (deep)" if deep else "Sonnet"
    console.print(f"Analyzing {len(hands)} hands with Claude ({model_name})...")
    console.print("[dim]This may take a moment...[/dim]\n")

    from poker_advisor.ai.analyzer import StrategyAnalyzer
    analyzer = StrategyAnalyzer()
    result = analyzer.analyze_full(hands, deep=deep)
    console.print(Markdown(result))


@app.command()
def train(
    session: Optional[str] = typer.Option(None, "--session", "-s",
                                          help="Filter by session ID"),
    count: int = typer.Option(5, "--count", "-n", help="Number of scenarios"),
    focus: Optional[str] = typer.Option(None, "--focus", "-f",
                                        help="Focus area (preflop, flop, turn, river, cbet)"),
):
    """Start an interactive training session."""
    from rich.markdown import Markdown
    from rich.panel import Panel
    from poker_advisor.training.session import TrainingSession

    _require_api_key()

    repo = _get_repo()
    training = TrainingSession(repo)

    console.print("[bold]Preparing training scenarios...[/bold]")
    scenarios = training.prepare(session_id=session, count=count, focus=focus)

    if not scenarios:
        console.print("[yellow]No suitable training scenarios found. "
                      "Import more hands first.[/yellow]")
        raise typer.Exit(1)

    console.print(f"[green]Ready! {len(scenarios)} scenarios prepared.[/green]\n")

    total_score = 0
    completed = 0

    for i, scenario in enumerate(scenarios, 1):
        console.print(f"\n[bold cyan]===  Scenario {i}/{len(scenarios)}  "
                      f"({scenario.scenario_type})  ===[/bold cyan]\n")
        console.print(Panel(scenario.description, title="Situation"))

        # Show available actions
        console.print("\n[bold]Available actions:[/bold]")
        for j, action in enumerate(scenario.available_actions, 1):
            console.print(f"  [cyan]{j}.[/cyan] {action}")
        console.print(f"  [cyan]0.[/cyan] [dim]Skip this scenario[/dim]")
        console.print(f"  [cyan]q.[/cyan] [dim]Quit training[/dim]")

        # Get user input
        choice = typer.prompt("\nYour choice (number or custom action)")

        if choice.lower() == "q":
            console.print("\n[dim]Training session ended.[/dim]")
            break

        if choice == "0":
            console.print("[dim]Skipped.[/dim]")
            continue

        # Resolve action
        try:
            idx = int(choice)
            if 1 <= idx <= len(scenario.available_actions):
                user_action = scenario.available_actions[idx - 1]
            else:
                user_action = choice
        except ValueError:
            user_action = choice

        # Optional reasoning
        reasoning = typer.prompt("Reasoning (optional, press Enter to skip)",
                                 default="")

        console.print(f"\n[dim]Evaluating your decision: {user_action}...[/dim]\n")

        try:
            evaluation = training.evaluate(scenario, user_action, reasoning)
        except Exception as e:
            console.print(f"[red]AI evaluation failed: {e}[/red]")
            continue

        # Show feedback
        score_style = ("green" if evaluation.score >= 7
                       else "yellow" if evaluation.score >= 4
                       else "red")
        console.print(f"[bold {score_style}]Score: {evaluation.score}/10[/bold {score_style}]\n")
        console.print(Markdown(evaluation.feedback))

        # Save result
        try:
            training.save_result(scenario, user_action, evaluation,
                                 focus_area=focus or "")
        except Exception:
            pass  # Non-critical — don't interrupt training

        total_score += evaluation.score
        completed += 1

    # Summary
    if completed > 0:
        avg = total_score / completed
        console.print(f"\n[bold]Training Summary[/bold]")
        console.print(f"  Completed: {completed}/{len(scenarios)}")
        console.print(f"  Average score: {avg:.1f}/10")
        console.print(f"\nUse [cyan]poker-advisor progress[/cyan] to view your history.")


@app.command()
def progress():
    """View training progress."""
    from poker_advisor.formatters.table import TableFormatter

    repo = _get_repo()
    results = repo.get_training_results()

    fmt = TableFormatter(console)
    fmt.print_training_progress(results)


if __name__ == "__main__":
    app()
