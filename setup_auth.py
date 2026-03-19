"""
Strava OAuth setup for PaceIQ.
Runs the full first-time authentication flow:
1. Opens browser to Strava auth URL
2. Catches the callback on localhost:8080
3. Exchanges code for tokens
4. Saves tokens to .env
5. Pulls last 4 weeks of activities
6. Generates first weekly plan
"""

import os
import sys
import time
import webbrowser
import pathlib
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from flask import Flask, request, redirect

# Ensure project directory is on sys.path
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from config import get_config, save_env_tokens
from strava_client import exchange_code_for_token, get_all_activities_since, StravaAPIError
from activity_analyzer import analyze_activity
from database import init_db, save_activity, get_recent_activities
from weekly_planner import generate_monday_plan, save_plan_to_file, get_current_week_number

CALLBACK_PORT = 8080
CALLBACK_PATH = "/callback"
STRAVA_AUTH_BASE = "https://www.strava.com/oauth/authorize"

# Shared state for the OAuth callback
_auth_code: Optional[str] = None
_auth_error: Optional[str] = None
_auth_done = threading.Event()


def _build_auth_url(client_id: str) -> str:
    """Build the Strava OAuth authorization URL."""
    params = [
        f"client_id={client_id}",
        "response_type=code",
        f"redirect_uri=http://localhost:{CALLBACK_PORT}{CALLBACK_PATH}",
        "approval_prompt=force",
        "scope=read,activity:read_all",
    ]
    return f"{STRAVA_AUTH_BASE}?" + "&".join(params)


def _run_callback_server() -> None:
    """Run a temporary Flask server to catch the OAuth callback."""
    global _auth_code, _auth_error
    app = Flask("paceiq_auth")

    @app.route(CALLBACK_PATH)
    def callback():
        global _auth_code, _auth_error
        code = request.args.get("code")
        error = request.args.get("error")

        if code:
            _auth_code = code
            _auth_done.set()
            return (
                "<html><body style='font-family:sans-serif;text-align:center;padding:50px'>"
                "<h2>Authorization successful!</h2>"
                "<p>You can close this tab and return to your terminal.</p>"
                "</body></html>"
            )
        elif error:
            _auth_error = error
            _auth_done.set()
            return (
                f"<html><body style='font-family:sans-serif;text-align:center;padding:50px'>"
                f"<h2>Authorization failed</h2>"
                f"<p>Error: {error}</p>"
                f"<p>Return to your terminal.</p>"
                f"</body></html>"
            ), 400
        else:
            return "No code or error received.", 400

    # Run in a thread that dies when _auth_done is set
    import logging
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)

    app.run(host="127.0.0.1", port=CALLBACK_PORT, debug=False, use_reloader=False)


def _pull_and_save_activities(access_token: str, weeks_back: int = 4) -> int:
    """
    Pull activities from Strava for the last N weeks and save to database.
    Returns the count of new activities saved.
    """
    since_dt = datetime.utcnow() - timedelta(weeks=weeks_back)
    since_ts = int(since_dt.timestamp())

    print(f"\nFetching activities since {since_dt.strftime('%Y-%m-%d')}...")

    try:
        raw_activities = get_all_activities_since(access_token, after_timestamp=since_ts)
    except StravaAPIError as e:
        print(f"Error fetching activities: {e}")
        return 0

    # Filter to only running activities
    runs = [a for a in raw_activities if a.get("type", "") == "Run" or a.get("sport_type", "") == "Run"]
    print(f"Found {len(runs)} running activities in the last {weeks_back} weeks.")

    saved = 0
    for raw in runs:
        analyzed = analyze_activity(raw)
        save_activity(analyzed)
        print(
            f"  Saved: {analyzed['date']} — {analyzed['run_type']} "
            f"{analyzed['distance_miles']:.1f} mi @ {analyzed['avg_pace_per_mile']}/mi"
        )
        saved += 1

    return saved


