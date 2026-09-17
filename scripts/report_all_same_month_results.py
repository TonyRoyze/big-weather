"""Render every detected site/month/feature difference from saved test results."""

import calendar
import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from analyze_elevation_relationships import FEATURES
from compare_same_month_years import OUT

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/report"


def main():
    tests = pd.read_csv(OUT / "tables/same_month_year_tests.csv")
    daily = pd.read_csv(OUT / "tables/same_month_daily.csv")
    tests["level"] = tests.level_p_holm < 0.05
    tests["spread"] = tests.spread_p_holm < 0.05
    selected = tests[tests.level | tests.spread]
    assert len(tests) == 6 * 7 * 12
    sites = sorted(tests.location_id.unique())
    text = [
        """=== Results Across All Historical Locations and Variables

The same-month comparisons cover six locations, seven variables, and twelve
calendar months: 504 comparisons, each testing both level and within-month spread
across 2020–2025. There are 45 detected level differences and five detected spread
differences. These counts refer to location–variable–month combinations, not
individual pairs of years. All six locations have detected differences.

The tables and graphs use the primary seven-day-block analysis with 4,999
permutations. Holm correction covers the 24 tests within each location–variable
family; it does not cover the whole exploratory scan. A dash means no detected
difference after correction, not proof of equality. Daily means describe the
weather features except precipitation, which uses daily totals. February 29 is
excluded to match calendar-day positions between years.

#figure(
  table(columns: (1.7fr, 1fr, 1fr, 1fr, 1fr, 1fr, 1fr), inset: 4pt,
    table.header([*Feature*], [*Batticaloa*], [*Colombo*], [*Galle*], [*Jaffna*], [*Matara*], [*Trincomalee*]),
"""
    ]
    for field, (label, _) in FEATURES.items():
        cells = []
        for site in sites:
            t = tests[(tests.location_id == site) & (tests.variable == field)]
            cells.append(f"[{t.level.sum()} / {t.spread.sum()}]")
        text.append(f"    [{label}], " + ", ".join(cells) + ",\n")
    text.append("""  ),
  caption: [Number of months with detected level / spread differences, out of
    twelve tested per cell. No shortwave-radiation difference passes this analysis.],
)

Spread differences occur in Batticaloa humidity (November), Colombo precipitation
(January), Colombo humidity (November), Trincomalee humidity (July), and Trincomalee
cloud cover (August). None of the temperature comparisons detects a spread change.
The following location tables identify all detected months, including variables
with no detected differences. Every detected combination is visualised below.
Boxplots show medians and quartiles, triangles show means, whiskers use 1.5 IQR,
and dots show individual daily values. These graphs show distributions across
all six years; the omnibus tests do not identify which specific year pairs differ.
""")
    plotted = []
    for site in sites:
        name = site.replace("lk_", "").title()
        text.append(f"\n#pagebreak()\n=== {name}\n\n")
        text.append(
            "#table(columns: (1.7fr, 2fr, 1.3fr), inset: 4pt,\n table.header([*Variable*], [*Level difference: months*], [*Spread difference: months*]),\n"
        )
        for field, (label, _) in FEATURES.items():
            sub = tests[(tests.location_id == site) & (tests.variable == field)]
            months = lambda kind, sub=sub: (
                ", ".join(calendar.month_abbr[m] for m in sub[sub[kind]].month) or "—"
            )
            text.append(f" [{label}], [{months('level')}], [{months('spread')}],\n")
        text.append(")\n\n")
        sub = selected[selected.location_id == site].sort_values(["variable", "month"])
        for batch in range(0, len(sub), 6):
            rows = sub.iloc[batch : batch + 6]
            fig, axes = plt.subplots(
                int(np.ceil(len(rows) / 3)),
                3,
                figsize=(12, 3.5 * int(np.ceil(len(rows) / 3))),
                squeeze=False,
                layout="constrained",
            )
            for ax, r in zip(axes.flat, rows.itertuples()):
                data = daily[(daily.location_id == site) & (daily.month == r.month)]
                values = [data[data.year == y][r.variable].to_numpy() for y in range(2020, 2026)]
                ax.boxplot(
                    values, tick_labels=[str(y)[2:] for y in range(2020, 2026)], showmeans=True
                )
                rng = np.random.default_rng(42)
                for i, v in enumerate(values, 1):
                    ax.scatter(
                        i + rng.uniform(-0.15, 0.15, len(v)), v, s=7, alpha=0.4, color="#167b79"
                    )
                label, unit = FEATURES[r.variable]
                ax.set(
                    title=f"{label} · {calendar.month_abbr[r.month]}\nLevel p={r.level_p_holm:.4f}; spread p={r.spread_p_holm:.4f}",
                    ylabel=unit,
                    xlabel="Year (20xx)",
                )
                ax.grid(axis="y", alpha=0.15)
                plotted.append((site, r.variable, r.month))
            for ax in list(axes.flat)[len(rows) :]:
                ax.axis("off")
            filename = f"all_same_month_{site}_{batch // 6 + 1}.png"
            fig.savefig(REPORT / "img" / filename, dpi=180)
            plt.close(fig)
            if batch:
                text.append("#pagebreak()\n")
            text.append(
                f'#figure(image("img/{filename}", width: 100%), caption: [{name}: detected same-month differences across 2020–2025. Panel p-values are Holm-adjusted within each location–variable family.])\n\n'
            )
    expected = set(zip(selected.location_id, selected.variable, selected.month))
    assert set(plotted) == expected and len(plotted) == len(expected)
    (REPORT / "all-same-month-results.typ").write_text("".join(text))
    print(
        f"Included all {len(tests)} comparisons in tables; plotted all {len(plotted)} detected combinations across six locations."
    )


if __name__ == "__main__":
    main()
