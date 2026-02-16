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
def batch_review(
    session: Optional[str] = typer.Option(None, "--session", "-s",
                                          help="Filter by session ID"),
    top: int = typer.Option(10, "--top", "-n",
                           help="Number of top EV loss hands to analyze"),
    deep: bool = typer.Option(True, "--deep/--no-deep",
                              help="Use deep analysis model"),
    no_cache: bool = typer.Option(False, "--no-cache",
                                 help="Disable analysis cache"),
):
    """Batch review - analyze top EV loss hands with AI, uses caching to avoid repeated calls."""
    from rich.markdown import Markdown

    _require_api_key()

    repo = _get_repo()
    hands = repo.get_all_hands(session_id=session)

    if not hands:
        console.print("[yellow]No hands found. Import a log file first.[/yellow]")
        raise typer.Exit(1)

    if len(hands) == 0:
        console.print("[yellow]No hands in this session.[/yellow]")
        raise typer.Exit(1)

    use_cache = not no_cache
    model_name = "deep (code model)" if deep else "lite"
    console.print(
        f"Batch reviewing {len(hands)} hands:"
        f" selecting top {top} EV loss hands with {model_name} analysis...\n"
    )
    if use_cache:
        cached_count = repo.get_cached_analysis_count(session_id=session)
        if cached_count > 0:
            console.print(f"[dim]Found {cached_count} cached analysis results[/dim]")
    console.print("[dim]This may take a moment...[/dim]\n")

    from poker_advisor.ai.analyzer import StrategyAnalyzer
    from poker_advisor.analysis.batch_reviewer import BatchReviewer

    analyzer = StrategyAnalyzer()
    reviewer = BatchReviewer(repo, analyzer)

    result = reviewer.review_top_ev_loss(
        hands, top_n=top, deep_ai=deep, use_cache=use_cache, session_id=session
    )
    report = reviewer.format_report(result)
    console.print(Markdown(report))


@app.command()
def filter_hands(
    session: Optional[str] = typer.Option(None, "--session", "-s",
                                          help="Filter by session ID"),
    won: Optional[bool] = typer.Option(None, "--won/--lost", help="Filter by hero winning/losing"),
    showdown: Optional[bool] = typer.Option(None, "--showdown/--no-showdown", help="Filter by went to showdown"),
    limit: int = typer.Option(20, "--limit", "-n", help="Number of hands to show"),
    sort: str = typer.Option("hand_id", "--sort", help="Sort by (hand_id|timestamp|pot)"),
    descending: bool = typer.Option(True, "--desc/--asc", help="Sort descending or ascending"),
):
    """Filter hands with multiple conditions and display."""
    repo = _get_repo()
    hands = repo.get_hands_by_filters(
        session_id=session,
        hero_won=won,
        went_to_showdown=showdown,
        limit=limit,
        sort_by=sort,
        descending=descending,
    )

    if not hands:
        console.print("[yellow]No hands match your filters.[/yellow]")
        raise typer.Exit(0)

    console.print(f"[green]Found {len(hands)} hands matching filters[/green]\n")
    from poker_advisor.formatters.table import TableFormatter
    fmt = TableFormatter(console)
    fmt.print_hands_list(hands)


@app.command()
def bookmarks(
    session: Optional[str] = typer.Option(None, "--session", "-s",
                                          help="Filter bookmarks by session"),
    type: Optional[str] = typer.Option(None, "--type", help="Filter by bookmark type (mistake|great_hand|review)"),
    grade: Optional[str] = typer.Option(None, "--grade", help="Filter by error grade (S|A|B|C)"),
    list: bool = typer.Option(True, "--list", help="List bookmarks"),
    add: Optional[int] = typer.Option(None, "--add", help="Add bookmark for hand ID"),
    remove: Optional[int] = typer.Option(None, "--remove", help="Remove bookmark by bookmark ID"),
    notes: str = typer.Option("", "--notes", help="Notes for new bookmark"),
    tags: str = typer.Option("", "--tags", help="Tags for new bookmark (comma-separated)"),
    btype: str = typer.Option("mistake", "--btype", help="Bookmark type (mistake|great_hand|review)"),
):
    """Manage bookmarks (错题本/收藏)."""
    repo = _get_repo()

    if add is not None:
        session_id = session or ""
        repo.add_bookmark(add, session_id, bookmark_type=btype, notes=notes, tags=tags)
        console.print(f"[green]Bookmark added for hand #{add}[/green]")
        raise typer.Exit(0)

    if remove is not None:
        repo.remove_bookmark(remove)
        console.print(f"[green]Bookmark #{remove} removed[/green]")
        raise typer.Exit(0)

    # List bookmarks
    bookmarks = repo.get_bookmarks(session_id=session, bookmark_type=type, error_grade=grade)
    if not bookmarks:
        console.print("[yellow]No bookmarks found.[/yellow]")
        raise typer.Exit(0)

    console.print(f"[green]Found {len(bookmarks)} bookmarks[/green]\n")
    for b in bookmarks:
        grade_str = f"[{b['error_grade']}]" if b.get('error_grade') else ""
        console.print(
            f"[bold]Bookmark #{b['id']}[/bold] - Hand #{b['hand_id']}"
            f" {grade_str} {b['bookmark_type']}"
        )
        if b.get('notes'):
            console.print(f"  Notes: {b['notes']}")
        if b.get('tags'):
            console.print(f"  Tags: {b['tags']}")
        console.print()


