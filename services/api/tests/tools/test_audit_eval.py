"""tools.audit_eval -- docs/design/eval.md §6a, §9 (T049). No model is called here."""

import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any

import httpx2
import pytest
from PIL import Image

from app.llm import Usage
from app.script import parse_text
from app.storyboard.workers_ai import WorkersAIRenderer
from app.verify.model import Audit, Check, CheckResult, Severity, Verdict
from tests.fakes import MemoryStore
from tests.script.conftest import two_page_text
from tests.storyboard.conftest import STYLE, extraction_of, shot_of
from tests.storyboard.test_workers_ai import ACCOUNT, WorkersAI, form
from tests.verify.conftest import described, judged
from tools.audit_eval import (
    FRAMES,
    RESULTS,
    AuditReport,
    AuditRun,
    InjectingRenderer,
    Label,
    LabelError,
    LabelledFrame,
    Story,
    audit_run,
    from_json,
    load_labels,
    measure,
    summarise,
    table,
    to_json,
    write_labels,
)
from tools.evaluate import EVAL


def run_of(label: str, verdict: Verdict, *failed: Check, frame: str = "f", n: int = 1) -> AuditRun:
    return AuditRun(frame, (0, 1), label, n, verdict, failed, (), 10, 5, None)  # type: ignore[arg-type]


RUNS = [
    run_of("correct", Verdict.PASS, frame="a"),
    run_of("correct", Verdict.FAIL, Check.UNSCRIPTED_OBJECT, frame="a", n=2),
    run_of("correct", Verdict.WARN, Check.LIGHT, frame="b"),
    run_of("correct", Verdict.ERROR, frame="b", n=2),
    run_of("unscripted", Verdict.FAIL, Check.TEXT_IN_FRAME, frame="c"),
    run_of("injected_person", Verdict.FAIL, Check.UNSCRIPTED_PERSON, frame="d"),
    run_of("injected_person", Verdict.PASS, frame="d", n=2),
    run_of("injected_object", Verdict.FAIL, Check.TEXT_IN_FRAME, frame="e"),
]


def test_summarise_counts_errors_but_keeps_them_out_of_every_rate() -> None:
    s = summarise(RUNS)
    assert (s.frames, s.runs, s.errors) == (5, 8, 1)
    assert (s.true_fail, s.false_fail, s.missed, s.true_pass) == (3, 1, 1, 2)
    assert (s.precision, s.recall, s.false_fail_rate) == (0.75, 0.75, 0.333)
    assert s.recall_by_label == {"unscripted": 1.0, "injected_person": 0.5, "injected_object": 1.0}
    # of the injected frames caught, the person one failed for a person, the object one didn't
    assert s.right_reason == 0.5
    assert s.false_fail_checks == {"unscripted_object": 1}


def test_summarise_of_nothing_is_zeros_not_a_division_error() -> None:
    s = summarise([])
    assert (s.precision, s.recall, s.false_fail_rate, s.right_reason) == (0.0, 0.0, 0.0, 0.0)


def test_the_table_has_a_row_per_report_in_order() -> None:
    first = AuditReport("2026-10-11", "abc+12345678", ("v", "r"), "cmd", tuple(RUNS))
    second = AuditReport("2026-10-12", "def+87654321", ("v", "r"), "cmd", tuple(RUNS[:3]))
    rows = table([first, second]).splitlines()
    assert len(rows) == 4 and rows[2].startswith("| 2026-10-11 | `abc+12345678` | 5 (8, 1) ")
    assert (
        "| 0.750 | 0.750 | 0.333 | 1.000 / 0.500 / 1.000 | 0.500 | `unscripted_object` 1 |"
        in rows[2]
    )
    assert "| n/a / n/a / n/a |" in rows[3]


def test_a_report_round_trips_through_json() -> None:
    report = AuditReport("2026-10-11", "abc+12345678", ("v", "r"), "cmd", tuple(RUNS))
    assert from_json(to_json(report)) == report


def frame(label: Label | None, **kw: Any) -> LabelledFrame:
    return LabelledFrame(
        kw.get("frame", "frames/x.png"),
        kw.get("sha256", "0" * 64),
        "story",
        (0, 1),
        1,
        label,
        (),  # type: ignore[arg-type]
    )


def test_load_labels_refuses_an_unlabelled_frame_and_an_unknown_kind(tmp_path: Path) -> None:
    write_labels(tmp_path / "story" / "labels.json", [frame("correct"), frame(None, frame="b")])
    with pytest.raises(LabelError, match="1 unlabelled"):
        load_labels(tmp_path)
    (tmp_path / "story" / "labels.json").write_text(
        json.dumps([{"frame": "f", "sha256": "0", "shot": [0, 1], "attempt": 1, "label": "fine"}])
    )
    with pytest.raises(LabelError, match="unknown label 'fine'"):
        load_labels(tmp_path)


