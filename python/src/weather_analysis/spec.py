"""Whitelist and canonicalize structured jobs; never accept SQL or Python code."""

from datetime import date
import hashlib
import json

TRANSFORM_VERSION = "custom-v1"
GROUPS = {"location_id", "elevation_band", "season", "year", "region"}
METRICS = {"temperature_2m", "precipitation", "wind_speed_10m", "relative_humidity_2m"}
OPERATIONS = {"count", "sum", "avg", "min", "max"}
SEASONS = {"winter", "spring", "summer", "autumn"}
BANDS = {"lowland", "midland", "highland", "alpine"}


def validate_spec(spec: dict) -> dict:
    if not isinstance(spec, dict) or set(spec) - {
        "name",
        "source",
        "filters",
        "group_by",
        "aggregations",
    }:
        raise ValueError("Unknown job fields")
    name = spec.get("name", "Untitled analysis")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
        raise ValueError("Name must contain 1–120 characters")
    if spec.get("source") != "enriched_weather":
        raise ValueError("Only enriched_weather is supported")
    groups = spec.get("group_by")
    if (
        not isinstance(groups, list)
        or not groups
        or not all(isinstance(x, str) and x in GROUPS for x in groups)
    ):
        raise ValueError("Choose one or more approved grouping columns")
    aggregations = spec.get("aggregations")
    if not isinstance(aggregations, dict) or not aggregations:
        raise ValueError("At least one aggregation is required")
    normalized = {}
    for metric, operations in aggregations.items():
        if metric not in METRICS or not isinstance(operations, list) or not operations:
            raise ValueError("Unknown metric or empty operations")
        if not all(isinstance(op, str) and op in OPERATIONS for op in operations):
            raise ValueError("Unknown aggregation function")
        normalized[metric] = sorted(set(operations))
    filters = spec.get("filters", {})
    if not isinstance(filters, dict) or set(filters) - (GROUPS | {"date"}):
        raise ValueError("Unknown filter fields")
    clean_filters = {}
    for field, values in filters.items():
        if not isinstance(values, list) or not values:
            raise ValueError("Filters must be nonempty lists; omit a field to select all")
        if field == "date":
            if len(values) != 2 or not all(isinstance(v, str) for v in values):
                raise ValueError("Date filter must be [start, end] in ISO format")
            bounds = [date.fromisoformat(v).isoformat() for v in values]
            if bounds[0] > bounds[1]:
                raise ValueError("Start date must not exceed end date")
            clean_filters[field] = bounds
        elif field == "year":
            if not all(type(v) is int and 1900 <= v <= 2200 for v in values):
                raise ValueError("Year is a list of individual integer years, not a range")
            clean_filters[field] = sorted(set(values))
        else:
            if not all(isinstance(v, str) and 0 < len(v) <= 120 for v in values):
                raise ValueError("Filter values must be nonempty strings")
            allowed = SEASONS if field == "season" else BANDS if field == "elevation_band" else None
            if allowed and not set(values).issubset(allowed):
                raise ValueError(f"Unsupported {field} value")
            clean_filters[field] = sorted(set(values))
    return {
        "name": name.strip(),
        "source": "enriched_weather",
        "filters": clean_filters,
        "group_by": sorted(set(groups)),
        "aggregations": dict(sorted(normalized.items())),
    }


def cache_key(spec: dict, version: str, fingerprint: str) -> str:
    query = {k: v for k, v in validate_spec(spec).items() if k != "name"}
    payload = [query, version, fingerprint, TRANSFORM_VERSION]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
