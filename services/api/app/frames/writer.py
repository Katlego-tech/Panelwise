"""The two hooks that write a frame's progress (verify.md §6 `FrameWriter`; T021).

`log` keeps every audited attempt in `frame_audits`; `on_frame` moves the shot's `frames` row through
verify.md §5. Each write is its own short transaction, so a frame's state is visible to the web while
its job still runs. The only path that writes a `frames` row's state, besides the restart sweep.
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.frames.model import ACCEPTED, FrameAuditRow, FrameRow
from app.verify.model import Audit, Check, FrameState, Severity, Verdict

_CHECK_ORDER = {check.value: i for i, check in enumerate(Check)}


def _jsonable(model: Any) -> dict[str, Any] | None:
    return None if model is None else model.model_dump(mode="json")


def withheld_check(row: FrameAuditRow | None) -> str | None:
    """The reason a frame was withheld, from its last audit: `audit_error` for an audit that
    couldn't run, else its first failed hard check in `Check` order (web.md §6)."""
    if row is None:
        return None
    if row.verdict == Verdict.ERROR:
        return "audit_error"
    failed = [c["check"] for c in row.checks if c["severity"] == Severity.HARD and not c["ok"]]
    return min(failed, key=_CHECK_ORDER.__getitem__) if failed else None


class FrameWriter:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        project_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> None:
        self.sessions = sessions
        self.project_id = project_id
        self.job_id = job_id

    async def log(self, audit: Audit, frame_asset: str) -> None:
        scene_index, shot_number = audit.shot
        async with self.sessions() as session:
            session.add(
                FrameAuditRow(
                    project_id=self.project_id,
                    job_id=self.job_id,
                    scene_index=scene_index,
                    shot_number=shot_number,
                    attempt=audit.attempt,
                    seed=audit.seed,
                    frame_asset=frame_asset,
                    description=_jsonable(audit.description),
                    judgement=_jsonable(audit.judgement),
                    checks=[
                        {"check": c.check.value, "severity": c.severity.value, "ok": c.ok, "detail": c.detail}
                        for c in audit.checks
                    ],
                    positions={name: p.value for name, p in audit.positions.items()},
                    verdict=audit.verdict.value,
                    models=list(audit.models),
                    prompt_tokens=audit.usage.prompt_tokens,
                    completion_tokens=audit.usage.completion_tokens,
                )
            )
            await session.commit()

    async def on_frame(
        self, shot: tuple[int, int], state: FrameState, attempt: int, asset: str | None
    ) -> None:
        scene_index, shot_number = shot
        async with self.sessions() as session:
            reason = None
            if state is FrameState.WITHHELD:
                last = await session.scalar(
                    select(FrameAuditRow)
                    .where(
                        FrameAuditRow.project_id == self.project_id,
                        FrameAuditRow.scene_index == scene_index,
                        FrameAuditRow.shot_number == shot_number,
                    )
                    .order_by(FrameAuditRow.attempt.desc(), FrameAuditRow.created_at.desc())
                    .limit(1)
                )
                reason = withheld_check(last)
            values = {
                "state": state.value,
                "attempt": attempt,
                "job_id": self.job_id,
                # Only an accepted frame references its image (web.md §3); nothing else ever does.
                "asset": asset if state.value in ACCEPTED else None,
                "withheld_check": reason,
                "failure": "render" if state is FrameState.FAILED else None,
            }
            await session.execute(
                insert(FrameRow)
                .values(project_id=self.project_id, scene_index=scene_index, shot_number=shot_number, **values)
                .on_conflict_do_update(index_elements=["project_id", "scene_index", "shot_number"], set_=values)
            )
            await session.commit()
