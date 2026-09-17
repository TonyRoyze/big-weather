"""Build the 2026 elevation report from saved nonparametric results."""

import calendar
from pathlib import Path

import pandas as pd
from analyze_elevation_relationships import FEATURES
from nonparametric_weather_tests import OUT


def main():
    tests = pd.read_csv(OUT / "tables/nonparametric_elevation_months.csv")
    text = [
        """== Elevation Differences Within Months in 2026

The same 100 locations are compared within each of January–August 2026 using
newly committed historical downloads. All eight months are complete, including
May. This updated coverage contains 583,200 hourly observations and 800 complete
location-month summaries. Source hashes and per-month hourly counts are verified
in a separate snapshot, extending the earlier May–August comparison without
changing the frozen historical year-by-year analysis. Each site contributes one
monthly summary: precipitation is mean daily total; other features use monthly means.

Locations are divided into three fixed elevation bands: below 500 m (48 sites),
500 to below 1,500 m (26 sites), and at least 1,500 m (26 sites). These thresholds
are applied consistently to every feature and month. Kruskal–Wallis compares
rank distributions across the three bands separately in each month. The plots
show variation between sites within each elevation band, not within-month daily
variation. That differs from the historical year-by-year comparisons.

To reduce confounding from country composition, elevation-band labels are
permuted only among sites within the same country. This preserves each country's
band counts. The same 9,999 label permutations are used for all months and
features. Holm adjustment covers the 56 month–feature tests. The resulting
p-values are calibrated against this restricted reference distribution, not the
usual chi-squared distribution. Countries with no elevation-band variation do not
supply within-country contrasts. Geographic confounding within countries and
spatial dependence remain; the tests do not establish causal elevation effects.

"""
    ]
    for months in [range(1, 5), range(5, 9)]:
        text.append(
            "#figure(table(columns: (1.7fr, 1fr, 1fr, 1fr, 1fr), inset: 5pt,\n table.header([*Feature*], "
            + ", ".join(f"[*{calendar.month_abbr[m]}*]" for m in months)
            + "),\n"
        )
        for field, (label, _) in FEATURES.items():
            sub = tests[(tests.variable == field) & tests.month.isin(months)].sort_values("month")
            text.append(
                f" [{label}], " + ", ".join(f"[{r.p_holm:.4f}]" for r in sub.itertuples()) + ",\n"
            )
        text.append(
            "), caption: [Holm-adjusted p-values for elevation-band differences. The correction covers all 56 tests across January–August 2026. Values below 0.05 indicate detected differences under country-restricted permutations.])\n\n"
        )
    text.append(
        "Detected months after correction are listed below. A dash means no detected difference, not equivalence.\n\n"
    )
    text.append(
        "#table(columns: (1fr, 2fr), inset: 5pt, table.header([*Feature*], [*Months with detected differences*]),\n"
    )
    for field, (label, _) in FEATURES.items():
        sub = tests[(tests.variable == field) & (tests.p_holm < 0.05)].sort_values("month")
        names = ", ".join(calendar.month_abbr[m] for m in sub.month) or "—"
        text.append(f" [{label}], [{names}],\n")
    text.append(")\n\n")
    text.append("""Kruskal–Wallis compares ranks; it is not exclusively a median test when
shapes differ. Boxplots retain the spread and overlap between locations. Adding
months changes the multiple-testing family, so corrected p-values for the earlier
months must also be updated.

A detected difference in one month and no detected difference in another does
not establish a significant month-by-elevation interaction. These are monthly
associations, not recurring seasonality or causal effects. Elevation-dependent
source downscaling remains particularly relevant for temperature and pressure.
""")
    for field, (label, _) in FEATURES.items():
        page_break = "#pagebreak()"
        text.append(f"""\n{page_break}
=== {label} Across Elevation Bands

#figure(
 image("img/nonparam_elevation_{field}.png", width: 100%),
 caption: [{label} by elevation band in January–August 2026. Dots represent individual
 location summaries; boxes show medians and interquartile ranges, with 1.5-IQR
 whiskers. The same sites and elevation bands are used in all eight panels.],
)
""")
    (Path(__file__).resolve().parents[1] / "docs/report/nonparametric-elevation.typ").write_text(
        "".join(text)
    )


if __name__ == "__main__":
    main()
