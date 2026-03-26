import bisect
import glob

import pandas as pd


def load_df() -> pd.DataFrame:
    base = "c:/lila-apm-tool/data"
    files = glob.glob(base + "/*.parquet")
    cols = ["user_id", "match_id", "map_id", "x", "y", "ts", "event"]

    parts: list[pd.DataFrame] = []
    for f in files:
        parts.append(pd.read_parquet(f, columns=cols))
    df = pd.concat(parts, ignore_index=True)

    if len(df) and isinstance(df["event"].iloc[0], (bytes, bytearray)):
        df["event"] = df["event"].map(
            lambda v: v.decode("utf-8") if isinstance(v, (bytes, bytearray)) else str(v)
        )
    df["ts"] = pd.to_datetime(df["ts"])
    return df


def main() -> None:
    df = load_df()
    map_id = "AmbroseValley"
    d = df[df["map_id"] == map_id].copy()

    position = d[d["event"] == "Position"][["user_id", "match_id", "ts"]].copy()
    # Index positions per (user_id, match_id) for fast "any later position?"
    pos_index = {}
    for (uid, mid), g in position.groupby(["user_id", "match_id"]):
        pos_index[(uid, mid)] = sorted(g["ts"].tolist())

    def has_later_position(uid: str, mid: str, t, window_seconds: float) -> bool:
        arr = pos_index.get((uid, mid))
        if not arr:
            return False
        # First index with value > t
        # (we'll then verify it's still within the time window)
        idx = bisect.bisect_right(arr, t)
        if idx >= len(arr):
            return False
        return (arr[idx] - t).total_seconds() <= window_seconds

    window_seconds = 20
    event_types = ["Kill", "Killed", "BotKill", "BotKilled", "KilledByStorm"]
    for ev in event_types:
        rows = d[d["event"] == ev][["user_id", "match_id", "ts"]]
        if rows.empty:
            print(ev, "no rows")
            continue

        # Limit sampling to keep runtime reasonable.
        rows_sample = rows.sample(n=min(60, len(rows)), random_state=42)

        later_count = 0
        total = 0
        for r in rows_sample.itertuples(index=False):
            uid = r.user_id
            mid = r.match_id
            t = r.ts
            if has_later_position(uid, mid, t, window_seconds=window_seconds):
                later_count += 1
            total += 1

        print(
            f"{ev}: later_position_within_{window_seconds}s_ratio={later_count/total:.3f} ({later_count}/{total})"
        )


if __name__ == "__main__":
    main()

