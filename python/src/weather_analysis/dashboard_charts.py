"""Descriptive dashboard summaries of complete daily observations."""
import json

import numpy as np
import pandas as pd

METRICS = ("wind_speed_10m", "relative_humidity_2m", "surface_pressure")
COLORS = ("#28747a", "#407eb5", "#9270aa", "#be8135", "#bc5365")


def summarize(frame, locations, metrics, daily_values=False):
    # Four equal-width elevation classes; add a fifth for regions reaching 3000 m.
    elevations = locations.elevation_m.dropna()
    low, high = (float(elevations.min()), float(elevations.max())) if len(elevations) else (0, 1)
    count = 5 if high >= 3000 else 4
    edges = np.linspace(low, high if high > low else low + count, count + 1)
    locations = locations.copy()
    locations["band"] = np.clip(np.searchsorted(edges, locations.elevation_m, side="right") - 1, 0, count - 1)
    bands = [{"id": i, "label": f"{edges[i]:.0f}–{edges[i+1]:.0f} m", "color": COLORS[i]} for i in range(count)]
    output = {}
    for metric in metrics:
        grouped = frame.groupby(["location_id", "date"])[metric]
        values = grouped.sum(min_count=1) if metric == "precipitation" else grouped.mean()
        daily = (values if daily_values else values.where(grouped.count() == 24)).dropna().rename("value").reset_index()
        daily = daily.merge(locations[["location_id", "name", "elevation_m", "band"]], on="location_id")
        vals = daily.value
        stats = None if daily.empty else {
            "count": len(vals), "mean": vals.mean(), "min": vals.min(), "max": vals.max(),
            "median": vals.median(), "variance": vals.var(ddof=0),
        }
        timelines = {}
        for period, freq in (("daily", "D"), ("weekly", "W-SUN"), ("monthly", "M")):
            daily["bucket"] = pd.to_datetime(daily.date).dt.to_period(freq).dt.start_time.dt.strftime("%Y-%m-%d")
            groups = daily.groupby(["band", "bucket"]).value
            timeline = groups.agg(mean="mean", count="count").reset_index()
            timeline["variance"] = groups.var(ddof=0).values
            timelines[period] = timeline.to_dict("records")
        scatter = daily.groupby(["location_id", "name", "elevation_m", "band"]).value.agg(mean="mean", count="count").reset_index().to_dict("records")
        histogram = []
        if len(vals):
            counts, boundaries = np.histogram(vals, bins=16)
            histogram = [{"low": boundaries[i], "high": boundaries[i+1], "count": int(n)} for i, n in enumerate(counts)]
        output[metric] = {"stats": stats, "timeline": timelines, "scatter": scatter, "histogram": histogram}
    return json.loads(json.dumps({"bands": bands, "metrics": output}, default=lambda v: v.item(), allow_nan=False))
