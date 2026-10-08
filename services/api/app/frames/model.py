"""A `frames` row: one shot's place in verify's state machine (web.md §3, §6; T047 creates and
reads it, T021 writes it). The only source of `FrameView`."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

FRAME_STATES = ("rendering", "auditing", "passed", "warned", "withheld", "failed")
ACCEPTED = ("passed", "warned")  # the only states that may reference an image


class FrameRow(Base):
    __tablename__ = "frames"
    __table_args__ = (
        CheckConstraint(
            "state IN ('rendering', 'auditing', 'passed', 'warned', 'withheld', 'failed')",
            name="frames_state",
        ),
        CheckConstraint("attempt >= 1", name="frames_attempt"),
        # A withheld frame's file is never referenced (web.md §3).
        CheckConstraint("asset IS NULL OR state IN ('passed', 'warned')", name="frames_asset"),
        # Why a failed frame failed (T021): the renderer or the restart sweep; no other state has one.
        CheckConstraint(
            "failure IS NULL OR (state = 'failed' AND failure IN ('render', 'restart'))",
            name="frames_failure",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    scene_index: Mapped[int] = mapped_column(primary_key=True)
    shot_number: Mapped[int] = mapped_column(primary_key=True)
    state: Mapped[str]
    attempt: Mapped[int]
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    asset: Mapped[str | None] = mapped_column(default=None)
    withheld_check: Mapped[str | None] = mapped_column(default=None)
    failure: Mapped[str | None] = mapped_column(default=None)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.clock_timestamp(), onupdate=func.clock_timestamp()
    )
