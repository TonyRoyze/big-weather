"""Local demo adapter using the official Codex CLI and managed ChatGPT login."""

import json
import os
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path


def status():
    binary = shutil.which("codex")
    if not binary:
        return {
            "configured": False,
            "provider": "codex",
            "message": "Install Codex CLI and run codex login on this computer.",
        }
    try:
        result = subprocess.run(
            [binary, "login", "status"], capture_output=True, text=True, timeout=10, check=False
        )
        ready = result.returncode == 0 and "ChatGPT" in result.stdout + result.stderr
    except (OSError, subprocess.TimeoutExpired):
        ready = False
    return {
        "configured": ready,
        "provider": "codex",
        "message": "Connected to local Codex · subscription usage applies."
        if ready
        else "Run codex login and sign in with ChatGPT on this computer.",
    }


def generate(instructions, payload, schema=None):
    if not status()["configured"]:
        raise RuntimeError(status()["message"])
    with tempfile.TemporaryDirectory(prefix="weather-codex-") as temp:
        output = Path(temp) / "answer.json"
        args = [
            shutil.which("codex"),
            "exec",
            "--ignore-user-config",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "-C",
            temp,
            "-c",
            "features.shell_tool=false",
            "-c",
            'web_search="disabled"',
            "-o",
            str(output),
        ]
        if os.getenv("WEATHER_CODEX_MODEL"):
            args.extend(["-m", os.environ["WEATHER_CODEX_MODEL"]])
        if schema:
            schema_path = Path(temp) / "schema.json"
            schema_path.write_text(json.dumps(schema))
            args.extend(["--output-schema", str(schema_path)])
        args.append("-")
        prompt = (
            instructions
            + "\nUse only the supplied data. Do not use tools or inspect files.\nDATA:\n"
            + payload
        )
        env = {
            k: v for k, v in os.environ.items() if k not in ("OPENAI_API_KEY", "OPENAI_BASE_URL")
        }
        process = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            env=env,
            start_new_session=True,
        )
        try:
            process.communicate(prompt, timeout=150)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise RuntimeError("Codex took too long. Try a shorter question.") from None
        if process.returncode or not output.exists():
            raise RuntimeError(
                "Codex could not complete the request. Check codex login status and your subscription usage limits."
            )
        return output.read_text().strip()
