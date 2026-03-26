import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from PIL import Image

st.set_page_config(layout="wide")
st.title("Player Journey Visualization Tool")
st.caption("Timeline playback, event markers, bot vs human styling, and heatmaps.")

EVENTS_KILL = {"Kill", "BotKill"}
EVENTS_DEATH = {"Killed", "BotKilled"}
EVENTS_STORM_DEATH = {"KilledByStorm"}
EVENTS_LOOT = {"Loot"}
EVENTS_POSITION = {"Position", "BotPosition"}
WORLD_X_MIN, WORLD_X_MAX = -500.0, 500.0
WORLD_Y_MIN, WORLD_Y_MAX = -500.0, 500.0

# Map configuration from README.md (world (x,z) -> minimap pixels 0..1024)
MAP_CONFIG = {
    "AmbroseValley": {"scale": 900.0, "origin_x": -370.0, "origin_z": -473.0},
    "GrandRift": {"scale": 581.0, "origin_x": -290.0, "origin_z": -290.0},
    "Lockdown": {"scale": 1000.0, "origin_x": -500.0, "origin_z": -500.0},
}


@st.cache_data
def load_data() -> pd.DataFrame:
    base_dir = os.path.dirname(__file__)
    data_folder = os.path.join(base_dir, "data")
    if not os.path.exists(data_folder):
        return pd.DataFrame()

    parquet_files = [f for f in os.listdir(data_folder) if f.endswith(".parquet")]
    if not parquet_files:
        return pd.DataFrame()

    dfs: list[pd.DataFrame] = []
    for file in parquet_files:
        file_path = os.path.join(data_folder, file)
        dfs.append(pd.read_parquet(file_path))

    df = pd.concat(dfs, ignore_index=True)

    # Parquet stores `event` as bytes like b'Position'.
    if len(df) > 0 and isinstance(df["event"].iloc[0], (bytes, bytearray)):
        df["event"] = df["event"].map(
            lambda v: v.decode("utf-8") if isinstance(v, (bytes, bytearray)) else str(v)
        )

    df["ts"] = pd.to_datetime(df["ts"])
    df["date"] = df["ts"].dt.date
    # Convert world coordinates (x,z) to a fixed world-coordinate space
    # matching the minimap placement bounds.
    # README note: `y` in the data is elevation, so we use `z` for 2D mapping.
    if {"x", "z", "map_id"}.issubset(df.columns):
        df["mx"] = np.nan
        df["my"] = np.nan
        span_x = WORLD_X_MAX - WORLD_X_MIN
        span_y = WORLD_Y_MAX - WORLD_Y_MIN
        for map_id, cfg in MAP_CONFIG.items():
            mask = df["map_id"] == map_id
            if not mask.any():
                continue
            scale = float(cfg["scale"])
            origin_x = float(cfg["origin_x"])
            origin_z = float(cfg["origin_z"])
            u = (df.loc[mask, "x"] - origin_x) / scale
            v = (df.loc[mask, "z"] - origin_z) / scale
            # Map u/v (0..1) into the fixed world-coordinate space.
            # With y-axis reversed in Plotly, v increasing maps correctly to
            # WORLD_Y_MAX (top) -> WORLD_Y_MIN (bottom).
            df.loc[mask, "mx"] = WORLD_X_MIN + u * span_x
            df.loc[mask, "my"] = WORLD_Y_MIN + v * span_y

    return df


@st.cache_data
def minimap_path(minimap_dir: str, map_id: str) -> str | None:
    for ext in [".png", ".jpg", ".jpeg"]:
        possible = os.path.join(minimap_dir, map_id + ext)
        if os.path.exists(possible):
            return possible
    return None


def load_square_minimap(map_path: str) -> Image.Image:
    img = Image.open(map_path).convert("RGBA")
    w, h = img.size
    resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
    if w == h:
        return img.resize((1024, 1024), resample=resample)
    # Pad to a square without stretching. This preserves the minimap content
    # and keeps a consistent mapping to the fixed world coordinate space.
    side = max(w, h)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    offset_x = (side - w) // 2
    offset_y = (side - h) // 2
    canvas.paste(img, (offset_x, offset_y))
    return canvas.resize((1024, 1024), resample=resample)


