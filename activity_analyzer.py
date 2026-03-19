"""
Activity analysis for PaceIQ.
Converts raw Strava data into structured, annotated run summaries.
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any

from profile import HR_ZONES, SHOE_ROTATION, RUNNER_PROFILE, SHOE_ASSIGNMENT_RULES


# ---------------------------------------------------------------------------
# Unit conversion helpers
# ---------------------------------------------------------------------------

def meters_to_miles(meters: float) -> float:
    """Convert meters to miles, rounded to 2 decimal places."""
    return round(meters / 1609.344, 2)


def seconds_to_pace(seconds_per_meter: float) -> str:
    """
    Convert seconds-per-meter (Strava's format) to a MM:SS string per mile.
    Returns '0:00' if input is zero or invalid.
    """
    if not seconds_per_meter or seconds_per_meter <= 0:
        return "0:00"
    seconds_per_mile = seconds_per_meter * 1609.344
    return format_pace(seconds_per_mile)


def format_pace(seconds_per_mile: float) -> str:
    """Format seconds-per-mile as MM:SS string."""
    if not seconds_per_mile or seconds_per_mile <= 0:
        return "0:00"
    total_seconds = int(round(seconds_per_mile))
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def pace_str_to_seconds(pace_str: str) -> float:
    """Convert 'M:SS' or 'MM:SS' pace string to seconds per mile."""
    try:
        parts = pace_str.strip().replace("/mi", "").replace("/mile", "").split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return 0.0
    except (ValueError, AttributeError):
        return 0.0


def get_hr_zone(bpm: float) -> str:
    """Return the zone name string for a given heart rate."""
    for zone_key, zone in HR_ZONES.items():
        if zone["min_hr"] <= bpm <= zone["max_hr"]:
            return zone_key
    return "Zone 5"


# ---------------------------------------------------------------------------
# Run classification
# ---------------------------------------------------------------------------

def classify_run(
    distance_miles: float,
    avg_pace_str: str,
    avg_hr: Optional[float],
) -> str:
    """
    Classify a run into: 'easy', 'tempo', 'long_run', 'race_effort', 'moderate'.

    Rules (in priority order):
    1. race_effort  → avg HR >= 183
    2. long_run     → distance >= 8 miles AND avg HR < 175
    3. tempo        → avg HR 175-183 AND avg pace between 7:30 and 9:30/mi
    4. easy         → avg pace > 10:00/mi AND avg HR < 165
    5. moderate     → everything else
    """
    hr = avg_hr or 0.0
    pace_seconds = pace_str_to_seconds(avg_pace_str)

    if hr >= 183:
        return "race_effort"

    if distance_miles >= 8 and hr < 175:
        return "long_run"

    pace_7_30 = pace_str_to_seconds("7:30")
    pace_9_30 = pace_str_to_seconds("9:30")
    if 175 <= hr <= 183 and pace_7_30 <= pace_seconds <= pace_9_30:
        return "tempo"

    pace_10_00 = pace_str_to_seconds("10:00")
    if pace_seconds > pace_10_00 and hr < 165:
        return "easy"

    return "moderate"


# ---------------------------------------------------------------------------
# HR zone breakdown
# ---------------------------------------------------------------------------

def compute_hr_zone_breakdown(heart_rate_data: List[Dict]) -> Dict[str, float]:
    """
    Given a list of HR data points [{time: seconds, value: bpm}, ...],
    compute minutes spent in each zone.
    Returns dict like {'Zone 1': 5.2, 'Zone 2': 22.1, ...}
    """
    zone_seconds = {z: 0.0 for z in HR_ZONES}

    for i, point in enumerate(heart_rate_data):
        if i + 1 < len(heart_rate_data):
            duration = heart_rate_data[i + 1]["time"] - point["time"]
        else:
            duration = 5  # assume ~5 second interval for last point
        bpm = point.get("value", 0)
        zone = get_hr_zone(bpm)
        zone_seconds[zone] = zone_seconds.get(zone, 0.0) + duration

    return {zone: round(secs / 60, 1) for zone, secs in zone_seconds.items()}


# ---------------------------------------------------------------------------
# Shoe recommendation
# ---------------------------------------------------------------------------

def recommend_shoe(run_type: str) -> str:
    """Return the PaceIQ-assigned shoe based on rule mapping (ignores Strava shoe metadata)."""
    return SHOE_ASSIGNMENT_RULES.get(run_type, SHOE_ASSIGNMENT_RULES.get("default", "Adidas Evo SL Woven"))


# ---------------------------------------------------------------------------
# Flag detection
# ---------------------------------------------------------------------------

def compute_flags(
    run_type: str,
    distance_miles: float,
    avg_hr: Optional[float],
    avg_pace_str: str,
) -> List[str]:
    """Return a list of flag strings for notable issues with this run."""
    flags = []
    hr = avg_hr or 0.0
    pace_seconds = pace_str_to_seconds(avg_pace_str)

    if run_type == "easy" and hr > 165:
        flags.append(
            f"Easy run HR too high — avg {hr:.0f} bpm exceeds 165 bpm easy zone ceiling"
        )

    if run_type == "tempo" and hr < 173:
        flags.append(
            f"Tempo HR low — avg {hr:.0f} bpm below target 175-183 bpm tempo zone"
        )

    if run_type == "long_run" and distance_miles < 8:
        flags.append(
            f"Long run distance below target — {distance_miles:.1f} mi (target: 10-11 mi)"
        )

    pace_10_30 = pace_str_to_seconds("10:30")
    if run_type == "easy" and 0 < pace_seconds < pace_str_to_seconds("9:00"):
        flags.append(
            "Easy pace may be too fast — consider slowing down to 10:15-10:30/mi for true aerobic benefit"
        )

    return flags


# ---------------------------------------------------------------------------
# Main activity analyzer
# ---------------------------------------------------------------------------

def analyze_activity(
    raw_strava_activity: Dict[str, Any],
    laps: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """
    Convert a raw Strava activity dict into an enriched PaceIQ activity dict.

    Returns dict with:
        strava_id, name, date, distance_miles, duration_seconds, avg_pace,
        avg_hr, max_hr, elevation_gain, run_type, hr_zone_breakdown,
        flags, shoe_recommendation, week_number, year
    """
    # Distance
    distance_miles = meters_to_miles(raw_strava_activity.get("distance", 0))

    # Duration
    duration_seconds = raw_strava_activity.get("moving_time", 0) or raw_strava_activity.get("elapsed_time", 0)

    # Pace — Strava provides average_speed in m/s
    avg_speed_ms = raw_strava_activity.get("average_speed", 0)
    if avg_speed_ms and avg_speed_ms > 0:
        seconds_per_meter = 1.0 / avg_speed_ms
        avg_pace = seconds_to_pace(seconds_per_meter)
    else:
        # Fall back to computing from duration and distance
        if distance_miles > 0 and duration_seconds > 0:
            spm = duration_seconds / distance_miles
            avg_pace = format_pace(spm)
        else:
            avg_pace = "0:00"

    # Heart rate
    avg_hr = raw_strava_activity.get("average_heartrate")
    max_hr = raw_strava_activity.get("max_heartrate")

    # Elevation (meters to feet)
    elevation_gain_m = raw_strava_activity.get("total_elevation_gain", 0)
    elevation_gain_ft = round(elevation_gain_m * 3.28084, 1)

    # Run type
    run_type = classify_run(distance_miles, avg_pace, avg_hr)

    # Date and week
    start_date_str = raw_strava_activity.get("start_date_local", "")
    if start_date_str:
        try:
            start_dt = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
            run_date = start_dt.strftime("%Y-%m-%d")
            iso_cal = start_dt.isocalendar()
            week_number = iso_cal[1]
            year = iso_cal[0]
        except ValueError:
            run_date = datetime.now().strftime("%Y-%m-%d")
            iso_cal = datetime.now().isocalendar()
            week_number = iso_cal[1]
            year = iso_cal[0]
    else:
        run_date = datetime.now().strftime("%Y-%m-%d")
        iso_cal = datetime.now().isocalendar()
        week_number = iso_cal[1]
        year = iso_cal[0]

    # HR zone breakdown from laps if available
    hr_zone_breakdown = {}
    if laps:
        # Approximate zone breakdown from lap data
        for zone_key in HR_ZONES:
            hr_zone_breakdown[zone_key] = 0.0
        for lap in laps:
            lap_hr = lap.get("average_heartrate", 0)
            lap_time_min = lap.get("elapsed_time", 0) / 60.0
            if lap_hr:
                zone = get_hr_zone(lap_hr)
                hr_zone_breakdown[zone] = hr_zone_breakdown.get(zone, 0.0) + lap_time_min

    # Flags
    flags = compute_flags(run_type, distance_miles, avg_hr, avg_pace)

    # Shoe recommendation
    shoe_recommendation = recommend_shoe(run_type)

    return {
        "strava_id": raw_strava_activity.get("id"),
        "name": raw_strava_activity.get("name", "Run"),
        "date": run_date,
        "distance_miles": distance_miles,
        "duration_seconds": duration_seconds,
        "avg_pace_per_mile": avg_pace,
        "avg_hr": avg_hr,
        "max_hr": max_hr,
        "elevation_gain": elevation_gain_ft,
        "run_type": run_type,
        "hr_zone_breakdown": hr_zone_breakdown,
        "flags": flags,
        "shoe_recommendation": shoe_recommendation,
        "shoe_used": shoe_recommendation,
        "shoe_source": "rule",
        "week_number": week_number,
        "year": year,
    }


# ---------------------------------------------------------------------------
# Weekly stats
# ---------------------------------------------------------------------------

def compute_weekly_stats(activities_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute aggregate weekly statistics from a list of activity dicts.
    Returns a dict with totals, averages, and trends.
    """
    if not activities_list:
        return {
            "total_miles": 0.0,
            "num_runs": 0,
            "tempo_runs": [],
            "tempo_avg_pace": None,
            "long_run_miles": 0.0,
            "avg_hr_easy": None,
            "flags": ["Weekly mileage exceeds 40 miles"] if False else [],
            "weekly_target": 30,
            "percent_of_target": 0.0,
        }

    total_miles = sum(a.get("distance_miles", 0) for a in activities_list)
    num_runs = len(activities_list)

    tempo_runs = [a for a in activities_list if a.get("run_type") == "tempo"]
    easy_runs = [a for a in activities_list if a.get("run_type") in ("easy", "moderate")]
    long_runs = [a for a in activities_list if a.get("run_type") == "long_run"]

    # Tempo pace average
    tempo_avg_pace = None
    if tempo_runs:
        pace_seconds_list = [
            pace_str_to_seconds(r.get("avg_pace_per_mile", "0:00"))
            for r in tempo_runs
            if r.get("avg_pace_per_mile", "0:00") != "0:00"
        ]
        if pace_seconds_list:
            avg_tempo_seconds = sum(pace_seconds_list) / len(pace_seconds_list)
            tempo_avg_pace = format_pace(avg_tempo_seconds)

    long_run_miles = max(
        (a.get("distance_miles", 0) for a in long_runs), default=0.0
    )

    # Easy run avg HR
    easy_hr_values = [
        a.get("avg_hr") for a in easy_runs if a.get("avg_hr") is not None
    ]
    avg_hr_easy = (
        round(sum(easy_hr_values) / len(easy_hr_values), 1) if easy_hr_values else None
    )

    flags = []
    if total_miles > 40:
        flags.append("Weekly mileage exceeds 40 miles — monitor recovery closely")

    percent_of_target = round((total_miles / 30) * 100, 1)

    return {
        "total_miles": round(total_miles, 2),
        "num_runs": num_runs,
        "tempo_runs": tempo_runs,
        "tempo_avg_pace": tempo_avg_pace,
        "long_run_miles": long_run_miles,
        "avg_hr_easy": avg_hr_easy,
        "flags": flags,
        "weekly_target": 30,
        "percent_of_target": percent_of_target,
    }
