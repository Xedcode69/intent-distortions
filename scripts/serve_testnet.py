"""Launch a testnet-only API and frontend; no worker or operator keys are loaded."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

from serve_replay import stop_process
from app.services.testnet_rehearsal import load_settings, local_art

ROOT = Path(__file__).resolve().parents[1]


def server_environments(directory, api_port, web_port):
    config, _, _, _, _ = local_art(directory)
    keep = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
            "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA", "SSL_CERT_FILE", "NODE_EXTRA_CA_CERTS", "LANG", "TERM"}
    env = {key: value for key, value in os.environ.items() if key.upper() in keep}
    env.update(ECHOES_ENV_FILE=str(Path(directory) / "profile.env"), APP_ENV="development", EXECUTION_MODE="testnet_rehearsal",
               TESTNET_REHEARSAL_DIR=str(directory), DATA_DIR=str(directory), DATABASE_URL=config.database_url,
               SERVICE_ROLE="api", SCHEDULER_ENABLED="false", ENABLE_CHAIN_WRITES="false", MAINNET_WRITES_APPROVED="false",
               MARKETPLACE_CROSSCHAIN_ENABLED="false", SIGNER_KEY_FILE="", ADMIN_TOKEN="", NEAR_NETWORK="testnet",
               NEAR_RPC_URL=config.near_rpc_url, NEAR_INTENTS_PARTNER_JWT="", NEAR_AI_API_KEY="", NEAR_INTENTS_1CLICK_JWT="",
               CORS_ORIGIN=f"http://127.0.0.1:{web_port}", PUBLIC_ORIGIN=f"http://127.0.0.1:{web_port}")
    frontend = {key: value for key, value in env.items() if key.upper() in keep}
    frontend.update(BACKEND_URL=f"http://127.0.0.1:{api_port}", APP_PROFILE="testnet", ECHOES_NEXT_DIST_DIR=".next-testnet",
                    NEXT_TELEMETRY_DISABLED="1")
    return env, frontend


def serve(directory, api_port=8002, web_port=3004):
    if api_port == web_port or not all(1024 <= p <= 65535 for p in (api_port, web_port)):
        raise ValueError("Choose distinct unprivileged local ports")
    for port in (api_port, web_port):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
    node = shutil.which("node") or next((str(path) for path in (ROOT / ".tools").glob("node-*/node.exe")), None)
    if not node or not (ROOT / "frontend/node_modules/next/dist/bin/next").is_file():
        raise ValueError("Install Node 22 and frontend npm dependencies")
    api_env, web_env = server_environments(directory, api_port, web_port)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    api = web = None
    try:
        with (Path(directory) / "api.log").open("a", encoding="utf-8") as log:
            api = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(api_port)],
                cwd=ROOT, env=api_env, stdout=log, stderr=log, creationflags=flags, start_new_session=os.name != "nt")
            for _ in range(80):
                if api.poll() is not None: raise ValueError("Testnet API stopped; inspect the local api.log")
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{api_port}/api/v1/health", timeout=1) as response:
                        health = json.load(response)
                        if health["mode"] == "testnet_rehearsal" and health["network"] == "testnet": break
                except (OSError, ValueError): time.sleep(.25)
            else: raise ValueError("Testnet API did not become ready")
            web = subprocess.Popen([node, "node_modules/next/dist/bin/next", "dev", "--hostname", "127.0.0.1", "--port", str(web_port)],
                cwd=ROOT / "frontend", env=web_env, creationflags=flags, start_new_session=os.name != "nt")
            print(f"TESTNET REHEARSAL: http://127.0.0.1:{web_port} — no background signing; Ctrl+C stops this site only.", flush=True)
            web.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for process in (web, api): stop_process(process)
