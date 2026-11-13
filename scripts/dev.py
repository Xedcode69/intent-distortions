"""Run both services via `uv run --locked python scripts/dev.py`."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
node=shutil.which("node") or next((str(p) for p in (root/".tools").glob("node-*/node.exe")),None)
if not node:raise SystemExit("Install Node.js 22 and run npm ci inside frontend first")
venv=root/".venv"/("Scripts/python.exe" if os.name=="nt" else "bin/python")
if not venv.exists() or Path(sys.prefix).resolve() != (root/".venv").resolve():
    raise SystemExit("Run this launcher inside the uv environment: uv run --locked python scripts/dev.py")
python=sys.executable
env=os.environ.copy()
env.pop("PYTHONPATH",None)
env["NEXT_TELEMETRY_DISABLED"]="1"
data=root/"data";data.mkdir(exist_ok=True)
flags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0
backend=frontend=None
try:
    with (data/"backend.log").open("a",encoding="utf-8") as log:
        backend=subprocess.Popen([python,"-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000"],cwd=root,env=env,stdout=log,stderr=log,creationflags=flags)
        frontend=subprocess.Popen([node,"node_modules/next/dist/bin/next","dev","--hostname","127.0.0.1"],cwd=root/"frontend",env=env,creationflags=flags)
        print("Intent Distortions: http://127.0.0.1:3000 — Ctrl+C stops both services.",flush=True)
        result=frontend.wait()
        if result:raise SystemExit(result)
except KeyboardInterrupt:
    pass
finally:
    for process in (frontend,backend):
        if process is not None and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill()
