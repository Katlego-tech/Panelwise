# Design — `verify` (the frame audit and re-render loop)

**Status:** agreed · **Owner:** Katlego (Claude) · **Tasks:** T020 (audit), T021 (re-render loop, audit
log: the API), T061 (the log and the retry in the web app), T062 (the architecture check) · **Spec:** [SPEC.md](../../SPEC.md) US2 (frame audit)

---

## 1. What this covers

Checking every rendered frame against its shot before anyone sees it, re-rendering it when it
fails, and logging every verdict. This is where Non-negotiable I is enforced **on pixels**: a frame
that shows a person, prop or event the script doesn't put in that shot is never shown. Up to T026,
grounding is enforced on text; this is the first check on images.

**Not covered:** rendering (T026 provides the renderer this calls: storyboard.md), comic layout (comic.md reads
the audit's speaker positions), portraits (characters.md).

## 2. Reference material

| Kind | Where |
| --- | --- |
| The vision decision | docs/nebius-findings.md § The vision decision: **option A**: no Nemotron model on Token Factory accepts images (U7), so a vision model (`NEBIUS_MODEL_VISION`, DeepSeek-V4.1-Flash since 2026-09-30: GLM-5.3-Flash stopped receiving images, findings § U7 re-check) *describes* the frame and Nemotron *judges* it. Option B, a self-hosted NVIDIA VLM on the ComfyUI GPU, is a stretch |
| Prior art in FrameFlow | **none**: FrameFlow had no image audit, no verdicts and no automatic re-render; "regenerate" was a user button with a random seed |
| Inputs | `Shot` (shots.md §6: framing, characters, props, time_of_day, source, span); `Entity` quotes (grounding.md §6); `Scene.int_ext`, `location` (script.md §6); the rendered frame (T026) |
| LLM seam | `structured_chat`, `Tier.VISION` and `Tier.REASONING` (llm.md §6). Image content parts are OpenAI-style (`image_url` data URLs), as probed in U7 |
| Expected renders | `E[N] = (1 − (1−p)^(k+1)) / p` for pass rate `p` and `k` re-renders (docs/submission/about.md) |

## 3. Domain model

```mermaid
classDiagram
    class FrameDescription {
        +list~SeenPerson~ people
        +Setting setting
        +Light light
        +ShotSize shot_size
        +list~SeenObject~ objects
        +bool has_text
    }
    class SeenObject {
        +str name
        +ObjectCategory category
        +bool held
    }
    class SeenPerson {
        +Position position
        +str appearance
    }
    class Judgement {
        +list~PersonCall~ people
        +list~ObjectCall~ objects
    }
    class PersonCall {
        +int person
        +str|None character
        +str|None support
    }
    class ObjectCall {
        +int object
        +ObjectKind kind
        +str|None support
    }
    class CheckResult {
        +Check check
        +Severity severity
        +bool ok
        +str detail
    }
    class Audit {
        +tuple~int,int~ shot
        +int attempt
        +int seed
        +FrameDescription description
        +Judgement judgement
        +tuple~CheckResult~ checks
        +Verdict verdict
        +dict~str,Position~ positions
        +tuple~str~ models
        +Usage usage
    }
    class FrameOutcome {
        +tuple~int,int~ shot
        +FrameState state
        +RenderedFrame|None frame
        +tuple~Audit~ audits
    }
    FrameDescription --> SeenPerson
    FrameDescription --> SeenObject
    Judgement --> PersonCall
    Judgement --> ObjectCall
    Audit --> FrameDescription
    Audit --> Judgement
    Audit --> CheckResult
    FrameOutcome --> Audit
```

- **The describer is blind to the shot.** It gets the image and a neutral instruction: count the
  people, where each one stands, what they look like in a short phrase, interior or exterior, the
  light, the shot size, the notable objects (each with a category from a fixed list and whether
  someone holds it), and whether any text or letters appear. It is never told
  what it *should* see, so it can't simply agree.
- **The judge is Nemotron** (`Tier.REASONING`, Nemotron 3 Super, thinking on). It gets the shot's
  grounded spec (characters with their quotes, props, location, time of day, the verbatim `source`)
  and the description. It decides only what needs judgement: which described person is which
  character (or nobody), and whether each object is a scripted prop, set dressing, or unscripted.
- **`PersonCall.person` and `ObjectCall.object`** are 0-based indexes into the description's `people`
  and `objects`. The judgement must call **every** person and **every** object **exactly once**; a
  judgement that skips one, repeats one, or indexes out of range is invalid, and the audit is
  `ERROR` (the frame is withheld).
- **`support` must be verbatim.** When the judge says an unnamed person or an object is supported
  by the script ("a crowd gathers"), `support` must quote the shot's `source` or a quote of one of
  the shot's entities. Code checks the quote with `normalize_for_grounding` substring matching,
  exactly as the grounding filter does. **A support that isn't found counts as unscripted.** For
  `set_dressing`, `support` must instead quote the scene heading (the location words that make a
  stove plausible in a kitchen).
- **`positions`**: character → `left | centre | right`, from the judge's person calls (each character
  matches at most one person, so the position is unambiguous). Stored with the audit; the comic
  reads the accepted audit's positions (comic.md §4, `PanelFrame.positions`).

