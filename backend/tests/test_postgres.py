"""Opt-in against an explicitly supplied disposable PostgreSQL server, never the app database."""
import os
import uuid
import pytest
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from app.database import Base,Release

@pytest.mark.skipif(not os.environ.get("ECHOES_PG_TEST_URL"),reason="disposable PostgreSQL URL not supplied")
def test_postgres_migrations_and_single_worker_lease(monkeypatch):
    from app.config import settings
    url=make_url(os.environ["ECHOES_PG_TEST_URL"]).set(drivername="postgresql+psycopg")
    schema="echoes_validation_"+uuid.uuid4().hex
    admin=create_engine(url)
    with admin.begin() as db:db.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped=url.update_query_dict({"options":f"-csearch_path={schema}"})
    monkeypatch.setattr(settings,"database_url",scoped.render_as_string(hide_password=False))
    engine=create_engine(scoped)
    try:
        config=Config("backend/alembic.ini")
        command.upgrade(config,"head");command.upgrade(config,"head")
        with engine.connect() as db:
            assert db.scalar(text("SELECT version_num FROM alembic_version"))=="0002"
            assert compare_metadata(MigrationContext.configure(db),Base.metadata)==[]
        factory=sessionmaker(engine,expire_on_commit=False)
        with factory.begin() as db:db.add(Release(number=1,sunday=1800000000,freeze_at=1800003600,state="scheduled",payload={}))
        with factory() as db:assert db.get(Release,1).payload=={}
        with engine.connect() as first,engine.connect() as second:
            assert first.scalar(text("SELECT pg_try_advisory_lock(771862023)"))
            first.commit()
            assert not second.scalar(text("SELECT pg_try_advisory_lock(771862023)"))
            second.commit()
            first.execute(text("SELECT pg_advisory_unlock(771862023)"));first.commit()
            assert second.scalar(text("SELECT pg_try_advisory_lock(771862023)"))
            second.execute(text("SELECT pg_advisory_unlock(771862023)"));second.commit()
    finally:
        engine.dispose()
        with admin.begin() as db:db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
