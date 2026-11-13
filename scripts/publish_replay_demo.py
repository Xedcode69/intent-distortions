"""Prepare a passed historical replay for the site's /demo page; no deployment."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    report = args.report.resolve()
    if not report.is_relative_to((ROOT / "data/replays").resolve()):
        raise ValueError("Choose a report inside this project's data/replays/")
    from app.services.demo_publication import publish_replay
    from app.services.historical_replay import replay_lock
    with replay_lock(ROOT / "data/replays/.historical-test.lock"):
        result = publish_replay(report, ROOT / "frontend/public/historical-demo")
    print(json.dumps({"status":"prepared", "page":"/demo", "sunday":result["sunday"],
                      "image_hash":result["artwork"]["image_hash"],
                      "deployment":"not_run; rebuild the frontend to include the prepared public assets"}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"status":"failed", "error_type":type(exc).__name__,
                          "hint":"A passed replay, original capture and valid frozen artwork are required; nothing was deployed."}))
        raise SystemExit(1)