### The checks

| Check | Decided by | Severity | Fails when |
|---|---|---|---|
| `UNSCRIPTED_PERSON` | judge + code | **hard** | a described person is called with no character (or a name not in `shot.characters`) and has no verified `support`; **or** a character is called for more than one person (every person after the first called for it counts as unscripted) |
| `UNSCRIPTED_OBJECT` | judge + code | **hard** | an object called `unscripted`; `scripted_prop` without a verified `support`; or `set_dressing` when the object is `held`, or its category is `animal`, `vehicle`, `weapon`, `screen_or_sign` or `food`, or its `support` isn't found in the heading |
| `TEXT_IN_FRAME` | code | **hard** | `has_text` (letters in the art could be words the script never said) |
| `SETTING` | code | **hard** | `interior`/`exterior` contradicts `Scene.int_ext` (`INT_EXT` accepts either; `unclear` passes) |
| `MISSING_CHARACTER` | code | soft | a shot character **who is a person** matched to no described person (an animal character, `species` set, is described as an object: T052) |
| `LIGHT` | code | soft | `light` is `day` and the shot's time is night-family (`NIGHT`, `MIDNIGHT`, `EVENING`), or `light` is `night` and the time is day-family (`DAY`, `MORNING`, `AFTERNOON`). Transitional times (`DAWN`, `DUSK`, `SUNRISE`, `SUNSET`, `MAGIC HOUR`), a `None` time, `dawn_or_dusk` and `unclear` always pass |
| `FRAMING` | code | soft | `shot_size` is two or more steps from the shot's framing on wide → medium → close → extreme_close (`over_shoulder`, `pov` count as medium; `insert` as close); `unclear` passes |

**Verdict:** `FAIL` if any hard check fails; `WARN` if only soft checks fail; `PASS` otherwise. Hard
checks are the ones that would put something unscripted on screen; soft checks are quality
(an omission, a wrong light), logged and shown but not blocking.

## 4. Flow

```mermaid
sequenceDiagram
    participant J as Frame job
    participant R as Renderer (T026)
    participant D as Describer (VISION)
    participant N as Judge (Nemotron, REASONING)
    participant L as Audit log (Postgres)
    loop attempt 1 .. max_renders
        J->>R: render(shot, attempt)  (seed from shot + attempt)
        R-->>J: RenderedFrame
        J->>D: image + neutral instruction → FrameDescription
        J->>N: shot spec + description → Judgement
        J->>J: verify supports; run the checks; verdict
        J->>L: Audit (every attempt, pass or fail)
        alt PASS or WARN
            J-->>J: state PASSED / WARNED; stop
        else FAIL and attempts left
            J-->>J: next attempt
        end
    end
    J-->>J: out of attempts: WITHHELD
```

