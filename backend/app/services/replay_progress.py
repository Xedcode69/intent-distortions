"""Small, allowlisted replay progress; never stores provider rows or credentials."""
from pathlib import Path
import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReplayProgress(BaseModel):
    model_config = ConfigDict(extra="ignore")
    schema_version: Literal["echo-replay-progress-v1"] = "echo-replay-progress-v1"
    status: Literal["idle", "running", "passed", "failed", "blocked", "interrupted"] = "idle"
    stage: Literal["waiting", "beacon", "checkpoint", "capture", "art_direction", "verification", "export", "complete"] = "waiting"
    sunday: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    start: int | None = Field(default=None, ge=0)
    end_ns: str | None = Field(default=None, pattern=r"^\d+$")
    started_at: int | None = Field(default=None, ge=0)
    updated_at: int | None = Field(default=None, ge=0)
    pages: int = Field(default=0, ge=0)
    received_rows: int = Field(default=0, ge=0)
    total_records: int | None = Field(default=None, ge=0)
    eligible_records: int | None = Field(default=None, ge=0)
    collection_complete: bool = False
    total_source: Literal["unknown_until_pagination_complete", "complete_capture"] = "unknown_until_pagination_complete"


class ProgressWriter:
    def __init__(self, directory, *, sunday, start, clock=time.time):
        self.path = Path(directory) / "progress.json"
        self.clock = clock
        self.value = ReplayProgress(status="running", sunday=sunday, start=start, started_at=int(clock()))

    def update(self, **changes):
        self.value = ReplayProgress.model_validate({**self.value.model_dump(), **changes, "updated_at":int(self.clock())})
        temporary = self.path.with_suffix(".json.tmp")
        try:
            temporary.write_text(self.value.model_dump_json() + "\n", encoding="utf-8")
            temporary.replace(self.path)
        except OSError:
            # Progress is advisory; a briefly locked display file cannot reset
            # or invalidate the capture. The next update retries publication.
            return False
        return True


def read_progress(directory, *, clock=time.time):
    path = Path(directory) / "progress.json"
    if not path.is_file():
        value = ReplayProgress()
    else:
        if path.stat().st_size > 8192:
            raise ValueError("Replay progress is unavailable")
        value = ReplayProgress.model_validate_json(path.read_bytes())
    now = int(clock())
    elapsed_until = now if value.status == "running" else (value.updated_at or now)
    return {**value.model_dump(), "server_time":now,
            "stale":value.status == "running" and (value.updated_at is None or now-value.updated_at > 120),
            "elapsed_seconds":max(0, elapsed_until-value.started_at) if value.started_at is not None else 0,
            "collection_percent":100 if value.collection_complete else None}
