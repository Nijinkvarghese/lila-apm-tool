import glob
from collections import defaultdict

import pandas as pd
from PIL import Image


def main() -> None:
    base = "c:/lila-apm-tool/data"
    files = glob.glob(base + "/*.parquet")
    cols = ["map_id", "x", "y"]

    stats = defaultdict(lambda: [float("inf"), float("-inf"), float("inf"), float("-inf")])

    for f in files:
        df = pd.read_parquet(f, columns=cols)
        for m, g in df.groupby("map_id"):
            s = stats[m]
            s[0] = min(s[0], float(g["x"].min()))
            s[1] = max(s[1], float(g["x"].max()))
            s[2] = min(s[2], float(g["y"].min()))
            s[3] = max(s[3], float(g["y"].max()))

    print("Exact x/y ranges across all parquet:")
    for m, (xmin, xmax, ymin, ymax) in sorted(stats.items()):
        print(f"{m}: x[{xmin:.3f},{xmax:.3f}] y[{ymin:.3f},{ymax:.3f}]")

    print()
    print("Minimap image sizes:")
    maps = ["AmbroseValley", "GrandRift", "Lockdown"]
    for map_id in maps:
        path = f"c:/lila-apm-tool/minimaps/{map_id}.png"
        try:
            img = Image.open(path)
            print(f"{map_id}: {img.size}")
        except Exception as e:
            # Some maps may not be png.
            for ext in [".png", ".jpg", ".jpeg"]:
                try_path = f"c:/lila-apm-tool/minimaps/{map_id}{ext}"
                try:
                    img = Image.open(try_path)
                    print(f"{map_id}: {img.size}")
                    break
                except Exception:
                    pass


if __name__ == "__main__":
    main()