- **Seeds** are deterministic: `seed(shot, attempt)`, so an attempt can be reproduced.
- **`max_renders` = 3** (the first render plus two re-renders, `k = 2`). With a pass rate `p = 0.6`
  that's `E[N] ≈ 1.56` renders per frame; the real `p` comes from T049's measurement.
- **A withheld frame is never shown.** The storyboard shows its shot as a text card:
  the verbatim `source`, the span, and "Frame withheld: failed audit (unscripted person)". The user
  can ask for more attempts later; each is audited the same way. The comic has its own withheld
  card, without the source (its bubbles letter the dialogue): comic.md §4 step 6.

**Failure paths:** the describer or judge call fails (an `LLMError`, or `ValidationError` after the
repair retry) → that attempt's audit is `ERROR`, logged, and the frame is **withheld**, never passed
unaudited. The renderer fails → the frame job fails (a `Job` `FAILED`). A frame is never shown
without a `PASS` or `WARN` audit.

**Animal characters (T052).** An animal character (`animals(extraction)`, storyboard.md §3.1:
its own `species`, or bound to an animal by `match_speaker`) is drawn as an animal, and the describer files an animal under objects (`ObjectCategory.ANIMAL`). So the judge's
spec lists it under **"Animals in this shot"** (name, species, its quotes), not under "Characters
in this shot"; the judge prompt says an animal listed there is called `scripted_prop` with a
verbatim support quote that names it; people are matched only against the shot's person
characters (`match_speaker` over those); and `MISSING_CHARACTER` checks person characters only.
An unscripted animal is still `UNSCRIPTED_OBJECT` (hard), as before.

## 5. State

```mermaid
stateDiagram-v2
    [*] --> RENDERING
    RENDERING --> AUDITING
    AUDITING --> PASSED: PASS
    AUDITING --> WARNED: WARN
    AUDITING --> RENDERING: FAIL, attempts left
    AUDITING --> WITHHELD: FAIL, no attempts left
    AUDITING --> WITHHELD: audit ERROR
    RENDERING --> FAILED: renderer error
    RENDERING --> FAILED: interrupted by an API restart (startup sweep)
    AUDITING --> FAILED: interrupted by an API restart (startup sweep)
    WITHHELD --> RENDERING: user asks for another attempt
    FAILED --> RENDERING: user asks for another attempt
    PASSED --> [*]
    WARNED --> [*]
    FAILED --> [*]
```

`PASSED` and `WARNED` are the only states whose frame may be displayed. No transition skips
`AUDITING`. The two sweep edges (added with docs/design/web.md, 2026-09-30) are taken only by the
startup sweep, for frames whose job died with the process; T021 implements them. `FAILED →
RENDERING` (T066, 2026-10-10) is "Try another render" on a frame whose renderer failed or whose
render a restart cut off, as on a withheld one: a failed frame is no longer the end of the line,
since one passing renderer error no longer stops the storyboard (storyboard.md §4).

## 6. Contracts

