"""Isolated historical-art testnet workflow. All signing requires --send and a reviewed plan."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
# Ignore ambient production credentials/configuration. Operator settings come
# exclusively from the prepared workspace; CLI signers remain in the OS keychain.
KEEP = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "HOME", "USERPROFILE", "APPDATA",
        "LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA", "SSL_CERT_FILE", "NODE_EXTRA_CA_CERTS", "LANG", "TERM"}
for key in list(os.environ):
    if key.upper() not in KEEP:
        os.environ.pop(key)
os.environ.update(ECHOES_ENV_FILE=os.devnull, APP_ENV="development", EXECUTION_MODE="demo")
sys.path.insert(0, str(ROOT / "backend"))

from app.services import testnet_rehearsal as lab


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare"); p.add_argument("report", type=Path); p.add_argument("--name", default="genesis")
    p.add_argument("--full-lab", action="store_true", help="Use separately built clock-controlled testnet contracts")
    for name in ("fixtures", "select", "advance", "tick", "recover"):
        p = commands.add_parser(name); p.add_argument("workspace", type=Path)
        if name == "select": p.add_argument("artwork_id")
        if name == "advance": p.add_argument("--to", required=True, help="UTC ISO timestamp, for example 2026-12-06T00:00:00Z")
        if name in ("advance", "tick"): p.add_argument("--send", action="store_true")
        if name == "recover": p.add_argument("--tx-hash", required=True)
    for name in ("check", "deploy-plan", "mint-plan", "deploy", "mint", "verify", "create-wallet", "serve"):
        p = commands.add_parser(name); p.add_argument("workspace", type=Path)
        if name == "check": p.add_argument("--online", action="store_true")
        if name in ("deploy", "mint", "create-wallet"):
            p.add_argument("--send", action="store_true", help="Explicitly authorize the named testnet operation")
        if name in ("deploy", "mint"): p.add_argument("--plan-sha256", help="SHA-256 of the reviewed plan")
        if name in ("mint", "create-wallet"): p.add_argument("--failed-tx", help="Finalized matching failed transaction required to clear an uncertain prior attempt")
        if name == "deploy":
            p.add_argument("--failed-tx");p.add_argument("--failed-role",choices=("nft","auction","market"))
        if name == "serve":
            p.add_argument("--api-port", type=int, default=8002); p.add_argument("--web-port", type=int, default=3004)
    args = parser.parse_args()
    if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
        raise ValueError("Run from the root with uv run --locked python scripts/testnet_rehearsal.py")
    if args.command == "prepare": return lab.prepare(args.report, args.name, args.full_lab)
    directory = lab.workspace(args.workspace)
    if args.command in ("fixtures", "select", "advance", "tick", "recover"):
        from app.services import testnet_lab
        if args.command == "fixtures": return await testnet_lab.fixtures(directory)
        if args.command == "select": return testnet_lab.select_edition(directory, args.artwork_id)
        if args.command == "recover": return await testnet_lab.recover(directory, args.tx_hash)
        if not args.send: raise lab.RehearsalError("Pass --send to authorize this testnet operator action")
        if args.command == "tick": return await testnet_lab.tick(directory)
        from datetime import datetime, timezone
        date = datetime.fromisoformat(args.to.replace("Z", "+00:00"))
        if date.utcoffset() != timezone.utc.utcoffset(date): raise lab.RehearsalError("Use an explicit UTC timestamp ending in Z")
        return await testnet_lab.advance(directory, int(date.timestamp()) * 10**9)
    if args.command == "check": return await lab.check(directory, args.online)
    if args.command.endswith("-plan"): return lab.save_plan(directory, args.command.split("-")[0])
    if args.command in ("deploy", "mint", "create-wallet") and not args.send:
        raise ValueError("Nothing signed. Review the plan and explicitly pass --send when ready.")
    if args.command in ("deploy", "mint") and not args.plan_sha256:
        raise ValueError("Supply the reviewed --plan-sha256 before signing")
    if args.command == "deploy":
        if bool(args.failed_tx) != bool(args.failed_role):raise lab.RehearsalError("Deployment recovery needs both --failed-tx and --failed-role")
        return await lab.deploy(directory, args.plan_sha256, failed_tx=args.failed_tx, failed_role=args.failed_role)
    if args.command == "mint": return await lab.mint(directory, args.plan_sha256, failed_tx=args.failed_tx)
    if args.command == "verify": return await lab.verify_mint(directory)
    if args.command == "create-wallet": return await lab.create_wallet(directory, failed_tx=args.failed_tx)
    if args.command == "serve":
        from serve_testnet import serve
        serve(directory, args.api_port, args.web_port)
        return {"status": "stopped", "signed": False}


if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        print(json.dumps(result, indent=2))
        if result.get("status") == "blocked": raise SystemExit(2)
    except (KeyboardInterrupt, SystemExit):
        raise
    except lab.RehearsalError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc), "automatic_retry": False}))
        raise SystemExit(2)
    except Exception as exc:
        # Deliberately omit exception text: RPC/HTTP failures can embed secrets.
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__,
                          "hint": "Check profile.env, readiness, reviewed plans and operator-journal.json. No automatic retry was attempted."}))
        raise SystemExit(1)
