"""Open a completed historical replay in an isolated local API/frontend profile."""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def stop_process(process):
    if process is None or process.poll() is not None:
        return
    if os.name == "nt":
        # Next.js starts a child server; terminate only this launcher's process tree.
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=subprocess.CREATE_NO_WINDOW, check=False)
    else:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait()


def preview_environment(directory, api_port, web_port):
    keep={"PATH","PATHEXT","SYSTEMROOT","WINDIR","COMSPEC","TEMP","TMP","TMPDIR","HOME","USERPROFILE",
          "LOCALAPPDATA","APPDATA","PROGRAMFILES","PROGRAMFILES(X86)","PROGRAMDATA","NODE_EXTRA_CA_CERTS",
          "SSL_CERT_FILE","LANG","LC_ALL","TERM","NO_COLOR","FORCE_COLOR"}
    env = {key:value for key,value in os.environ.items() if key.upper() in keep}
    # Rendering has finished; neither preview process needs integration/signing credentials.
    for key in list(env):
        if key.startswith(("NEAR_", "S3_", "SIGNER_", "AWS_")) or key in ("ADMIN_TOKEN", "DATABASE_URL", "ECHOES_ENV_FILE", "PYTHONPATH"):
            env.pop(key)
    env.update(ECHOES_ENV_FILE=str(directory / "preview.env"), APP_ENV="development",
               EXECUTION_MODE="historical_replay", DATABASE_URL=f"sqlite:///{(directory/'replay.db').as_posix()}",
               DATA_DIR=str(directory), STORAGE_PROVIDER="local_content_addressed", ENABLE_CHAIN_WRITES="false",
               MAINNET_WRITES_APPROVED="false", SCHEDULER_ENABLED="false", SERVICE_ROLE="api", ADMIN_TOKEN="",
               NEAR_NFT_CONTRACT="", NEAR_AUCTION_CONTRACT="", NEAR_INTENTS_PARTNER_JWT="", NEAR_AI_API_KEY="", NEAR_NETWORK="testnet",
               SIGNER_KEY_FILE="", CORS_ORIGIN=f"http://127.0.0.1:{web_port}",
               PUBLIC_ORIGIN=f"http://127.0.0.1:{web_port}", BACKEND_URL=f"http://127.0.0.1:{api_port}",
               APP_PROFILE="replay", ECHOES_NEXT_DIST_DIR=".next-replay", NEXT_TELEMETRY_DISABLED="1")
    frontend = env.copy()
    for key in list(frontend):
        if key.startswith(("NEAR_", "S3_", "SIGNER_", "AWS_")) or key in ("ADMIN_TOKEN", "DATABASE_URL", "ECHOES_ENV_FILE"):
            frontend.pop(key)
    return env, frontend


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--api-port", type=int, default=8001)
    parser.add_argument("--web-port", type=int, default=3003)
    args = parser.parse_args()
    if args.api_port == args.web_port or not all(1 <= port <= 65535 for port in (args.api_port, args.web_port)):
        raise SystemExit("Choose two distinct ports between 1 and 65535")
    directory = args.report.resolve().parent
    if not directory.is_relative_to((ROOT / "data/replays").resolve()):
        raise SystemExit("Select an isolated report inside this project's data/replays/")
    report = json.loads(args.report.read_text(encoding="utf-8"))
    if report.get("mode") != "historical_replay" or report.get("status") != "passed":
        raise SystemExit("Complete and verify the historical replay before opening its preview")
    if not all((directory / name).is_file() for name in ("replay.db", "preview.env")):
        raise SystemExit("Replay database/profile is missing")
    if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
        raise SystemExit("Use uv run --locked python scripts/serve_replay.py <report.json>")
    for port in (args.api_port, args.web_port):
        with socket.socket() as probe:
            try: probe.bind(("127.0.0.1", port))
            except OSError: raise SystemExit(f"Port {port} is in use; choose a different port") from None
    node = shutil.which("node") or next((str(path) for path in (ROOT / ".tools").glob("node-*/node.exe")), None)
    if not node or not (ROOT / "frontend/node_modules/next/dist/bin/next").is_file():
        raise SystemExit("Install Node.js 22 and run npm ci inside frontend")
    api_env, frontend_env = preview_environment(directory, args.api_port, args.web_port)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    backend = frontend = None
    try:
        with (directory / "preview-api.log").open("a", encoding="utf-8") as log:
            backend = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(args.api_port)],
                                       cwd=ROOT, env=api_env, stdout=log, stderr=log, creationflags=flags,
                                       start_new_session=os.name != "nt")
            ready = False
            for _ in range(60):
                if backend.poll() is not None:
                    raise RuntimeError("Replay API stopped; inspect its local preview-api.log")
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{args.api_port}/api/v1/health", timeout=1) as response:
                        if json.load(response)["mode"] == "historical_replay": ready = True; break
                except (OSError, ValueError): time.sleep(.25)
            if not ready: raise RuntimeError("Replay API did not become ready")
            frontend = subprocess.Popen([node, "node_modules/next/dist/bin/next", "dev", "--hostname", "127.0.0.1", "--port", str(args.web_port)],
                                        cwd=ROOT / "frontend", env=frontend_env, creationflags=flags,
                                        start_new_session=os.name != "nt")
            print(f"Historical replay: http://127.0.0.1:{args.web_port} — Ctrl+C stops this preview only.", flush=True)
            code = frontend.wait()
            if code: raise SystemExit(code)
    except KeyboardInterrupt:
        pass
    finally:
        for process in (frontend, backend):
            stop_process(process)


if __name__ == "__main__": main()
