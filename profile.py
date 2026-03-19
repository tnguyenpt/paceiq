"""
Runner profile for Tony — SF-based runner targeting sub 1:40 half marathon.
All data is hardcoded here and used throughout the system.
"""

RUNNER_PROFILE = {
    "name": "Tony",
    "location": "San Francisco, CA",
    "fitness": {
        "tempo_pace_min": "8:27",
        "tempo_pace_max": "8:35",
        "tempo_hr_avg": 176,
        "easy_pace_min": "10:15",
        "easy_pace_max": "10:30",
        "easy_hr_min": 155,
        "easy_hr_max": 165,
        "resting_hr": 54,
        "tempo_peak_hr": 190,
        "max_hr": 208,
        "max_hr_note": "True max HR unknown; estimated >205-210 based on ability to sustain 190 comfortably.",
        "threshold_hr": 183,
        "true_zone2_min": 155,
        "true_zone2_max": 165,
        "tempo_zone_min": 175,
        "tempo_zone_max": 183,
    },
    "goals": {
        "weekly_mileage_target": 30,
        "race_goal": "Sub 1:40 half marathon",
        "race_target_pace": "7:38",
        "race_date_target": "May 2026",
        "race_event": "Bay Area half marathon or time trial",
        "training_days_per_week": "5-6",
    },
    "history": {
        "miles_2022": 1297,
        "streak_2022": "365-day running streak",
        "previous_half_pr": "1:53",
        "note": "Experienced runner with strong base fitness",
    },
    "terrain_note": (
        "SF hills caveat: slower paces on hilly routes are NOT underperformance. "
        "Account for San Francisco's significant elevation changes when evaluating pace targets. "
        "A 9:15 pace on a hilly SF route may represent the same effort as 8:30 on flat ground."
    ),
}

WEEKLY_SCHEDULE = {
    "Monday": {
        "type": "rest_or_easy",
        "description": "Rest or easy 3-4 miles",
        "distance_min": 0,
        "distance_max": 4,
        "shoe": "Adidas Evo SL Woven",
        "hr_target_max": 165,
    },
    "Tuesday": {
        "type": "easy",
        "description": "Easy 4-5 miles",
        "distance_min": 4,
        "distance_max": 5,
        "shoe": "Adidas Evo SL Woven",
        "hr_target_max": 165,
    },
    "Wednesday": {
        "type": "tempo",
        "description": "Tempo session: 1mi warmup + 4mi tempo + 1mi cooldown = 6 miles total",
        "distance_min": 5.5,
        "distance_max": 6.5,
        "shoe": "Saucony Endorphin Speed 5",
        "hr_target_min": 175,
        "hr_target_max": 183,
        "structure": {
            "warmup": "1 mile easy",
            "main": "4 miles at tempo pace",
            "cooldown": "1 mile easy",
        },
    },
    "Thursday": {
        "type": "easy",
        "description": "Easy 5 miles",
        "distance_min": 4.5,
        "distance_max": 5.5,
        "shoe": "Adidas Evo SL Woven",
        "hr_target_max": 165,
    },
    "Friday": {
        "type": "easy",
        "description": "Easy 4 miles",
        "distance_min": 3.5,
        "distance_max": 4.5,
        "shoe": "Adidas Evo SL Woven",
        "hr_target_max": 165,
    },
    "Saturday": {
        "type": "long_run",
        "description": "Long run 10-11 miles",
        "distance_min": 10,
        "distance_max": 11,
        "shoe": "Adidas Evo SL Woven",
        "hr_target_max": 165,
    },
    "Sunday": {
        "type": "easy",
        "description": "Easy 5-6 miles",
        "distance_min": 5,
        "distance_max": 6,
        "shoe": "Adidas Evo SL Woven",
        "hr_target_max": 165,
    },
}

