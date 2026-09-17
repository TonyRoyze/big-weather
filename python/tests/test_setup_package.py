"""Installer payload integrity and secret-exclusion tests; no Windows required."""

import importlib.util
from pathlib import Path
import tarfile

import pytest

spec = importlib.util.spec_from_file_location(
    "build_windows_setup", Path(__file__).resolve().parents[2] / "scripts/build_windows_setup.py"
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@pytest.fixture
def package_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    for name in [
        "README.md",
        "Makefile",
        "pyproject.toml",
        ".gitignore",
        ".env.example",
        "scripts/check_setup.py",
        "scripts/team-launch.sh",
        "python/src/example.py",
        "docs/test.md",
        "config/locations_regional_100.csv",
    ]:
        file = root / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("example\n")
    for name in [
        ".env",
        ".git/config",
        ".venv/secret.txt",
        "data/cache/private.json",
        "python/src/__pycache__/cached.pyc",
        "dist/old.exe",
    ]:
        file = root / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("SECRET\n")
    return root


def test_payload_is_reproducible_and_excludes_secrets(package_root, published, tmp_path):
    _, store = published
    first, second = tmp_path / "first.tar.gz", tmp_path / "second.tar.gz"
    metadata = builder.write_payload(package_root, store, first)
    builder.write_payload(package_root, store, second)
    assert first.read_bytes() == second.read_bytes()
    assert metadata["dataset_version"] == "test-v1"
    with tarfile.open(first) as archive:
        names = archive.getnames()
        assert ".env.example" in names
        assert ".env" not in names
        assert "data/platform/active.json" in names
        assert "SETUP-MANIFEST.json" in names
        assert all(
            not name.startswith((".git/", ".venv/", "data/cache/", "dist/")) for name in names
        )
        assert all(
            b"SECRET" not in archive.extractfile(item).read() for item in archive.getmembers()
        )


def test_corrupt_release_is_rejected(package_root, published, tmp_path):
    _, store = published
    file = next((store / "releases/test-v1/enriched_weather").glob("*.parquet"))
    with file.open("ab") as handle:
        handle.write(b"corrupt")
    with pytest.raises(ValueError, match="checksum mismatch"):
        builder.write_payload(package_root, store, tmp_path / "payload.tar.gz")


def test_setup_without_published_data(package_root, tmp_path):
    output = tmp_path / "setup.tar.gz"
    metadata = builder.write_payload(package_root, tmp_path / "missing", output)
    assert metadata["dataset_version"] is None
    with tarfile.open(output) as archive:
        assert "config/locations_regional_100.csv" in archive.getnames()
        assert not any(n.startswith("data/platform/") for n in archive.getnames())
