"""
Configuration loader for PaceIQ.
Reads environment variables from .env file and provides shoe mileage persistence.
"""

import os
import json
import pathlib
from dotenv import load_dotenv

# Load .env from the project directory
_project_dir = pathlib.Path(__file__).parent
load_dotenv(_project_dir / ".env")

# PaceIQ data directory in home folder
PACEIQ_DATA_DIR = pathlib.Path.home() / ".paceiq"
SHOE_MILES_FILE = PACEIQ_DATA_DIR / "shoe_miles.json"
DB_PATH = PACEIQ_DATA_DIR / "activities.db"
PLANS_DIR = PACEIQ_DATA_DIR / "plans"


def _ensure_data_dir() -> None:
    """Create ~/.paceiq directory and subdirectories if they don't exist."""
    PACEIQ_DATA_DIR.mkdir(parents=True, exist_ok=True)
    PLANS_DIR.mkdir(parents=True, exist_ok=True)


def get_config() -> dict:
    """Return all config values as a dict. Raises ValueError if required keys are missing."""
    _ensure_data_dir()

    config = {
        "strava_client_id": os.getenv("STRAVA_CLIENT_ID", ""),
        "strava_client_secret": os.getenv("STRAVA_CLIENT_SECRET", ""),
        "strava_refresh_token": os.getenv("STRAVA_REFRESH_TOKEN", ""),
        "llm_provider": os.getenv("LLM_PROVIDER", "openclaw"),
        "llm_model": os.getenv("LLM_MODEL", "openai-codex/gpt-5.3-codex"),
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "db_path": str(DB_PATH),
        "shoe_miles_file": str(SHOE_MILES_FILE),
        "plans_dir": str(PLANS_DIR),
        "data_dir": str(PACEIQ_DATA_DIR),
    }

    return config


def get_required_config() -> dict:
    """Like get_config() but raises if critical Strava API keys are missing."""
    config = get_config()
    missing = []

    if not config["strava_client_id"]:
        missing.append("STRAVA_CLIENT_ID")
    if not config["strava_client_secret"]:
        missing.append("STRAVA_CLIENT_SECRET")

    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            f"Copy .env.example to .env and fill in your API keys."
        )

    return config


def load_shoe_miles() -> dict:
    """Load shoe mileage from ~/.paceiq/shoe_miles.json. Returns defaults if not found."""
    _ensure_data_dir()

    default_miles = {
        "Adidas Evo SL Woven": 0.0,
        "Saucony Endorphin Speed 5": 0.0,
        "Mizuno Neo Zen": 0.0,
        "Alphaflys": 0.0,
    }

    if not SHOE_MILES_FILE.exists():
        save_shoe_miles(default_miles)
        return default_miles

    try:
        with open(SHOE_MILES_FILE, "r") as f:
            data = json.load(f)
        # Ensure all known shoes are present
        for shoe in default_miles:
            if shoe not in data:
                data[shoe] = 0.0
        return data
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load shoe miles file: {e}. Using defaults.")
        return default_miles


def save_shoe_miles(shoe_miles: dict) -> None:
    """Persist shoe mileage to ~/.paceiq/shoe_miles.json."""
    _ensure_data_dir()
    try:
        with open(SHOE_MILES_FILE, "w") as f:
            json.dump(shoe_miles, f, indent=2)
    except IOError as e:
        print(f"Warning: Could not save shoe miles: {e}")


def add_shoe_miles(shoe_name: str, miles: float) -> dict:
    """Add miles to a specific shoe and save. Returns updated shoe miles dict."""
    shoe_miles = load_shoe_miles()
    if shoe_name in shoe_miles:
        shoe_miles[shoe_name] = round(shoe_miles[shoe_name] + miles, 2)
    else:
        shoe_miles[shoe_name] = round(miles, 2)
    save_shoe_miles(shoe_miles)
    return shoe_miles


def save_env_tokens(tokens: dict) -> None:
    """Write Strava tokens back to the .env file."""
    env_path = _project_dir / ".env"

    # Read existing .env content
    existing_lines = []
    if env_path.exists():
        with open(env_path, "r") as f:
            existing_lines = f.readlines()

    # Keys we might update
    update_keys = {
        "STRAVA_REFRESH_TOKEN": tokens.get("refresh_token", ""),
        "STRAVA_ACCESS_TOKEN": tokens.get("access_token", ""),
    }

    updated_keys = set()
    new_lines = []

    for line in existing_lines:
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if key in update_keys:
                new_lines.append(f"{key}={update_keys[key]}\n")
                updated_keys.add(key)
                continue
        new_lines.append(line)

    # Append any keys not already present
    for key, value in update_keys.items():
        if key not in updated_keys and value:
            new_lines.append(f"{key}={value}\n")

    with open(env_path, "w") as f:
        f.writelines(new_lines)
