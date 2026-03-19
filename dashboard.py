"""
Rich terminal dashboard for PaceIQ.
Displays post-run analysis, weekly summaries, and shoe mileage.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from rich.rule import Rule
from rich import box

from profile import SHOE_ROTATION, HR_ZONES, RUNNER_PROFILE

console = Console()


# ---------------------------------------------------------------------------
# Helper formatters
# ---------------------------------------------------------------------------

def _check(condition: bool) -> str:
    return "[green]OK[/green]" if condition else "[red]MISS[/red]"


def _pace_in_range(pace_str: str, min_pace: str, max_pace: str) -> bool:
    """Return True if pace_str is within [min_pace, max_pace] (lower seconds = faster)."""
    from activity_analyzer import pace_str_to_seconds
    pace_s = pace_str_to_seconds(pace_str)
    min_s = pace_str_to_seconds(min_pace)
    max_s = pace_str_to_seconds(max_pace)
    if pace_s <= 0:
        return False
    return min_s <= pace_s <= max_s


def _hr_in_range(hr: Optional[float], low: float, high: float) -> bool:
    if hr is None:
        return False
    return low <= hr <= high


# ---------------------------------------------------------------------------
# Post-run analysis display
# ---------------------------------------------------------------------------

def display_post_run_analysis(
    activity_dict: Dict[str, Any],
    claude_feedback: str,
    weekly_miles: float,
    shoe_miles: Dict[str, float],
) -> None:
    """
    Print a formatted post-run analysis panel to the terminal.

    Args:
        activity_dict: Analyzed activity from activity_analyzer
        claude_feedback: Coaching text from Claude
        weekly_miles: Total miles run this week so far
        shoe_miles: Dict of shoe name → total miles
    """
    run_type = activity_dict.get("run_type", "easy")
    distance = activity_dict.get("distance_miles", 0.0)
    avg_pace = activity_dict.get("avg_pace_per_mile", "0:00")
    avg_hr = activity_dict.get("avg_hr") or 0
    max_hr = activity_dict.get("max_hr") or 0
    elevation = activity_dict.get("elevation_gain", 0)
    shoe_used = activity_dict.get("shoe_used", "Unknown")
    flags = activity_dict.get("flags", [])
    run_date = activity_dict.get("date", datetime.now().strftime("%Y-%m-%d"))
    name = activity_dict.get("name", "Run")

    try:
        dt = datetime.strptime(run_date, "%Y-%m-%d")
        day_name = dt.strftime("%A")
    except ValueError:
        day_name = ""

    weekly_target = 30
    pct = round((weekly_miles / weekly_target) * 100)

    # Progress bar
    filled = min(int(pct / 5), 20)
    bar = "[green]" + "█" * filled + "[/green]" + "░" * (20 - filled)

    # Determine target/HR checks based on run type
    fitness = RUNNER_PROFILE["fitness"]

    if run_type == "tempo":
        pace_ok = _pace_in_range(avg_pace, "7:30", "9:00")
        hr_ok = _hr_in_range(avg_hr, 175, 183)
        target_label = f"TEMPO TARGET: {avg_pace}/mi (target 8:00–8:35/mi)"
        hr_label = f"HR ZONE: {avg_hr:.0f} bpm (target 175–183 bpm)"
        effort_label = "EFFORT: Threshold/tempo"
    elif run_type == "long_run":
        pace_ok = True  # long run pace is flexible
        hr_ok = _hr_in_range(avg_hr, 145, 175)
        target_label = f"LONG RUN: {distance:.1f} miles (target 10–11 mi)"
        hr_label = f"HR ZONE: {avg_hr:.0f} bpm (target 145–175 bpm)"
        effort_label = "EFFORT: Aerobic long effort"
    elif run_type == "race_effort":
        pace_ok = _pace_in_range(avg_pace, "7:00", "8:30")
        hr_ok = avg_hr >= 183
        target_label = f"RACE EFFORT: {avg_pace}/mi"
        hr_label = f"HR ZONE: {avg_hr:.0f} bpm (race territory)"
        effort_label = "EFFORT: Race/VO2max"
    else:  # easy or moderate
        pace_ok = _pace_in_range(avg_pace, "9:45", "11:30")
        hr_ok = _hr_in_range(avg_hr, 145, 170)
        target_label = f"EASY TARGET: {avg_pace}/mi (target 10:15–10:30/mi)"
        hr_label = f"HR ZONE: {avg_hr:.0f} bpm (target 155–165 bpm)"
        effort_label = "EFFORT: Aerobic easy"

    # Build shoe status line
    shoe_current = shoe_miles.get(shoe_used, 0.0)
    shoe_max = SHOE_ROTATION.get(shoe_used, {}).get("max_miles", 500)
    shoe_pct = round((shoe_current / shoe_max) * 100) if shoe_max > 0 else 0
    shoe_status = f"{shoe_used} at {shoe_current:.0f}/{shoe_max} mi ({shoe_pct}%)"

    # Header
    run_type_label = run_type.replace("_", " ").upper()
    console.print()
    console.rule(
        f"[bold cyan]PaceIQ Post-Run Analysis — {run_type_label} | {day_name} {run_date}[/bold cyan]",
        style="cyan",
    )

    # Activity summary
    console.print(
        f"\n[bold]Activity:[/bold] {name}\n"
        f"  {distance:.2f} miles  |  {avg_pace}/mi avg  |  {avg_hr:.0f} bpm avg  |  "
        f"max {max_hr:.0f} bpm  |  {elevation:.0f} ft gain"
    )

    # Status checks
    console.print()
    pace_icon = "[green]OK[/green]" if pace_ok else "[red]MISS[/red]"
    hr_icon = "[green]OK[/green]" if hr_ok else "[red]MISS[/red]"

    console.print(f"  [{pace_icon}] {target_label}")
    console.print(f"  [{hr_icon}] {hr_label}")
    console.print(f"  [cyan]--[/cyan] {effort_label}")

    # Flags
    if flags:
        console.print()
        console.print("[bold yellow]FLAGS:[/bold yellow]")
        for flag in flags:
            console.print(f"  [yellow]! {flag}[/yellow]")

    # SF terrain caveat
    if elevation > 200:
        console.print(
            f"\n  [dim]Note: {elevation:.0f} ft elevation — SF hills likely affected pace. "
            f"Effort-based assessment is more meaningful than raw pace here.[/dim]"
        )

    # Week progress
    console.print()
    console.print(
        f"[bold]WEEK PROGRESS:[/bold] {weekly_miles:.1f}/{weekly_target} miles ({pct}%)"
    )
    console.print(f"  {bar}")

    # Shoe check
    shoe_color = "green" if shoe_pct < 80 else "yellow" if shoe_pct < 95 else "red"
    console.print(f"\n[bold]SHOE CHECK:[/bold] [{shoe_color}]{shoe_status}[/{shoe_color}]")

    # Claude coaching note
    console.print()
    console.rule("[bold magenta]COACH NOTE[/bold magenta]", style="magenta")
    console.print(f"\n[italic]{claude_feedback}[/italic]")

    # Next run recommendation
    shoe_rec = activity_dict.get("shoe_recommendation", "Adidas Evo SL Woven")
    console.print(
        f"\n[bold]Next run:[/bold] See weekly plan for tomorrow's session. "
        f"Suggested shoe: [cyan]{shoe_rec}[/cyan]"
    )
    console.rule(style="cyan")
    console.print()


# ---------------------------------------------------------------------------
# Weekly dashboard
# ---------------------------------------------------------------------------

def display_weekly_dashboard(
    weekly_stats: Dict[str, Any],
    shoe_miles: Dict[str, float],
    week_num: Optional[int] = None,
    activities: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """
    Display a comprehensive weekly training dashboard.

    Args:
        weekly_stats: Output from activity_analyzer.compute_weekly_stats()
        shoe_miles: Current shoe mileage dict
        week_num: ISO week number (optional, shown in header)
        activities: List of activity dicts for the week (for table display)
    """
    total_miles = weekly_stats.get("total_miles", 0.0)
    num_runs = weekly_stats.get("num_runs", 0)
    tempo_pace = weekly_stats.get("tempo_avg_pace", "N/A") or "N/A"
    long_run = weekly_stats.get("long_run_miles", 0.0)
    easy_hr = weekly_stats.get("avg_hr_easy")
    pct = weekly_stats.get("percent_of_target", 0)
    flags = weekly_stats.get("flags", [])
    target = weekly_stats.get("weekly_target", 30)

    week_label = f" Week {week_num}" if week_num else ""
    console.print()
    console.rule(
        f"[bold cyan]PaceIQ Weekly Dashboard{week_label}[/bold cyan]",
        style="cyan",
    )

    # Summary stats table
    summary_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    summary_table.add_column("Metric", style="bold")
    summary_table.add_column("Value", style="cyan")
    summary_table.add_column("Status", style="green")

    miles_color = "green" if total_miles >= target else "yellow" if total_miles >= target * 0.7 else "red"
    summary_table.add_row(
        "Total Miles",
        f"{total_miles:.1f} / {target}",
        f"[{miles_color}]{pct:.0f}% of target[/{miles_color}]",
    )
    summary_table.add_row("Runs Completed", str(num_runs), "")
    summary_table.add_row(
        "Tempo Avg Pace",
        tempo_pace,
        "[green]on track[/green]" if tempo_pace != "N/A" else "[dim]no tempo run[/dim]",
    )
    long_color = "green" if long_run >= 8 else "yellow" if long_run >= 6 else "red"
    summary_table.add_row(
        "Long Run",
        f"{long_run:.1f} mi",
        f"[{long_color}]{'OK' if long_run >= 8 else 'below target'}[/{long_color}]",
    )
    if easy_hr is not None:
        easy_hr_color = "green" if easy_hr <= 165 else "yellow" if easy_hr <= 170 else "red"
        summary_table.add_row(
            "Avg Easy HR",
            f"{easy_hr:.0f} bpm",
            f"[{easy_hr_color}]{'controlled' if easy_hr <= 165 else 'elevated'}[/{easy_hr_color}]",
        )

    console.print(summary_table)

    # Progress bar
    filled = min(int(pct / 5), 20)
    bar = "█" * filled + "░" * (20 - filled)
    console.print(f"  [green]{bar}[/green]  {total_miles:.1f} mi")

    # Sub-1:40 goal context
    race_target_pace = RUNNER_PROFILE["goals"]["race_target_pace"]
    console.print(
        f"\n  [bold]Goal:[/bold] Sub 1:40 half marathon | Race pace target: {race_target_pace}/mi"
    )

    # Flags
    if flags:
        console.print()
        console.print("[bold yellow]Weekly Flags:[/bold yellow]")
        for flag in flags:
            console.print(f"  [yellow]! {flag}[/yellow]")

    # Activities breakdown
    if activities:
        console.print()
        act_table = Table(
            title="This Week's Runs",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
        )
        act_table.add_column("Date", style="dim", width=12)
        act_table.add_column("Type", width=12)
        act_table.add_column("Miles", justify="right", width=8)
        act_table.add_column("Pace", justify="right", width=10)
        act_table.add_column("Avg HR", justify="right", width=8)
        act_table.add_column("Shoe", width=24)

        type_colors = {
            "tempo": "magenta",
            "long_run": "blue",
            "easy": "green",
            "moderate": "yellow",
            "race_effort": "red",
        }

        for act in sorted(activities, key=lambda a: a.get("date", "")):
            run_type = act.get("run_type", "easy")
            color = type_colors.get(run_type, "white")
            hr_val = act.get("avg_hr")
            hr_str = f"{hr_val:.0f}" if hr_val else "N/A"
            shoe = act.get("shoe_used", "")
            shoe_short = shoe.split(" ")[0] if shoe else ""

            act_table.add_row(
                act.get("date", "?"),
                f"[{color}]{run_type.replace('_', ' ')}[/{color}]",
                f"{act.get('distance_miles', 0):.1f}",
                act.get("avg_pace_per_mile", "N/A"),
                hr_str,
                shoe,
            )

        console.print(act_table)

    # Shoe mileage
    console.print()
    display_shoe_mileage(shoe_miles)
    console.rule(style="cyan")
    console.print()


# ---------------------------------------------------------------------------
# Shoe mileage tracker
# ---------------------------------------------------------------------------

def display_shoe_mileage(shoe_miles: Dict[str, float]) -> None:
    """Display a shoe mileage tracker table."""
    table = Table(
        title="Shoe Rotation",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Shoe", width=28)
    table.add_column("Role", width=20)
    table.add_column("Miles", justify="right", width=8)
    table.add_column("Max", justify="right", width=8)
    table.add_column("Status", width=18)
    table.add_column("Health", width=14)

    for shoe_name, info in SHOE_ROTATION.items():
        current = shoe_miles.get(shoe_name, 0.0)
        max_miles = info.get("max_miles", 500)
        pct = (current / max_miles) * 100 if max_miles > 0 else 0
        status = info.get("status", "active")

        if status == "not yet purchased":
            health = "[dim]not owned[/dim]"
            pct_str = "N/A"
        elif pct >= 95:
            health = "[red]RETIRE SOON[/red]"
            pct_str = f"[red]{pct:.0f}%[/red]"
        elif pct >= 80:
            health = "[yellow]getting worn[/yellow]"
            pct_str = f"[yellow]{pct:.0f}%[/yellow]"
        else:
            health = "[green]good[/green]"
            pct_str = f"[green]{pct:.0f}%[/green]"

        filled = min(int(pct / 10), 10)
        bar = "█" * filled + "░" * (10 - filled)

        table.add_row(
            f"[bold]{shoe_name}[/bold]",
            info.get("role", ""),
            f"{current:.0f}",
            f"{max_miles}",
            f"[dim]{bar}[/dim] {pct_str}",
            health,
        )

    console.print(table)


# ---------------------------------------------------------------------------
# Status display
# ---------------------------------------------------------------------------

def display_status(
    weekly_stats: Dict[str, Any],
    shoe_miles: Dict[str, float],
    recent_activities: List[Dict[str, Any]],
    week_num: Optional[int] = None,
) -> None:
    """Quick status overview — compact version of the dashboard."""
    total_miles = weekly_stats.get("total_miles", 0.0)
    pct = weekly_stats.get("percent_of_target", 0)
    num_runs = weekly_stats.get("num_runs", 0)
    target = weekly_stats.get("weekly_target", 30)

    console.print()
    week_str = f"Week {week_num} " if week_num else ""
    console.rule(f"[bold cyan]PaceIQ Status — {week_str}{datetime.now().strftime('%Y-%m-%d')}[/bold cyan]")

    # Week at a glance
    filled = min(int(pct / 5), 20)
    bar = "█" * filled + "░" * (20 - filled)
    miles_color = "green" if total_miles >= target else "yellow" if total_miles >= target * 0.7 else "red"

    console.print(
        f"\n  [{miles_color}]{total_miles:.1f} / {target} miles ({pct:.0f}%)[/{miles_color}] this week — {num_runs} runs"
    )
    console.print(f"  [dim]{bar}[/dim]")

    # Most recent run
    if recent_activities:
        last = recent_activities[0]
        run_type = last.get("run_type", "easy")
        console.print(
            f"\n  [bold]Last run:[/bold] {last.get('date', '?')} — "
            f"{last.get('distance_miles', 0):.1f} mi {run_type} @ "
            f"{last.get('avg_pace_per_mile', 'N/A')}/mi "
            f"({last.get('avg_hr', 'N/A')} bpm avg)"
        )

    # Quick shoe status
    console.print()
    for shoe, miles in shoe_miles.items():
        max_m = SHOE_ROTATION.get(shoe, {}).get("max_miles", 500)
        if SHOE_ROTATION.get(shoe, {}).get("status") == "not yet purchased":
            continue
        pct_shoe = (miles / max_m) * 100 if max_m > 0 else 0
        color = "red" if pct_shoe >= 90 else "yellow" if pct_shoe >= 75 else "green"
        short = shoe[:20]
        console.print(f"  [{color}]{short:20s}[/{color}] {miles:5.0f} mi")

    console.rule(style="cyan")
    console.print()
