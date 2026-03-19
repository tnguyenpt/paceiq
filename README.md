# PaceIQ — AI Running Coach

AI-assisted coaching workflow for a sub-1:40 half marathon goal.

## Product Lens (PM framing)

**Problem:** training data exists (Strava/Garmin), but actionable daily coaching is inconsistent.

**Who it's for:** self-coached runners who want personalized, structured guidance from their own activity history.

**Job to be done:** *"Turn my recent runs into clear next-run decisions and weekly planning."*

**MVP Success Criteria:**
- Sync recent activities reliably
- Produce post-run analysis with clear coaching guidance
- Generate weekly plan from recent data
- Track shoe mileage and training consistency

## Core capabilities

- Strava sync + activity ingestion
- Run classification (easy/tempo/long/etc.)
- HR zone and pacing analysis
- Weekly plan generation
- Shoe rotation mileage tracking
- CLI dashboard + status commands
- Optional webhook listener

## AI provider modes

PaceIQ supports 3 coaching modes:

1. `LLM_PROVIDER=openclaw` (recommended)
   - Uses existing OpenClaw agent runtime
2. `LLM_PROVIDER=openai`
   - Direct OpenAI API key
3. `LLM_PROVIDER=anthropic`
   - Direct Anthropic API key

If AI is unavailable, sync still proceeds and returns fallback messaging.

## Architecture

```text
paceiq/
├── main.py              # CLI orchestration
├── strava_client.py     # OAuth + API integration
├── activity_analyzer.py # Run analysis and heuristics
├── coach.py             # Provider-agnostic coaching layer
├── weekly_planner.py    # Weekly plan generation + save
├── database.py          # SQLite persistence
├── profile.py           # Runner profile and training targets
└── dashboard.py         # Terminal output UX
```

## Setup

```bash
cd /home/clawed/projects/paceiq
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Required `.env` values

```env
STRAVA_CLIENT_ID=...
STRAVA_CLIENT_SECRET=...
STRAVA_REFRESH_TOKEN=

LLM_PROVIDER=openclaw
LLM_MODEL=openai-codex/gpt-5.3-codex
OPENCLAW_SESSION_ID=
# OPENAI_API_KEY=
# ANTHROPIC_API_KEY=
```

### Authorize Strava

```bash
./.venv/bin/python setup_auth.py
```

## Usage

```bash
./.venv/bin/python main.py            # dashboard
./.venv/bin/python main.py status     # quick status
./.venv/bin/python main.py sync       # sync + analyze recent runs
./.venv/bin/python main.py plan       # generate weekly plan
./.venv/bin/python main.py analyze <activity_id>
./.venv/bin/python main.py webhook
```

## Data storage

- `~/.paceiq/activities.db`
- `~/.paceiq/shoe_miles.json`
- `~/.paceiq/plans/`

## Garmin snapshot workflow

Weekly trend tracker file:
- `garmin_snapshot.md`

Current process: manual Garmin screenshots + periodic value logging.

## Tradeoffs

- Chose CLI-first UX for iteration speed
- Used OpenClaw bridge to reuse existing AI runtime
- Added timeout/fallback behavior to keep sync reliable under AI instability

## Suggested screenshots (portfolio)

Add these files under `docs/screenshots/`:

- `dashboard-status.png`
- `post-run-analysis.png`
- `weekly-plan-output.png`
- `garmin-weekly-snapshot.png`

When ready, they can be embedded directly in this README.

## Next iteration (portfolio roadmap)

- `--no-ai` explicit mode for guaranteed fast sync
- Provider health check command
- Better report artifacts (weekly summary markdown/json)
- More test coverage for analyzer and planner logic
