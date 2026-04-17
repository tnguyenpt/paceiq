# Jarvis

Your personal Discord running coach and agent orchestrator

---

Jarvis is a Discord bot that lives in Tony's personal server. In the **#running** channel, it's a full-stack running coach — pulling from Strava, analyzing every run, generating weekly training plans, and tracking shoe mileage. In **#general**, it's just Jarvis: a sharp, resourceful assistant for whatever Tony needs.

The PaceIQ engine handles the data plumbing (Strava OAuth, activity analysis, HR zone breakdowns, SQLite persistence). Jarvis handles the judgment, the coaching voice, and the Discord interface.

---

## Architecture

```text
Jarvis (Discord bot)
├── discord_bot.py        # Bot core: message routing, slash commands, conversation history
│
└── PaceIQ engine
    ├── main.py           # CLI orchestration + command routing
    ├── coach.py          # Jarvis coaching persona + Claude integration
    ├── strava_client.py  # OAuth + Strava API
    ├── activity_analyzer.py  # Run classification, HR zones, elevation handling
    ├── weekly_planner.py # Weekly plan generation
    ├── database.py       # SQLite persistence
    ├── profile.py        # Tony's runner profile and training targets
    └── dashboard.py      # Terminal output UX
```

### Discord Channel Structure

| Channel | Mode | What Jarvis does |
|---|---|---|
| #running | Running coach | Full PaceIQ analysis, plans, shoe tracking |
| #general | General assistant | Whatever you need |
| #jarvis / #stride | Running coach | Same as #running |
| DMs | General assistant | Full access, conversational |

---

## Setup

### Prerequisites

- Python 3.9+
- Strava developer account + app ([developers.strava.com](https://developers.strava.com))
- Anthropic API key
- Discord bot token

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

Follow the OAuth prompts. This saves your refresh token to `.env`.

### Discord Bot Setup

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Create a new application → Bot tab → create bot, copy token
3. Under "Privileged Gateway Intents", enable **Message Content Intent**
4. OAuth2 → URL Generator → select `bot` + `applications.commands` scopes
5. Bot permissions: Read Messages, Send Messages, Read Message History, Use Slash Commands
6. Copy the generated URL, open it in browser, invite bot to your server
7. In Discord: right-click your #running channel → Copy Channel ID → paste as `DISCORD_RUNNING_CHANNEL_ID`

---

## Usage

### Terminal

```bash
python main.py                    # Full weekly dashboard
python main.py sync               # Pull Strava activities + run analysis
python main.py plan               # Generate this week's training plan
python main.py status             # Quick status: miles, shoes, recent runs
python main.py analyze <id>       # Analyze a specific Strava activity
python main.py discord            # Start Jarvis Discord bot
```

### Discord Slash Commands

| Command | What it does |
|---|---|
| `/sync` | Pull latest Strava activities and post analysis |
| `/plan` | Generate this week's training plan |
| `/status` | Current week mileage, run count, shoe check |
| `/run <activity_id>` | Analyze a specific Strava activity |

### Discord Natural Language

Just talk to Jarvis in #running or #general. In #running, every message gets full training context injected. Ask things like:

- "How was my run yesterday?"
- "Should I do a tempo today or push it to tomorrow?"
- "My legs feel heavy — what's going on?"
- "What's the plan for Saturday?"

---

## Channel Setup Recommendation

```
Your Discord Server
├── #general       ← Jarvis general assistant
├── #running       ← PaceIQ running coach mode (set as DISCORD_RUNNING_CHANNEL_ID)
└── #garmin-log    ← Drop weekly Garmin snapshots here
```

---

## Identity Files

| File | Purpose |
|---|---|
| `SOUL.md` | Core values and who Jarvis is |
| `IDENTITY.md` | Role, name, vibe |
| `USER.md` | Tony's context and preferences |
| `JARVIS.md` | Operating principles |
| `HEARTBEAT.md` | Periodic task schedule |
| `TOOLS.md` | Available tools and integrations |

---

## Future Agents

Jarvis is designed to grow. Planned channel expansions:

- **#hsr** — HSR Bot integration (tactical gaming assistant)
- **#finance** — spending summaries, budget check-ins
- **#projects** — project status pings, git activity digests

Each channel becomes its own agent mode. Same Jarvis, different context injection.

---

## Data Storage

- `~/.paceiq/activities.db` — SQLite activity history
- `~/.paceiq/shoe_miles.json` — Shoe mileage tracking
- `~/.paceiq/plans/` — Generated training plans
- `garmin_snapshot.md` — Weekly Garmin readiness log
