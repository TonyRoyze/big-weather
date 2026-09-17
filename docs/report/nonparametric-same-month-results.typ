=== Relationships Between Year and Locations on Weather Variables

The same-month comparisons cover six locations, seven variables, and twelve
calendar months: 504 comparisons, each testing both ranks and within-month spread
across 2020–2025. There are 43 detected rank differences and 8 detected spread
differences. These counts refer to location–variable–month combinations, not
individual pairs of years. All six locations have detected differences.

// The tables and graphs use the primary seven-day-block analysis with 9,999
// permutations. Holm correction covers the 24 tests within each location–variable
// family; it does not cover the whole exploratory scan. A dash means no detected
// difference after correction, not proof of equality. Daily means describe the
// weather features except precipitation, which uses daily totals. February 29 is
// excluded to match calendar-day positions between years.

#figure(
  table(columns: (1.7fr, 1fr, 1fr, 1fr, 1fr, 1fr, 1fr), inset: 4pt,
    table.header([*Feature*], [*Batticaloa*], [*Colombo*], [*Galle*], [*Jaffna*], [*Matara*], [*Trincomalee*]),
    [Temperature], [3 / 0], [6 / 0], [5 / 0], [5 / 0], [4 / 0], [3 / 0],
    [Daily precipitation], [0 / 0], [0 / 1], [0 / 1], [0 / 1], [1 / 1], [0 / 0],
    [Wind speed at 10 m], [1 / 0], [1 / 0], [1 / 0], [0 / 1], [2 / 0], [1 / 0],
    [Relative humidity], [0 / 1], [3 / 1], [3 / 0], [1 / 0], [3 / 0], [0 / 0],
    // [Surface pressure], [0 / 0], [0 / 0], [0 / 0], [0 / 0], [0 / 0], [0 / 0],
    [Cloud cover], [0 / 0], [0 / 0], [0 / 0], [0 / 0], [0 / 0], [0 / 1],
    // [Shortwave radiation], [0 / 0], [0 / 0], [0 / 0], [0 / 0], [0 / 0], [0 / 0],
  ),
  caption: [Number of months with detected rank / spread differences. Ranks are tested with Kruskal–Wallis and spread with Fligner–Killeen scores.],
)

Every detected combination is visualised below. Boxplots show medians and quartiles, triangles show means, whiskers use 1.5 IQR, and dots show individual daily values.

=== Batticaloa

// #table(columns: (1.7fr, 2fr, 1.3fr), inset: 4pt,
//  table.header([*Variable*], [*Rank difference: months*], [*Spread difference: months*]),
//  [Temperature], [Jan, Feb, Dec], [—],
//  [Daily precipitation], [—], [—],
//  [Wind speed at 10 m], [Apr], [—],
//  [Relative humidity], [—], [Nov],
//  [Surface pressure], [—], [—],
//  [Cloud cover], [—], [—],
//  [Shortwave radiation], [—], [—],
// )

#figure(image("img/nonparam_same_month_lk_batticaloa_1.png", width: 100%), caption: [Batticaloa: detected differences across 2020–2025.])

=== Colombo

// #table(columns: (1.7fr, 2fr, 1.3fr), inset: 4pt,
//  table.header([*Variable*], [*Rank difference: months*], [*Spread difference: months*]),
//  [Temperature], [Jan, Feb, Mar, Apr, Sep, Dec], [—],
//  [Daily precipitation], [—], [Jan],
//  [Wind speed at 10 m], [Mar], [—],
//  [Relative humidity], [Mar, Apr, Sep], [Nov],
//  [Surface pressure], [—], [—],
//  [Cloud cover], [—], [—],
//  [Shortwave radiation], [—], [—],
// )

#figure(image("img/nonparam_same_month_lk_colombo_1.png", width: 100%), caption: [Colombo: detected differences across 2020–2025.])

#figure(image("img/nonparam_same_month_lk_colombo_2.png", width: 100%), caption: [Colombo: detected differences across 2020–2025.])


#pagebreak()
=== Galle

// #table(columns: (1.7fr, 2fr, 1.3fr), inset: 4pt,
//  table.header([*Variable*], [*Rank difference: months*], [*Spread difference: months*]),
//  [Temperature], [Jan, Feb, Mar, Apr, Dec], [—],
//  [Daily precipitation], [—], [Jan],
//  [Wind speed at 10 m], [Oct], [—],
//  [Relative humidity], [Jan, Feb, Mar], [—],
//  [Surface pressure], [—], [—],
//  [Cloud cover], [—], [—],
//  [Shortwave radiation], [—], [—],
// )

#figure(image("img/nonparam_same_month_lk_galle_1.png", width: 100%), caption: [Galle: detected differences across 2020–2025.])

#figure(image("img/nonparam_same_month_lk_galle_2.png", width: 100%), caption: [Galle: detected differences across 2020–2025.])


#pagebreak()
=== Jaffna

// #table(columns: (1.7fr, 2fr, 1.3fr), inset: 4pt,
//  table.header([*Variable*], [*Rank difference: months*], [*Spread difference: months*]),
//  [Temperature], [Jan, Feb, Apr, Sep, Dec], [—],
//  [Daily precipitation], [—], [Aug],
//  [Wind speed at 10 m], [—], [Apr],
//  [Relative humidity], [Jun], [—],
//  [Surface pressure], [—], [—],
//  [Cloud cover], [—], [—],
//  [Shortwave radiation], [—], [—],
// )

#figure(image("img/nonparam_same_month_lk_jaffna_1.png", width: 100%), caption: [Jaffna: detected differences across 2020–2025.])


#figure(image("img/nonparam_same_month_lk_jaffna_2.png", width: 100%), caption: [Jaffna: detected differences across 2020–2025.])


#pagebreak()
=== Matara

// #table(columns: (1.7fr, 2fr, 1.3fr), inset: 4pt,
//  table.header([*Variable*], [*Rank difference: months*], [*Spread difference: months*]),
//  [Temperature], [Jan, Feb, Mar, Dec], [—],
//  [Daily precipitation], [Jan], [Jan],
//  [Wind speed at 10 m], [Feb, Oct], [—],
//  [Relative humidity], [Jan, Feb, Mar], [—],
//  [Surface pressure], [—], [—],
//  [Cloud cover], [—], [—],
//  [Shortwave radiation], [—], [—],
// )

#figure(image("img/nonparam_same_month_lk_matara_1.png", width: 100%), caption: [Matara: detected differences across 2020–2025.])


#figure(image("img/nonparam_same_month_lk_matara_2.png", width: 100%), caption: [Matara: detected differences across 2020–2025.])


#pagebreak()
=== Trincomalee

// #table(columns: (1.7fr, 2fr, 1.3fr), inset: 4pt,
//  table.header([*Variable*], [*Rank difference: months*], [*Spread difference: months*]),
//  [Temperature], [Jan, Feb, Mar], [—],
//  [Daily precipitation], [—], [—],
//  [Wind speed at 10 m], [Apr], [—],
//  [Relative humidity], [—], [—],
//  [Surface pressure], [—], [—],
//  [Cloud cover], [—], [Aug],
//  [Shortwave radiation], [—], [—],
// )

#figure(image("img/nonparam_same_month_lk_trincomalee_1.png", width: 100%), caption: [Trincomalee: detected differences across 2020–2025.])

