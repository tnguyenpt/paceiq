"""
Provider-agnostic coaching engine for PaceIQ.
Supports Anthropic and OpenAI-compatible models.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Optional, List, Dict, Any

from config import get_config
from profile import (
    RUNNER_PROFILE,
    WEEKLY_SCHEDULE,
    TEMPO_PROGRESSION,
    SHOE_ROTATION,
    HR_ZONES,
    FUEL_PROTOCOL,
)


def _llm_settings() -> tuple[str, str, str]:
    cfg = get_config()
    provider = (cfg.get("llm_provider") or "openai").strip().lower()
    model = (cfg.get("llm_model") or "openai-codex/gpt-5.3-codex").strip()

    if provider == "openclaw":
        # Uses OpenClaw's configured agent/model (no provider API key required in this app).
        session_id = os.getenv("OPENCLAW_SESSION_ID", "")
        return provider, model, session_id

    if provider == "anthropic":
        api_key = cfg.get("anthropic_api_key", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set. Add it to your .env file.")
        return provider, model, api_key

    if provider == "openai":
        api_key = cfg.get("openai_api_key", "")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set. Add it to your .env file.")
        return provider, model, api_key

    raise ValueError("LLM_PROVIDER must be 'openai', 'anthropic', or 'openclaw'.")


def build_system_prompt() -> str:
    profile = RUNNER_PROFILE
    fitness = profile["fitness"]
    goals = profile["goals"]
    history = profile["history"]

    tempo_targets = "\n".join(
        f"  Week {t['week']}: {t['pace_min']}–{t['pace_max']}/mi at {t['hr_min']}–{t['hr_max']} bpm — {t['notes']}"
        for t in TEMPO_PROGRESSION
    )

    shoe_info = "\n".join(
        f"  {shoe}: {info['role']} ({info['status']}) — {info['notes']}"
        for shoe, info in SHOE_ROTATION.items()
    )

    zone_info = "\n".join(
        f"  {zone}: {info['min_hr']}–{info['max_hr']} bpm — {info['description']}"
        for zone, info in HR_ZONES.items()
    )

    weekly_structure = "\n".join(
        f"  {day}: {info['description']}"
        for day, info in WEEKLY_SCHEDULE.items()
    )

    return f"""You are PaceIQ, a personalized running coach for Tony, a San Francisco-based runner targeting a sub-1:40 half marathon in May 2026.

## TONY'S PROFILE

**Current Fitness:**
- Tempo pace: {fitness['tempo_pace_min']}–{fitness['tempo_pace_max']}/mile at {fitness['tempo_hr_avg']} bpm avg
- Easy pace: {fitness['easy_pace_min']}–{fitness['easy_pace_max']}/mile at {fitness['easy_hr_min']}–{fitness['easy_hr_max']} bpm
- Resting HR: {fitness.get('resting_hr', 'N/A')} bpm
- Tempo session peak HR: {fitness.get('tempo_peak_hr', 'N/A')} bpm
- Max HR estimate: {fitness['max_hr']} bpm ({fitness.get('max_hr_note', 'estimate')})
- Threshold HR (Garmin): {fitness['threshold_hr']} bpm
- True Zone 2: {fitness['true_zone2_min']}–{fitness['true_zone2_max']} bpm
- Tempo zone: {fitness['tempo_zone_min']}–{fitness['tempo_zone_max']} bpm

**Goals:**
- Race goal: {goals['race_goal']} — target pace {goals['race_target_pace']}/mile
- Race timing: {goals['race_date_target']}, {goals['race_event']}
- Weekly mileage target: {goals['weekly_mileage_target']} miles
- Training: {goals['training_days_per_week']} days/week

**History:**
- {history['miles_2022']} miles in 2022 with a {history['streak_2022']}
- Previous half marathon PR: {history['previous_half_pr']}
- {history['note']}

## HEART RATE ZONES
{zone_info}

## WEEKLY TRAINING STRUCTURE
{weekly_structure}

## TEMPO PROGRESSION TARGETS
{tempo_targets}

## SHOE ROTATION
{shoe_info}

## FUEL PROTOCOL
{FUEL_PROTOCOL}

## IMPORTANT CONTEXT
{profile['terrain_note']}

