import json

import pandas as pd
import pytest

from weather_analysis import AnalysisService, DatasetStore, publish
from weather_analysis.evidence import export_evidence
from weather_analysis.spec import cache_key, validate_spec

SPEC = {
    "name": "Temperature",
    "source": "enriched_weather",
    "filters": {},
    "group_by": ["location_id"],
    "aggregations": {"temperature_2m": ["avg", "count"]},
}


def test_publication_is_immutable_and_failure_preserves_active(published):
    source, root = published
    store = DatasetStore(root)
    assert store.manifest["tables"]["enriched_weather"]["rows"] == 4
    with pytest.raises(FileExistsError):
        publish(source, root, "test-v1")
    hourly = source / "processed/enriched_weather/part.parquet"
    data = pd.read_parquet(hourly)
    pd.concat([data, data.iloc[:1]]).to_parquet(hourly)
    with pytest.raises(ValueError, match="unique"):
        publish(source, root, "bad-v2")
    assert DatasetStore(root).version == "test-v1"
    assert len(store.read("enriched_weather")) == 4
    assert not list((root / "releases").glob(".staging-*"))
    with pytest.raises(ValueError):
        store.table_path("../../secrets")


@pytest.mark.parametrize(
    "changes",
    [
        {"source": "../../file"},
        {"group_by": ["unknown"]},
        {"aggregations": {"temperature_2m": ["eval"]}},
        {"filters": {"season": ["DJF"]}},
        {"filters": {"year": ["2024"]}},
        {"filters": {"location_id": []}},
        {"filters": {"date": ["2024-02-01", "2024-01-01"]}},
    ],
)
def test_invalid_jobs_rejected(changes):
    with pytest.raises(ValueError):
        validate_spec({**SPEC, **changes})


def test_cache_normalizes_order_and_tracks_versions():
    first = {**SPEC, "group_by": ["season", "location_id"], "filters": {"year": [2024, 2023]}}
    second = {
        **first,
        "name": "Renamed",
        "group_by": ["location_id", "season"],
        "filters": {"year": [2023, 2024, 2024]},
    }
    assert cache_key(first, "v1", "abc") == cache_key(second, "v1", "abc")
    assert cache_key(first, "v2", "abc") != cache_key(first, "v1", "abc")
    assert cache_key(first, "v1", "xyz") != cache_key(first, "v1", "abc")


@pytest.mark.integration
def test_spark_result_cache_filter_and_failure(published):
    pytest.importorskip("pyspark")
    _, root = published
    service = AnalysisService(root)
    first = service.submit_job(SPEC)
    meta = service.get_job_status(first)
    assert meta["status"] == "completed", meta
    assert meta["input_rows"] == 4 and meta["output_rows"] == 2
    result = service.load_job_result(first)
    assert result.temperature_2m_avg.tolist() == [21.0, 11.0]
    assert result.temperature_2m_count.tolist() == [2, 2]
    repeated = service.submit_job({**SPEC, "name": "Same calculation"})
    assert service.get_job_status(repeated)["cache_hit"] is True
    assert service.get_job_status(repeated)["result_job_id"] == first
    pd.testing.assert_frame_equal(result, service.load_job_result(repeated))
    filtered = service.submit_job(
        {**SPEC, "filters": {"location_id": ["a"], "date": ["2024-01-02", "2024-01-02"]}}
    )
    assert service.load_job_result(filtered).temperature_2m_avg.tolist() == [22.0]
    empty = service.submit_job({**SPEC, "filters": {"location_id": ["missing"]}})
    assert service.load_job_result(empty).empty
    failure_service = AnalysisService(root, ttl_seconds=0, timeout_seconds=0.001)
    failed = failure_service.submit_job(SPEC)
    assert failure_service.get_job_status(failed)["status"] == "failed"
    with pytest.raises(ValueError, match="failed"):
        failure_service.load_job_result(failed)
    assert len(service.list_jobs()) == 5


def test_evidence_has_known_values_and_provenance(published, tmp_path):
    _, root = published
    output = tmp_path / "evidence"
    report = export_evidence(DatasetStore(root), output)
    frame = pd.read_parquet(output / "elevation_comparison.parquet").set_index("elevation_band")
    assert frame.loc["lowland", "mean_location_temperature_c"] == 21.0
    assert frame.loc["highland", "mean_location_daily_precipitation_mm"] == 1.5
    assert json.loads((output / "metadata.json").read_text())["dataset"]["version"] == "test-v1"
    assert "not independent" in report.read_text()
