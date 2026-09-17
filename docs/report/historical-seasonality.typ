=== Recurring Seasonality in the Older Records

Seasonality is tested using six complete years (2020–2025) at Batticaloa,
Colombo, Galle, Jaffna, Matara, and Trincomalee. The sample contains 315,648
hourly records and 432 complete location-year-month summaries, including leap
years. Precipitation is expressed as mean daily total to remove month-length
 differences; other features use monthly means.

Each site's twelve monthly values are ranked within each year. The Friedman
statistic measures agreement in calendar-month ordering across years, and
Kendall's W measures its strength from zero to one. With only six years, the
large-sample Friedman p-value is replaced by an exact circular-shift test.
Each year's monthly ranks are rotated relative to the calendar while preserving
cyclic order. Fixing the first year's phase leaves 12⁵ = 248,832 relative
rotations. The p-value is the proportion with at least the observed alignment.
Holm correction covers all 42 site–feature tests.

#figure(
  image("img/historical_seasonal_cycles.png", width: 92%),
  caption: [Historical monthly cycles, 2020–2025. Each point averages the same
    calendar month equally across six complete years at one coastal site.
    Rainfall is mean daily total.],
)

All seven weather features show significant recurring monthly alignment at all
six sites after correction. Temperature has W from 0.745 to 0.931; precipitation
has W from 0.503 to 0.623. The weakest agreement is wind at Batticaloa
(W = 0.401), which still passes the corrected test (p = 0.0081).

#figure(
  table(
    columns: (1.5fr, 1fr, 1fr, 1fr), inset: 5pt,
    table.header([*Feature*], [*Significant sites*], [*W range*], [*Largest adjusted p*]),
    [Temperature], [6 / 6], [0.745–0.931], [0.0026],
    [Precipitation], [6 / 6], [0.503–0.623], [0.0020],
    [Wind speed], [6 / 6], [0.401–0.857], [0.0081],
    [Relative humidity], [6 / 6], [0.470–0.843], [0.0037],
    [Surface pressure], [6 / 6], [0.612–0.927], [0.0026],
    [Cloud cover], [6 / 6], [0.567–0.758], [0.0026],
    [Shortwave radiation], [6 / 6], [0.675–0.807], [0.00024],
  ),
  caption: [Historical seasonal-alignment tests. W measures agreement in monthly
    ranks, not explained variance. Largest adjusted p-values are rounded upward.],
)

Batticaloa's six-year mean temperature peaks in June and reaches its minimum in
January, a 4.48 °C difference. Colombo peaks in March and reaches its minimum in
November, a 1.91 °C difference. Both sites have their highest mean daily rainfall
in November, but their driest months differ: June at Batticaloa and February at
Colombo. Rainfall peak-to-trough differences are 11.69 and 13.80 mm/day respectively.
These describe six-year averages, not identical peak months in every year.

=== Seasonal Weather and Elevation

The historical data support recurring seasonal weather patterns at the six
coastal sites. They do not establish that the regional elevation associations
observed in May–August 2026 recur seasonally. Historical sites span only 3–10 m,
compared with 3–4,321 m across the regional sample. Seasonal weather variation
and seasonal changes in an elevation association are distinct questions; combining
these samples without accounting for their different coverage would confound them.
Repeated annual coverage across the regional elevation range is needed for the
second question.

The rotation test assumes independent years and uniformly exchangeable cyclic
phase under the null. It preserves within-year cyclic ordering, but wraps December
to January and does not preserve dependence across actual year boundaries.
Six years provide limited evidence about longer climate cycles. Geographic
confounding and elevation-dependent source downscaling remain limitations of the
separate elevation tests. The results do not assign one monsoon regime to every
country.