```python
# app/verify/model.py
class Position(StrEnum): LEFT = "left"; CENTRE = "centre"; RIGHT = "right"
class Setting(StrEnum): INTERIOR = "interior"; EXTERIOR = "exterior"; UNCLEAR = "unclear"
class Light(StrEnum): DAY = "day"; NIGHT = "night"; DAWN_OR_DUSK = "dawn_or_dusk"; UNCLEAR = "unclear"
class ShotSize(StrEnum): WIDE = "wide"; MEDIUM = "medium"; CLOSE = "close"; EXTREME_CLOSE = "extreme_close"; UNCLEAR = "unclear"
class ObjectKind(StrEnum): SCRIPTED_PROP = "scripted_prop"; SET_DRESSING = "set_dressing"; UNSCRIPTED = "unscripted"
class ObjectCategory(StrEnum): FURNITURE = "furniture"; ARCHITECTURE = "architecture"; NATURE = "nature"; CLOTHING = "clothing"; ANIMAL = "animal"; VEHICLE = "vehicle"; WEAPON = "weapon"; SCREEN_OR_SIGN = "screen_or_sign"; FOOD = "food"; OTHER = "other"
class Check(StrEnum): UNSCRIPTED_PERSON; UNSCRIPTED_OBJECT; TEXT_IN_FRAME; SETTING; MISSING_CHARACTER; LIGHT; FRAMING   # value = the name in lower case
class Severity(StrEnum): HARD = "hard"; SOFT = "soft"
class Verdict(StrEnum): PASS = "pass"; WARN = "warn"; FAIL = "fail"; ERROR = "error"
class FrameState(StrEnum): RENDERING; AUDITING; PASSED; WARNED; WITHHELD; FAILED   # value = the name in lower case
@dataclass(frozen=True) class CheckResult: check: Check; severity: Severity; ok: bool; detail: str
@dataclass(frozen=True) class Audit: shot: tuple[int, int]; attempt: int; seed: int; description: FrameDescription | None; judgement: Judgement | None; checks: tuple[CheckResult, ...]; verdict: Verdict; positions: dict[str, Position]; models: tuple[str, ...]; usage: Usage
@dataclass(frozen=True) class FrameOutcome: shot: tuple[int, int]; state: FrameState; frame: RenderedFrame | None; audits: tuple[Audit, ...]

# app/verify/schema.py — the two model calls (strict json_schema)
class SeenPerson(BaseModel): position: Position; appearance: str
class SeenObject(BaseModel): name: str; category: ObjectCategory; held: bool
class FrameDescription(BaseModel): people: list[SeenPerson]; setting: Setting; light: Light; shot_size: ShotSize; objects: list[SeenObject]; has_text: bool
class PersonCall(BaseModel): person: int; character: str | None; support: str | None   # person: 0-based index into description.people
class ObjectCall(BaseModel): object: int; kind: ObjectKind; support: str | None        # object: 0-based index into description.objects
class Judgement(BaseModel): people: list[PersonCall]; objects: list[ObjectCall]

# The renderer T026 must provide (verify depends on this shape, nothing more)
@dataclass(frozen=True) class RenderedFrame: shot: tuple[int, int]; attempt: int; seed: int; png: bytes; width: int; height: int; prompt: str
class Renderer(Protocol):
    async def render(self, shot: Shot, attempt: int, seed: int, width: int, height: int) -> RenderedFrame: ...
    # width × height: the storyboard's 16:9 size, or a comic panel's rect (comic.md §4 step 6)

# app/verify/audit.py (T020)
async def describe_frame(model: NebiusChatModel, png: bytes) -> tuple[FrameDescription, ChatResult]: ...
#   the blind describer on its own (Tier.VISION, no shot details); audit_frame calls it, and so do
#   portraits (characters.md), which need only people and has_text
def seed_for(shot: Shot, attempt: int) -> int: ...          # int.from_bytes(sha256(f"{scene_index}:{number}:{attempt}").digest()[:4], "big")  (unsigned)
def run_checks(shot: Shot, scene: Scene, description: FrameDescription, judgement: Judgement,
               extraction: Extraction) -> tuple[tuple[CheckResult, ...], Verdict, dict[str, Position]]: ...   # pure
async def audit_frame(model: NebiusChatModel, frame: RenderedFrame, shot: Shot, screenplay: Screenplay,
                      extraction: Extraction) -> Audit: ...

# app/verify/loop.py (T021)
async def render_until_accepted(model: NebiusChatModel, renderer: Renderer, shot: Shot, screenplay: Screenplay,
                                extraction: Extraction, *, width: int, height: int, max_renders: int = 3,
                                first_attempt: int = 1,
                                log: Callable[[Audit], Awaitable[None]],
                                on_state: Callable[[FrameState, int], Awaitable[None]] | None = None) -> FrameOutcome: ...
#   on_state(state, attempt) is awaited on every §5 transition, before the work of the new state:
#   RENDERING and AUDITING for each attempt, then the terminal state. It is how web.md's `frames` rows
#   show a frame in progress (added with docs/design/web.md, 2026-09-30).
#   first_attempt (T021): attempts run first_attempt .. first_attempt + max_renders − 1, each seeded
#   seed_for(shot, attempt). The storyboard passes 1 and 3; "Try another render" on a frame withheld at
#   attempt n passes n + 1 and 1: one more audited attempt, reproducible like the rest.
#   Order, a contract: each attempt's `log(audit)` is awaited before the next on_state, so the terminal
#   state's writer can read the audit that decided it. An audit ERROR withholds at once (no retry).
#   A renderer exception is re-raised after on_state(FAILED, attempt): the caller fails its job.

# The renderer the frame writers need: a Renderer that remembers where it stored each attempt (T021).
class SupportsAsset(Protocol):
    @property
    def asset(self) -> str: ...                   # the attempt's Storage path, frames/<…>.png (read-only: a frozen dataclass fits)
class RecordingRenderer(Renderer, Protocol):
    def record(self, shot: tuple[int, int], attempt: int) -> SupportsAsset: ...
    # recorded before render() returns, so a lookup after it never misses; storyboard.md §6's
    # ComfyRenderer (its RenderRecord has .asset) and T062's SketchRenderer are both one
```

