# AI Travel Agent

A simple AI travel agent built on the Gemini API. It helps users plan trips: searching flights and hotels, checking the weather, and assembling day-by-day itineraries. All travel data comes from local JSON fixtures in `data/` — there are no external API calls beyond the LLM.

It exposes two interfaces:

- an interactive **CLI chat** (`python -m agent.chat`)
- a **FastAPI endpoint** (`POST /chat`) with in-memory multi-turn conversations

## How it works

The agent is a standard Gemini function-calling loop, written plainly with no frameworks:

```
agent/
├── config.py   # env vars (model, data dir)
├── prompt.py   # system prompt
├── tools.py    # tool schemas + implementations backed by data/*.json
├── loop.py     # the tool-calling loop
├── chat.py     # CLI entrypoint
└── api.py      # FastAPI app
data/
├── flights.json
├── hotels.json
└── weather.json
scripts/
└── generate_traffic.py   # sends ~20 sample queries to the API
```

The model can call four tools:

| Tool | What it does |
|---|---|
| `search_flights(origin, destination, date)` | Look up flights between two cities |
| `search_hotels(city, check_in, check_out)` | Look up hotels for a stay |
| `get_weather(city, date)` | Get a forecast for a city |
| `create_itinerary(destination, num_days, notes?)` | Assemble a day-by-day trip plan |

## Setup

Requires Python 3.11+ and a Gemini API key (free tier works).

With [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv sync
```

Or with pip:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

Then configure your key:

```bash
cp .env.example .env
# edit .env and set GEMINI_API_KEY
```

Environment variables:

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `GEMINI_API_KEY` | yes | — | Gemini API key |
| `GEMINI_MODEL` | no | `gemini-3.5-flash` | Model used by the agent |
| `GEMINI_JUDGE_MODEL` | no | `gemini-3.1-pro-preview` | Model used by the eval judges (evals only) |

## Usage

### CLI chat

```bash
uv run python -m agent.chat
```

```
you> Find me a flight from New York to Miami on March 12, 2026.
agent> I found a few options for you! ...
```

Type `quit` (or Ctrl-D) to exit. Conversation history is kept for the session.

### API

Start the server:

```bash
uv run uvicorn agent.api:app
```

Send a message:

```bash
curl -s localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "I need a hotel in Paris from June 10 to June 14, 2026."}'
```

```json
{"reply": "Here are some hotels in Paris for those dates! ...", "conversation_id": "1f0e..."}
```

To continue a conversation, pass the returned `conversation_id` back:

```bash
curl -s localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "Which one is cheapest?", "conversation_id": "1f0e..."}'
```

Conversations are held in memory and reset when the server restarts. `GET /health` returns `{"status": "ok"}`.

### Traffic generator

With the API server running, send ~20 varied sample queries (including one multi-turn conversation):

```bash
uv run python scripts/generate_traffic.py
```

Point it at a different host with an argument or env var:

```bash
uv run python scripts/generate_traffic.py http://localhost:9000
# or
TRAVEL_AGENT_URL=http://localhost:9000 uv run python scripts/generate_traffic.py
```

## Notes

- Flight, hotel, and weather data are static fixtures — edit the files in `data/` to change what the agent can find.
- There is no database, auth, or persistence; this is intentionally a minimal service.