def classify_bots(df_match: pd.DataFrame) -> set[str]:
    # README rule:
    # - Humans: UUID-like `user_id`
    # - Bots: numeric `user_id` strings (optionally with a leading '-')
    user_str = df_match["user_id"].astype(str)
    bot_mask = user_str.str.match(r"^-?\d+$", na=False)
    return set(df_match.loc[bot_mask, "user_id"].unique())


def decimate_series(x: np.ndarray, y: np.ndarray, max_points: int) -> tuple[list[float], list[float]]:
    n = len(x)
    if n <= max_points:
        return x.tolist(), y.tolist()
    idx = np.linspace(0, n - 1, max_points).astype(int)
    return x[idx].tolist(), y[idx].tolist()


def build_paths_polyline(
    df_positions: pd.DataFrame,
    user_ids: set[str],
    max_points_per_user: int = 250,
) -> tuple[list[float], list[float]]:
    xs: list[float] = []
    ys: list[float] = []

    subset = df_positions[df_positions["user_id"].isin(user_ids)].sort_values(["user_id", "ts"])
    if subset.empty:
        return xs, ys

    for _, g in subset.groupby("user_id", sort=False):
        x, y = g["mx"].to_numpy(), g["my"].to_numpy()
        x2, y2 = decimate_series(x, y, max_points_per_user)
        xs.extend(x2)
        ys.extend(y2)
        xs.append(None)
        ys.append(None)

    return xs, ys


def add_event_markers(
    fig: go.Figure,
    df_events: pd.DataFrame,
    bot_users: set[str],
    name: str,
    human_symbol: str,
    bot_symbol: str,
    size: int,
    event_color: str,
):
    if df_events.empty:
        return

    # Performance: limit points per user to avoid browser overload on dense matches.
    max_events_per_user = 200
    if "ts" in df_events.columns:
        df_events = (
            df_events.sort_values("ts")
            .groupby("user_id", as_index=False, group_keys=False)
            .tail(max_events_per_user)
        )

    human_rows = df_events[~df_events["user_id"].isin(bot_users)]
    bot_rows = df_events[df_events["user_id"].isin(bot_users)]

    label_map = {
        "Kill": ("Human Kills", "Bot Kills"),
        "Death": ("Human Deaths", "Bot Deaths"),
        "Storm death": ("Human Storm Deaths", "Bot Storm Deaths"),
        "Loot": ("Human Loot", "Bot Loot"),
    }
    human_label, bot_label = label_map.get(
        name,
        (f"Human {name}", f"Bot {name}"),
    )

    human_legend = not human_rows.empty
    bot_legend = not bot_rows.empty

    if not human_rows.empty:
        fig.add_trace(
            go.Scattergl(
                x=human_rows["mx"],
                y=human_rows["my"],
                mode="markers",
                marker=dict(size=size, color=event_color, symbol=human_symbol),
                name=human_label,
                showlegend=human_legend,
            )
        )

    if not bot_rows.empty:
        fig.add_trace(
            go.Scattergl(
                x=bot_rows["mx"],
                y=bot_rows["my"],
                mode="markers",
                marker=dict(size=size, color=event_color, symbol=bot_symbol),
                name=bot_label,
                showlegend=bot_legend,
            )
        )


data = load_data()
if data.empty:
    st.warning("No data found. Please add `.parquet` files into the `data/` folder.")
    st.stop()

base_dir = os.path.dirname(__file__)
minimap_dir = os.path.join(base_dir, "minimaps")

st.sidebar.header("Filters")
selected_map = st.sidebar.selectbox("Select Map", options=sorted(data["map_id"].unique()))
df_map = data[data["map_id"] == selected_map]

available_dates = sorted(df_map["date"].unique())
date_choice = st.sidebar.selectbox(
    "Select Date",
    options=["All dates"] + [str(d) for d in available_dates],
)
if date_choice != "All dates":
    df_map = df_map[df_map["date"] == pd.to_datetime(date_choice).date()]

match_options = sorted(df_map["match_id"].unique())
selected_match = st.sidebar.selectbox(
    "Select Match",
    options=["All matches"] + match_options,
    index=0,
)
timeline_enabled = selected_match != "All matches" and len(match_options) > 0

