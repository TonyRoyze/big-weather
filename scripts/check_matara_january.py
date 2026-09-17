"""Exact two-year January example and block-length sensitivity for Matara temperature."""

import itertools
import json

import numpy as np
import pandas as pd
from compare_same_month_years import OUT, f_stat, test
from statsmodels.stats.multitest import multipletests


def main():
    daily = pd.read_csv(OUT / "tables/same_month_daily.csv")
    d = daily[(daily.location_id == "lk_matara") & (daily.month == 1)]
    x = (
        d[d.year.isin([2020, 2021])]
        .pivot(index="year", columns="day", values="temperature_2m")
        .to_numpy()
    )
    outputs = []
    for block in [7, 3]:
        choices = list(itertools.product([False, True], repeat=int(np.ceil(31 / block))))
        for kind in ["level", "spread"]:
            values = x if kind == "level" else x - np.median(x, axis=1, keepdims=True)

            def statistic(a, kind=kind):
                return f_stat(
                    a if kind == "level" else np.abs(a - np.median(a, axis=-1, keepdims=True))
                )

            observed = float(statistic(values))
            perm = np.broadcast_to(values, (len(choices), *values.shape)).copy()
            for i, choice in enumerate(choices):
                for j, swap in enumerate(choice):
                    if swap:
                        perm[i, :, j * block : (j + 1) * block] = values[
                            ::-1, j * block : (j + 1) * block
                        ]
            p = float(np.mean(statistic(perm) >= observed - 1e-12))
            outputs.append(
                {
                    "block_days": block,
                    "test": kind,
                    "statistic": observed,
                    "p": p,
                    "permutations": len(choices),
                }
            )
    frame = pd.DataFrame(outputs)
    for ix in frame.groupby("block_days").groups.values():
        frame.loc[ix, "p_holm"] = multipletests(frame.loc[ix, "p"], method="holm")[1]
    frame.to_csv(OUT / "tables/matara_january_2020_2021.csv", index=False)
    (OUT / "matara_january_example.json").write_text(
        json.dumps(
            {
                "2020_mean": x[0].mean(),
                "2021_mean": x[1].mean(),
                "2020_sd": x[0].std(ddof=1),
                "2021_sd": x[1].std(ddof=1),
                "interpretation": "Exact matched-block exchanges; 7-day primary has only 32 assignments and low power; 3-day sensitivity uses 2048 assignments",
            },
            indent=2,
        )
        + "\n"
    )
    sensitivity = []
    for month in range(1, 13):
        d = daily[(daily.location_id == "lk_matara") & (daily.month == month)]
        values = d.pivot(index="year", columns="day", values="temperature_2m").to_numpy()
        _, p, _, sp = test(values, block=3)
        sensitivity.append({"month": month, "level_p": p, "spread_p": sp})
    sensitivity = pd.DataFrame(sensitivity)
    adj = multipletests(sensitivity[["level_p", "spread_p"]].to_numpy().ravel(), method="holm")[
        1
    ].reshape(-1, 2)
    sensitivity[["level_p_holm", "spread_p_holm"]] = adj
    sensitivity.to_csv(OUT / "tables/matara_temperature_block3.csv", index=False)
    print(frame.to_string(index=False))
    print(sensitivity.to_string(index=False))


if __name__ == "__main__":
    main()
