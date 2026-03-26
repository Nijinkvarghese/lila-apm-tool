# Lila APM Player Journey Visualization Tool

This is a Streamlit web app that visualizes player journeys and events on LILA maps using the provided parquet telemetry.

## Local setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Ensure these folders exist in the repo root:
   - `data/` (parquet files)
   - `minimaps/` (one image per `map_id`, e.g. `AmbroseValley.png`)

3. Run the app:

```bash
streamlit run app.py --server.port 8506
```

Then open:
`http://127.0.0.1:8506`

## What the tool shows

From parquet columns:
- `x`, `y`: world coordinates
- `ts`: timestamp
- `event`: event type (`Position`, `Kill`, `Killed`, `BotKill`, `BotKilled`, `Loot`, `KilledByStorm`)

The UI supports filtering by:
- map (`map_id`)
- date (derived from `ts`)
- match (`match_id`)

It also provides:
- timeline slider (shows match state up to a chosen timestamp)
- bots vs humans styling (heuristic described in `ARCHITECTURE.md`)
- event markers (kills, deaths, loot, storm deaths)
- heatmap overlays (traffic / kill zones / death zones)

## Hosted App
[Add your deployed URL here]