df_sel = df_map[df_map["match_id"] == selected_match] if timeline_enabled else df_map
st.caption(f"Rows in selection: {len(df_sel):,}")

bot_users = classify_bots(df_sel)
human_users = set(df_sel["user_id"].unique()) - bot_users
total_players = len(df_sel["user_id"].unique())
total_kills = int(df_sel[df_sel["event"].isin(EVENTS_KILL)].shape[0])

st.sidebar.subheader("Summary Stats")
st.sidebar.write(f"Total Players: {total_players}")
st.sidebar.write(f"Humans: {len(human_users)} | Bots: {len(bot_users)}")
kills_total_placeholder = st.sidebar.empty()
kills_total_placeholder.write(f"Total Kills: {total_kills:,}")

show_paths = st.sidebar.checkbox("Toggle Paths", value=True)
show_markers = st.sidebar.checkbox("Toggle Markers", value=True)

st.sidebar.header("Help")
st.sidebar.markdown(
    """
Markers legend:
- Blue paths = human movement
- Orange paths = bot movement
- Kill = green `X`
- Death = red circles
- Loot = gold stars
- Storm death = black circles
"""
)

st.sidebar.header("Heatmaps")
heatmap_choice = st.sidebar.selectbox("Heatmap overlay", ["Off", "Traffic (positions)", "Kill zones", "Death zones"])
heatmap_opacity = st.sidebar.slider("Heatmap opacity", 0.05, 0.6, 0.25, 0.05)
heatmap_bins = st.sidebar.slider("Heatmap resolution (bins)", 30, 150, 80, 10)

