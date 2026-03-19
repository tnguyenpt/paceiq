#!/usr/bin/env python3
"""
PaceIQ — AI Running Coach for Tony
Entry point with CLI for all commands.

Usage:
    python main.py                    # Show dashboard
    python main.py analyze [id]       # Analyze specific Strava activity
    python main.py sync               # Pull recent activities from Strava
    python main.py plan               # Generate this week's training plan
    python main.py webhook            # Start Strava webhook listener
    python main.py status             # Quick status check
"""

import sys
import pathlib
import argparse
from datetime import datetime, timedelta, UTC

# Ensure the project directory is on sys.path so imports work
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from config import get_config, load_shoe_miles, add_shoe_miles
from database import (
    init_db,
    save_activity,
    get_recent_activities,
    get_activities_by_week,
    get_activity_by_strava_id,
    save_weekly_summary,
    get_all_activities_for_weeks,
)
from activity_analyzer import analyze_activity, compute_weekly_stats
from weekly_planner import (
    get_current_week_number,
    generate_monday_plan,
    should_generate_plan,
    save_plan_to_file,
    get_latest_plan,
    format_weekly_schedule_text,
)
from dashboard import (
    display_post_run_analysis,
    display_weekly_dashboard,
    display_shoe_mileage,
    display_status,
    console,
)
from strava_client import (
    refresh_access_token,
    get_activities,
    get_activity_detail,
    get_all_activities_since,
    StravaAPIError,
)


# ---------------------------------------------------------------------------
# Helper: get Strava access token (refreshes if needed)
# ---------------------------------------------------------------------------

def _get_access_token() -> str:
    """Refresh Strava token and return a valid access token."""
    config = get_config()
    client_id = config.get("strava_client_id", "")
    client_secret = config.get("strava_client_secret", "")
    refresh_token = config.get("strava_refresh_token", "")

    if not client_id or not client_secret:
        console.print("[red]Error: STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET not set in .env[/red]")
        console.print("Run 'python setup_auth.py' to set up Strava authorization.")
        sys.exit(1)

    if not refresh_token or refresh_token == "your_refresh_token_here":
        console.print("[red]Error: STRAVA_REFRESH_TOKEN not set. Run 'python setup_auth.py' first.[/red]")
        sys.exit(1)

    try:
        from config import save_env_tokens
        tokens = refresh_access_token(client_id, client_secret, refresh_token)
        # Save new refresh token if it changed
        if tokens.get("refresh_token") != refresh_token:
            save_env_tokens(tokens)
        return tokens["access_token"]
    except StravaAPIError as e:
        console.print(f"[red]Strava token refresh failed: {e}[/red]")
        sys.exit(1)


def _get_current_week_activities():
    """Return activities for the current ISO week."""
    week_num, year = get_current_week_number()
    return get_activities_by_week(week_num, year)


def _get_last_n_weeks_activities(n: int = 2):
    """Return activities from the last n weeks."""
    week_num, year = get_current_week_number()
    week_nums = []
    y = year
    w = week_num
    for _ in range(n):
        week_nums.append((w, y))
        w -= 1
        if w < 1:
            w = 52
            y -= 1
    all_activities = []
    for wn, yr in week_nums:
        all_activities.extend(get_activities_by_week(wn, yr))
    return all_activities


# ---------------------------------------------------------------------------
# Command: dashboard (default)
# ---------------------------------------------------------------------------

def cmd_dashboard() -> None:
    """Show the full weekly dashboard."""
    week_num, year = get_current_week_number()
    activities = get_activities_by_week(week_num, year)
    weekly_stats = compute_weekly_stats(activities)
    shoe_miles = load_shoe_miles()

    display_weekly_dashboard(
        weekly_stats=weekly_stats,
        shoe_miles=shoe_miles,
        week_num=week_num,
        activities=activities,
    )

    # Show the latest plan if one exists
    plan = get_latest_plan()
    if plan:
        console.print("[bold]Latest Training Plan:[/bold]")
        console.print(f"[dim]{plan[:800]}{'...' if len(plan) > 800 else ''}[/dim]")
        console.print()


