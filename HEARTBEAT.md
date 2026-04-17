# HEARTBEAT.md — Jarvis Periodic Tasks

Tasks Jarvis should handle on a schedule:

## After Every Run
- Run `python main.py sync` to pull new Strava activity and post analysis

## Every Monday Morning
- Run `python main.py plan` to generate the weekly training plan

## Every Sunday Evening
- Prompt Tony to log a garmin_snapshot.md entry (resting HR, HRV, sleep score, training readiness)

## Ongoing
- Monitor shoe mileage — alert at 300 miles (check condition) and 450 miles (replace soon)
- Track weekly mileage — flag if approaching 40 miles (recovery week needed)
