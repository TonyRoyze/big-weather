from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import requests
import requests_cache
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HOURLY_VARIABLES = (
    "temperature_2m",
    "precipitation",
    "wind_speed_10m",
    "relative_humidity_2m",
)


class OpenMeteoError(RuntimeError):
    pass


class OpenMeteoClient:
    def __init__(self, cache_path: Path, delay_seconds: float = 0.12) -> None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.session = requests_cache.CachedSession(
            str(cache_path), backend="sqlite", expire_after=None, stale_if_error=True
        )
        self.session.headers.update({"User-Agent": "DS4004-big-weather/0.1 (academic project)"})
        self.delay_seconds = delay_seconds

    @retry(
        retry=retry_if_exception_type((requests.RequestException, OpenMeteoError)),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        response = self.session.get(url, params=params, timeout=60)
        if not getattr(response, "from_cache", False):
            time.sleep(self.delay_seconds)
        if response.status_code == 429 or response.status_code >= 500:
            raise OpenMeteoError(f"temporary API failure ({response.status_code})")
        response.raise_for_status()
        payload = response.json()
        if payload.get("error"):
            raise OpenMeteoError(str(payload.get("reason", "unknown API error")))
        return payload

    def geocode(self, name: str, country_code: str) -> dict[str, Any]:
        payload = self._get(
            GEOCODING_URL,
            {"name": name, "count": 10, "language": "en", "format": "json"},
        )
        matches = payload.get("results", [])
        match = next(
            (item for item in matches if item.get("country_code", "").upper() == country_code),
            None,
        )
        if match is None:
            raise OpenMeteoError(f"no geocoding result for {name!r} in {country_code}")
        return match

    def elevation(self, latitude: float, longitude: float) -> float:
        payload = self._get(ELEVATION_URL, {"latitude": latitude, "longitude": longitude})
        values = payload.get("elevation", [])
        if not values or values[0] is None:
            raise OpenMeteoError(f"no elevation returned for {latitude}, {longitude}")
        return float(values[0])

    def historical_weather(
        self, latitude: float, longitude: float, start_date: str, end_date: str
    ) -> dict[str, Any]:
        return self._get(
            ARCHIVE_URL,
            {
                "latitude": latitude,
                "longitude": longitude,
                "start_date": start_date,
                "end_date": end_date,
                "hourly": ",".join(HOURLY_VARIABLES),
                "timezone": "UTC",
                "wind_speed_unit": "ms",
                "models": "era5",
            },
        )
