"""Frame-audit accuracy on labelled frames, on the real account (docs/design/eval.md §6a; T049).

    cd services/api && uv run python -m tools.audit_eval collect <project-id> <story>
    cd services/api && uv run python -m tools.audit_eval inject <story> <scene.shot> \
        (--person|--object) TEXT --seed N
    cd services/api && uv run python -m tools.audit_eval run [--runs N] [--out PATH]

`collect` writes a project's story and one unlabelled entry per audited attempt; nothing is called.
`inject` draws a shot's prompt plus one sentence on Workers AI (neurons) and labels it. `run` audits
every labelled frame N times (default 3) on Token Factory, writes eval/results/audit-<date>.json and
prints the table eval/README.md carries. Labels are checked by a person before `run`.
"""

import asyncio
import hashlib
import json
import subprocess
import sys
import uuid
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal, cast, get_args

import httpx2

from app.core.config import Settings
from app.grounding import Extraction
from app.llm import NebiusChatModel
from app.projects.codec import (
    dump_extraction,
    dump_plan,
    dump_screenplay,
    load_extraction,
    load_plan,
    load_screenplay,
)
from app.script import Screenplay
from app.shots import Shot, ShotPlan
from app.storage import AssetStore, SupabaseStore
from app.storyboard.prompt import build_frame_prompt
from app.storyboard.styles import PUBLIC_STYLES, load_styles
from app.storyboard.workers_ai import WorkersAIAccount, WorkersAIRenderer
from app.verify import prompts
from app.verify.audit import audit_frame
from app.verify.model import Audit, Check, ObjectKind, RenderedFrame, Verdict
from tools.evaluate import EVAL

type Label = Literal["correct", "unscripted", "injected_person", "injected_object"]
LABELS: tuple[str, ...] = get_args(Label.__value__)
FRAMES = EVAL / "frames"
RESULTS = EVAL / "results"
WIDTH, HEIGHT = 1280, 720  # the storyboard's frame (storyboard.md §6)
EXPECTED: dict[str, Check] = {  # the check an injected frame should fail for (§6a.1)
    "injected_person": Check.UNSCRIPTED_PERSON,
    "injected_object": Check.UNSCRIPTED_OBJECT,
}


class LabelError(ValueError):
    """labels.json can't be measured yet: an unlabelled frame or an unknown kind."""


@dataclass(frozen=True)
class LabelledFrame:
    frame: str
    sha256: str
    story: str
    shot: tuple[int, int]
    attempt: int
    label: Label | None
    seen: tuple[str, ...]
    note: str = ""


@dataclass(frozen=True)
class AuditRun:
    frame: str
    shot: tuple[int, int]
    label: Label
    run: int
    verdict: Verdict
    failed_checks: tuple[Check, ...]
    unscripted: tuple[str, ...]
    tokens_in: int
    tokens_out: int
    error: str | None


@dataclass(frozen=True)
class AuditSummary:
    frames: int
    runs: int
    errors: int
    true_fail: int
    false_fail: int
    missed: int
    true_pass: int
    precision: float
    recall: float
    false_fail_rate: float
    recall_by_label: dict[str, float]
    right_reason: float
    false_fail_checks: dict[str, int]


@dataclass(frozen=True)
class AuditReport:
    date: str
    variant: str
    models: tuple[str, ...]
    command: str
    runs: tuple[AuditRun, ...]


# --- labels ---------------------------------------------------------------------------------------


def _frame_of(data: dict[str, Any], story: str) -> LabelledFrame:
    label = data.get("label")
    if label is not None and label not in LABELS:
        raise LabelError(f"{story}: {data.get('frame')} has an unknown label {label!r}")
    return LabelledFrame(
        frame=str(data["frame"]),
        sha256=str(data["sha256"]),
        story=story,
        shot=(int(data["shot"][0]), int(data["shot"][1])),
        attempt=int(data["attempt"]),
        label=cast(Label | None, label),
        seen=tuple(str(s) for s in data.get("seen", ())),
        note=str(data.get("note", "")),
    )


def read_labels(path: Path) -> list[LabelledFrame]:
    """One story's labels.json, as written (unlabelled entries included)."""
    entries: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    return [_frame_of(e, path.parent.name) for e in entries]


def load_labels(root: Path) -> list[LabelledFrame]:
    """Every eval/frames/*/labels.json, sorted by story, shot and attempt. Refuses an unlabelled
    frame: `run` measures only what a person has labelled."""
    frames = [f for path in sorted(root.glob("*/labels.json")) for f in read_labels(path)]
    unlabelled = [f"{f.story}: {f.frame}" for f in frames if f.label is None]
    if unlabelled:
        raise LabelError(f"{len(unlabelled)} unlabelled: {', '.join(unlabelled[:5])}")
    return sorted(frames, key=lambda f: (f.story, f.shot, f.attempt, f.frame))


