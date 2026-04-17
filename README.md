# Stride

**S**mart **T**raining **R**ecommendations for **I**ndividual **D**istance **E**vents

Your personal running coach — lives in Discord, powered by Strava and Claude.

---

Stride is a Discord bot that connects to your Strava data and coaches you after every run. Ask it anything in your `#running` channel and it responds with real data from your training. It knows your pace targets, HR zones, shoe rotation, and 8-week tempo progression.

The PaceIQ engine handles the data plumbing — Strava OAuth, activity analysis, HR zone breakdowns, SQLite persistence. Stride handles the judgment, the coaching voice, and the Discord interface.

---

## Architecture

```text
Stride (Discord bot)
├── discord_bot.py        # Bot core: message routing, slash commands, conversation history
│
└── PaceIQ engine
    ├── main.py           # CLI orchestration + command routing
    ├── coach.py          # Stride coaching persona + Claude integration
    ├── strava_client.py  # OAuth + Strava API
    ├── activity_analyzer.py  # Run classification, HR zones, elevation handling
    ├── weekly_planner.py # Weekly plan generation
    ├── database.py       # SQLite persistence
    ├── profile.py        # Tony's runner profile and training targets
    └── dashboard.py      # Terminal output UX
```

### Discord Channel Structure

| Channel | What Stride does |
|---|---|
| `#running` | Full PaceIQ analysis, plans, shoe tracking — set as `DISCORD_RUNNING_CHANNEL_ID` |
| `#general` | General assistant mode |
| DMs | Full access, conversational |

---

## Setup

### Prerequisites

- Python 3.9+
- Strava developer account + app ([developers.strava.com](https://developers.strava.com))
- Anthropic API key ([console.anthropic.com](https://console.anthropic.com))
- Discord bot token ([discord.com/developers](https://discord.com/developers))

### Installation

```bash
cd /path/to/paceiq
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configure .env

```bash
cp .env.example .env
# Edit .env with your keys
```

Required values:

```env
STRAVA_CLIENT_ID=...
STRAVA_CLIENT_SECRET=...
STRAVA_REFRESH_TOKEN=        # filled by setup_auth.py

ANTHROPIC_API_KEY=...

DISCORD_BOT_TOKEN=...
DISCORD_RUNNING_CHANNEL_ID=  # right-click channel in Discord → Copy ID
```

### Authorize Strava

```bash
python setup_auth.py
```

Follow the OAuth prompts. This saves your refresh token to `.env` and pulls the last 4 weeks of activities.

### Discord Bot Setup

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. New Application → name it "Stride" → Bot tab → Add Bot → copy token
3. Under **Privileged Gateway Intents**, enable **Message Content Intent**
4. OAuth2 → URL Generator → select `bot` + `applications.commands` scopes
5. Bot permissions: Read Messages, Send Messages, Read Message History, Use Slash Commands
6. Open the generated URL in browser → invite Stride to your server
7. In Discord: right-click your `#running` channel → Copy Channel ID → paste as `DISCORD_RUNNING_CHANNEL_ID` in `.env`

---

## Usage

### Start Stride

```bash
python main.py discord            # Start Stride Discord bot
```

### Terminal Commands

```bash
python main.py                    # Full weekly dashboard
python main.py sync               # Pull Strava activities + run analysis
python main.py plan               # Generate this week's training plan
python main.py status             # Quick status: miles, shoes, recent runs
python main.py analyze <id>       # Analyze a specific Strava activity
```

### Discord Slash Commands

| Command | What it does |
|---|---|
| `/sync` | Pull latest Strava activities and post analysis |
| `/plan` | Generate this week's training plan |
| `/status` | Current week mileage, run count, shoe check |
| `/run <activity_id>` | Analyze a specific Strava activity |

### Natural Language in Discord

Talk to Stride in `#running` — every message gets full training context injected automatically:

- "How was my run yesterday?"
- "Should I do a tempo today or push it to tomorrow?"
- "My legs feel heavy — what's going on?"
- "What's the plan for Saturday's long run?"

---

## Recommended Channel Setup

```
Your Discord Server
├── #running       ← Stride running coach (set as DISCORD_RUNNING_CHANNEL_ID)
├── #general       ← General assistant mode
└── #garmin-log    ← Drop weekly Garmin snapshots here manually
```

---

## Data Storage

- `~/.paceiq/activities.db` — SQLite activity history
- `~/.paceiq/shoe_miles.json` — Shoe mileage tracking
- `~/.paceiq/plans/` — Generated training plans
- `garmin_snapshot.md` — Weekly Garmin readiness log (manual entry)