def run_setup() -> None:
    """Execute the full OAuth + initial data pull setup flow."""
    print("\n" + "=" * 60)
    print("  PaceIQ — Strava Authorization Setup")
    print("=" * 60)

    config = get_config()

    client_id = config.get("strava_client_id", "")
    client_secret = config.get("strava_client_secret", "")

    if not client_id or not client_secret:
        print("\nError: STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET must be set in your .env file.")
        print("Get your credentials at: https://developers.strava.com/")
        sys.exit(1)

    # Initialize database
    init_db()
    print("\nDatabase initialized at ~/.paceiq/activities.db")

    # Check if we already have a refresh token
    existing_refresh = config.get("strava_refresh_token", "")
    if existing_refresh and existing_refresh != "your_refresh_token_here":
        print(f"\nExisting refresh token found. Skipping OAuth flow.")
        print("To re-authorize, remove STRAVA_REFRESH_TOKEN from your .env file.")

        # Use existing token to pull activities
        from strava_client import refresh_access_token
        try:
            tokens = refresh_access_token(client_id, client_secret, existing_refresh)
            access_token = tokens["access_token"]
            saved_count = _pull_and_save_activities(access_token, weeks_back=4)
            print(f"\nSaved {saved_count} activities to database.")
        except StravaAPIError as e:
            print(f"Error refreshing token: {e}")
            print("Your refresh token may be expired. Delete it from .env and run setup again.")
            sys.exit(1)
    else:
        # Full OAuth flow
        auth_url = _build_auth_url(client_id)

        print("\nStep 1: Authorize PaceIQ to access your Strava account.")
        print(f"\nAuth URL:\n  {auth_url}\n")

        # Try to open browser automatically
        print("Attempting to open browser automatically...")
        opened = webbrowser.open(auth_url)
        if not opened:
            print("Could not open browser automatically.")
            print(f"Please manually visit the URL above.")

        print(f"\nWaiting for authorization callback on port {CALLBACK_PORT}...")
        print("(The browser will redirect to localhost after you authorize)")

        # Start callback server in background thread
        server_thread = threading.Thread(target=_run_callback_server, daemon=True)
        server_thread.start()

        # Wait up to 5 minutes for the callback
        auth_received = _auth_done.wait(timeout=300)

        if not auth_received:
            print("\nTimeout: No authorization received within 5 minutes.")
            sys.exit(1)

        if _auth_error:
            print(f"\nAuthorization failed: {_auth_error}")
            sys.exit(1)

        print(f"\nAuthorization code received!")

        # Exchange code for tokens
        print("Exchanging code for access tokens...")
        try:
            tokens = exchange_code_for_token(client_id, client_secret, _auth_code)
        except StravaAPIError as e:
            print(f"Token exchange failed: {e}")
            sys.exit(1)

        # Save tokens to .env
        save_env_tokens(tokens)
        print("Tokens saved to .env file.")

        # Show athlete info
        athlete = tokens.get("athlete", {})
        if athlete:
            first = athlete.get("firstname", "")
            last = athlete.get("lastname", "")
            print(f"\nConnected as: {first} {last}")

        access_token = tokens["access_token"]
        saved_count = _pull_and_save_activities(access_token, weeks_back=4)
        print(f"\nSaved {saved_count} activities to database.")

    # Generate first weekly plan
    print("\nGenerating your first weekly training plan...")
    week_num, year = get_current_week_number()

    try:
        from database import get_all_activities_for_weeks
        # Get activities from last 2 weeks for context
        prev_week = week_num - 1 if week_num > 1 else 52
        prev_year = year if week_num > 1 else year - 1
        recent = get_all_activities_for_weeks([prev_week, week_num], year)
        if prev_week < week_num:
            recent += get_all_activities_for_weeks([prev_week], prev_year)

        plan = generate_monday_plan(recent)
        plan_path = save_plan_to_file(plan, week_num=week_num, year=year)
        print(f"\nWeekly plan saved to: {plan_path}")
    except Exception as e:
        print(f"\nCould not generate weekly plan: {e}")
        print("Run 'python main.py plan' to generate it manually.")

    print("\n" + "=" * 60)
    print("  Setup complete! Run 'python main.py' to start PaceIQ.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run_setup()
