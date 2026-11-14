#!/app/.venv/bin/python
"""Upgrade the configured database without relying on platform CLI arguments."""
import os
from pathlib import Path
import sys

from alembic import command
from alembic.config import Config


def main():
    root = Path(os.environ.get("ECHOES_ROOT", Path(__file__).resolve().parents[1]))
    config = Config(str(root / "backend/alembic.ini"))
    config.set_main_option("script_location", (root / "backend/alembic").as_posix())
    config.set_main_option("prepend_sys_path", (root / "backend").as_posix())
    print("Applying database migrations to head.", flush=True)
    command.upgrade(config, "head")
    print("Database migrations complete.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Database errors/configuration can contain credentials; do not dump them.
        print(f"Database migration failed ({type(exc).__name__}); check the database and environment configuration.", file=sys.stderr)
        raise SystemExit(1)
