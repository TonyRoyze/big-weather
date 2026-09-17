from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from weather_analysis.ask import Plan, answer, sql_for, validate_plan
from weather_analysis.explorer import create_app


def data():
    return SimpleNamespace(
        features={
            "temperature_2m": ("Temperature", "°C", "mean"),
            "precipitation": ("Rain", "mm/day", "sum"),
        },
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
        locations=pd.DataFrame({"location_id": ["a"]}),
        metadata=dict,
        fingerprint="test",
        store=None,
    )


def plan(**kwargs):
    return Plan(
        explanation="Latest week",
        clarification=None,
        metric="temperature_2m",
        start=date(2024, 1, 1),
        end=date(2024, 1, 7),
        locations=["a"],
        group_by="date",
        operation="mean",
        chart="line",
    ).model_copy(update=kwargs)


@pytest.mark.parametrize(
    "updates",
    [
        {"metric": "temperature_2m); DROP TABLE weather; --"},
        {"locations": ["a' OR 1=1 --"]},
        {"locations": []},
        {"start": date(2023, 1, 1)},
        {"operation": "sum"},
        {"chart": "scatter"},
    ],
)
def test_reject_invalid_plan(updates):
    with pytest.raises(ValueError):
        validate_plan(plan(**updates), data())


def test_sql_uses_complete_days_and_exclusive_end():
    sql = sql_for(plan(), data())
    assert "COUNT(`temperature_2m`) = 24" in sql
    assert "timestamp < TIMESTAMP '2024-01-08'" in sql
    assert "AVG(value)" in sql


def test_clarification_never_starts_spark(monkeypatch):
    monkeypatch.setattr(
        "weather_analysis.ask.make_plan", lambda *_: plan(clarification="Which country?")
    )
    monkeypatch.setattr("weather_analysis.ask.run_spark", lambda *_: pytest.fail("Spark started"))
    assert answer("Compare weather", data(), ".") == {"clarification": "Which country?"}


def test_empty_results_do_not_call_summary(monkeypatch):
    monkeypatch.setattr("weather_analysis.ask.make_plan", lambda *_: plan())
    monkeypatch.setattr(
        "weather_analysis.ask.run_spark", lambda *_: {"records": [], "sql": "", "complete_days": 0}
    )
    monkeypatch.setattr("weather_analysis.ask.client", lambda: pytest.fail("Summary called"))
    assert "No complete" in answer("Show temperature", data(), ".")["summary"]


def test_api_validation_and_configuration(monkeypatch):
    monkeypatch.setenv("WEATHER_AI_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = TestClient(create_app())
    assert client.get("/api/ask/status").json()["configured"] is False
    assert client.post("/api/ask", json={"question": "x"}).status_code == 422
    assert (
        client.post("/api/ask", json={"question": "hello", "sql": "DROP TABLE x"}).status_code
        == 422
    )


@pytest.mark.integration
def test_real_spark_complete_days(tmp_path):
    import json

    from weather_analysis.ask import run_spark
    from weather_analysis.explorer import ExplorerData

    loc = tmp_path / "raw/locations"
    loc.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "location_id": "a",
                "name": "Coast",
                "country": "LK",
                "region": "Asia",
                "latitude": 7.0,
                "longitude": 80.0,
                "elevation_m": 10.0,
            }
        ]
    ).to_parquet(loc / "part.parquet")
    directory = tmp_path / "raw/weather/location_id=a/year=2024"
    directory.mkdir(parents=True)
    pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=47, freq="h", tz="UTC"),
            "temperature_2m": [20.0] * 24 + [30.0] * 23,
        }
    ).to_parquet(directory / "weather.parquet", index=False, coerce_timestamps="us")
    (directory / "_source.json").write_text(
        json.dumps({"request": {"location_id": "a", "start": "2024-01-01", "end": "2024-01-02"}})
    )
    result = run_spark(plan(end=date(2024, 1, 2)), ExplorerData(".", tmp_path), tmp_path)
    assert result["complete_days"] == 1
    assert result["records"][0]["value"] == 20
    assert result["records"][1].get("value") is None


def test_codex_plan_uses_schema_without_openai_key(monkeypatch):
    from weather_analysis.ask import make_plan
    monkeypatch.setenv("WEATHER_AI_PROVIDER", "codex")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    calls = []
    def generate(instructions, payload, schema):
        calls.append(schema)
        return plan().model_dump_json()
    monkeypatch.setattr("weather_analysis.codex_demo.generate", generate)
    assert make_plan("Show temperature", {}) == plan()
    assert calls[0]["additionalProperties"] is False


def test_codex_invalid_output_is_rejected(monkeypatch):
    from weather_analysis.ask import make_plan
    monkeypatch.setenv("WEATHER_AI_PROVIDER", "codex")
    monkeypatch.setattr("weather_analysis.codex_demo.generate", lambda *_: '{"sql":"DELETE FROM weather"}')
    with pytest.raises(ValueError):
        make_plan("Show temperature", {})
