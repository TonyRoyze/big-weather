== Elevation Differences Within Months in 2026

The same 100 locations are compared within each of January–August 2026 using
newly committed historical downloads. All eight months are complete, including
May. This updated coverage contains 583,200 hourly observations and 800 complete
location-month summaries. Source hashes and per-month hourly counts are verified
in a separate snapshot, extending the earlier May–August comparison without
changing the frozen historical year-by-year analysis.

Locations are divided into three fixed elevation bands: below 500 m (48 sites),
500 to below 1,500 m (26 sites), and at least 1,500 m (26 sites). These thresholds
are applied consistently to every feature and month. Kruskal–Wallis compares
rank distributions across the three bands separately in each month. The plots
show variation between sites within each elevation band, not within-month daily
variation. That differs from the historical year-by-year comparisons.

#figure(table(columns: (1.7fr, 1fr, 1fr, 1fr, 1fr), inset: 5pt,
 table.header([*Feature*], [*Jan*], [*Feb*], [*Mar*], [*Apr*]),
 [Temperature], [0.0056], [0.0056], [0.0056], [0.0056],
 [Daily precipitation], [0.2760], [0.0092], [0.0056], [0.0056],
 [Wind speed at 10 m], [0.0056], [0.0056], [0.0056], [0.0056],
 [Relative humidity], [1.0000], [1.0000], [1.0000], [0.4238],
 [Surface pressure], [0.0056], [0.0056], [0.0056], [0.0056],
 [Cloud cover], [1.0000], [0.7344], [0.0056], [0.0075],
 [Shortwave radiation], [1.0000], [0.5360], [0.5093], [1.0000],
), caption: [Elevation-band differences. Values below 0.05 indicate detected differences under country-restricted permutations.])

#figure(table(columns: (1.7fr, 1fr, 1fr, 1fr, 1fr), inset: 5pt,
 table.header([*Feature*], [*May*], [*Jun*], [*Jul*], [*Aug*]),
 [Temperature], [0.0056], [0.0056], [0.0056], [0.0056],
 [Daily precipitation], [0.0210], [0.0210], [0.1003], [0.0576],
 [Wind speed at 10 m], [0.0056], [0.0056], [0.0056], [0.0056],
 [Relative humidity], [0.0266], [0.0056], [0.0056], [0.0056],
 [Surface pressure], [0.0056], [0.0056], [0.0056], [0.0056],
 [Cloud cover], [1.0000], [0.1264], [0.0154], [0.0056],
 [Shortwave radiation], [1.0000], [0.4238], [0.3640], [0.0075],
), caption: [Elevation-band differences. Values below 0.05 indicate detected differences under country-restricted permutations.])

// Detected months after correction are listed below. A dash means no detected difference, not equivalence.

// #table(columns: (1fr, 2fr), inset: 5pt, table.header([*Feature*], [*Months with detected differences*]),
//  [Temperature], [Jan, Feb, Mar, Apr, May, Jun, Jul, Aug],
//  [Daily precipitation], [Feb, Mar, Apr, May, Jun],
//  [Wind speed at 10 m], [Jan, Feb, Mar, Apr, May, Jun, Jul, Aug],
//  [Relative humidity], [May, Jun, Jul, Aug],
//  [Surface pressure], [Jan, Feb, Mar, Apr, May, Jun, Jul, Aug],
//  [Cloud cover], [Mar, Apr, Jul, Aug],
//  [Shortwave radiation], [Aug],
// )

// Kruskal–Wallis compares ranks; it is not exclusively a median test when
// shapes differ. Boxplots retain the spread and overlap between locations. Adding
// months changes the multiple-testing family, so corrected p-values for the earlier
// months must also be updated.

// A detected difference in one month and no detected difference in another does
// not establish a significant month-by-elevation interaction. These are monthly
// associations, not recurring seasonality or causal effects. Elevation-dependent
// source downscaling remains particularly relevant for temperature and pressure.

#pagebreak()
=== Temperature Across Elevation Bands

#figure(
 image("img/nonparam_elevation_temperature_2m.png", width: 100%),
 caption: [Temperature by elevation band in January–August 2026. Dots represent individual
 location summaries; boxes show medians and interquartile ranges, with 1.5-IQR
 whiskers.],
)

#pagebreak()
=== Daily precipitation Across Elevation Bands

#figure(
 image("img/nonparam_elevation_precipitation.png", width: 100%),
 caption: [Daily precipitation by elevation band in January–August 2026. Dots represent individual
 location summaries; boxes show medians and interquartile ranges, with 1.5-IQR
 whiskers.],
)

#pagebreak()
=== Wind speed at 10 m Across Elevation Bands

#figure(
 image("img/nonparam_elevation_wind_speed_10m.png", width: 100%),
 caption: [Wind speed at 10 m by elevation band in January–August 2026. Dots represent individual
 location summaries; boxes show medians and interquartile ranges, with 1.5-IQR
 whiskers.],
)

#pagebreak()
=== Relative humidity Across Elevation Bands

#figure(
 image("img/nonparam_elevation_relative_humidity_2m.png", width: 100%),
 caption: [Relative humidity by elevation band in January–August 2026. Dots represent individual
 location summaries; boxes show medians and interquartile ranges, with 1.5-IQR
 whiskers.],
)

#pagebreak()
=== Surface pressure Across Elevation Bands

#figure(
 image("img/nonparam_elevation_surface_pressure.png", width: 100%),
 caption: [Surface pressure by elevation band in January–August 2026. Dots represent individual
 location summaries; boxes show medians and interquartile ranges, with 1.5-IQR
 whiskers.],
)

#pagebreak()
=== Cloud cover Across Elevation Bands

#figure(
 image("img/nonparam_elevation_cloud_cover.png", width: 100%),
 caption: [Cloud cover by elevation band in January–August 2026. Dots represent individual
 location summaries; boxes show medians and interquartile ranges, with 1.5-IQR
 whiskers.],
)

#pagebreak()
=== Shortwave radiation Across Elevation Bands

#figure(
 image("img/nonparam_elevation_shortwave_radiation.png", width: 100%),
 caption: [Shortwave radiation by elevation band in January–August 2026. Dots represent individual
 location summaries; boxes show medians and interquartile ranges, with 1.5-IQR
 whiskers.],
)