## COACHING STYLE GUIDELINES
- Be direct and conversational — Tony is an experienced runner, not a beginner
- Lead with the most important insight, not a generic compliment
- Call out issues clearly but constructively
- Reference specific numbers from Tony's data
- Keep responses focused — 3-6 sentences for post-run feedback, 8-15 sentences for weekly plans
- Use running jargon appropriately (tempo, Z2, threshold, negative split, etc.)
- Always account for SF terrain when evaluating pace
- If HR is elevated on easy days, flag it and suggest causes/fixes
- Celebrate progress toward the sub-1:40 goal specifically
"""


def _stream_response(messages: List[Dict[str, str]], system: str) -> str:
    provider, model, api_key = _llm_settings()

    if provider == "openclaw":
        # Route prompts through OpenClaw's configured agent session.
        prompt_parts = [
            "You are PaceIQ's coaching brain. Keep responses concise and specific.",
            "",
            "SYSTEM CONTEXT:",
            system,
            "",
            "USER REQUEST:",
            "\n\n".join(m["content"] for m in messages if m.get("content")),
        ]
        prompt = "\n".join(prompt_parts)

        cmd = ["openclaw", "agent", "--agent", "main", "--message", prompt]
        if api_key:
            cmd.extend(["--session-id", api_key])

        timeout_sec = int(os.getenv("OPENCLAW_AGENT_TIMEOUT_SEC", "45"))
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"OpenClaw bridge timed out after {timeout_sec}s. "
                "Set OPENCLAW_AGENT_TIMEOUT_SEC to adjust."
            ) from exc

        if result.returncode != 0:
            raise RuntimeError(
                "OpenClaw bridge failed. Set OPENCLAW_SESSION_ID (optional) and ensure gateway is running. "
                f"stderr: {result.stderr.strip()}"
            )

        text = result.stdout.strip()
        if not text:
            raise RuntimeError("OpenClaw bridge returned empty output.")

        print(text)
        return text

    if provider == "anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        full = ""
        with client.messages.stream(
            model=model,
            max_tokens=1024,
            system=system,
            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
        ) as stream:
            for chunk in stream.text_stream:
                print(chunk, end="", flush=True)
                full += chunk
        print()
        return full

    # provider == openai
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    full = ""
    stream = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            *messages,
        ],
        stream=True,
        temperature=0.4,
    )
    for event in stream:
        delta = event.choices[0].delta
        text = getattr(delta, "content", None)
        if text:
            print(text, end="", flush=True)
            full += text
    print()
    return full


def analyze_run_with_ai(
    activity_dict: Dict[str, Any],
    weekly_progress: Dict[str, Any],
    prev_activities: Optional[List[Dict[str, Any]]] = None,
) -> str:
    system = build_system_prompt()

    run_type = activity_dict.get("run_type", "unknown")
    distance = activity_dict.get("distance_miles", 0)
    avg_pace = activity_dict.get("avg_pace_per_mile", "0:00")
    avg_hr = activity_dict.get("avg_hr", "N/A")
    max_hr = activity_dict.get("max_hr", "N/A")
    elevation = activity_dict.get("elevation_gain", 0)
    flags = activity_dict.get("flags", [])
    shoe = activity_dict.get("shoe_used", "unknown")
    date = activity_dict.get("date", "unknown")
    name = activity_dict.get("name", "Run")

    zone_breakdown = activity_dict.get("hr_zone_breakdown", {})
    zone_summary = ""
    if zone_breakdown:
        parts = [f"{zone}: {mins:.1f} min" for zone, mins in zone_breakdown.items() if mins > 0]
        zone_summary = ", ".join(parts)

    week_miles = weekly_progress.get("total_miles", 0)
    week_target = weekly_progress.get("weekly_target", 30)
    week_pct = weekly_progress.get("percent_of_target", 0)
    week_runs = weekly_progress.get("num_runs", 0)

    prev_context = ""
    if prev_activities:
        recent = prev_activities[-3:] if len(prev_activities) >= 3 else prev_activities
        lines = []
        for act in recent:
            lines.append(
                f"  {act.get('date', '?')}: {act.get('run_type', '?')} — "
                f"{act.get('distance_miles', 0):.1f} mi @ {act.get('avg_pace_per_mile', '?')} "
                f"| {act.get('avg_hr', '?')} bpm"
            )
        prev_context = "Recent activity history:\n" + "\n".join(lines)

    flags_str = "\n".join(f"  ⚠ {f}" for f in flags) if flags else "  None"

    user_message = f"""Tony just finished a run. Provide direct, specific coaching feedback.

