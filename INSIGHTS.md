# Insights

Notes:
- All numeric evidence below comes from quick aggregation over your parquet data in `data/`.
- “Bots vs humans” is computed using the heuristic in `ARCHITECTURE.md` (user_id appearing in `BotKill`/`BotKilled`).

## 1. Combat events are bot-dominated in the provided slice

Observation:
Combat events appear to be dominated by entities classified as bots under the current heuristic.

Note:
This likely reflects either dataset composition or limitations in the bot-detection heuristic.

Action:
Further validation of bot labeling is required before using combat distributions for balancing decisions.

Actionable takeaway for level design:
- Use the tool’s bot/human overlays and event markers to verify encounter design assumptions (is this a bot-heavy simulation scenario?).
- Metrics likely affected:
  - encounter density (where kills cluster)
  - difficulty tuning (if humans are not participating in combat in this dataset)

Why a level designer should care:
- If real player behavior differs from bot behavior, heatmaps and kill-zone suggestions need recalibration before gameplay iteration.

## 2. Clear traffic hotspots exist per map (chokepoints)

What caught our eye:
- The heatmap’s “traffic (positions)” shows one dominant bin (highest count) per map, indicating chokepoints or heavily-traveled lanes.

Supporting evidence (highest-traffic bin):
- `AmbroseValley`: hotspot near (x=90.26, y=107.05) with count=906
- `GrandRift`: hotspot near (x=-160.10, y=40.56) with count=92
- `Lockdown`: hotspot near (x=116.80, y=34.01) with count=399

Actionable takeaway for level design:
- Add/adjust cover, entry angles, and visibility blockers around these coordinates to control the frequency of third-party kills.
- Metrics likely affected:
  - time-to-contact (via pathing)
  - kill dispersion (reducing overly concentrated kill zones)

Why a level designer should care:
- Traffic hotspots strongly influence where fights naturally occur, even without explicit encounter scripting.

## 3. Storm deaths have map-specific clustering locations

What caught our eye:
- When switching the heatmap overlay to “death zones” and enabling storm death markers, storm-related deaths cluster to specific areas per map.

Supporting evidence (storm-death location center):
- `AmbroseValley`: storm deaths mean location around (x=19.70, y=115.30), total storm deaths=17
- `GrandRift`: mean around (x=3.67, y=22.35), total storm deaths=5
- `Lockdown`: mean around (x=48.87, y=42.21), total storm deaths=17

Actionable takeaway for level design:
- Review storm edge timing routes and safety staging near those regions:
  - ensure there are meaningful “late-rotation” options
  - check if the geometry funnels players into unavoidable storm exposure
- Metrics likely affected:
  - storm death rate
  - survivability during late match rotations

Why a level designer should care:
- Storm pressure often determines match pacing and “final fight” locations; tuning it changes retention-driving moments.

## 4. Player movement is highly centralized

Observation:
Player paths are heavily concentrated in a small region of the map.

Evidence:
Movement paths overlap significantly in the center, while outer areas show sparse activity.

Impact:
Large portions of the map are underutilized.

Action:
Redistribute incentives (loot, objectives) to outer regions to improve map usage.

Why it matters:
Balanced spatial usage leads to more varied gameplay and reduces repetitive encounters.