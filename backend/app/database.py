import time
from sqlalchemy import create_engine, String, Integer, BigInteger, JSON, Text, UniqueConstraint, ForeignKey, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import settings

class Base(DeclarativeBase):
    pass

class Swap(Base):
    __tablename__ = "intents_swaps"
    key: Mapped[str] = mapped_column(String(64),primary_key=True)
    created_at_unix: Mapped[int] = mapped_column(Integer,index=True)
    status: Mapped[str] = mapped_column(String(32),index=True)
    normalized: Mapped[dict] = mapped_column(JSON)
    last_verified_at: Mapped[int] = mapped_column(Integer)

class Epoch(Base):
    __tablename__ = "epochs"
    __table_args__ = (UniqueConstraint("mode","number"),)
    id: Mapped[str] = mapped_column(String(80),primary_key=True)
    number: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(32))
    start: Mapped[int] = mapped_column(Integer)
    end: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)

class Artwork(Base):
    __tablename__ = "artworks"
    id: Mapped[str] = mapped_column(String(80),primary_key=True)
    epoch_id: Mapped[str] = mapped_column(ForeignKey("epochs.id"),unique=True)
    image_hash: Mapped[str] = mapped_column(String(64),unique=True)
    payload: Mapped[dict] = mapped_column(JSON)

class EpochTransaction(Base):
    __tablename__ = "epoch_transactions"
    __table_args__ = (UniqueConstraint("epoch_id","position"), UniqueConstraint("epoch_id","record_key"))
    id: Mapped[int] = mapped_column(primary_key=True)
    epoch_id: Mapped[str] = mapped_column(ForeignKey("epochs.id"))
    record_key: Mapped[str] = mapped_column(String(64))
    position: Mapped[int] = mapped_column(Integer)
    record: Mapped[dict] = mapped_column(JSON)

class Job(Base):
    __tablename__ = "pipeline_jobs"
    key: Mapped[str] = mapped_column(String(160),primary_key=True)
    kind: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24),index=True)
    attempts: Mapped[int] = mapped_column(Integer,default=0)
    updated_at: Mapped[int] = mapped_column(Integer,default=lambda:int(time.time()))
    error: Mapped[str | None] = mapped_column(Text,nullable=True)
    payload: Mapped[dict] = mapped_column(JSON,default=dict)

class Release(Base):
    __tablename__ = "weekly_releases"
    number: Mapped[int] = mapped_column(Integer,primary_key=True)
    sunday: Mapped[int] = mapped_column(BigInteger,unique=True)
    freeze_at: Mapped[int] = mapped_column(BigInteger)
    state: Mapped[str] = mapped_column(String(32),index=True,default="scheduled")
    payload: Mapped[dict] = mapped_column(JSON,default=dict)
    error: Mapped[str | None] = mapped_column(String(80),nullable=True)
    updated_at: Mapped[int] = mapped_column(BigInteger,default=lambda:int(time.time()))

class Protocol(Base):
    __tablename__ = "protocol_config"
    id: Mapped[str] = mapped_column(String(64),primary_key=True)
    commitment: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)

class Observation(Base):
    __tablename__ = "collection_observations"
    id: Mapped[int] = mapped_column(Integer,primary_key=True)
    release_number: Mapped[int] = mapped_column(ForeignKey("weekly_releases.number"),index=True)
    started_at: Mapped[int] = mapped_column(BigInteger)
    completed_at: Mapped[int] = mapped_column(BigInteger)
    snapshot_hash: Mapped[str] = mapped_column(String(64))
    evidence: Mapped[dict] = mapped_column(JSON)

class Effect(Base):
    __tablename__ = "chain_effects"
    key: Mapped[str] = mapped_column(String(160),primary_key=True)
    account: Mapped[str] = mapped_column(String(64))
    contract: Mapped[str] = mapped_column(String(64))
    method: Mapped[str] = mapped_column(String(64))
    args_hash: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(24))
    signed_transaction: Mapped[str] = mapped_column(Text)
    transaction_hash: Mapped[str] = mapped_column(String(64),unique=True)
    created_at: Mapped[int] = mapped_column(BigInteger)
    payload: Mapped[dict] = mapped_column(JSON,default=dict)

class ChainEvent(Base):
    __tablename__ = "chain_events"
    key: Mapped[str] = mapped_column(String(160),primary_key=True)
    transaction_hash: Mapped[str] = mapped_column(String(64))
    receipt_id: Mapped[str] = mapped_column(String(64))
    contract: Mapped[str] = mapped_column(String(64),index=True)
    token_id: Mapped[str | None] = mapped_column(String(80),nullable=True,index=True)
    kind: Mapped[str] = mapped_column(String(32),index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    block_height: Mapped[int] = mapped_column(BigInteger)
    timestamp_ns: Mapped[str] = mapped_column(String(32))

def init_db(url=None,create_schema=None):
    settings.data_dir.mkdir(parents=True,exist_ok=True)
    target=url or settings.database_url
    if target.startswith("postgresql://"): target=target.replace("postgresql://","postgresql+psycopg://",1)
    engine = create_engine(target,pool_pre_ping=True,connect_args={"check_same_thread":False} if target.startswith("sqlite") else {"options":"-c statement_timeout=30000"})
    if target.startswith("sqlite"):
        @event.listens_for(engine,"connect")
        def foreign_keys(connection,record): connection.execute("PRAGMA foreign_keys=ON")
    if create_schema if create_schema is not None else settings.app_env!="production":
        Base.metadata.create_all(engine)
    return sessionmaker(engine,expire_on_commit=False)
