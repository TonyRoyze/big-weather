from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[2] / "dashboard/app.py"


def test_dashboard_pages_and_empty_filter(published, monkeypatch):
    _, root = published
    monkeypatch.setenv("WEATHER_PLATFORM_ROOT", str(root))
    app = AppTest.from_file(str(APP)).run(timeout=30)
    assert not app.exception
    assert app.metric[0].value == "2"
    app.sidebar.radio[0].set_value("Exploration").run()
    assert not app.exception
    app.multiselect[0].set_value([]).run()
    assert "No observations" in app.info[0].value
    for page in ["Evidence", "Custom analysis", "Job history", "Pipeline"]:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception


def test_missing_dataset_has_setup_instructions(tmp_path, monkeypatch):
    monkeypatch.setenv("WEATHER_PLATFORM_ROOT", str(tmp_path / "missing"))
    monkeypatch.setenv("WEATHER_REGIONAL_ROOT", str(tmp_path / "regional"))
    app = AppTest.from_file(str(APP)).run()
    assert not app.exception
    assert "No published dataset" in app.info[0].value


def test_on_demand_charts_only_load_after_request(published, monkeypatch):
    from weather_analysis.storage import DatasetStore

    monkeypatch.setenv("WEATHER_PLATFORM_ROOT", str(published[1]))
    reads = []
    original = DatasetStore.read

    def tracked(self, name, **kwargs):
        reads.append(name)
        return original(self, name, **kwargs)

    monkeypatch.setattr(DatasetStore, "read", tracked)
    app = AppTest.from_file(str(APP)).run(timeout=30)
    app.sidebar.radio[0].set_value("On-demand charts").run()
    assert not app.exception
    assert "daily_metrics" not in reads
    app.button[0].click().run()
    assert not app.exception
    assert "daily_metrics" in reads
    assert len(app.get("plotly_chart")) == 2
    reads.clear()
    app.button[0].click().run()
    assert not app.exception
    assert "daily_metrics" not in reads
    app.multiselect[0].set_value([])
    app.button[0].click().run()
    assert not app.exception
    assert "Choose at least one" in app.warning[0].value


def test_raw_preview_without_published_release(raw_preview, tmp_path, monkeypatch):
    monkeypatch.setenv('WEATHER_PLATFORM_ROOT', str(tmp_path / 'missing'))
    monkeypatch.setenv('WEATHER_REGIONAL_ROOT', str(raw_preview))
    app = AppTest.from_file(str(APP)).run(timeout=30)
    assert not app.exception
    assert app.metric[0].value == '1 / 600'
    assert 'Unpublished preview' in app.warning[0].value
    assert len(app.get('plotly_chart')) == 0
    next(b for b in app.button if b.label == 'Load preview').click().run()
    assert not app.exception
    assert len(app.get('plotly_chart')) == 1
    app.multiselect[0].set_value([]).run()
    assert not app.exception
    assert any('Choose a location' in i.value for i in app.info)
