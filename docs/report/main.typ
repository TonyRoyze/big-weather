#import "@preview/classy-tudelft-thesis:0.1.0": *

#show: base.with(
  // These first two parameters are only used for the pdf metadata.
  title: "Geospatial Weather and Elevation Analysis",
  name: "Big Weather project team",
  // What is displayed at the top-right of the page. The top-left of the page displays the current chapter.
  rightheader: "Big Weather",
  // Main and math fonts
  main-font: "Stix Two Text",
  math-font: "Stix Two Math",
  // Colors used for internal references (figures, equations, sections) and citations
  ref-color: olive,
  cite-color: blue,
  // Language, used for correct hyphenation patterns and default word for outline title, etc.
  language: "en",
  region: "GB",
)

#maketitlepage(
  title: [Geospatial Weather and Elevation Analysis],
  name: [Group E],
  members: (
    [Vidura Gunawardana - s16655],
    [Thishakya De Silva - s16794],
    [Kaumindi Herath - s16943],
  ),
)
#outline()
#show: switch-page-numbering
#set par(
  justify: true,
  first-line-indent: 0pt,
  spacing: 2em,
)
#show link: underline
#show link: set text(fill: blue)
#set figure.caption(position: bottom)
#include "content.typ"