def test_labels_round_trip_and_sort_by_story_shot_attempt(tmp_path: Path) -> None:
    b = LabelledFrame("frames/b.png", "1" * 64, "s", (1, 2), 2, "unscripted", ("a second kite",))
    a = LabelledFrame("frames/a.png", "2" * 64, "s", (0, 3), 1, "correct", ())
    write_labels(tmp_path / "s" / "labels.json", [b, a])
    assert load_labels(tmp_path) == [a, b]


class Refusing:
    """A model that must never be called."""

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"the model was called ({name})")


async def test_a_frame_whose_bytes_changed_stops_the_run_before_any_model_call() -> None:
    screenplay = parse_text(*two_page_text())
    store = MemoryStore()
    await store.put("frames/x.png", b"other bytes", "image/png")
    labelled = frame("correct", sha256=hashlib.sha256(b"the labelled bytes").hexdigest())
    story = Story(screenplay, None, None)  # type: ignore[arg-type]
    with pytest.raises(LabelError, match="isn't the frame that was labelled"):
        await measure(Refusing(), store, [labelled], {"story": story}, 3)  # type: ignore[arg-type]


def test_an_audit_is_kept_with_its_failed_checks_in_enum_order_and_its_unscripted_names() -> None:
    description = described(
        objects=[
            {"name": "kite", "category": "other", "held": True},
            {"name": "bicycle", "category": "vehicle", "held": False},
        ]
    )
    judgement = judged(
        objects=[
            {"object": 0, "kind": "scripted_prop", "support": "kite"},
            {"object": 1, "kind": "unscripted", "support": None},
        ]
    )
    checks = (
        CheckResult(Check.TEXT_IN_FRAME, Severity.HARD, False, "text"),
        CheckResult(Check.UNSCRIPTED_OBJECT, Severity.HARD, False, "object 1"),
        CheckResult(Check.LIGHT, Severity.SOFT, True, ""),
    )
    audit = Audit(
        (0, 1), 1, 0, description, judgement, checks, Verdict.FAIL, {}, ("v",), Usage(100, 20, 0)
    )
    kept = audit_run(frame("injected_object"), 2, audit)
    assert kept.failed_checks == (Check.UNSCRIPTED_OBJECT, Check.TEXT_IN_FRAME)
    assert (kept.unscripted, kept.run, kept.tokens_in, kept.tokens_out) == (
        ("bicycle",),
        2,
        100,
        20,
    )
    errored = audit_run(
        frame("correct"),
        1,
        Audit((0, 1), 1, 0, None, None, (), Verdict.ERROR, {}, (), Usage(0, 0, 0)),
    )
    assert errored.error and errored.unscripted == ()


async def test_an_injected_frame_is_the_shot_prompt_plus_one_sentence_under_its_own_key() -> None:
    screenplay = parse_text(*two_page_text())
    extraction = extraction_of(screenplay, [("NANDI", "NANDI (60s, oilskin coat)")])
    ai, store = WorkersAI(), MemoryStore()
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(ai))
    kw: dict[str, Any] = dict(
        style=STYLE, store=store, screenplay=screenplay, extraction=extraction, client=client,
        account=ACCOUNT,
    )  # fmt: skip
    shot = shot_of(screenplay, 0, [0])
    real = await WorkersAIRenderer(**kw).render(shot, 1, 5, 1280, 720)
    injecting = InjectingRenderer("A bicycle leans against the wall.", **kw)
    injected = await injecting.render(shot, 1, 5, 1280, 720)
    assert injected.prompt == f"{real.prompt} A bicycle leans against the wall."
    assert form(ai.posts[1])["prompt"] == injected.prompt
    assert len(store.objects) == 2  # its own key: never the real frame's
    assert injecting.record((0, 1), 1).prompt.text() == real.prompt
    assert Image.open(io.BytesIO(injected.png)).size == (1280, 720)


def committed_reports() -> list[AuditReport]:
    paths = sorted(
        RESULTS.glob("audit-*.json"), key=lambda p: [int(n) for n in re.findall(r"\d+", p.stem)]
    )
    return [from_json(p.read_text(encoding="utf-8")) for p in paths]


def test_the_readme_audit_table_is_the_committed_reports() -> None:
    readme = (EVAL / "README.md").read_text(encoding="utf-8")
    reports = committed_reports()
    if reports:
        assert table(reports) in readme
    else:
        assert "## Frame-audit accuracy (T049)" in readme and "not measured yet" in readme


def test_every_committed_label_is_a_known_kind() -> None:
    if FRAMES.exists():
        for path in FRAMES.glob("*/labels.json"):
            for entry in json.loads(path.read_text(encoding="utf-8")):
                assert entry["label"] in {
                    None,
                    "correct",
                    "unscripted",
                    "injected_person",
                    "injected_object",
                }
