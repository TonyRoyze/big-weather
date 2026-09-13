# Presentation working outline

Status: slide content plan; teammates should create and rehearse the final deck.
Use 8–10 slides, adapting duration to the assessment instructions.

| Slide | Message | Evidence / visual | Owner action |
| --- | --- | --- | --- |
| 1. Research question | How do weather patterns vary with elevation and geography? | Selected-location map | State team scope |
| 2. Data | 36 locations; 2019–2024 ERA5 hourly observations | Coverage/quality counts from manifest | Explain units and attribution |
| 3. Architecture | Reproducible extraction → Spark → published results → dashboard | Architecture diagram | Distinguish local threads from cluster nodes |
| 4. Quality and methods | Comparisons depend on coverage and weighting | Validation counts + one aggregation example | Explain rainfall denominator and seasons |
| 5. Temperature finding | Insert one quantified, qualified finding | Elevation scatter and/or seasonal signed slopes | Cite version, sample size, confounding |
| 6. Geographic/seasonal finding | Insert second team finding | Ranked locations or seasonal heatmap | Include units and dates |
| 7. Time/change finding | Describe observed annual variation | Annual anomaly plot | Explain study-mean baseline; avoid climate-trend claims |
| 8. Engineering evidence | Measured processing and cache behavior | Repeated benchmark medians; miss/hit times | Include hardware and timing boundaries |
| 9. Live demonstration | A reproducible result can be explored and reused | Dashboard and saved job provenance | Rehearse sequence below |
| 10. Conclusions | Supported insights, limitations and next steps | Two findings + one uncertainty | Add sources and team contributions |

## Demonstration script

1. Start `make dashboard` in advance with the agreed published dataset.
2. Show coverage and the map; explain where each source enters the pipeline.
3. Filter the exploration page to the locations and dates behind a finding.
4. Submit a named custom analysis and show its new result and provenance.
5. Submit the same calculation again and show the cache hit and matching values.
6. Download result/provenance; show where the team used it in the report.

For a guaranteed first miss, choose an unused valid filter combination or use the
CLI's `--no-cache` option first; the UI deliberately reuses cached calculations.
Keep a completed job and screenshots available if the live demonstration fails.
Do not rely on network ingestion during the presentation. Spark UI screenshots
must be captured while a processing job is actually running.

## Figure checklist

Every chart needs a readable title, units, legend, date range, population/denominator,
dataset version and source attribution. Use identical colors for elevation bands
across charts. Use exported figures or screenshots tested at presentation size.
Do not replace missing results with invented numbers or imply model causality.