**Audit log table** (`frame_audits`, T021, migration `0004`, `lock_down` like every table, deploy.md
§6; one row per audited attempt, passed or not):

| Column | Type | Notes |
|---|---|---|
| `id` | uuid, primary key | |
| `project_id` | uuid, FK `projects` on delete cascade | so a frame's attempts across its jobs (the upload's, each retry's) are one indexed read |
| `job_id` | uuid, FK `jobs` on delete cascade | the job that ran the attempt |
| `target` | text, CHECK `storyboard`/`comic`, default `storyboard` | which frame was audited: the storyboard's 1280 × 720 frame or a comic panel at its rect (T064, migration `0005`, comic.md §4a). Rows written before 0005 are `storyboard` |
| `scene_index`, `shot_number`, `attempt` | int, `attempt ≥ 1` | **unique** `(project_id, target, scene_index, shot_number, attempt)` (`(project_id, scene_index, shot_number, attempt)` until 0005), which is also the read's index |
| `seed` | **bigint** | `seed_for` is an unsigned 32-bit value: it overflows `integer` |
| `frame_asset` | text | the attempt's Storage path; never sent to the web (only a `frames` row's accepted asset is, as a signed URL) |
| `description`, `judgement` | jsonb, null | null on an ERROR audit that didn't get that far |
| `checks` | jsonb list of `{check, severity, ok, detail}` | `[]` on an ERROR audit |
| `positions` | jsonb `{character: position}` | `{}` on an ERROR audit |
| `verdict` | text, CHECK `pass`/`warn`/`fail`/`error` | |
| `models` | jsonb list of model ids | |
| `prompt_tokens`, `completion_tokens` | int | `Audit.usage`'s two counts (reasoning tokens are inside completion's) |
| `created_at` | timestamptz, `clock_timestamp()` | |

Nothing in it quotes more of the script than the shot's own `source`. A frame's **last audit** is its
row with the greatest `attempt`. Every read for the storyboard (`audits_of`, `withheld_check`,
`FrameView.audits`) filters `target = 'storyboard'`; the comic job's rows are read by nothing in the
web app yet (comic.md §4a).

**T021's writers** (`app/frames/writer.py`). Each write is its own short transaction (a frame's state
must be visible while its job still runs). The `frames` row is written by exactly these hooks and the
restart sweep.

