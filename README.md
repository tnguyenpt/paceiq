# PaceIQ — AI Running Coach

A personalized running coach agent for Tony, targeting a sub-1:40 half marathon in May 2026. Built with Strava API integration and configurable AI coaching (OpenClaw bridge, OpenAI/Codex, or Anthropic).

## Features

- **Post-run analysis** — automatic classification, HR zone breakdown, pace evaluation
- **AI coaching feedback** — provider-configurable coaching feedback after every run
- **Weekly training plans** — generated Monday mornings based on your recent performance
- **Shoe rotation tracking** — persistent mileage tracking across your shoe rotation
- **Strava webhook support** — real-time notifications for new activities
- **SF terrain awareness** — accounts for San Francisco's hills in pace evaluation
- **Tempo progression tracking** — structured build toward 7:38/mile race pace

---

## Setup

### 1. Get API Credentials

**Strava:**
1. Go to [developers.strava.com](https://developers.strava.com)
2. Create an application
3. Note your **Client ID** and **Client Secret**
4. Set the Authorization Callback Domain to `localhost`

**LLM Provider (choose one):**
- **OpenAI/Codex**: create an API key in OpenAI and set `OPENAI_API_KEY`
- **Anthropic**: create an API key in Anthropic and set `ANTHROPIC_API_KEY`

### 2. Install Dependencies

```bash
cd /home/clawed/projects/paceiq
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and fill in your credentials:

```env
STRAVA_CLIENT_ID=your_client_id_here
STRAVA_CLIENT_SECRET=your_client_secret_here
STRAVA_REFRESH_TOKEN=your_refresh_token_here
LLM_PROVIDER=openclaw
LLM_MODEL=openai-codex/gpt-5.3-codex
OPENCLAW_SESSION_ID=
# OPENAI_API_KEY=your_openai_api_key_here
# ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

### 4. Authorize Strava (OAuth Setup)

```bash
python setup_auth.py
```

This will:
- Open your browser to Strava's authorization page
- Catch the OAuth callback on `localhost:8080`
- Save your tokens to `.env`
- Pull your last 4 weeks of activities
- Generate your first weekly training plan

### 5. Start Using PaceIQ

```bash
python main.py
```

---

## Usage

### Show Dashboard (default)

```bash
python main.py
```

Shows your current week's progress, all activities, shoe mileage, and the latest training plan.

### Sync Recent Activities

```bash
python main.py sync
```

Pulls all running activities from the last 7 days from Strava. For each new activity:
- Analyzes distance, pace, heart rate, and run type
- Classifies the effort (easy, tempo, long run, race effort)
- Gets Claude coaching feedback (streamed live)
- Displays a formatted post-run analysis
- Updates shoe mileage tracking

Run this after every workout to get coaching feedback.

### Analyze a Specific Activity

```bash
python main.py analyze 12345678901
```

Fetches a specific Strava activity by its numeric ID, analyzes it, and generates Claude coaching feedback. Useful for analyzing older runs or re-analyzing with updated context.

To find an activity ID: go to the activity on Strava's website — the ID is the number in the URL (`strava.com/activities/12345678901`).

### Generate Weekly Training Plan

```bash
python main.py plan
```

Uses your recent activity history to generate a personalized week-by-week training plan with Claude. The plan includes:
- Day-by-day session targets
- Pace and HR targets for each run
- Shoe recommendations
- Fueling reminders for long runs and tempo sessions

Plans are saved to:
- `~/.paceiq/plans/week_plan_{year}_w{week}.txt`
- `~/Desktop/paceiq_week_plan.txt` (if Desktop exists)
- `~/paceiq_week_plan.txt` (fallback)

### Start Webhook Listener

```bash
python main.py webhook
```

Starts a Flask server on port 5000 that listens for Strava push notifications. When a new activity is uploaded to Strava, it automatically triggers a sync and analysis.

To use webhooks, you need to:
1. Have a publicly accessible URL (use ngrok or similar for local dev: `ngrok http 5000`)
2. Register the webhook with Strava's API

### Quick Status Check

```bash
python main.py status
```

Shows a compact view of:
- Current week's mileage vs 30-mile target
- Most recent run summary
- Shoe mileage for all shoes in rotation

---

## Data Storage

All data is stored locally:

| Path | Contents |
|------|----------|
| `~/.paceiq/activities.db` | SQLite database of all activities |
| `~/.paceiq/shoe_miles.json` | Persistent shoe mileage tracker |
| `~/.paceiq/plans/` | Weekly training plan files |
| `.env` | API credentials (keep private) |

---

## Training Structure

### Weekly Schedule

| Day | Session | Shoe |
|-----|---------|------|
| Monday | Rest or easy 3-4 miles | Evo SL |
| Tuesday | Easy 4-5 miles | Evo SL |
| Wednesday | Tempo: 1mi WU + 4mi tempo + 1mi CD | Speed 5 |
| Thursday | Easy 5 miles | Evo SL |
| Friday | Easy 4 miles | Evo SL |
| Saturday | Long run 10-11 miles | Evo SL |
| Sunday | Easy 5-6 miles | Evo SL |

### Tempo Progression

| Week | Pace Target | HR Target |
|------|-------------|-----------|
| 1-2 | 8:27–8:35/mi | 176–180 bpm |
| 3 | 8:20–8:30/mi | 176–181 bpm |
| 4 | 8:10–8:20/mi | 177–182 bpm |
| 5-6 | 8:00–8:10/mi | 177–183 bpm |
| 7-8 | 7:45–8:00/mi | 178–183 bpm |
| Race | 7:38/mi sustained | — |

### HR Zones

| Zone | BPM Range | Purpose |
|------|-----------|---------|
| Zone 1 | < 145 | Recovery |
| Zone 2 | 145–165 | Easy/aerobic base |
| Zone 3 | 165–175 | Moderate |
| Zone 4 | 175–183 | Threshold/tempo |
| Zone 5 | 183+ | Race/VO2max |

---

## Shoe Rotation

| Shoe | Role | Notes |
|------|------|-------|
| Adidas Evo SL Woven | Easy + long runs | Primary trainer, breaking in |
| Saucony Endorphin Speed 5 | Tempo + quality | Reserve for hard days only |
| Mizuno Neo Zen | Retiring | Easy miles only until retired |
| Alphaflys | Race day | Not yet purchased |

---

## Architecture

```
paceiq/
├── main.py              # CLI entry point and command orchestration
├── profile.py           # Tony's runner profile (hardcoded data)
├── config.py            # Environment config + shoe miles persistence
├── database.py          # SQLite layer (activities, weekly summaries)
├── strava_client.py     # Strava OAuth + API calls
├── activity_analyzer.py # Run classification, HR zones, stats
├── coach.py             # AI coaching engine (OpenClaw bridge, OpenAI/Codex, or Anthropic)
├── weekly_planner.py    # Weekly plan generation and storage
├── dashboard.py         # Rich terminal UI
├── setup_auth.py        # First-time Strava OAuth setup
├── requirements.txt     # Python dependencies
└── .env.example         # Environment variable template
```

---

## Notes

- **SF terrain**: PaceIQ automatically notes when elevation is significant and adjusts pace expectations accordingly. A 9:15 pace on a hilly SF route may represent the same effort as 8:30 on flat ground.
- **Heart rate drift**: On easy days, if HR creeps above 165 bpm, PaceIQ will flag it. This is common in heat or after hard efforts.
- **Shoe mileage**: Updated automatically on every sync. Alerts when shoes approach retirement mileage.
- **LLM model**: Configurable via `LLM_PROVIDER` + `LLM_MODEL` in `.env` (supports OpenClaw bridge, OpenAI/Codex, and Anthropic).
