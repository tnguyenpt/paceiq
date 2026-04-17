"""
Stride Discord Bot — orchestrator for Tony's personal Discord server.

Channel routing:
- #running (DISCORD_RUNNING_CHANNEL_ID) → full PaceIQ running coach mode
- #general → general Stride assistant mode
- Other channels → Stride responds contextually

Slash commands:
- /sync → pull latest Strava activities
- /plan → generate this week's training plan
- /status → current week summary
- /run [activity_id] → analyze a specific activity
"""

import os
import sys
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from coach import analyze_run_with_ai, generate_weekly_plan, build_system_prompt
from database import get_recent_activities, get_activities_by_week, get_activities_since, init_db
from activity_analyzer import compute_weekly_stats, meters_to_miles, seconds_to_pace
from weekly_planner import get_current_week_number, get_tempo_target_for_week
from config import get_config, load_shoe_miles
from strava_client import refresh_access_token, get_all_activities_since, get_activity_detail, get_athlete, StravaAPIError
import anthropic

# Channel IDs from env
RUNNING_CHANNEL_ID = int(os.getenv("DISCORD_RUNNING_CHANNEL_ID", "0"))

# Conversation history per channel/thread (in-memory, resets on restart)
conversation_history: dict[int, list[dict]] = {}
MAX_HISTORY = 10  # messages to keep per thread

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree


def get_channel_mode(channel_id: int, channel_name: str) -> str:
    """Determine the mode based on which channel the message is in."""
    if channel_id == RUNNING_CHANNEL_ID or "running" in channel_name.lower() or "stride" in channel_name.lower():
        return "running"
    elif "general" in channel_name.lower():
        return "general"
    else:
        return "general"


def build_running_context() -> str:
    """Build context string with recent and historical activity data for running mode."""
    from datetime import date
    from collections import defaultdict

    try:
        init_db()
        week_num, year = get_current_week_number()
        week_activities = get_activities_by_week(week_num, year)
        recent = get_recent_activities(7)
        shoe_miles = load_shoe_miles()

        context_lines = []

        # Current week summary
        if week_activities:
            stats = compute_weekly_stats(week_activities)
            context_lines.append(f"This week (Week {week_num}): {stats['total_miles']:.1f} miles, {len(week_activities)} runs")
            if stats.get("avg_tempo_pace"):
                context_lines.append(f"  Avg tempo pace: {stats['avg_tempo_pace']}")

        # Last 7 days detail
        if recent:
            context_lines.append("\nRecent runs (last 7 days):")
            for act in recent:
                context_lines.append(
                    f"  {act.get('date', '?')}: {act.get('run_type', 'run')} "
                    f"{act.get('distance_miles', 0):.1f}mi @ {act.get('avg_pace', '?')}/mi"
                    f" | {act.get('avg_hr', '?')} bpm"
                )

        # YTD summary — monthly mileage breakdown
        ytd_start = f"{date.today().year}-01-01"
        ytd_activities = get_activities_since(ytd_start)
        if ytd_activities:
            monthly = defaultdict(float)
            ytd_total = 0.0
            for act in ytd_activities:
                d = act.get("date", "")
                if len(d) >= 7:
                    month = d[:7]  # "YYYY-MM"
                    miles = act.get("distance_miles", 0) or 0
                    monthly[month] += miles
                    ytd_total += miles

            context_lines.append(f"\nYTD total: {ytd_total:.1f} miles across {len(ytd_activities)} runs")
            context_lines.append("Monthly breakdown:")
            for month in sorted(monthly):
                context_lines.append(f"  {month}: {monthly[month]:.1f} miles")

        # Shoe mileage
        if shoe_miles:
            context_lines.append("\nShoe mileage:")
            for shoe, miles in shoe_miles.items():
                context_lines.append(f"  {shoe}: {miles:.0f} miles")

        return "\n".join(context_lines) if context_lines else "No activity data available."
    except Exception as e:
        return f"(Could not load activity data: {e})"