@app.command()
def generate_plan(
    session: Optional[str] = typer.Option(None, "--session", "-s",
                                          help="Generate plan based on this session"),
):
    """Generate personalized training plan based on your leaks."""
    from rich.markdown import Markdown
    from poker_advisor.training.plan_generator import TrainingPlanGenerator
    from poker_advisor.analysis.calculator import StatsCalculator
    from poker_advisor.analysis.leak_detector import LeakDetector

    repo = _get_repo()
    hands = repo.get_all_hands(session_id=session)

    if not hands:
        console.print("[yellow]No hands found for training plan generation.[/yellow]")
        raise typer.Exit(1)

    # Calculate stats and detect leaks
    console.print("[dim]Calculating stats and detecting leaks...[/dim]")
    calculator = StatsCalculator()
    leak_detector = LeakDetector()
    stats = calculator.calculate(hands)
    leaks = leak_detector.detect(stats)

    # Generate plan
    console.print("[dim]Generating personalized training plan...[/dim]")
    generator = TrainingPlanGenerator()
    plan = generator.generate_plan(leaks, stats)
    report = generator.format_plan(plan)

    # Save to database
    try:
        with _get_db().connect() as conn:
            conn.execute(
                """INSERT INTO training_plans
                (plan_name, focus_areas, difficulty, duration_days, created_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (
                    plan.plan_name,
                    ",".join(m.focus_area for m in plan.modules),
                    plan.start_difficulty.value,
                    plan.duration_days,
                ),
            )
    except Exception:
        pass

    console.print(Markdown(report))


@app.command()
def review_notes(
    hand: Optional[int] = typer.Option(None, "--hand", help="Filter notes by hand ID"),
    list: bool = typer.Option(True, "--list", help="List all notes"),
    add: Optional[int] = typer.Option(None, "--add", help="Add note for hand ID"),
    text: str = typer.Option("", "--text", help="Note text when adding"),
    tags: str = typer.Option("", "--tags", help="Tags for note (comma-separated)"),
    remove: Optional[int] = typer.Option(None, "--remove", help="Remove note by ID"),
):
    """Manage review notes (复盘笔记)."""
    repo = _get_repo()

    if add is not None:
        repo.add_review_note(hand_id=add, note_content=text, tags=tags)
        console.print(f"[green]Note added for hand #{add}[/green]")
        raise typer.Exit(0)

    if remove is not None:
        repo.remove_review_note(remove)
        console.print(f"[green]Note #{remove} removed[/green]")
        raise typer.Exit(0)

    # List notes
    notes = repo.get_review_notes(hand_id=hand)
    if not notes:
        console.print("[yellow]No review notes found.[/yellow]")
        raise typer.Exit(0)

    console.print(f"[green]Found {len(notes)} review notes[/green]\n")
    for note in notes:
        console.print(f"[bold]Note #{note['id']}[/bold] - Hand #{note['hand_id']}")
        if note.get('tags'):
            console.print(f"  Tags: {note['tags']}")
        console.print(f"  {note['note_content']}")
        console.print()


@app.command()
def train(
    session: Optional[str] = typer.Option(None, "--session", "-s",
                                          help="Filter by session ID"),
    count: int = typer.Option(5, "--count", "-n", help="Number of scenarios"),
    focus: Optional[str] = typer.Option(None, "--focus", "-f",
                                        help="Focus area (preflop, flop, turn, river, cbet)"),
    difficulty: Optional[str] = typer.Option(None, "--difficulty", "-d",
                                              help="Difficulty level (beginner|intermediate|advanced|expert)"),
):
    """Start an interactive training session."""
    from rich.markdown import Markdown
    from rich.panel import Panel
    from poker_advisor.training.session import TrainingSession

    _require_api_key()

    repo = _get_repo()

    from poker_advisor.training.session import Difficulty
    initial_diff = Difficulty.BEGINNER
    if difficulty:
        initial_diff = Difficulty(difficulty.lower())

    training = TrainingSession(repo, initial_difficulty=initial_diff)

    console.print(f"[bold]Preparing training scenarios (difficulty: {training.current_difficulty.value})...[/bold]")
    scenarios = training.prepare(session_id=session, count=count, focus=focus, difficulty=initial_diff)

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