```python
class FrameWriter:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], project_id: uuid.UUID, job_id: uuid.UUID,
                 *, target: AuditTarget = AuditTarget.STORYBOARD): ...   # AuditTarget(StrEnum): STORYBOARD, COMIC (T064)
    async def log(self, audit: Audit, frame_asset: str) -> None: ...      # one frame_audits row, with the writer's target
    #   on_frame below raises ValueError on a COMIC writer: a comic panel has no frames row
    async def on_frame(self, shot: tuple[int, int], state: FrameState, attempt: int, asset: str | None) -> None: ...
    #   upserts the frames row and sets every column on every write: state, attempt, job_id; asset only
    #   for PASSED/WARNED, else null; withheld_check only for WITHHELD (from the frame's last audit: its
    #   first failed hard check in Check order, lower case, or "audit_error" when its verdict is ERROR),
    #   else null; failure "render" only for FAILED, else null. No column outlives its state.

def frame_hooks(writer: FrameWriter, renderer: RecordingRenderer, shot: tuple[int, int]
                ) -> tuple[Callable[[Audit], Awaitable[None]], Callable[[FrameState, int], Awaitable[None]]]: ...
#   (log, on_state) for render_until_accepted: log(audit) → writer.log(audit, renderer.record(shot, audit.attempt).asset);
#   on_state(state, attempt) → writer.on_frame(shot, state, attempt, renderer.record(shot, attempt).asset
#   if state is PASSED or WARNED else None). The one adapter: the retry uses it, and so does T026's
#   build_storyboard for its log and on_frame (storyboard.md §4), so the asset rule is stated once.
```

**The architecture check** (T062, `app/frames/check.py`): the loop end to end with no image model.

```python
class SketchRenderer:   # a RecordingRenderer
    def __init__(self, store: AssetStore): ...
    async def render(self, shot, attempt, seed, width, height) -> RenderedFrame: ...
    #   draws with Pillow at exactly width × height from random.Random(seed): a horizon, one to three
    #   figures, a box, pencil grey on paper; PNG with no metadata, so the same seed is the same bytes;
    #   stores it at frames/<sha256 of the PNG>.png (content address, put is idempotent) and records it
async def run_check(sessions, store: AssetStore, model: NebiusChatModel, project_id: uuid.UUID,
                    *, bucket: str, shots: int = 3) -> uuid.UUID: ...   # → the throwaway project's id
```

- **It never touches the project it is given.** It copies that project's screenplay, extraction and
  plan, and its `owner` and `pdf_path` (the same Storage object: nothing is re-uploaded), into a **new
  project** titled "{title} (architecture check)", with one
  `storyboard` job `DONE` (so the list shows it planned), and works only there. Its frames, a sketch
  that passes included, belong to that copy; delete the copy to discard them. A sketch the audit
  passes is a test artefact, not evidence of grounding: it shows the path an accepted frame takes.
- **It refuses** (`CheckRefused`, before writing anything) unless `bucket`, the store's bucket, which
  the command passes from `SUPABASE_STORAGE_BUCKET`, is `panelwise-dev` (the dev bucket, never the
  hosted demo's), and unless the source project exists and has a plan.
- For the copy's first `shots` shots **in plan order**, one `frame_attempt` job (`RUNNING` at stage
  `rendering`, `DONE` after the last shot, `FAILED` if a render raises) runs `render_until_accepted`
  with the **real** audit (`Tier.VISION` describer, `Tier.REASONING` judge: the only spend, two calls
  per attempt) through `frame_hooks`. `python -m app.frames.check <project-id> [--shots N]` builds
  the store and model from settings, calls `run_check`, and prints each shot's states and verdicts
  and the copy's id. Most sketches end `withheld` after three attempts: the path a wrong frame takes.

## 7. Structure

| Path | New? | Responsibility | Task |
| --- | --- | --- | --- |
| `services/api/app/verify/{__init__,model,schema,prompts,audit}.py` | new | `describe_frame` (also used by portraits), judge, checks, verdict | T020 |
| `services/api/app/verify/run.py` | new | live check: audit one PNG against one planned shot on the real account | T020 |
| `services/api/app/verify/loop.py` | new | render → audit → retry → state | T021 |
| `services/api/app/frames/{model,writer}.py` + migrations `0003` (`frames.failure`), `0004` (`frame_audits`) | new | `FrameAuditRow`, `FrameWriter`, `frame_hooks` | T021 |
| `services/api/app/frames/check.py` | new | `SketchRenderer`, `run_check`, `python -m app.frames.check` | T062 |
| web: the audit log view (per shot: attempts, verdicts, checks) | new | built to web.md §4.4 step 5 | T061 |
| `services/api/tests/{verify,frames}/` | new | §9 | T020, T021, T062 |