STRAVA_TOOLS = [
    {
        "name": "get_activities",
        "description": (
            "Fetch runs from Strava for a date range. Use this when asked about specific "
            "time periods, YTD stats, monthly breakdowns, recent runs, or any historical data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "End date YYYY-MM-DD (optional, defaults to today)"},
            },
            "required": ["start_date"],
        },
    },
    {
        "name": "get_activity_detail",
        "description": "Fetch full detail for a specific run including laps and splits.",
        "input_schema": {
            "type": "object",
            "properties": {
                "activity_id": {"type": "integer", "description": "Strava activity ID"},
            },
            "required": ["activity_id"],
        },
    },
    {
        "name": "get_athlete_stats",
        "description": "Fetch the athlete's Strava profile and all-time stats.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


def _get_access_token() -> str:
    cfg = get_config()
    tokens = refresh_access_token(cfg["strava_client_id"], cfg["strava_client_secret"], cfg["strava_refresh_token"])
    return tokens["access_token"]


def _format_activity(a: dict) -> str:
    dist = meters_to_miles(a.get("distance", 0))
    pace = seconds_to_pace(a.get("average_speed", 0)) if a.get("average_speed") else "?"
    hr = a.get("average_heartrate", "?")
    name = a.get("name", "Run")
    date = (a.get("start_date_local") or "")[:10]
    run_type = a.get("type", "Run")
    return f"{date} | {name} | {dist:.1f}mi @ {pace}/mi | {hr} bpm avg"


def _execute_strava_tool(tool_name: str, tool_input: dict) -> str:
    try:
        token = _get_access_token()

        if tool_name == "get_activities":
            from datetime import datetime, timezone
            start = datetime.strptime(tool_input["start_date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            after_ts = int(start.timestamp())

            end_date = tool_input.get("end_date")
            if end_date:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                before_ts = int(end_dt.timestamp())
            else:
                before_ts = None

            raw = get_all_activities_since(token, after_timestamp=after_ts)
            runs = [a for a in raw if a.get("type") == "Run" or a.get("sport_type") == "Run"]
            if before_ts:
                runs = [a for a in runs if int(datetime.fromisoformat(a["start_date_local"].replace("Z","")).replace(tzinfo=timezone.utc).timestamp()) <= before_ts]

            if not runs:
                return "No runs found in that date range."

            total_miles = sum(meters_to_miles(a.get("distance", 0)) for a in runs)
            lines = [f"{len(runs)} runs, {total_miles:.1f} total miles\n"]
            for a in sorted(runs, key=lambda x: x.get("start_date_local", ""), reverse=True):
                lines.append(_format_activity(a))
            return "\n".join(lines)

        elif tool_name == "get_activity_detail":
            a = get_activity_detail(token, tool_input["activity_id"])
            dist = meters_to_miles(a.get("distance", 0))
            pace = seconds_to_pace(a.get("average_speed", 0)) if a.get("average_speed") else "?"
            lines = [
                f"{a.get('name')} — {(a.get('start_date_local') or '')[:10]}",
                f"Distance: {dist:.2f}mi | Pace: {pace}/mi | Avg HR: {a.get('average_heartrate','?')} bpm | Max HR: {a.get('max_heartrate','?')} bpm",
                f"Elevation gain: {a.get('total_elevation_gain',0):.0f}m | Moving time: {a.get('moving_time',0)//60}min",
            ]
            laps = a.get("laps", [])
            if laps:
                lines.append(f"\nLaps ({len(laps)}):")
                for i, lap in enumerate(laps, 1):
                    lp = seconds_to_pace(lap.get("average_speed", 0)) if lap.get("average_speed") else "?"
                    lm = meters_to_miles(lap.get("distance", 0))
                    lines.append(f"  Lap {i}: {lm:.2f}mi @ {lp}/mi | {lap.get('average_heartrate','?')} bpm")
            return "\n".join(lines)

        elif tool_name == "get_athlete_stats":
            athlete = get_athlete(token)
            return (
                f"Name: {athlete.get('firstname','')} {athlete.get('lastname','')}\n"
                f"Location: {athlete.get('city','')}, {athlete.get('state','')}\n"
                f"Follower count: {athlete.get('follower_count', 'N/A')}\n"
                f"All-time runs: available via activity history"
            )

        return f"Unknown tool: {tool_name}"

    except StravaAPIError as e:
        return f"Strava error: {e}"
    except Exception as e:
        return f"Tool error: {e}"


async def ask_jarvis(channel_id: int, user_message: str, mode: str) -> str:
    """Send a message to Claude as Stride, with Strava tool use."""
    config = get_config()
    api_key = config.get("anthropic_api_key") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return "ANTHROPIC_API_KEY not set — can't reach Claude."

    client = anthropic.Anthropic(api_key=api_key)

    system = build_system_prompt()
    if mode == "running":
        running_ctx = build_running_context()
        system += f"\n\n## Current Training Data\n{running_ctx}"

    if channel_id not in conversation_history:
        conversation_history[channel_id] = []

    history = conversation_history[channel_id]
    history.append({"role": "user", "content": user_message})

    if len(history) > MAX_HISTORY * 2:
        history = history[-(MAX_HISTORY * 2):]
        conversation_history[channel_id] = history

    # Agentic tool-use loop
    messages = list(history)
    response_text = ""
    try:
        while True:
            response = await asyncio.to_thread(
                client.messages.create,
                model=config.get("llm_model") or "claude-haiku-4-5",
                max_tokens=1024,
                system=system,
                tools=STRAVA_TOOLS,
                messages=messages,
            )

            if response.stop_reason == "tool_use":
                # Execute all tool calls and collect results
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = await asyncio.to_thread(_execute_strava_tool, block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

            else:
                # Final text response
                for block in response.content:
                    if hasattr(block, "text"):
                        response_text += block.text
                break

    except Exception as e:
        return f"Error reaching Claude: {e}"

    history.append({"role": "assistant", "content": response_text})
    return response_text


@bot.event
async def on_ready():
    print(f"Stride online as {bot.user}")
    try:
        synced = await tree.sync()
        print(f"Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


@bot.event
async def on_message(message: discord.Message):
    # Ignore self
    if message.author == bot.user:
        return

    # Only respond when mentioned or in DMs, or in designated channels
    is_dm = isinstance(message.channel, discord.DMChannel)
    is_mentioned = bot.user in message.mentions
    channel_name = getattr(message.channel, "name", "") or ""
    is_jarvis_channel = (
        getattr(message.channel, "id", 0) == RUNNING_CHANNEL_ID
        or "running" in channel_name.lower()
        or "general" in channel_name.lower()
        or "jarvis" in channel_name.lower()
        or "stride" in channel_name.lower()
    )

    # In threads, respond to everything (thread = focused conversation)
    is_thread = isinstance(message.channel, discord.Thread)

    if not (is_dm or is_mentioned or is_jarvis_channel or is_thread):
        await bot.process_commands(message)
        return

    # Clean the message content (strip mention)
    content = message.content
    if bot.user in message.mentions:
        content = content.replace(f"<@{bot.user.id}>", "").strip()
        content = content.replace(f"<@!{bot.user.id}>", "").strip()

    if not content:
        await bot.process_commands(message)
        return

    # Determine mode
    mode = get_channel_mode(getattr(message.channel, "id", 0), channel_name)

    # Use thread ID if in a thread, else channel ID
    convo_id = message.channel.id

    async with message.channel.typing():
        response = await ask_jarvis(convo_id, content, mode)

    # Discord has a 2000 char limit — split if needed
    if len(response) <= 2000:
        await message.reply(response)
    else:
        chunks = [response[i:i+1900] for i in range(0, len(response), 1900)]
        for chunk in chunks:
            await message.channel.send(chunk)

    await bot.process_commands(message)


# ─── Slash Commands ───────────────────────────────────────────────────────────

@tree.command(name="sync", description="Pull latest Strava activities and post analysis")
async def slash_sync(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    try:
        from main import cmd_sync
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            cmd_sync()
        output = f.getvalue() or "Sync complete."
        # Trim if too long
        if len(output) > 1800:
            output = output[:1800] + "\n...(truncated)"
        await interaction.followup.send(f"```\n{output}\n```")
    except Exception as e:
        await interaction.followup.send(f"Sync failed: {e}")


@tree.command(name="plan", description="Generate this week's training plan")
async def slash_plan(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    try:
        from weekly_planner import generate_monday_plan, get_current_week_number
        from database import get_activities_by_week
        week_num, year = get_current_week_number()
        # Get last 2 weeks of activities
        prev_week = week_num - 1
        prev_year = year if prev_week > 0 else year - 1
        if prev_week == 0:
            prev_week = 52
        activities = get_activities_by_week(week_num, year) + get_activities_by_week(prev_week, prev_year)
        plan = generate_monday_plan(activities)
        if len(plan) > 1800:
            plan = plan[:1800] + "\n...(see full plan in plan file)"
        await interaction.followup.send(plan)
    except Exception as e:
        await interaction.followup.send(f"Plan generation failed: {e}")


@tree.command(name="status", description="Current week mileage, next run, shoe check")
async def slash_status(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    try:
        init_db()
        week_num, year = get_current_week_number()
        week_activities = get_activities_by_week(week_num, year)
        shoe_miles = load_shoe_miles()

        lines = [f"**Week {week_num} Status**"]

        if week_activities:
            stats = compute_weekly_stats(week_activities)
            total = stats.get("total_miles", 0)
            target = 30
            pct = int(total / target * 100)
            lines.append(f"Miles: {total:.1f}/{target} ({pct}%)")
            lines.append(f"Runs: {len(week_activities)}")
        else:
            lines.append("No runs logged this week yet.")

        if shoe_miles:
            lines.append("\n**Shoe Mileage:**")
            for shoe, miles in shoe_miles.items():
                warning = " ⚠️ check condition" if miles >= 300 else ""
                warning = " 🚨 replace soon" if miles >= 450 else warning
                lines.append(f"  {shoe}: {miles:.0f} mi{warning}")

        await interaction.followup.send("\n".join(lines))
    except Exception as e:
        await interaction.followup.send(f"Status failed: {e}")


@tree.command(name="run", description="Analyze a specific Strava activity by ID")
@app_commands.describe(activity_id="Strava activity ID")
async def slash_run(interaction: discord.Interaction, activity_id: str):
    await interaction.response.defer(thinking=True)
    try:
        from main import cmd_analyze
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            cmd_analyze(activity_id)
        output = f.getvalue() or "Analysis complete."
        if len(output) > 1800:
            output = output[:1800] + "\n...(truncated)"
        await interaction.followup.send(f"```\n{output}\n```")
    except Exception as e:
        await interaction.followup.send(f"Analysis failed: {e}")


def run_discord_bot():
    """Entry point called from main.py"""
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("Error: DISCORD_BOT_TOKEN not set in .env")
        sys.exit(1)
    print("Starting Stride Discord bot...")
    bot.run(token)


if __name__ == "__main__":
    run_discord_bot()
