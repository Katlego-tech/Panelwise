"""Frame queries (web.md §6). Functions take a session and never commit."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.frames.model import FrameRow


async def frames_of(session: AsyncSession, project_id: uuid.UUID) -> list[FrameRow]:
    rows = await session.execute(
        select(FrameRow)
        .where(FrameRow.project_id == project_id)
        .order_by(FrameRow.scene_index, FrameRow.shot_number)
    )
    return list(rows.scalars())