## 8. Decisions & alternatives

| Decision | Chosen | Rejected, and why |
|---|---|---|
| Who sees the image | a vision model, blind to the shot | Nemotron directly: no Token Factory Nemotron accepts images (U7); telling the describer what to expect: it would agree |
| Who judges | Nemotron (reasoning tier) + code | the vision model judging itself: not NVIDIA, and it already saw the image without the spec, which is the point |
| Countable checks | code | the judge counting: code is exact and free |
| Where a comic panel's attempts are logged (T064) | `frame_audits` with a `target` column | a second `comic_audits` table: the same columns twice, and two writers to keep in step; logging nothing: every attempt is kept (§4), a comic panel's too |
| "Supported by the script" | only with a verbatim quote, verified in code | trusting the judge's say-so: the same failure the grounding filter exists to stop |
| After the last failed attempt | withhold the frame | show the "best" failed frame: that shows something unscripted |
| Audit error | withhold | pass unaudited: the one outcome this module exists to prevent |
| Re-render feedback | a new seed | feeding the failed checks into the prompt: SDXL-Turbo at cfg 1 ignores negative prompts (FrameFlow's own config note); revisit with the T003 model |
| Hard vs soft | hard = would show something unscripted; soft = quality | failing on every soft miss: burns renders on lighting a storyboard can live with |

**Accepted residual risk:** the audit can only judge what the describer reports. A person or object
the describer misses passes unseen. T049 measures exactly this (recall on frames with a deliberately
injected extra person or object); if it's poor, the describer prompt or model changes, or option B.

Deviations from [docs/architecture-defaults.md](../architecture-defaults.md): none. Wording for the
pitch and README (per the vision decision): *"a vision model describes each frame; Nemotron audits
it against the script."*

## 9. How this is verified

- `run_checks` (pure) on hand-built descriptions and judgements: every check's pass and fail —
  including **two people called as one character** (the second is unscripted), a name not in the
  shot, a skipped or repeated index (`ERROR`), a held object or an animal called `set_dressing`,
  every `LIGHT` family and exemption, `unclear` framing — each
  severity's effect on the verdict, `support` quotes verified (and a fake support counted as
  unscripted), `INT_EXT` and `unclear` passing, positions derived.
- `audit_frame` with `httpx2.MockTransport`: the describer call carries the image and **no** shot
  details; the judge call carries the spec and the description; `VISION` then `REASONING` tiers.
- `render_until_accepted` with a fake renderer: pass first time; fail then pass; three fails →
  `WITHHELD`; an audit error → `WITHHELD`; every attempt logged; deterministic seeds.
- **Accuracy (T049, eval.md):** a labelled set of frames, including ones rendered with a deliberately
  injected extra person or object, gives the audit's precision and recall for the README.

## 10. Open questions

- [x] Does the describer honour `json_schema`? **Answered 2026-09-30 (T020):** GLM-5.3-Flash turned out
  not to receive images at all (findings § U7 re-check), so the describer is now DeepSeek-V4.1-Flash,
  which returned schema-valid descriptions on every live call, no repair needed.
- [ ] How reliable is the describer's `shot_size`? If noisy, `FRAMING` stays soft (it is) or is
  dropped. In T020's three live runs it matched what the frames show.
- [ ] **Precision on correct frames (for T049).** Live, the describer filed plates and bowls under
  `food`, which can never be set dressing, and set `has_text` on two of three frames whose only candidates are papers and plans on a table. Both
  push a frame toward FAIL, the safe side, but a good frame could burn its renders. T049 measures the
  false-FAIL rate; if it's high, the category list or the describer prompt changes, not the rule.
- [ ] Option B (a self-hosted NVIDIA VLM on the ComfyUI GPU) would let Nemotron-family models see
  the image directly; revisit once T003's GPU exists.
