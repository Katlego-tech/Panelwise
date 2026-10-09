"""The storyboard (storyboard.md §3.3, §4, §6 `build.py`; T026): every shot through verify's loop,
at most `concurrency` at once, each attempt and state written by T021's writer as it happens.

A shot whose renderer fails stops the storyboard: no new shot starts, the shots in flight are
awaited (their drawings and audits are paid for, and their rows are kept), then StoryboardError
names the first failed shot in plan order. A withheld frame is information, not a failure.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from app.frames.writer import FrameWriter, frame_hooks
from app.grounding import Extraction
from app.llm import NebiusChatModel
from app.script import Screenplay
from app.shots import Shot, ShotPlan
from app.storyboard.model import Storyboard, StoryboardError, StoryboardFrame
from app.storyboard.render import RenderRecord, RenderRecorder
from app.verify.loop import render_until_accepted
from app.verify.model import Check, FrameOutcome, FrameState, Severity, Verdict

log = logging.getLogger(__name__)

_CHECK_ORDER = {check: i for i, check in enumerate(Check)}


def frame_of(outcome: FrameOutcome, record: RenderRecord | None) -> StoryboardFrame:
    """The storyboard's view of one outcome (§3.3), from its last attempt's record. Pure."""
    last = outcome.audits[-1] if outcome.audits else None
    accepted = outcome.state in (FrameState.PASSED, FrameState.WARNED)
    noted: tuple[Check, ...] = ()
    if last is not None and outcome.state in (FrameState.WITHHELD, FrameState.WARNED):
        severity = Severity.HARD if outcome.state is FrameState.WITHHELD else Severity.SOFT
        failed = (c.check for c in last.checks if c.severity is severity and not c.ok)
        noted = tuple(sorted(failed, key=_CHECK_ORDER.__getitem__))
    if outcome.frame is not None:
        prompt: str | None = outcome.frame.prompt
    else:
        prompt = None if record is None else record.prompt.text()
    return StoryboardFrame(
        shot=outcome.shot,
        state=outcome.state,
        asset=record.asset if accepted and record is not None else None,
        prompt=prompt,
        seed=None if last is None else last.seed,
        attempts=len(outcome.audits),
        verdict=Verdict.ERROR if last is None else last.verdict,
        noted_checks=noted,
    )


async def build_storyboard(
    model: NebiusChatModel,
    renderer: RenderRecorder,
    plan: ShotPlan,
    screenplay: Screenplay,
    extraction: Extraction,
    *,
    writer: FrameWriter,
    progress: Callable[[int, int], Awaitable[None]] | None = None,
    width: int = 1280,
    height: int = 720,
    concurrency: int = 2,
    max_renders: int = 3,
) -> Storyboard:
    gate = asyncio.Semaphore(concurrency)
    failed: list[tuple[int, int]] = []  # shots whose renderer raised
    errors: list[BaseException] = []  # anything else (an audit or database error)
    settled = 0
    total = len(plan.shots)

    async def one(shot: Shot) -> FrameOutcome | None:
        nonlocal settled
        key = (shot.scene_index, shot.number)
        async with gate:
            if failed or errors:  # something failed: start nothing new
                return None
            log_audit, write_state = frame_hooks(writer, renderer, key)
            states: list[FrameState] = []

            async def on_state(state: FrameState, attempt: int) -> None:
                await write_state(state, attempt)
                # Recorded once written: the loop enters FAILED only when the renderer raised, so a
                # write that fails first is never mistaken for the renderer's failure.
                states.append(state)

            try:
                outcome = await render_until_accepted(
                    model,
                    renderer,
                    shot,
                    screenplay,
                    extraction,
                    width=width,
                    height=height,
                    max_renders=max_renders,
                    log=log_audit,
                    on_state=on_state,
                )
            except Exception as error:
                if states and states[-1] is FrameState.FAILED:
                    failed.append(key)  # the loop has already written the frame FAILED
                else:
                    errors.append(error)
                return None
        settled += 1
        if progress is not None:
            try:
                await progress(settled, total)
            except Exception:  # progress is shown, not load-bearing: never fail a shot over it
                log.warning("storyboard progress %d/%d not written", settled, total, exc_info=True)
        return outcome

    outcomes = await asyncio.gather(*(one(shot) for shot in plan.shots))
    if errors:
        raise errors[0]
    if failed:
        order = {(s.scene_index, s.number): i for i, s in enumerate(plan.shots)}
        first = min(failed, key=order.__getitem__)
        raise StoryboardError(f"the renderer failed on shot {first}", shot=first)

    frames: list[StoryboardFrame] = []
    renders = cached = 0
    for outcome in outcomes:
        if outcome is None:  # unreachable without a failure; kept for the type
            continue
        records = [renderer.record(outcome.shot, a.attempt) for a in outcome.audits]
        renders += sum(not r.cached for r in records)
        cached += sum(r.cached for r in records)
        frames.append(frame_of(outcome, records[-1] if records else None))
    return Storyboard(renderer.style.key, width, height, tuple(frames), renders, cached)
