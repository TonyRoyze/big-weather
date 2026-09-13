# Windows team setup

Share **`dist/BigWeather-Setup.exe`** with teammates. It is a standalone Windows
x64 bootstrapper containing the project source and the active published dataset.
Teammates do not need to install Python, Java, Git, Go or Make beforehand.

## Teammate steps

1. Double-click `BigWeather-Setup.exe` with an Internet connection.
2. If Windows asks to enable WSL, approve the administrator prompt. If setup says
   to restart, restart Windows and run the **same EXE again**. It never reboots the
   machine automatically.
3. Wait for **Setup complete**. Use **Big Weather Dashboard** on the desktop.
   It starts the server and opens the browser when the health check passes.
4. Keep the dashboard console open while using the app. **Big Weather Terminal**
   opens the prepared environment; **Big Weather Project** opens the source folder.

Supported target: up-to-date Windows 10/11, Intel/AMD 64-bit, with WSL support and
virtualization available. Allow roughly 8 GB free disk space; 8 GB RAM is a practical
minimum for local work and 16 GB gives more room for full processing. These are
planning estimates. Network download time depends on Ubuntu/package availability.

## What setup does

- Enables Windows Subsystem for Linux if needed, then installs/reuses Ubuntu 24.04.
- Installs Python 3.12 (Ubuntu's Python), Java 21, Make, Git and CA certificates
  through Ubuntu's signed package repositories.
- Creates a Linux user named `bigweather` and a project virtual environment.
- Installs the project's ingestion, PySpark, Streamlit, Plotly and development/test
  dependencies from the configured Python package index (normally PyPI).
- Extracts this build's source and published Parquet snapshot, so dashboard and
  findings work can start without rerunning historical ingestion.
- Checks imports, a real PySpark computation, Parquet writing/reading and the bundled
  location data before creating desktop shortcuts.

PySpark runs inside WSL's Linux environment; the desktop shortcuts and browser run
on Windows. This uses the same POSIX file locking/process behavior as the current
application. It does not claim native Windows Python support. Microsoft's WSL
installation and command references describe the underlying setup commands:
https://learn.microsoft.com/windows/wsl/install and
https://learn.microsoft.com/windows/wsl/basic-commands.

## Files and repeat runs

The project lives at:

```text
\\wsl.localhost\Ubuntu-24.04\home\bigweather\projects\big-weather-<package-id>
```

The package ID is derived from the bundled source/data archive. Rerunning an
identical build preserves extracted code, the virtual environment and data, and
retries dependency installation and verification. A different build installs into
a different folder; copy any teammate edits deliberately when switching builds.
An existing unfinished folder is not overwritten automatically.

The installer adds a project user and required packages to Ubuntu 24.04. It leaves
existing WSL default distro/user settings alone. The Linux project user has no
password/sudo setup; use the Windows WSL root account for administrative maintenance
if needed. Application launchers run as the ordinary project user.

The bundled snapshot includes processed data and location metadata, not raw API
responses or raw hourly input partitions. Run `make ingest-all` from the project
terminal before rebuilding the full pipeline from raw sources. Existing dashboard
and analysis jobs work with the snapshot immediately.

## Troubleshooting and validation limits

- If a restart is requested, setup is **not complete** until a second successful run.
- School-managed PCs may need their administrator to enable WSL/virtualization.
  Do not change organizational policy; ask the machine administrator to enable it.
- Network/package failures leave a log under
  `%LOCALAPPDATA%\BigWeatherSetup\<package-id>\setup.log`. Retry the same EXE after
  resolving the displayed failure.
- If port 8501 is occupied, close the existing server before opening the dashboard.
- This is an unsigned team build, so Windows may show an unknown-publisher warning.
  Its SHA-256 checksum is supplied alongside the EXE.
- The binary is cross-compiled on macOS. Archive integrity, source tests, shell
  syntax and local Spark verification can be checked here; the actual Windows
  UAC/restart/WSL flow needs a first-machine Windows smoke test before broad rollout.

## Maintainer: rebuild

From the original repository checkout, with Python dependencies and Go installed:

```bash
make windows-setup
```

The builder validates the published Parquet checksums, packages allowlisted source
files and the active dataset, and cross-compiles Go for Windows amd64. It excludes
`.env`, Git history, virtual environments, caches, raw data and previous installers.
It writes:

```text
dist/BigWeather-Setup.exe
dist/BigWeather-Setup.exe.sha256
dist/BigWeather-Setup.manifest.json
```

`installer/windows/payload.tar.gz` and `dist/` are generated and ignored by Git.
The manifest lists bundled file hashes. `BigWeather-Setup.exe --extract <folder>`
extracts its scripts and archive for inspection without installing anything.
Go is only a build-time requirement; the installer does not add it to teammate PCs.
Typst (for rebuilding the archived interim report) is optional and not installed.
