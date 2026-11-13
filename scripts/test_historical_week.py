"""Prepare or run a real historical-week replay with no signing or production writes."""
import argparse
import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sunday", help="Completed Sunday in UTC, e.g. 2026-11-08; defaults to latest released Sunday")
    parser.add_argument("--start", type=int, help="Explicit replay genesis Unix seconds; default previous Sunday 00:00 UTC")
    parser.add_argument("--ai", choices=("fallback", "required"), default="fallback", help="Fallback tests mathematics without an AI key; required tests real NEAR AI")
    parser.add_argument("--output", type=Path, help="Separate output directory inside ignored data/replays/")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true", help="Check local requirements without network requests")
    actions.add_argument("--prepare", action="store_true", help="Fetch/verify public beacon and checkpoint only; needs no Explorer JWT")
    args = parser.parse_args()
    from app.config import settings
    from app.services.historical_replay import ReplayPlan, replay_week, replay_lock

    plan = ReplayPlan.build(args.sunday, args.start, args.ai)
    allowed = (ROOT / "data/replays").resolve()
    directory = (args.output or allowed / plan.name).resolve()
    if directory == allowed or not directory.is_relative_to(allowed):
        raise ValueError("Use a dedicated directory inside data/replays/; application state cannot be reused")
    action = "check" if args.check else "prepare" if args.prepare else "run"
    with replay_lock(allowed / ".historical-test.lock"):
        report = await replay_week(plan, settings, directory, action=action,
                                   progress=lambda message: print(message, flush=True))
    print(json.dumps({"status": report["status"], "sunday": plan.sunday,
                      "requirements": report["requirements"], "stages": report["stages"],
                      "report": str(directory / ("readiness.json" if action == "check" else "report.json"))}, indent=2))
    if report["status"] == "passed":
        print(f'Preview: uv run --locked python scripts/serve_replay.py "{directory / "report.json"}"')
        print(f'Site demo: uv run --locked python scripts/publish_replay_demo.py "{directory / "report.json"}"')
    return 0 if report["status"] in ("ready", "checkpoint_prepared", "passed") else 2 if report["status"] == "blocked" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception as exc:
        # Provider exceptions may include credential-bearing URLs; keep terminal output redacted.
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__,
                          "hint": "Check the Sunday, isolated output path and replay environment. No transaction was signed."}))
        raise SystemExit(1)
