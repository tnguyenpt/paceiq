"""
Strava API client for PaceIQ.
Handles OAuth token refresh, activity fetching, and webhook listener.
"""

import time
import threading
from typing import Optional, Dict, Any, List

import requests
from flask import Flask, request, jsonify

STRAVA_AUTH_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"


class StravaAPIError(Exception):
    """Raised when a Strava API call fails."""
    pass


# ---------------------------------------------------------------------------
# Token management
# ---------------------------------------------------------------------------

def refresh_access_token(
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> Dict[str, Any]:
    """
    Exchange a refresh token for a new access token.

    Returns dict with: access_token, refresh_token, expires_at, token_type
    Raises StravaAPIError on failure.
    """
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    try:
        resp = requests.post(STRAVA_AUTH_URL, data=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        raise StravaAPIError(f"Token refresh failed: {e}") from e

    if "access_token" not in data:
        raise StravaAPIError(f"Token refresh returned unexpected response: {data}")

    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", refresh_token),
        "expires_at": data.get("expires_at"),
        "token_type": data.get("token_type", "Bearer"),
    }


def exchange_code_for_token(
    client_id: str,
    client_secret: str,
    code: str,
) -> Dict[str, Any]:
    """
    Exchange an authorization code for access and refresh tokens.
    Used during initial OAuth setup.

    Returns dict with: access_token, refresh_token, expires_at, athlete
    Raises StravaAPIError on failure.
    """
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
    }

    try:
        resp = requests.post(STRAVA_AUTH_URL, data=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        raise StravaAPIError(f"Code exchange failed: {e}") from e

    if "access_token" not in data:
        raise StravaAPIError(f"Code exchange returned unexpected response: {data}")

    return data


# ---------------------------------------------------------------------------
# Activity fetching
# ---------------------------------------------------------------------------

def get_activities(
    access_token: str,
    after_timestamp: Optional[int] = None,
    per_page: int = 30,
    page: int = 1,
) -> List[Dict[str, Any]]:
    """
    Fetch a list of activities from Strava.

    Args:
        access_token: Valid Strava access token
        after_timestamp: Unix timestamp — only return activities after this time
        per_page: Number of activities per page (max 200)
        page: Page number for pagination

    Returns:
        List of raw Strava activity dicts.
    Raises StravaAPIError on failure.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    params: Dict[str, Any] = {
        "per_page": min(per_page, 200),
        "page": page,
    }
    if after_timestamp is not None:
        params["after"] = after_timestamp

    try:
        resp = requests.get(
            f"{STRAVA_API_BASE}/athlete/activities",
            headers=headers,
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            raise StravaAPIError("Strava rate limit exceeded. Wait 15 minutes and try again.") from e
        raise StravaAPIError(f"Failed to fetch activities: {e}") from e
    except requests.RequestException as e:
        raise StravaAPIError(f"Network error fetching activities: {e}") from e


def get_all_activities_since(
    access_token: str,
    after_timestamp: int,
) -> List[Dict[str, Any]]:
    """
    Paginate through all activities since a given timestamp.
    Handles Strava's 200-per-page limit automatically.
    """
    all_activities = []
    page = 1

    while True:
        batch = get_activities(
            access_token,
            after_timestamp=after_timestamp,
            per_page=200,
            page=page,
        )
        if not batch:
            break
        all_activities.extend(batch)
        if len(batch) < 200:
            break
        page += 1
        time.sleep(0.5)  # be polite to the API

    return all_activities


def get_activity_detail(
    access_token: str,
    activity_id: int,
) -> Dict[str, Any]:
    """
    Fetch detailed activity data including laps and segment efforts.

    Returns:
        Detailed Strava activity dict with laps list.
    Raises StravaAPIError on failure.
    """
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        resp = requests.get(
            f"{STRAVA_API_BASE}/activities/{activity_id}",
            headers=headers,
            params={"include_all_efforts": True},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            raise StravaAPIError(f"Activity {activity_id} not found on Strava.") from e
        if e.response is not None and e.response.status_code == 429:
            raise StravaAPIError("Strava rate limit exceeded.") from e
        raise StravaAPIError(f"Failed to fetch activity {activity_id}: {e}") from e
    except requests.RequestException as e:
        raise StravaAPIError(f"Network error fetching activity: {e}") from e


def get_athlete(access_token: str) -> Dict[str, Any]:
    """Fetch the authenticated athlete's profile."""
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        resp = requests.get(
            f"{STRAVA_API_BASE}/athlete",
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        raise StravaAPIError(f"Failed to fetch athlete profile: {e}") from e


# ---------------------------------------------------------------------------
# Webhook listener (Flask)
# ---------------------------------------------------------------------------

# Module-level storage for webhook events
_webhook_events: List[Dict] = []
_webhook_callback = None


def start_webhook_listener(
    port: int = 5000,
    verify_token: str = "paceiq_webhook_token",
    event_callback=None,
) -> Flask:
    """
    Start a Flask webhook listener for Strava push notifications.

    Strava sends a GET for subscription verification and POST for events.

    Args:
        port: Port to listen on (default 5000)
        verify_token: Token Strava uses to verify your endpoint
        event_callback: Optional callable(event_dict) called on each new event

    Returns:
        Flask app instance (caller should run it).
    """
    global _webhook_callback
    _webhook_callback = event_callback

    app = Flask("paceiq_webhook")

    @app.route("/webhook", methods=["GET"])
    def webhook_verify():
        """Strava subscription validation challenge."""
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == verify_token:
            return jsonify({"hub.challenge": challenge})
        return jsonify({"error": "Verification failed"}), 403

    @app.route("/webhook", methods=["POST"])
    def webhook_event():
        """Handle incoming Strava event notification."""
        event = request.get_json(force=True, silent=True) or {}
        _webhook_events.append(event)

        print(f"\n[Webhook] New event: {event.get('object_type')} {event.get('aspect_type')} "
              f"id={event.get('object_id')}")

        if _webhook_callback and callable(_webhook_callback):
            try:
                threading.Thread(
                    target=_webhook_callback,
                    args=(event,),
                    daemon=True,
                ).start()
            except Exception as e:
                print(f"[Webhook] Callback error: {e}")

        return jsonify({"status": "ok"})

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "running", "events_received": len(_webhook_events)})

    print(f"Starting PaceIQ webhook listener on port {port}...")
    print(f"Webhook URL: http://0.0.0.0:{port}/webhook")
    print(f"Verify token: {verify_token}")

    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
    return app
