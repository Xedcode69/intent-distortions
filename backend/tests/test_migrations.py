"""Exercise the hosted migration entrypoint on an isolated database, never app state."""
import os
from pathlib import Path
import subprocess
import sys

from sqlalchemy import create_engine, inspect, text

from app.database import Base


ROOT = Path(__file__).resolve().parents[2]


def test_hosted_migration_preserves_data_and_works_outside_repository(tmp_path):
    database = tmp_path / "migration.db"
    environment = {
        **os.environ,
        "ECHOES_ROOT": str(ROOT),
        "ECHOES_ENV_FILE": str(tmp_path / "no-private-env"),
        "APP_ENV": "test",
        "EXECUTION_MODE": "live",
        "SERVICE_ROLE": "api",
        "DATABASE_URL": "sqlite:///" + database.as_posix(),
        "DATA_DIR": str(tmp_path / "data"),
        "ENABLE_CHAIN_WRITES": "false",
        "SCHEDULER_ENABLED": "false",
    }

    def migrate():
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/migrate.py")],
            cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, result.stderr
        assert "Database migrations complete." in result.stdout

    migrate()
    engine = create_engine(environment["DATABASE_URL"])
    try:
        schema = inspect(engine)
        assert set(schema.get_table_names()) == set(Base.metadata.tables) | {"alembic_version"}
        for name, table in Base.metadata.tables.items():
            assert {column["name"] for column in schema.get_columns(name)} == set(table.columns.keys())
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0002"
            connection.execute(text("INSERT INTO weekly_releases (number,sunday,freeze_at,state,payload,updated_at) VALUES (1,1794700800,1794769200,'scheduled','{}',1794700800)"))
        migrate()
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT state FROM weekly_releases WHERE number=1")) == "scheduled"
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0002"
    finally:
        engine.dispose()


def test_hosted_migration_failure_blocks_deploy_without_logging_secrets(tmp_path):
    environment = {
        **os.environ,
        "ECHOES_ROOT": str(ROOT),
        "ECHOES_ENV_FILE": str(tmp_path / "no-private-env"),
        "APP_ENV": "test",
        "DATABASE_URL": "invalid-dialect://user:do-not-log-this@database/db",
    }
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/migrate.py")],
        cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 1
    assert "Database migration failed" in result.stderr
    assert "Database migrations complete." not in result.stdout
    assert "do-not-log-this" not in result.stdout + result.stderr
