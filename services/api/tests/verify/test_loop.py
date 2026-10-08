"""render_until_accepted: verify.md §4, §5, §9. A fake renderer and a scripted audit, no network."""

from collections.abc import Iterator
from typing import Any

import pytest

from app.grounding import Extraction
from app.llm import NebiusChatModel, Usage
from app.script import Screenplay
from app.shots import Shot
from app.verify import loop
from app.verify.audit import seed_for
from app.verify.model import Audit, FrameState, RenderedFrame, Verdict
from tests.verify.conftest import kitchen_shot


class FakeRenderer:
    def __init__(self, *, fail_on: int | None = None) -> None:
        self.calls: list[tuple[int, int, int, int]] = []
        self.fail_on = fail_on

    async def render(
        self, shot: Shot, attempt: int, seed: int, width: int, height: int
    ) -> RenderedFrame:
        self.calls.append((attempt, seed, width, height))
        if attempt == self.fail_on:
            raise RuntimeError("the renderer fell over")
        return RenderedFrame(
            (shot.scene_index, shot.number), attempt, seed, b"png", width, height, "p"
        )


def audits_with(monkeypatch: pytest.MonkeyPatch, verdicts: list[Verdict]) -> list[RenderedFrame]:
    """audit_frame answers each attempt with the next verdict; returns the frames it was shown."""
    seen: list[RenderedFrame] = []
    answers: Iterator[Verdict] = iter(verdicts)

    async def fake(
        model: Any, frame: RenderedFrame, shot: Shot, screenplay: Any, extraction: Any
    ) -> Audit:
        seen.append(frame)
        return Audit(
            frame.shot,
            frame.attempt,
            frame.seed,
            None,
            None,
            (),
            next(answers),
            {},
            ("m",),
            Usage(0, 0, 0),
        )

    monkeypatch.setattr(loop, "audit_frame", fake)
    return seen


class Recorder:
    def __init__(self) -> None:
        self.audits: list[Audit] = []
        self.states: list[tuple[FrameState, int]] = []

    async def log(self, audit: Audit) -> None:
        self.audits.append(audit)

    async def on_state(self, state: FrameState, attempt: int) -> None:
        self.states.append((state, attempt))


async def run(
    renderer: FakeRenderer, screenplay: Screenplay, extraction: Extraction, rec: Recorder, **kw: Any
) -> Any:
    return await loop.render_until_accepted(
        NebiusChatModel.__new__(NebiusChatModel),
        renderer,
        kitchen_shot(),
        screenplay,
        extraction,
        width=1280,
        height=720,
        log=rec.log,
        on_state=rec.on_state,
        **kw,
    )


R, A = FrameState.RENDERING, FrameState.AUDITING


async def test_a_frame_that_passes_first_time(
    monkeypatch: pytest.MonkeyPatch, screenplay: Screenplay, extraction: Extraction
) -> None:
    audits_with(monkeypatch, [Verdict.PASS])
    rec, renderer = Recorder(), FakeRenderer()
    outcome = await run(renderer, screenplay, extraction, rec)
    assert outcome.state is FrameState.PASSED
    assert outcome.frame is not None and outcome.frame.attempt == 1
    assert rec.states == [(R, 1), (A, 1), (FrameState.PASSED, 1)]
    assert [a.attempt for a in rec.audits] == [1]


async def test_fail_then_pass_re_renders_with_a_new_seed(
    monkeypatch: pytest.MonkeyPatch, screenplay: Screenplay, extraction: Extraction
) -> None:
    audits_with(monkeypatch, [Verdict.FAIL, Verdict.WARN])
    rec, renderer = Recorder(), FakeRenderer()
    outcome = await run(renderer, screenplay, extraction, rec)
    assert outcome.state is FrameState.WARNED
    shot = kitchen_shot()
    assert [(a, s) for a, s, _, _ in renderer.calls] == [
        (1, seed_for(shot, 1)),
        (2, seed_for(shot, 2)),
    ]
    assert seed_for(shot, 1) != seed_for(shot, 2)
    assert rec.states == [(R, 1), (A, 1), (R, 2), (A, 2), (FrameState.WARNED, 2)]


async def test_three_fails_withhold_the_frame_and_log_every_attempt(
    monkeypatch: pytest.MonkeyPatch, screenplay: Screenplay, extraction: Extraction
) -> None:
    audits_with(monkeypatch, [Verdict.FAIL] * 3)
    rec, renderer = Recorder(), FakeRenderer()
    outcome = await run(renderer, screenplay, extraction, rec)
    assert outcome.state is FrameState.WITHHELD
    assert outcome.frame is None  # a withheld frame is never handed on
    assert [a.attempt for a in outcome.audits] == [1, 2, 3]
    assert [a.attempt for a in rec.audits] == [1, 2, 3]
    assert rec.states[-1] == (FrameState.WITHHELD, 3)


async def test_an_audit_error_withholds_at_once(
    monkeypatch: pytest.MonkeyPatch, screenplay: Screenplay, extraction: Extraction
) -> None:
    audits_with(monkeypatch, [Verdict.ERROR, Verdict.PASS])
    rec, renderer = Recorder(), FakeRenderer()
    outcome = await run(renderer, screenplay, extraction, rec)
    assert outcome.state is FrameState.WITHHELD
    assert len(renderer.calls) == 1  # never re-rendered towards an unaudited pass
    assert rec.states == [(R, 1), (A, 1), (FrameState.WITHHELD, 1)]


async def test_a_renderer_error_fails_the_frame_and_is_raised(
    monkeypatch: pytest.MonkeyPatch, screenplay: Screenplay, extraction: Extraction
) -> None:
    audits_with(monkeypatch, [Verdict.FAIL])
    rec = Recorder()
    with pytest.raises(RuntimeError, match="fell over"):
        await run(FakeRenderer(fail_on=2), screenplay, extraction, rec)
    assert rec.states == [(R, 1), (A, 1), (R, 2), (FrameState.FAILED, 2)]
    assert [a.attempt for a in rec.audits] == [1]


async def test_first_attempt_4_runs_attempt_4_alone(
    monkeypatch: pytest.MonkeyPatch, screenplay: Screenplay, extraction: Extraction
) -> None:
    seen = audits_with(monkeypatch, [Verdict.FAIL])
    rec, renderer = Recorder(), FakeRenderer()
    outcome = await run(renderer, screenplay, extraction, rec, first_attempt=4, max_renders=1)
    assert outcome.state is FrameState.WITHHELD
    assert [(a, s) for a, s, _, _ in renderer.calls] == [(4, seed_for(kitchen_shot(), 4))]
    assert [f.attempt for f in seen] == [4]
    assert rec.states == [(R, 4), (A, 4), (FrameState.WITHHELD, 4)]


async def test_seeds_are_deterministic(
    monkeypatch: pytest.MonkeyPatch, screenplay: Screenplay, extraction: Extraction
) -> None:
    calls: list[list[tuple[int, int, int, int]]] = []
    for _ in range(2):
        audits_with(monkeypatch, [Verdict.FAIL] * 3)
        renderer = FakeRenderer()
        await run(renderer, screenplay, extraction, Recorder())
        calls.append(renderer.calls)
    assert calls[0] == calls[1]


@pytest.mark.parametrize(("first", "count"), [(0, 3), (1, 0)])
async def test_attempt_numbers_start_at_one(
    screenplay: Screenplay, extraction: Extraction, first: int, count: int
) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        await run(
            FakeRenderer(),
            screenplay,
            extraction,
            Recorder(),
            first_attempt=first,
            max_renders=count,
        )
