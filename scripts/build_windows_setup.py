"""Build the Windows x64 setup EXE on macOS/Linux/Windows using Go's cross-compiler.

Only the build machine needs Python + Go. Teammates only need the resulting EXE.
The allowlist excludes secrets, virtual environments, raw data, caches and Git history.
"""

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "installer/windows"


def package_files(root: Path, store: Path) -> list[tuple[Path, str]]:
    manifest = json.loads((store / "active.json").read_text())
    version = manifest["version"]
    if (
        not isinstance(version, str)
        or not version
        or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
            for c in version
        )
    ):
        raise ValueError("Invalid published version")
    release = store / "releases" / version
    release_manifest = json.loads((release / "manifest.json").read_text())
    for name, expected in release_manifest["checksums"].items():
        file = release / name
        if not file.resolve().is_relative_to(release.resolve()):
            raise ValueError("Invalid release checksum path")
        with file.open("rb") as handle:
            if hashlib.file_digest(handle, "sha256").hexdigest() != expected:
                raise ValueError(f"Release checksum mismatch: {file}")
    files = [
        (root / name, name)
        for name in ["README.md", "Makefile", "pyproject.toml", ".gitignore", ".env.example"]
    ]
    for folder in ["python/src", "python/tests", "dashboard", "config"]:
        for file in sorted((root / folder).rglob("*")):
            if (
                file.is_file()
                and not file.is_symlink()
                and file.suffix in {".py", ".csv"}
                and "__pycache__" not in file.parts
            ):
                files.append((file, file.relative_to(root).as_posix()))
    for file in sorted((root / "docs").glob("*.md")):
        files.append((file, file.relative_to(root).as_posix()))
    for name in ["benchmark.py", "check_setup.py", "team-launch.sh"]:
        files.append((root / "scripts" / name, "scripts/" + name))
    for folder in [release, store / "evidence" / version]:
        if folder.exists():
            for file in sorted(folder.rglob("*")):
                if (
                    file.is_file()
                    and not file.is_symlink()
                    and file.suffix in {".parquet", ".json", ".md"}
                ):
                    files.append((file, "data/platform/" + file.relative_to(store).as_posix()))
    files.append((store / "active.json", "data/platform/active.json"))
    if any(file.is_symlink() for file, _ in files):
        raise ValueError("Payload must not contain symlinks")
    return sorted(files, key=lambda pair: pair[1])


def write_payload(root: Path, store: Path, target: Path) -> dict:
    files = package_files(root, store)
    metadata = {
        "format": 1,
        "dataset_version": json.loads((store / "active.json").read_text())["version"],
        "files": {},
    }
    # Normalize timestamps/ownership to make identical inputs produce an identical payload.
    with (
        target.open("wb") as destination,
        gzip.GzipFile(fileobj=destination, mode="wb", mtime=0, filename="") as compressed,
        tarfile.open(fileobj=compressed, mode="w|") as archive,
    ):
        for file, name in files:
            data = file.read_bytes()
            metadata["files"][name] = hashlib.sha256(data).hexdigest()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o755 if name.endswith(".sh") else 0o644
            archive.addfile(info, io.BytesIO(data))
        data = (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode()
        info = tarfile.TarInfo("SETUP-MANIFEST.json")
        info.size, info.mode = len(data), 0o644
        archive.addfile(info, io.BytesIO(data))
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, default=ROOT / "data/platform")
    parser.add_argument("--output", type=Path, default=ROOT / "dist/BigWeather-Setup.exe")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    metadata = write_payload(ROOT, args.store, INSTALLER / "payload.tar.gz")
    subprocess.run(
        ["go", "build", "-trimpath", "-ldflags=-s -w", "-o", str(args.output.resolve()), "."],
        cwd=INSTALLER,
        env={**os.environ, "GOOS": "windows", "GOARCH": "amd64", "CGO_ENABLED": "0"},
        check=True,
    )
    with args.output.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    args.output.with_suffix(".exe.sha256").write_text(f"{digest}  {args.output.name}\n")
    args.output.with_suffix(".manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"Built {args.output} ({args.output.stat().st_size / 1024**2:.1f} MiB)")
    print(f"Dataset: {metadata['dataset_version']}; SHA256: {digest}")


if __name__ == "__main__":
    main()