def known_frames(root: Path) -> set[str]:
    """Every frame already in any story's labels.json under `root`."""
    return {f.frame for path in root.glob("*/labels.json") for f in read_labels(path)}


def write_labels(path: Path, frames: Sequence[LabelledFrame]) -> None:
    entries = [
        {k: v for k, v in asdict(f).items() if k != "story"} | {"shot": list(f.shot)}
        for f in frames
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# --- summary and table ----------------------------------------------------------------------------


def _ratio(n: int, d: int) -> float:
    return round(n / d, 3) if d else 0.0


def _failed(run: AuditRun) -> bool:
    return run.verdict is Verdict.FAIL


def summarise(runs: Sequence[AuditRun]) -> AuditSummary:
    """§6a.4: ERROR runs are counted but never in a rate; FAIL is the positive."""
    judged = [r for r in runs if r.verdict is not Verdict.ERROR]
    bad = [r for r in judged if r.label != "correct"]
    good = [r for r in judged if r.label == "correct"]
    true_fail = sum(map(_failed, bad))
    false_fail = sum(map(_failed, good))
    by_label: dict[str, float] = {}
    for label in LABELS[1:]:
        of = [r for r in bad if r.label == label]
        if of:
            by_label[label] = _ratio(sum(map(_failed, of)), len(of))
    caught = [r for r in bad if _failed(r) and r.label in EXPECTED]
    right = sum(EXPECTED[r.label] in r.failed_checks for r in caught)
    checks: dict[str, int] = {}
    for r in good:
        if _failed(r):
            for c in r.failed_checks:
                checks[c.value] = checks.get(c.value, 0) + 1
    return AuditSummary(
        frames=len({r.frame for r in runs}),
        runs=len(runs),
        errors=len(runs) - len(judged),
        true_fail=true_fail,
        false_fail=false_fail,
        missed=len(bad) - true_fail,
        true_pass=len(good) - false_fail,
        precision=_ratio(true_fail, true_fail + false_fail),
        recall=_ratio(true_fail, len(bad)),
        false_fail_rate=_ratio(false_fail, len(good)),
        recall_by_label=by_label,
        right_reason=_ratio(right, len(caught)),
        false_fail_checks=dict(sorted(checks.items(), key=lambda kv: (-kv[1], kv[0]))),
    )


HEADER = (
    "| Date | Variant | Frames (runs, errors) | Precision | Recall | False-FAIL rate "
    "| Recall: unscripted / person / object | Right reason | Top false-FAIL checks |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"
)


def table(reports: Sequence[AuditReport]) -> str:
    """One row per report, in the order given (§6a.5)."""
    rows = [HEADER]
    for report in reports:
        s = summarise(report.runs)
        per = " / ".join(
            f"{s.recall_by_label[k]:.3f}" if k in s.recall_by_label else "n/a" for k in LABELS[1:]
        )
        top = ", ".join(f"`{c}` {n}" for c, n in list(s.false_fail_checks.items())[:3]) or "none"
        rows.append(
            f"| {report.date} | `{report.variant}` | {s.frames} ({s.runs}, {s.errors}) "
            f"| {s.precision:.3f} | {s.recall:.3f} | {s.false_fail_rate:.3f} | {per} "
            f"| {s.right_reason:.3f} | {top} |"
        )
    return "\n".join(rows)


def to_json(report: AuditReport) -> str:
    return json.dumps(asdict(report), indent=2, ensure_ascii=False) + "\n"


def from_json(text: str) -> AuditReport:
    data = json.loads(text)
    runs = tuple(
        AuditRun(
            frame=r["frame"],
            shot=(r["shot"][0], r["shot"][1]),
            label=r["label"],
            run=r["run"],
            verdict=Verdict(r["verdict"]),
            failed_checks=tuple(Check(c) for c in r["failed_checks"]),
            unscripted=tuple(r["unscripted"]),
            tokens_in=r["tokens_in"],
            tokens_out=r["tokens_out"],
            error=r["error"],
        )
        for r in data["runs"]
    )
    return AuditReport(data["date"], data["variant"], tuple(data["models"]), data["command"], runs)


def audit_run(frame: LabelledFrame, run: int, audit: Audit) -> AuditRun:
    """One audit as the report keeps it (pure)."""
    assert frame.label is not None
    unscripted: tuple[str, ...] = ()
    if audit.description is not None and audit.judgement is not None:
        objects = audit.description.objects
        unscripted = tuple(
            objects[c.object].name
            for c in audit.judgement.objects
            if c.kind is ObjectKind.UNSCRIPTED and 0 <= c.object < len(objects)
        )
    failed = {c.check for c in audit.checks if not c.ok}
    return AuditRun(
        frame=frame.frame,
        shot=frame.shot,
        label=frame.label,
        run=run,
        verdict=audit.verdict,
        failed_checks=tuple(c for c in Check if c in failed),
        unscripted=unscripted,
        tokens_in=audit.usage.prompt_tokens,
        tokens_out=audit.usage.completion_tokens,
        error="the audit couldn't run" if audit.verdict is Verdict.ERROR else None,
    )


def variant() -> str:
    """The code and the audit's prompts the report measured (§6a.4)."""
    words = (prompts.DESCRIBE_PROMPT + prompts.JUDGE_PROMPT).encode()
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except OSError, subprocess.CalledProcessError:
        sha = "nogit"
    return f"{sha}+{hashlib.sha256(words).hexdigest()[:8]}"


# --- the three commands ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Story:
    screenplay: Screenplay
    extraction: Extraction
    plan: ShotPlan

    def shot(self, key: tuple[int, int]) -> Shot:
        return next(s for s in self.plan.shots if (s.scene_index, s.number) == key)


def load_story(root: Path, story: str) -> Story:
    data = json.loads((root / story / "story.json").read_text(encoding="utf-8"))
    return Story(
        load_screenplay(data["screenplay"]),
        load_extraction(data["extraction"]),
        load_plan(data["plan"]),
    )


def _store(settings: Settings, client: httpx2.AsyncClient) -> SupabaseStore:
    return SupabaseStore(
        url=settings.supabase_url,
        secret_key=settings.supabase_secret_key,
        bucket=settings.supabase_storage_bucket,
        client=client,
    )


async def collect(project_id: uuid.UUID, story: str, *, root: Path = FRAMES) -> int:
    from app.db import make_engine, make_sessions
    from app.frames.repo import audits_of
    from app.projects.model import ProjectRow

    settings = Settings()
    engine = make_engine(settings)
    try:
        async with make_sessions(engine)() as session:
            row = await session.get(ProjectRow, project_id)
            if row is None or None in (row.screenplay, row.extraction, row.plan):
                print("that project has no plan", file=sys.stderr)
                return 2
            audits = await audits_of(session, project_id)
            story_data = {
                "project": str(project_id),
                "screenplay": dump_screenplay(load_screenplay(row.screenplay)),
                "extraction": dump_extraction(load_extraction(row.extraction)),
                "plan": dump_plan(load_plan(row.plan)),
            }
    finally:
        await engine.dispose()
    folder = root / story
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "story.json").write_text(
        json.dumps(story_data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    path = folder / "labels.json"
    known = read_labels(path) if path.exists() else []
    # A frame drawn once and audited in two projects (a store hit) is measured once (§6a.2).
    have = known_frames(root)
    added: list[LabelledFrame] = []
    async with httpx2.AsyncClient(timeout=60) as client:
        store = _store(settings, client)
        for rows in audits.values():
            for a in rows:
                if a.frame_asset in have:
                    continue
                png = await store.get(a.frame_asset)
                added.append(
                    LabelledFrame(
                        a.frame_asset,
                        hashlib.sha256(png).hexdigest(),
                        story,
                        (a.scene_index, a.shot_number),
                        a.attempt,
                        None,
                        (),
                    )
                )
                have.add(a.frame_asset)
    write_labels(path, [*known, *added])
    print(f"{story}: {len(added)} frames added, {len(known) + len(added)} in {path}")
    return 0


async def inject(
    story: str, key: tuple[int, int], label: Label, text: str, seed: int, *, root: Path = FRAMES
) -> int:
    settings = Settings()
    account = WorkersAIAccount.from_settings(settings)
    if account is None:
        print("CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN are needed.", file=sys.stderr)
        return 2
    told = load_story(root, story)
    shot = told.shot(key)
    private = settings.panelwise_private_styles
    style = load_styles(PUBLIC_STYLES, Path(private) if private else None).get(None)
    async with httpx2.AsyncClient(timeout=60) as client:
        renderer = InjectingRenderer(
            text,
            style=style,
            store=_store(settings, client),
            screenplay=told.screenplay,
            extraction=told.extraction,
            client=client,
            account=account,
            max_words=settings.render_max_words,
        )
        frame = await renderer.render(shot, 1, seed, WIDTH, HEIGHT)
    record = renderer.record(key, 1)
    path = root / story / "labels.json"
    known = read_labels(path) if path.exists() else []
    entry = LabelledFrame(
        record.asset,
        hashlib.sha256(frame.png).hexdigest(),
        story,
        key,
        1,
        label,
        (text,),
        f"injected, seed {seed}",
    )
    write_labels(path, [*[f for f in known if f.frame != entry.frame], entry])
    print(f"{record.asset} ({'stored already' if record.cached else f'{record.neurons} neurons'})")
    return 0


class InjectingRenderer(WorkersAIRenderer):
    """The real renderer with one sentence appended to every prompt (§6a.3). The render key covers
    the prompt as sent, so an injected frame never collides with a real one."""

    def __init__(self, sentence: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.sentence = sentence

    async def render(
        self, shot: Shot, attempt: int, seed: int, width: int, height: int
    ) -> RenderedFrame:
        prompt = build_frame_prompt(
            shot, self.screenplay, self.extraction, self.style, max_words=self.max_words
        )
        return await self.render_text(
            shot, attempt, seed, width, height, f"{prompt.text()} {self.sentence}", prompt
        )


def result_path(day: str, root: Path = RESULTS) -> Path:
    base = root / f"audit-{day}"
    path, n = base.with_suffix(".json"), 1
    while path.exists():
        n += 1
        path = base.parent / f"{base.name}-{n}.json"
    return path


async def measure(
    model: NebiusChatModel,
    store: AssetStore,
    frames: Sequence[LabelledFrame],
    stories: dict[str, Story],
    runs: int,
) -> list[AuditRun]:
    """Every frame's bytes checked first (exit before any model call), then each audited `runs`
    times, sequentially."""
    pngs: dict[str, bytes] = {}
    for f in frames:
        png = await store.get(f.frame)
        if hashlib.sha256(png).hexdigest() != f.sha256:
            raise LabelError(f"{f.story}: {f.frame} isn't the frame that was labelled")
        pngs[f.frame] = png
    out: list[AuditRun] = []
    for f in frames:
        story = stories[f.story]
        shot = story.shot(f.shot)
        rendered = RenderedFrame(f.shot, f.attempt, 0, pngs[f.frame], WIDTH, HEIGHT, "")
        for n in range(1, runs + 1):
            audit = await audit_frame(model, rendered, shot, story.screenplay, story.extraction)
            out.append(audit_run(f, n, audit))
            print(
                f"{f.story} {f.shot} a{f.attempt} [{f.label}] run {n}: {audit.verdict}", flush=True
            )
    return out


async def run(runs: int, out: Path | None, argv: list[str], *, root: Path = FRAMES) -> int:
    try:
        frames = load_labels(root)
    except LabelError as exc:
        print(f"FAIL  {exc}", file=sys.stderr)
        return 2
    stories = {s: load_story(root, s) for s in {f.story for f in frames}}
    settings = Settings()
    model = NebiusChatModel.from_settings(settings)
    try:
        async with httpx2.AsyncClient(timeout=60) as client:
            try:
                results = await measure(model, _store(settings, client), frames, stories, runs)
            except LabelError as exc:
                print(f"FAIL  {exc}", file=sys.stderr)
                return 2
    finally:
        await model.aclose()
    day = date.today().isoformat()
    path = out or result_path(day)
    report = AuditReport(
        day,
        variant(),
        (settings.nebius_model_vision, settings.nebius_model_reasoning),
        " ".join(["uv run python -m tools.audit_eval run", *argv]),
        tuple(results),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_json(report), encoding="utf-8")
    print(f"\nwrote {path}\n\n{table([report])}")
    return 0


def _shot_key(value: str) -> tuple[int, int] | None:
    """`2.4` as the web names it (scene from 1) → (scene_index, number)."""
    scene, _, number = value.partition(".")
    if not (scene.isdigit() and number.isdigit()) or int(scene) < 1:
        return None
    return int(scene) - 1, int(number)


async def main(argv: list[str]) -> int:
    match argv:
        case ["collect", project, story]:
            try:
                return await collect(uuid.UUID(project), story)
            except ValueError:
                pass
        case ["inject", story, shot, ("--person" | "--object") as kind, text, "--seed", seed] if (
            seed.isdigit() and (key := _shot_key(shot)) is not None
        ):
            label: Label = "injected_person" if kind == "--person" else "injected_object"
            return await inject(story, key, label, text, int(seed))
        case ["run", *rest]:
            runs, out, args = 3, None, iter(rest)
            ok = True
            for arg in args:
                value = next(args, "")
                if arg == "--runs" and value.isdigit() and int(value) > 0:
                    runs = int(value)
                elif arg == "--out" and value and not value.startswith("--"):
                    out = Path(value)
                else:
                    ok = False
            if ok:
                return await run(runs, out, rest)
        case _:
            pass
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
