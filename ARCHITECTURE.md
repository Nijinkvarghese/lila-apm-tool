# Architecture Doc (1 page max)

## Tech stack (and why)

- Python + Streamlit: fastest way to ship an interactive, shareable web UI without building a separate frontend.
- Pandas + PyArrow: reads the provided parquet telemetry efficiently and enables fast filtering/grouping.
- Plotly: renders minimap overlays, event markers, and heatmaps with good hover/zoom behavior.

## Data flow (parquet -> user-visible UI)

1. App start loads all parquet files from `data/` using `pandas.read_parquet` and concatenates them.
2. The parquet column `event` is stored as bytes (e.g. `b'Position'`), so the app decodes it into strings.
3. Derived fields:
   - `ts` is converted to datetime.
   - `date` is extracted from `ts` to support date filtering.
4. UI filters compute a selected slice by:
   - `map_id` (map selection)
   - `date` (optional)
   - `match_id` (optional, enables timeline playback only when a single match is selected)
5. The selected slice is then further filtered by a “timeline cursor”:
   - when timeline is enabled, only rows with `ts <= cursor_ts` are rendered.
6. Rendering components:
   - Paths: `event == Position` plotted as decimated polylines (separate for bots vs humans).
   - Latest positions: for each `user_id`, the last `Position` row up to the cursor time.
   - Event markers:
     - kills from `event in {Kill, BotKill}`
     - deaths from `event in {Killed, BotKilled}`
     - storm deaths from `event == KilledByStorm`
     - loot from `event == Loot`
   - Heatmaps:
     - traffic uses `Position` rows
     - kill zones uses kill events
     - death zones uses death + storm-death events

## Mapping world coordinates onto the minimap

The app uses a fixed coordinate system derived from the dataset’s world bounds.

- Dynamic axis scaling based on filtered data was avoided to ensure consistent alignment between player coordinates and the minimap across all filters and matches.
- It loads the minimap image for the selected `map_id` from `minimaps/`.
- To avoid stretching:
  - it measures the minimap image aspect ratio (width/height),
  - keeps `x_range` from data,
  - derives a `y_range` that matches the image aspect ratio,
  - re-centers `y_min/y_max` around the data center.
- Plotly axes are set with:
  - `y` reversed (`autorange="reversed"`) so the image orientation matches the coordinate system expectation.

## Bot detection assumption (explicit trade-off)

The dataset schema does not include a direct “is_bot” field.
Current heuristic:
- Any `user_id` that appears in bot-specific events `BotKill` or `BotKilled` is treated as a bot for all rendering.

Trade-off:
- If the dataset semantics encode “bot” relative to a different participant, this heuristic could swap bot/human labels.
- I documented this in the code and used it to satisfy the requirement to visually distinguish bots.

## What I would do differently with more time

- Validate bot semantics against the README (or by deeper sampling) and implement a more robust bot classification.
- Improve performance for large slices by precomputing per-match downsampled trajectories.
- Add optional “show only current positions” mode to reduce clutter during timeline playback.