**TODAY'S RUN — {date} ({name})**
- Type: {run_type}
- Distance: {distance:.2f} miles
- Avg pace: {avg_pace}/mi
- Avg HR: {avg_hr} bpm | Max HR: {max_hr} bpm
- Elevation gain: {elevation:.0f} ft (SF terrain — account for hills)
- Shoe: {shoe}
{f'- HR Zone breakdown: {zone_summary}' if zone_summary else ''}

**FLAGS:**
{flags_str}

**WEEK PROGRESS:**
- Miles this week: {week_miles:.1f} / {week_target} miles ({week_pct:.0f}%)
- Runs this week: {week_runs}

{prev_context}

Give Tony direct coaching feedback on this run. Was the effort appropriate? How does it fit the sub-1:40 goal? What's the one key takeaway? What should the next run focus on?"""

    return _stream_response([{"role": "user", "content": user_message}], system)


def generate_weekly_plan(
    week_num: int,
    prev_week_activities: List[Dict[str, Any]],
    current_week_miles: float = 0.0,
) -> str:
    system = build_system_prompt()

    if prev_week_activities:
        prev_miles = sum(a.get("distance_miles", 0) for a in prev_week_activities)
        tempo_runs = [a for a in prev_week_activities if a.get("run_type") == "tempo"]
        long_runs = [a for a in prev_week_activities if a.get("run_type") == "long_run"]

        prev_lines = []
        for act in prev_week_activities:
            prev_lines.append(
                f"  {act.get('date', '?')} ({act.get('run_type', '?')}): "
                f"{act.get('distance_miles', 0):.1f} mi @ {act.get('avg_pace_per_mile', '?')} "
                f"| {act.get('avg_hr', 'N/A')} bpm avg"
            )
        prev_detail = "\n".join(prev_lines) if prev_lines else "  No data"
        prev_total = f"{prev_miles:.1f}"
        prev_tempo = f"{tempo_runs[0].get('avg_pace_per_mile', 'N/A')}" if tempo_runs else "No tempo run"
        prev_long = f"{max((a.get('distance_miles', 0) for a in long_runs), default=0):.1f} mi" if long_runs else "No long run"
    else:
        prev_detail = "  No previous week data available"
        prev_total = "unknown"
        prev_tempo = "unknown"
        prev_long = "unknown"

    tempo_target = None
    for t in TEMPO_PROGRESSION:
        if t["week"] == week_num:
            tempo_target = t
            break
    if not tempo_target and TEMPO_PROGRESSION:
        tempo_target = TEMPO_PROGRESSION[-1]

    tempo_target_str = (
        f"{tempo_target['pace_min']}–{tempo_target['pace_max']}/mi at "
        f"{tempo_target['hr_min']}–{tempo_target['hr_max']} bpm"
        if tempo_target
        else "maintain current tempo pace"
    )

    user_message = f"""Generate Tony's weekly training plan for Week {week_num}.

**PREVIOUS WEEK RECAP:**
Total miles: {prev_total}
Tempo session: {prev_tempo}
Long run: {prev_long}
Breakdown:
{prev_detail}

**THIS WEEK'S TEMPO TARGET:** {tempo_target_str}
{f'**Miles already logged this week:** {current_week_miles:.1f}' if current_week_miles > 0 else ''}

**GENERATE:** A day-by-day plan for the full week (Mon–Sun) with:
1. Specific distance targets for each run
2. Pace/HR targets for each session
3. Which shoe to wear
4. One key focus cue per session
5. Any adjustments based on last week's performance
6. Fueling reminder for the long run and tempo

Keep it practical and specific. Tony needs to know exactly what to do each day."""

    return _stream_response([{"role": "user", "content": user_message}], system)


def get_recovery_recommendation(activity_dict: Dict[str, Any]) -> str:
    system = build_system_prompt()

    run_type = activity_dict.get("run_type", "unknown")
    distance = activity_dict.get("distance_miles", 0)
    avg_hr = activity_dict.get("avg_hr", "N/A")
    max_hr = activity_dict.get("max_hr", "N/A")
    elevation = activity_dict.get("elevation_gain", 0)

    user_message = f"""Tony just finished a {run_type} run: {distance:.1f} miles, avg HR {avg_hr}, max HR {max_hr}, {elevation:.0f} ft elevation.

Give a brief, specific recovery recommendation: what to do in the next 24-48 hours, any nutrition/sleep tips, and whether tomorrow's planned run should be modified. Keep it to 3-4 sentences."""

    return _stream_response([{"role": "user", "content": user_message}], system)