TEMPO_PROGRESSION = [
    {
        "week": 1,
        "pace_min": "8:35",
        "pace_max": "8:45",
        "hr_min": 174,
        "hr_max": 180,
        "notes": "Base week — establish rhythm",
    },
    {
        "week": 2,
        "pace_min": "8:27",
        "pace_max": "8:35",
        "hr_min": 176,
        "hr_max": 180,
        "notes": "Current week — building tempo confidence",
    },
    {
        "week": 3,
        "pace_min": "8:20",
        "pace_max": "8:30",
        "hr_min": 176,
        "hr_max": 181,
        "notes": "Slight push — stay controlled",
    },
    {
        "week": 4,
        "pace_min": "8:10",
        "pace_max": "8:20",
        "hr_min": 177,
        "hr_max": 182,
        "notes": "Building — check recovery before pushing",
    },
    {
        "week": 5,
        "pace_min": "8:00",
        "pace_max": "8:10",
        "hr_min": 177,
        "hr_max": 183,
        "notes": "Mid-cycle push",
    },
    {
        "week": 6,
        "pace_min": "8:00",
        "pace_max": "8:10",
        "hr_min": 177,
        "hr_max": 183,
        "notes": "Consolidation week",
    },
    {
        "week": 7,
        "pace_min": "7:45",
        "pace_max": "8:00",
        "hr_min": 178,
        "hr_max": 183,
        "notes": "Race-specific build",
    },
    {
        "week": 8,
        "pace_min": "7:45",
        "pace_max": "8:00",
        "hr_min": 178,
        "hr_max": 183,
        "notes": "Peak tempo work",
    },
]

SHOE_ROTATION = {
    "Adidas Evo SL Woven": {
        "role": "easy and long runs",
        "status": "primary — breaking in",
        "use_for": ["easy", "long_run", "moderate"],
        "max_miles": 500,
        "notes": "New shoe, breaking in gradually. Primary trainer.",
    },
    "Saucony Endorphin Speed 5": {
        "role": "tempo and quality sessions",
        "status": "active",
        "use_for": ["tempo", "race_effort"],
        "max_miles": 400,
        "notes": "Carbon-plated speed shoe. Reserve for quality days only.",
    },
    "Mizuno Neo Zen": {
        "role": "retiring — easy miles only",
        "status": "retiring",
        "use_for": ["easy"],
        "max_miles": 600,
        "notes": "Nearing end of life. Easy miles only until retired.",
    },
    "Alphaflys": {
        "role": "race day",
        "status": "not yet purchased",
        "use_for": ["race_effort"],
        "max_miles": 300,
        "notes": "Planned race day shoe. Not yet purchased.",
    },
}

HR_ZONES = {
    "Zone 1": {
        "name": "Recovery",
        "min_hr": 0,
        "max_hr": 144,
        "description": "Very easy, active recovery",
    },
    "Zone 2": {
        "name": "Easy/Aerobic",
        "min_hr": 145,
        "max_hr": 165,
        "description": "True aerobic base building — Tony's easy zone",
    },
    "Zone 3": {
        "name": "Moderate",
        "min_hr": 165,
        "max_hr": 175,
        "description": "Moderate effort — aerobic but pushing",
    },
    "Zone 4": {
        "name": "Threshold/Tempo",
        "min_hr": 175,
        "max_hr": 183,
        "description": "Lactate threshold — Tony's tempo zone",
    },
    "Zone 5": {
        "name": "Race/VO2max",
        "min_hr": 183,
        "max_hr": 999,
        "description": "Race effort, VO2max work",
    },
}

FUEL_PROTOCOL = (
    "Pre-run: Celsius energy drink 45-60 minutes before. "
    "Miles 1-5: Nerds clusters (fast-digesting sugar). "
    "Mile 5: BPN GO caffeinated gel (first caffeine hit). "
    "Mile 9: BPN GO caffeinated gel (second caffeine hit). "
    "Throughout: BPN electrolytes in water — critical for SF heat and humidity. "
    "Post-run: Prioritize protein within 30 minutes for recovery."
)
