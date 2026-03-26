import glob
import json

import numpy as np
import pandas as pd


def main() -> None:
    base = "c:/lila-apm-tool/data"
    files = glob.glob(base + "/*.parquet")
    cols = ["user_id", "match_id", "map_id", "x", "y", "ts", "event"]

    parts: list[pd.DataFrame] = []
    for f in files:
        parts.append(pd.read_parquet(f, columns=cols))

    df = pd.concat(parts, ignore_index=True)

    # Decode event bytes -> strings.
    if len(df) and isinstance(df["event"].iloc[0], (bytes, bytearray)):
        df["event"] = df["event"].map(
            lambda v: v.decode("utf-8") if isinstance(v, (bytes, bytearray)) else str(v)
        )

    df["ts"] = pd.to_datetime(df["ts"])
    df["date"] = df["ts"].dt.date

    maps = sorted(df["map_id"].unique())

    EVENTS_POSITION = {"Position"}
    EVENTS_KILL = {"Kill", "BotKill"}
    EVENTS_DEATH = {"Killed", "BotKilled"}
    EVENTS_STORM_DEATH = {"KilledByStorm"}
    EVENTS_LOOT = {"Loot"}

    summary = {}
    for m in maps:
        d = df[df["map_id"] == m].copy()
        bot_users = set(d[d["event"].isin({"BotKill", "BotKilled"})]["user_id"].unique())

        kills = d[d["event"].isin(EVENTS_KILL)]
        deaths = d[d["event"].isin(EVENTS_DEATH)]
        storm = d[d["event"].isin(EVENTS_STORM_DEATH)]
        loot = d[d["event"].isin(EVENTS_LOOT)]
        positions = d[d["event"].isin(EVENTS_POSITION)]

        kill_bot = int(kills[kills["user_id"].isin(bot_users)].shape[0])
        kill_human = int(kills.shape[0] - kill_bot)
        death_bot = int(deaths[deaths["user_id"].isin(bot_users)].shape[0])
        death_human = int(deaths.shape[0] - death_bot)

        storm_xy_mean = None
        if len(storm):
            storm_xy_mean = (float(storm["x"].mean()), float(storm["y"].mean()))

        traffic_hotspot = None
        if len(positions):
            nbins = 40
            x = positions["x"].to_numpy()
            y = positions["y"].to_numpy()
            counts, xedges, yedges = np.histogram2d(x, y, bins=nbins)
            ix, iy = np.unravel_index(np.argmax(counts), counts.shape)
            xc = float((xedges[ix] + xedges[ix + 1]) / 2)
            yc = float((yedges[iy] + yedges[iy + 1]) / 2)
            traffic_hotspot = (xc, yc, int(counts[ix, iy]))

        summary[m] = {
            "dates": [str(x) for x in sorted(d["date"].unique(), key=str)],
            "bot_user_count": len(bot_users),
            "human_user_count": len(set(d["user_id"].unique()) - bot_users),
            "kills_total": int(kills.shape[0]),
            "kills_human": kill_human,
            "kills_bot": kill_bot,
            "deaths_total": int(deaths.shape[0]),
            "deaths_human": death_human,
            "deaths_bot": death_bot,
            "storm_deaths_total": int(storm.shape[0]),
            "storm_xy_mean": storm_xy_mean,
            "loot_total": int(loot.shape[0]),
            "traffic_hotspot": traffic_hotspot,
        }

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