st.sidebar.header("Timeline (playback)")
if timeline_enabled and not df_sel.empty:
    min_ts = df_sel["ts"].min()
    max_ts = df_sel["ts"].max()
    min_ms = int(min_ts.value // 10**6)
    max_ms = int(max_ts.value // 10**6)

    default_ms = max_ms
    step = max(1, (max_ms - min_ms) // 250)
    current_ms = st.sidebar.slider("Show up to", min_value=min_ms, max_value=max_ms, value=default_ms, step=step)
    current_ts = pd.to_datetime(current_ms * 10**6)
    df_upto = df_sel[df_sel["ts"] <= current_ts]
else:
    current_ts = None
    df_upto = df_sel

total_kills_upto = int(df_upto[df_upto["event"].isin(EVENTS_KILL)].shape[0])
kills_total_placeholder.write(f"Total Kills: {total_kills_upto:,}")

if df_sel.empty or not {"mx", "my"}.issubset(df_sel.columns):
    st.warning("Selected data does not include required `mx`/`my` columns.")
    st.stop()

# Fixed world coordinate space (do not auto-scale by filtered data).
x_min, x_max = WORLD_X_MIN, WORLD_X_MAX
y_min, y_max = WORLD_Y_MIN, WORLD_Y_MAX

map_path = minimap_path(minimap_dir, selected_map)
img = None
if map_path and os.path.exists(map_path):
    img = load_square_minimap(map_path)

fig = go.Figure()

if img is not None:
    # Put minimap behind everything.
    if img is not None:
        fig.add_layout_image(
        dict(
            source=img,
            xref="x",
            yref="y",
            x=WORLD_X_MIN,
            y=WORLD_Y_MIN, # Anchor to the 'top' for reversed axes
            sizex=WORLD_X_MAX - WORLD_X_MIN,
            sizey=WORLD_Y_MAX - WORLD_Y_MIN,
            sizing="stretch",
            opacity=1.0, # Full visibility for Level Designers
            layer="below",
        )
    )
else:
    st.warning(f"Minimap image not found for map_id={selected_map!r}")

# Heatmap overlay
if heatmap_choice != "Off" and not df_upto.empty:
    if heatmap_choice == "Traffic (positions)":
        df_heat = df_upto[df_upto["event"].isin(EVENTS_POSITION)]
        colorscale = "Hot"
    elif heatmap_choice == "Kill zones":
        df_heat = df_upto[df_upto["event"].isin(EVENTS_KILL)]
        colorscale = "YlOrRd"
    else:
        df_heat = df_upto[df_upto["event"].isin(EVENTS_DEATH.union(EVENTS_STORM_DEATH))]
        colorscale = "YlOrRd"

    if not df_heat.empty:
        heatmap_intensity = min(0.95, heatmap_opacity * 1.9)
        fig.add_trace(
            go.Histogram2d(
                x=df_heat["mx"],
                y=df_heat["my"],
                nbinsx=heatmap_bins,
                nbinsy=heatmap_bins,
                colorscale=colorscale,
                opacity=heatmap_intensity,
                showscale=False,
                hoverinfo="skip",
            )
        )

# Player paths + latest positions (up to the timeline cursor)
df_pos_upto = df_upto[df_upto["event"].isin(EVENTS_POSITION)]
if show_paths and not df_pos_upto.empty:
    latest = df_pos_upto.sort_values("ts").groupby("user_id", as_index=False).tail(1)
    latest_human = latest[latest["user_id"].isin(human_users)]
    latest_bot = latest[latest["user_id"].isin(bot_users)]

    fig.add_trace(
        go.Scattergl(
            x=latest_human["mx"],
            y=latest_human["my"],
            mode="markers",
            marker=dict(size=8, color="blue", symbol="circle"),
            name="Humans",
        )
    )
    fig.add_trace(
        go.Scattergl(
            x=latest_bot["mx"],
            y=latest_bot["my"],
            mode="markers",
            marker=dict(size=8, color="orange", symbol="triangle-up"),
            name="Bots",
        )
    )

    # Paths as single polyline per group (use None separators for breaks)
    human_xs, human_ys = build_paths_polyline(df_pos_upto, human_users)
    bot_xs, bot_ys = build_paths_polyline(df_pos_upto, bot_users)

    if human_xs:
        fig.add_trace(
            go.Scattergl(
                x=human_xs,
                y=human_ys,
                mode="lines",
                line=dict(width=2, color="rgba(0, 0, 255, 0.35)"),
                name="Human paths",
            )
        )
    if bot_xs:
        fig.add_trace(
            go.Scattergl(
                x=bot_xs,
                y=bot_ys,
                mode="lines",
                line=dict(width=2, color="rgba(255, 165, 0, 0.35)"),
                name="Bot paths",
            )
        )

# Event markers (up to the timeline cursor)
if show_markers:
    df_kills = df_upto[df_upto["event"].isin(EVENTS_KILL)]
    df_deaths = df_upto[df_upto["event"].isin(EVENTS_DEATH)]
    df_storm = df_upto[df_upto["event"].isin(EVENTS_STORM_DEATH)]
    df_loot = df_upto[df_upto["event"].isin(EVENTS_LOOT)]

    add_event_markers(
        fig,
        df_kills,
        bot_users,
        name="Kill",
        human_symbol="x",
        bot_symbol="x",
        size=12,
        event_color="green",
    )
    add_event_markers(
        fig,
        df_deaths,
        bot_users,
        name="Death",
        human_symbol="circle",
        bot_symbol="circle",
        size=11,
        event_color="red",
    )
    add_event_markers(
        fig,
        df_storm,
        bot_users,
        name="Storm death",
        human_symbol="circle",
        bot_symbol="circle",
        size=12,
        event_color="black",
    )
    add_event_markers(
        fig,
        df_loot,
        bot_users,
        name="Loot",
        human_symbol="star",
        bot_symbol="star",
        size=13,
        event_color="goldenrod",
    )

# Axis / layout
fig.update_xaxes(range=[WORLD_X_MIN, WORLD_X_MAX], showgrid=False, zeroline=False)
fig.update_yaxes(
    range=[WORLD_Y_MIN, WORLD_Y_MAX], # Fixed coordinate system with reversed Y-axis to match minimap orientation
    autorange="reversed",
    scaleanchor="x",
    scaleratio=1,
    showgrid=False,
    zeroline=False
)
fig.update_xaxes(range=[x_min, x_max], showgrid=False, zeroline=False)

if timeline_enabled and current_ts is not None:
    fig_title = f"Player Journey | {selected_map} | Match {selected_match} | {str(current_ts)[:19]}"
else:
    fig_title = f"Player Journey | {selected_map}"

fig.update_layout(
    title=fig_title,
    height=780,
    legend=dict(orientation="h"),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=10, r=10, t=60, b=10),
)

st.plotly_chart(fig, use_container_width=True)