"""
Backward-compatible wrapper for older imports.
Use coach.py for provider-agnostic AI coaching.
"""

from coach import (
    analyze_run_with_ai as analyze_run_with_claude,
    generate_weekly_plan,
    get_recovery_recommendation,
    build_system_prompt,
)