# ---------------------------------------------------------------------------
# Command: sync
# ---------------------------------------------------------------------------

def cmd_sync() -> None:
    """Pull recent Strava activities, analyze them, and save to database."""
    console.print("\n[bold cyan]Syncing activities from Strava...[/bold cyan]")

    access_token = _get_access_token()
    console.print("[green]Token refreshed.[/green]")

    # Pull activities from last 7 days
    since_dt = datetime.now(UTC) - timedelta(days=7)
    since_ts = int(since_dt.timestamp())

    try:
        raw_activities = get_all_activities_since(access_token, after_timestamp=since_ts)
    except StravaAPIError as e:
        console.print(f"[red]Failed to fetch activities: {e}[/red]")
        sys.exit(1)

    # Filter to runs only
    runs = [
        a for a in raw_activities
        if a.get("type", "") in ("Run",) or a.get("sport_type", "") in ("Run",)
    ]

    if not runs:
        console.print("No new running activities in the last 7 days.")
        cmd_status()
        return

    console.print(f"Found [bold]{len(runs)}[/bold] run(s) in the last 7 days.\n")

    shoe_miles = load_shoe_miles()
    week_num, year = get_current_week_number()
    all_week_activities = get_activities_by_week(week_num, year)

    new_count = 0
    ai_available = True
    for raw in runs:
        strava_id = raw.get("id")

        # Check if already in database
        existing = get_activity_by_strava_id(strava_id) if strava_id else None
        if existing:
            console.print(f"[dim]Skipping already-saved activity: {raw.get('name', 'Run')} ({raw.get('start_date_local', '')[:10]})[/dim]")
            continue

        # Fetch detailed data with laps
        laps = None
        try:
            if strava_id:
                detail = get_activity_detail(access_token, strava_id)
                laps = detail.get("laps", [])
                raw = detail  # use detailed data
        except StravaAPIError as e:
            console.print(f"[yellow]Could not fetch activity detail: {e}. Using summary data.[/yellow]")

        # Analyze the activity
        analyzed = analyze_activity(raw, laps=laps)

        # Add shoe miles
        shoe_used = analyzed.get("shoe_used", "")
        if shoe_used:
            shoe_miles = add_shoe_miles(shoe_used, analyzed.get("distance_miles", 0))

        # Save to database
        save_activity(analyzed)
        new_count += 1

        # Get weekly context for Claude feedback
        all_week_activities = get_activities_by_week(week_num, year)
        weekly_stats = compute_weekly_stats(all_week_activities)
        recent = get_recent_activities(5)

        console.print(f"\n[bold]New activity: {analyzed['name']}[/bold]")

        # Get AI coaching feedback
        if ai_available:
            try:
                from coach import analyze_run_with_ai
                console.print("[cyan]Getting coaching feedback...[/cyan]\n")
                feedback = analyze_run_with_ai(
                    activity_dict=analyzed,
                    weekly_progress=weekly_stats,
                    prev_activities=recent,
                )
            except Exception as e:
                ai_available = False
                console.print(f"[yellow]Could not get AI feedback: {e}[/yellow]")
                feedback = "AI bridge timed out/offline; data synced successfully."
        else:
            feedback = "AI bridge timed out/offline; data synced successfully."

        # Display post-run analysis
        display_post_run_analysis(
            activity_dict=analyzed,
            claude_feedback=feedback,
            weekly_miles=weekly_stats.get("total_miles", 0),
            shoe_miles=shoe_miles,
        )

    if new_count == 0:
        console.print("[green]All recent activities already synced.[/green]")
    else:
        console.print(f"[green]Synced {new_count} new activit{'y' if new_count == 1 else 'ies'}.[/green]")

    # Save weekly summary
    all_week_activities = get_activities_by_week(week_num, year)
    weekly_stats = compute_weekly_stats(all_week_activities)
    save_weekly_summary({
        "week_number": week_num,
        "year": year,
        "total_miles": weekly_stats["total_miles"],
        "tempo_avg_pace": weekly_stats.get("tempo_avg_pace", ""),
        "long_run_miles": weekly_stats.get("long_run_miles", 0),
        "num_runs": weekly_stats["num_runs"],
        "notes": f"Synced {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    })

    # Auto-generate plan if it's Monday and no plan today
    if should_generate_plan():
        console.print("\n[bold]It's Monday — generating weekly training plan...[/bold]")
        last_2_weeks = _get_last_n_weeks_activities(2)
        try:
            generate_monday_plan(last_2_weeks)
        except Exception as e:
            console.print(f"[yellow]Could not generate plan: {e}[/yellow]")


# ---------------------------------------------------------------------------
# Command: analyze
# ---------------------------------------------------------------------------

def cmd_analyze(activity_id: str) -> None:
    """Analyze a specific Strava activity by ID."""
    console.print(f"\n[bold cyan]Analyzing Strava activity {activity_id}...[/bold cyan]")

    # First check local database
    try:
        strava_id = int(activity_id)
    except ValueError:
        console.print("[red]Error: Activity ID must be a number.[/red]")
        sys.exit(1)

    existing = get_activity_by_strava_id(strava_id)

    # Fetch from Strava regardless to get full detail
    access_token = _get_access_token()

    try:
        raw = get_activity_detail(access_token, strava_id)
    except StravaAPIError as e:
        if existing:
            console.print(f"[yellow]Could not fetch from Strava: {e}. Using cached data.[/yellow]")
            # Use cached data for Claude analysis
            week_num, year = get_current_week_number()
            all_week = get_activities_by_week(existing.get("week_number", week_num), existing.get("year", year))
            weekly_stats = compute_weekly_stats(all_week)
            shoe_miles = load_shoe_miles()
            recent = get_recent_activities(5)
            from coach import analyze_run_with_ai
            feedback = analyze_run_with_ai(existing, weekly_stats, recent)
            display_post_run_analysis(existing, feedback, weekly_stats["total_miles"], shoe_miles)
            return
        else:
            console.print(f"[red]Could not fetch activity: {e}[/red]")
            sys.exit(1)

    laps = raw.get("laps", [])
    analyzed = analyze_activity(raw, laps=laps)

    # Save/update in database
    save_activity(analyzed)

    # Update shoe miles
    shoe_used = analyzed.get("shoe_used", "")
    if shoe_used and not existing:  # only add miles if not already in DB
        add_shoe_miles(shoe_used, analyzed.get("distance_miles", 0))

    shoe_miles = load_shoe_miles()
    week_num = analyzed.get("week_number")
    year = analyzed.get("year")
    all_week = get_activities_by_week(week_num, year) if week_num and year else []
    weekly_stats = compute_weekly_stats(all_week)
    recent = get_recent_activities(5)

    try:
        from coach import analyze_run_with_ai
        console.print("[cyan]Getting coaching feedback...[/cyan]\n")
        feedback = analyze_run_with_ai(analyzed, weekly_stats, recent)
    except Exception as e:
        console.print(f"[yellow]Could not get Claude feedback: {e}[/yellow]")
        feedback = f"AI bridge timed out/offline; data synced successfully. Details: {e}"

    display_post_run_analysis(
        activity_dict=analyzed,
        claude_feedback=feedback,
        weekly_miles=weekly_stats.get("total_miles", 0),
        shoe_miles=shoe_miles,
    )


# ---------------------------------------------------------------------------
# Command: plan
# ---------------------------------------------------------------------------

def cmd_plan() -> None:
    """Generate and save this week's training plan."""
    console.print("\n[bold cyan]Generating weekly training plan...[/bold cyan]\n")

    last_2_weeks = _get_last_n_weeks_activities(2)

    if not last_2_weeks:
        console.print("[yellow]No recent activities found in database. Running sync first...[/yellow]")
        try:
            cmd_sync()
            last_2_weeks = _get_last_n_weeks_activities(2)
        except SystemExit:
            pass

    try:
        plan = generate_monday_plan(last_2_weeks)
    except Exception as e:
        console.print(f"[red]Could not generate plan: {e}[/red]")
        # Show the schedule template as fallback
        week_num, _ = get_current_week_number()
        console.print(format_weekly_schedule_text(week_num))
        return

    week_num, year = get_current_week_number()
    path = save_plan_to_file(plan, week_num=week_num, year=year)
    console.print(f"\n[green]Plan saved to: {path}[/green]")


# ---------------------------------------------------------------------------
# Command: webhook
# ---------------------------------------------------------------------------

def cmd_webhook() -> None:
    """Start the Strava webhook listener."""
    console.print("\n[bold cyan]Starting PaceIQ webhook listener...[/bold cyan]")
    console.print("Press Ctrl+C to stop.\n")

    def on_strava_event(event: dict) -> None:
        """Called when Strava sends a new activity notification."""
        object_type = event.get("object_type")
        aspect_type = event.get("aspect_type")
        object_id = event.get("object_id")

        if object_type == "activity" and aspect_type == "create":
            console.print(f"\n[green]New activity detected: {object_id}[/green]")
            console.print("Run 'python main.py sync' to fetch and analyze it.")
            # Auto-sync
            try:
                cmd_sync()
            except SystemExit:
                console.print("[yellow]Auto-sync failed. Run sync manually.[/yellow]")

    from strava_client import start_webhook_listener
    start_webhook_listener(port=5000, event_callback=on_strava_event)


# ---------------------------------------------------------------------------
# Command: status
# ---------------------------------------------------------------------------

def cmd_status() -> None:
    """Quick status check — week progress and shoe mileage."""
    week_num, year = get_current_week_number()
    activities = get_activities_by_week(week_num, year)
    weekly_stats = compute_weekly_stats(activities)
    shoe_miles = load_shoe_miles()
    recent = get_recent_activities(3)

    display_status(
        weekly_stats=weekly_stats,
        shoe_miles=shoe_miles,
        recent_activities=recent,
        week_num=week_num,
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="paceiq",
        description="PaceIQ — AI Running Coach for Tony",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  (none)          Show full weekly dashboard
  analyze [id]    Analyze a specific Strava activity by ID
  sync            Pull recent activities from Strava and get coaching feedback
  plan            Generate this week's training plan with Claude
  webhook         Start Strava webhook listener (port 5000)
  status          Quick status: week progress and shoe mileage

Examples:
  python main.py
  python main.py sync
  python main.py analyze 12345678901
  python main.py plan
  python main.py status
        """,
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="dashboard",
        choices=["dashboard", "analyze", "sync", "plan", "webhook", "status"],
        help="Command to run (default: dashboard)",
    )
    parser.add_argument(
        "activity_id",
        nargs="?",
        default=None,
        help="Strava activity ID (for 'analyze' command)",
    )

    args = parser.parse_args()

    # Initialize database on every run
    try:
        init_db()
    except Exception as e:
        console.print(f"[red]Database initialization failed: {e}[/red]")
        sys.exit(1)

    # Route to command handler
    if args.command == "dashboard" or args.command is None:
        cmd_dashboard()

    elif args.command == "sync":
        cmd_sync()

    elif args.command == "analyze":
        if not args.activity_id:
            console.print("[red]Error: 'analyze' requires a Strava activity ID.[/red]")
            console.print("Usage: python main.py analyze 12345678901")
            sys.exit(1)
        cmd_analyze(args.activity_id)

    elif args.command == "plan":
        cmd_plan()

    elif args.command == "webhook":
        cmd_webhook()

    elif args.command == "status":
        cmd_status()

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
