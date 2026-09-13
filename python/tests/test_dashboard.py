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
    for page in ["Custom analysis", "Job history", "Pipeline"]:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception


def test_missing_dataset_has_setup_instructions(tmp_path, monkeypatch):
    monkeypatch.setenv("WEATHER_PLATFORM_ROOT", str(tmp_path / "missing"))
    app = AppTest.from_file(str(APP)).run()
    assert not app.exception
    assert "No published dataset" in app.info[0].value
