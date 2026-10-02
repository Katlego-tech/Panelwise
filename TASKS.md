# `Panelwise` — Tasks

**Plan:** [PLAN.md](PLAN.md) · **Spec:** [SPEC.md](SPEC.md) · **Designs:** [docs/design/](docs/design/)

> One of the three shared-state files (with [AGENTS.md](AGENTS.md) and [STATUS.md](STATUS.md)).
> **One writer per task** — claim it in STATUS.md before you start.

---

## How tasks are written here

A task is a **contract**, not a reminder. The person writing it and the person (or AI) building it
are usually not the same, and the builder will implement *exactly* what the task specifies — so a
task that under-specifies gets you something plausible-looking and wrong: the right file with a
`TODO` in it, a component that renders *a* screen rather than *the* screen, a function with the
agreed name and a stubbed body.

**The task is under-specified if a competent implementer who read nothing else could build
something structurally different from what you intend.** When that's true, the fix is not a longer
sentence — it's a design doc ([docs/design-documentation.md](docs/design-documentation.md)) and a
reference to it.

### Anatomy

```
- [ ] T0nn [P] [US1] <imperative one-line summary>
      Design:  docs/design/<lane>.md §<section>        <- the structure to build to
      Files:   <paths this task creates or changes>
      Contract:<exact signature / schema / props — or the design §ref that has it>
      Verify:  <the command or check that proves it works>
      Done:    <the observable end state, in the user's or caller's terms>
```

| Field | Required when | Why it's there |
| --- | --- | --- |
| **Design** | the task creates structure (types, services, screens, flows) | gives the implementer a diagram to build to instead of a guess |
| **Files** | always, unless genuinely unknowable | stops two lanes colliding; makes "did it touch the right thing" reviewable |
| **Contract** | anything another lane or task consumes | lets parallel lanes compose instead of each inventing an interface |
| **Verify** | always | a task with no check is a task nobody can close honestly |
| **Done** | always | phrased as an outcome, so "the file exists" can't pass for "it works" |

### Rules

1. **No placeholder deliverables.** A task may not be closed with `TODO`, `FIXME`, `pass`,
   `NotImplementedError`, an empty component, hard-coded fake data standing in for a real call, or
   a function that returns a constant to make a test green. If the real thing can't be built yet,
   the task is **blocked**, not done — say so in STATUS.md and name what unblocks it.
   *The one exception:* a deliberately stubbed dependency that the task text names as a stub, with
   a follow-up task ID already written for replacing it.
2. **Every task is a vertical slice.** "Create the module skeleton" is not a task; "parse a
   pain.001 payload into a `Transfer` and reject a malformed one" is. Scaffolding is part of the
   first behavioural task, not a task of its own.
3. **Sized to one sitting.** If a task can't be finished and verified in one working session,
   split it. Long tasks are where placeholders come from — the implementer runs out of room and
   leaves a marker.
4. **Tests first, and the test must fail for the right reason.** A test that passes against an
   empty implementation is not a test. Write it, watch it fail, then implement.
5. **UI tasks name their visual reference by path.** Never "build the dashboard" — always "build
   the dashboard in `<path>/screen.png`, matching layout, tokens and copy". See
   [docs/design-documentation.md](docs/design-documentation.md) § UI is a special case.
6. **One story label per task.** If a task serves two user stories, it's two tasks.
7. **`[P]` means genuinely parallel** — disjoint files *and* no unmet dependency. If two `[P]`
   siblings both touch the same file, one of them is mislabelled.

### Good vs. bad

> ❌ `- [ ] T014 [US2] Build the compliance dashboard`
>
> Produces: *a* dashboard. Some cards, some invented metrics, a chart library nobody chose.
>
> ✅
> ```
> - [ ] T014 [US2] Build the Compliance Health Dashboard screen
>       Design:  docs/design/compliance-ui.md §3 (component tree), §2 (reference)
>       Files:   apps/web/src/pages/ComplianceDashboard.tsx, apps/web/src/components/compliance/*
>       Contract:consumes GET /api/compliance/health -> ComplianceHealth (docs/design/compliance-ui.md §6)
>       Verify:  npm test -w apps/web && npm run dev, compare against legacy/mockups/compliance/screen.png
>       Done:    all six modules from the mockup render with live data from the endpoint; no
>                hard-coded metric values remain in the component
> ```

---

## Legend

Format: `[ID] [P?] [Story] Description`

- **[ID]** — task identifier `Tnnn`, monotonically increasing, never reused.
- **[P]** — parallelizable: touches different files from its siblings and has no unmet dependency.
- **[Story]** — the label the task serves (`US1`–`USn`, `SET` setup, `FND` foundational,
  `DSN` design/documentation, `POL` polish).
- Commit format: `feat(scope): Tnnn short description` (e.g. `feat(audio): T041 add HIP whisper loader`).

Each user-story phase is ordered **Design → Tests FIRST (must FAIL) → Implementation → Checkpoint**.

---

## Phase 1 — Setup and foundations

> One line per task for now. **Whoever claims a task expands it to the full
> `Design/Files/Contract/Verify/Done` format in the same PR, before writing code.** "Port from"
> names the FrameFlow source; the porter adds a row to the table in
> [CHANGES-FROM-FRAMEFLOW.md](CHANGES-FROM-FRAMEFLOW.md).

- [x] T001 [FND] **Token Factory check.** Answer U1–U7 with real calls against our account and write the answers to `docs/nebius-findings.md`. Lane `llm`.
      Design:  none (research, no structure). Questions U1–U6 come from `frameflow-nebius-hackathon/PLAN.md` §3; U7 is Panelwise's own: is a vision model served, and does it accept an image in a chat message?
      Files:   docs/nebius-findings.md, .env.example (model IDs and hosts corrected to what answered)
      Contract:for each of U1–U7, `docs/nebius-findings.md` gives: the verdict, the exact request (key redacted), the relevant part of the raw response, and the consequence for T004 / `verify`. It closes with the settled values for every `NEBIUS_*` variable in `.env.example`.
      Verify:  every verdict cites a response captured on or after 2026-09-28; `.env.example` model IDs all appear in `GET /v1/models` output recorded in the doc
      Done:    T004's implementer can write the provider without making a single exploratory call, and STATUS.md's "vision model?" risk is closed or turned into a named plan
- [x] T002 [P] [SET] **Versions + local stack.** Pin Python/Node, `services/api/pyproject.toml` (uv), Next.js app in `apps/web`, `docker-compose.yml` (postgres, redis, api, web). CI green on the gate. Lane `infra`.
      Design:  PLAN.md § Technical Context (versions, stack) and § Project structure (paths). No new entities.
      Files:   services/api/{pyproject.toml,uv.lock,.python-version,Dockerfile,app/main.py,app/core/config.py,app/api/v1/health.py,tests/test_health.py}; apps/web/{package.json,pnpm-lock.yaml,Dockerfile,next.config.ts,tsconfig.json,eslint.config.mjs,vitest.config.ts,app/api/health/route.ts,app/api/health/route.test.ts}; docker-compose.yml; .github/workflows/ci.yml (versions); PLAN.md (versions row)
      Contract:API `GET /api/v1/health` pings Postgres (`SELECT 1`) and Redis (`PING`) → 200 `{"status":"ok","checks":{"postgres":"ok","redis":"ok"}}`; any failure → 503, `"status":"degraded"`, the failing check reads `"error: <ExceptionType>"` (no connection strings or messages leak). Web `GET /api/health` calls `${API_URL}/api/v1/health` → mirrors its status code with `{"web":"ok","api":<api body>}`; API unreachable → 502 `{"web":"ok","api":null,"error":"api unreachable"}`.
      Verify:  bash scripts/gate.sh (ruff, pyright, pytest, eslint, tsc, vitest, build, osv, jscpd all run); docker compose up --build --wait, then curl localhost:3000/api/health → 200 with both checks "ok"; docker compose stop redis → 503 with redis "error: …"
      Done:    `docker compose up` brings up all four services healthy on pinned versions, and the gate runs real checks on both projects (count > 2) locally and in CI
- [ ] T003 [P] [SET] **ComfyUI on a Nebius GPU.** Bring up ComfyUI on Nebius AI Cloud, record cost/hour and seconds per frame in `infra/nebius/README.md`. Lane `infra`.
- [x] T004 [FND] **Nebius provider with tiers.** Fast, reasoning and vision tiers, per-call `tier=`, `structured_chat` + repair retry, strip `<think>`. Port from `app/services/llm_provider.py`, `openai_compat.py`. Depends on T001. Lane `llm`.
      Design:  docs/design/llm.md (all sections); measured behaviour in docs/nebius-findings.md
      Files:   services/api/app/llm/{__init__,client,structured,smoke}.py; services/api/app/core/config.py; services/api/tests/llm/*; CHANGES-FROM-FRAMEFLOW.md (ported rows)
      Contract:docs/design/llm.md §6, verbatim
      Verify:  bash scripts/gate.sh (tests use httpx.MockTransport, no network); uv run python -m app.llm.smoke answers on FAST and REASONING with FAST reasoning_tokens == 0
      Done:    T006 can call `await structured_chat(model, messages, Extraction, Tier.FAST)` and get a validated object plus the model that answered and its token usage, on the real account
- [x] T005 [P] [FND] **Script module.** Port from `screenplay_parser.py`, `scene_time.py`, `dialogue_linker.py`. Lane `script+grounding`.
      Design:  docs/design/script.md (all sections)
      Files:   services/api/app/script/{__init__,model,parser,scene_time,speakers}.py; services/api/tests/script/*; services/api/pyproject.toml (pdfplumber; fpdf2 dev); CHANGES-FROM-FRAMEFLOW.md (ported rows)
      Contract:docs/design/script.md §6, verbatim
      Verify:  bash scripts/gate.sh; the end-to-end test parses a 2-page self-written PDF built with fpdf2 into the expected scenes, and every element's Span slices back to its own text
      Done:    `parse_pdf(bytes)` returns ordered scenes whose every action and dialogue element names the page and lines it came from; `resolve_times` and `match_speaker` are ready for T006/T007
- [x] T006 [FND] **Grounding module.** Port from `extraction_service.py`, `grounding.py`, `governance_service.py`; runs on Nemotron. Depends on T004, T005. Lane `script+grounding`.
      Design:  docs/design/grounding.md (all sections)
      Files:   services/api/app/grounding/{__init__,model,text,schema,filter,extract,run}.py; services/api/tests/grounding/*; CHANGES-FROM-FRAMEFLOW.md (ported rows)
      Contract:docs/design/grounding.md §6, verbatim
      Verify:  bash scripts/gate.sh (no network in tests); `uv run python -m app.grounding.run <sample.pdf>` on the real account prints grounded entities with page/line spans, faithfulness, recall, model and tokens
      Done:    the Phase 1 checkpoint: a sample script parses and extracts on Nemotron with a faithfulness score and a recall score, and every entity shown quotes the script at a located span
- [x] T039 [FND] **Parser and grounding fixes found by the samples.** `INT./EXT.` headings; paragraph breaks lost at pdfplumber's 13 pt rows; the time of a two-dash heading; wrapped parentheticals; dialogue quotes that start with the speaker's cue (samples/README.md § Parser findings, § Live run). Depends on T031. Lane `script+grounding`.
      Design:  docs/design/script.md §4 (classification, heading split, row height), §8, §10; docs/design/grounding.md §3, §4, §6, §8 (the cue-header rule)
      Files:   services/api/app/script/parser.py; services/api/app/grounding/{text,filter,extract,__init__}.py; services/api/tests/script/test_parser.py; services/api/tests/grounding/{test_text_and_filter,test_extract}.py; docs/design/{script,grounding}.md; samples/README.md (counts, findings, live numbers); CHANGES-FROM-FRAMEFLOW.md if a ported row changes
      Contract:parser: `INT./EXT.` (and `EXT./INT.`) is a heading with `IntExt.INT_EXT`; `parse_pdf` reads 12 pt rows (`y_density=12`); a heading with 2+ separators whose last segment is a known time (`ABSOLUTE_TIMES | RELATIVE_TIMES`) takes it as the time and everything before it as the location; a line under a cue that opens `(` without closing, followed by lines at the same indent until one ends `)`, is one parenthetical (anything else replays as dialogue). Grounding: a quote not located as-is is kept only if its leading line(s) equal the rendered header of one speech (cue, optional `(extension)`, optional `(parenthetical)`, normalised) and the rest is non-empty and inside that same speech; the kept `Quote.text` is the rest, without the header. Nothing else is loosened. The extraction prompt says not to include cues or parentheticals in a quote.
      Verify:  bash scripts/gate.sh (tests first, each failing for the right reason; samples' committed PDFs unchanged, README counts updated); `uv run python -m app.grounding.run ../../samples/<name>.pdf` for all three samples on the real account, before/after numbers in samples/README.md
      Done:    all three samples parse with every scene and paragraph break of their source, and a dialogue quote Lightning prefixes with its cue is kept, located at that speech, without the cue; the-red-kite's live recall is above 0/3
- [x] T048 [FND] **Join a line-break hyphen in element text.** samples/README.md finding 5: `sea- green` / `south- westerly` stay spaced in `Action.text` / `Dialogue.text`, so a quote the model copies is not located and comic lettering shows the space. Depends on T039. Lane `script+grounding`.
      Design:  docs/design/script.md §3 (`Scene.elements`, the join rule), §8 (decision row), §9; docs/design/grounding.md § line-break hyphen; docs/design/comic.md §4 step 5
      Files:   services/api/app/script/parser.py; services/api/app/grounding/text.py (`_LINEBREAK_HYPHEN`: a spaced `--` keeps its space); services/api/tests/script/test_parser.py; services/api/tests/grounding/test_text_and_filter.py; services/api/tests/samples/test_samples.py; services/api/tests/comic/test_bubbles.py; samples/README.md (finding 5, live numbers); docs/design/comic/*.png only if a reference page changes
      Contract:`_Open.close` joins its stripped lines with one space, except that a line ending in a run of `-` `–` `—` `−` with a non-whitespace character before the run joins the next line with no space. Spans and `Screenplay.text` are unchanged. `normalize_for_grounding` joins a dash run across a line break only when a non-whitespace, non-dash character precedes the run. For every element of every sample, `normalize_for_grounding(e.text) == normalize_for_grounding(<its span's lines joined by "\n">)`
      Verify:  bash scripts/gate.sh (tests first: `sea-green` / `south-westerly` in `sipho-and-siphokazi`, `LOST PROPERTY - PLATFORM 9` and `WAIT -- NO` spaced, `stops--then` and `wait—what` joined, a dash-only line kept spaced; the every-element invariant over all three samples; per sample, the exact list of elements whose text differs from the plain `" "` join; the comic letters `south-westerly` from the parsed sample); `uv run python -m app.grounding.run ../../samples/sipho-and-siphokazi.pdf` on the real account, number in samples/README.md
      Done:    `sipho-and-siphokazi`'s elements read `sea-green` and `south-westerly`, a quote the model copies from either is located, and the comic letters `south-westerly`; no sample element's text changes except at a line-break hyphen, as the per-sample list shows
- [x] T050 [US1] **A title is redacted with the name it precedes.** "MR. DUBE" and "OFFICER MOLOI" reach frame prompts as "MR. a person" / "OFFICER a person" (STATUS.md open items). Lane `storyboard`.
      Design:  docs/design/storyboard.md §3.1 (names never enter a prompt: the title rule), §9; docs/design/characters.md §3 rule 2, §9
      Files:   services/api/app/characters/redact.py; services/api/tests/characters/test_redact.py; services/api/tests/storyboard/* only if an expectation names a title
      Contract:`TITLE_WORDS = frozenset({"MR","MRS","MS","MISS","DR","SIR","LADY","OFFICER","NURSE","DOCTOR"})` ⊂ `NAME_STOP_WORDS`; in `_redact`, one or more title words (UPPER or Title case, separated by whitespace; only `MR`, `MRS`, `MS`, `DR` may carry a `.`) directly before a name run join it and are replaced with it, possessive included; a title not followed by a name run is untouched. `redact_names` labels by the name run only (the title doesn't change own/other). Redaction still only removes words
      Verify:  bash scripts/gate.sh (tests first: "MR. DUBE", "Mr Dube", "Dr. Khumalo", "OFFICER VAN WYK'S", "LADY MACBETH" all become one label; "the OFFICER nods", "Mr. Nobody" (not a name), "the OFFICER. Moloi turns" (sentence end: only Moloi redacted) and the "MR." of "MR. AND MRS. DUBE" unchanged; "OFFICER VAN WYK" built from that cue; storyboard §9 invariant over the samples still holds); `uv run python -m app.storyboard.prompts ../../samples/lost-property.pdf` on the real account shows no title left beside "a person"
      Done:    no frame prompt for any sample contains a title word directly before "a person", and nothing that isn't a name is redacted
- [x] T051 [US1] **Extraction knows animals and other names.** A grounded `species` on animal characters and `other_names` on characters and props (STATUS.md decision, 2026-10-01: MARMALADE the cat, "Gerald" the toy giraffe). Lane `script+grounding`.
      Design:  docs/design/grounding.md §3 (Animals and other names), §4 (what the model is asked for), §6, §8, §9
      Files:   services/api/app/grounding/{schema,model,extract,filter}.py; services/api/tests/grounding/*; services/api/app/grounding/run.py (print species / other names)
      Contract:`ProposedEntity` gains `species: str | None` and `other_names: list[str]` (both required in the strict schema; Python defaults for hand-built proposals); `Entity` gains `species: str | None = None`, `other_names: tuple[str, ...] = ()`; `ground` keeps a species (leading article stripped) only on a model CHARACTER when it is 1–3 words with a letter, no word in `PERSON_WORDS` or a name token of a *different* character, found as whole words in one of that entity's located **Action** quotes (first passing wins across chunks), and an other name when the script mentions it as a whole word, it differs from the name under `normalise`, and it has a name token (union across chunks); CUE backfills and locations have neither; faithfulness and recall unchanged
      Verify:  bash scripts/gate.sh (tests first: grounding.md §9 T051 cases); `uv run python -m app.grounding.run ../../samples/lost-property.pdf` on the real account shows MARMALADE with species `cat` and "Gerald" among some entity's other names (two runs, numbers in samples/README.md)
      Done:    an extraction of `lost-property` says MARMALADE is a cat and knows "Gerald" as another name, each traceable to the script, and nothing ungrounded is kept
- [x] T052 [US1] **Prompts and the audit use them: a cat is "the cat", Gerald is "the giraffe", animals aren't figures.** Depends on T051. Lane `storyboard` (verify parts: lane `verify`, same owner).
      Design:  docs/design/storyboard.md §3.1 (visible_characters, Labels), §6, §9; docs/design/verify.md (Animal characters, the `MISSING_CHARACTER` row); docs/design/characters.md rule 2
      Files:   services/api/app/characters/{redact,labels}.py; services/api/app/storyboard/{prompt,prompts}.py; services/api/app/verify/{prompts,audit}.py; services/api/tests/{characters,storyboard,verify}/*
      Contract:storyboard.md §6 verbatim: `animals`, `redaction_labels` (token → label; persons `a person`, animals `the <species>`, named props `the <name>`, `it` for a label holding a name token or an unpaired other name (paired = it shares a scene with the entity's name, species or a located quote); precedence person > animal > prop > it, then extraction order), `redact`, `visible_characters(shot, screenplay, extraction)` (people only); `build_frame_prompt`, `cites_this_shot` and `names_in` use them (names_in over every labelled name and other name); `COUNT`/`PLACEMENT` use people only; verify's `render_spec` lists animal characters under "Animals in this shot", the judge prompt says how to call them, person matching and `MISSING_CHARACTER` use person characters only. `redact_all` / `redact_names` keep their behaviour
      Verify:  bash scripts/gate.sh (tests first: storyboard.md §9 Labels; verify: an animal described as an object and called `scripted_prop` with support passes, no `missing_character` for it, a person still can't be matched to it); `uv run python -m app.storyboard.prompts ../../samples/lost-property.pdf` on the real account: no prompt contains "Marmalade" or "Gerald", "the cat" and "the giraffe" appear where the script names them ("Even the cat comes back", "a person dances with the giraffe"), every part cited
      Done:    `lost-property`'s frame prompts draw the cat as a cat and the toy as a giraffe, count only people as figures, and name no one; the audit expects the cat as an animal, not a person

**Checkpoint:** a sample script parses and extracts on Nemotron with a faithfulness score.

- [ ] T037 [SET] **Deploy stack: Vercel + Railway + Supabase Postgres, Redis removed.** Lane `infra`.
      Design:  docs/design/deploy.md (§1, §4, §6, §7 rows marked T037)
      Files:   apps/web/vercel.json; apps/web/next.config.ts; services/api/app/{main.py,core/config.py}; services/api/tests/test_health.py; services/api/pyproject.toml + uv.lock (redis out); docker-compose.yml; .env.example; docs/deploy.md
      Contract:docs/design/deploy.md §6 (env names, deploy configs, health checks postgres only)
      Verify:  bash scripts/gate.sh; docker compose up --build --wait healthy without Redis; then, with Katlego's accounts (Railway configured in its dashboard, docs/deploy.md): the Railway URL's /api/v1/health answers ok against Supabase, and the Vercel URL's /api/health answers 200 through it
      Done:    the code needs no Redis, and the three hosted services are reachable from each other on the real accounts. Blocked on accounts until Katlego creates them; docs/deploy.md lists the steps

---

## Phase 2 — US1: script → grounded storyboard

- [x] T007 [US1] **Shot planner.** Port from `shot_service.py`. Depends on T006. Lane `shots`.
      Design:  docs/design/shots.md (all sections)
      Files:   services/api/app/shots/{__init__,model,schema,planner,run}.py; services/api/tests/shots/*; CHANGES-FROM-FRAMEFLOW.md (ported row)
      Contract:docs/design/shots.md §6, verbatim
      Verify:  bash scripts/gate.sh (no network in tests); `uv run python -m app.shots.run <sample.pdf>` on the real account prints every shot with its span and verbatim source, and every scene element appears in exactly one shot
      Done:    T008 can take a `ShotPlan` whose every shot cites the script lines it covers and names only extracted characters and props present in that scene
- [x] T008 [US1] **Storyboard, part 1: styles, name redaction, grounded frame prompts.** No GPU needed. Port from `storyboard_service.py` (prompt pieces) and `storyboard_styles.py`. Depends on T007. Its `styles/*.toml` need the team's answer on which styles stay public (storyboard.md §10). Lane `storyboard`.
      Design:  docs/design/storyboard.md §3.1, §3.2, §6 (`styles.py`, `redact.py`, `prompt.py`, `prompts.py`), §8, §9 (prompt, redaction, styles); characters.md §3 rules 1–3
      Files:   services/api/app/storyboard/{__init__,styles,prompt,prompts}.py; services/api/app/characters/{__init__,redact}.py; services/api/app/core/config.py + .env.example + docs/design/deploy.md §6 (`PANELWISE_PRIVATE_STYLES`, `COMFYUI_MAX_WORDS`); styles/*.toml + styles/README.md; services/api/tests/{storyboard,characters}/*; CHANGES-FROM-FRAMEFLOW.md (ported rows)
      Contract:docs/design/storyboard.md §6 `styles.py`, `redact.py`, `prompt.py`, `prompts.py`, verbatim
      Verify:  bash scripts/gate.sh (no network; the §9 prompt invariant over every shot of the self-written sample in every public style, the adversarial redaction fixture, every §3.2 style rejection); then `uv run python -m app.storyboard.prompts samples/<self-written>.pdf` on the real account prints every shot's prompt parts with their spans
      Done:    for every shot of the sample, the printed prompt's every script part cites this shot's heading or a covered element, and no prompt carries a name, a line of dialogue, a parenthetical or anything from outside the shot; `load_styles` loads the public styles and rejects every §3.2 violation
- [ ] T026 [US1] **Storyboard, part 2: ComfyUI renderer, Supabase Storage, the storyboard job.** Port from `image_provider.py` (ComfyUI only) and `image_postprocess.py`; `image_cache.py` is dropped (storyboard.md §8). Depends on T008, T003 (GPU, model, `frame.json`), T020, T021 (`render_until_accepted`; T021 builds against a fake renderer, so it doesn't wait on this), T043 (the pipeline it adds the RENDERING stage to), T046 (the job that runs it). **Blocked on T003.** Lane `storyboard`.
      Design:  docs/design/storyboard.md §3.3, §4, §6 (`workflow.py`, `render.py`, `store.py`, `model.py`, `build.py`), §9; verify.md §4–§6 (the loop and the `Renderer` it calls)
      Files:   services/api/app/storyboard/{model,workflow,render,build,run}.py; services/api/app/projects/pipeline.py (RENDERING stage in `run_pipeline`: `on_advance(RENDERING, 60, plan)`, `build_storyboard` with T021's writers, progress mapped into 60–100; T046's `run_job` then marks the job DONE; web.md §6, §7); infra/comfyui/workflows/frame.json; services/api/app/core/config.py + .env.example + docs/design/deploy.md §6 (`COMFYUI_URL`, `COMFYUI_TIMEOUT_S`, `SUPABASE_STORAGE_BUCKET`); services/api/app/images/README.md (removed); services/api/tests/storyboard/*; infra/nebius/README.md (seconds per frame); CHANGES-FROM-FRAMEFLOW.md (ported rows)
      Contract:docs/design/storyboard.md §6 `workflow.py`, `render.py`, `model.py`, `build.py`, verbatim (`ComfyRenderer` satisfies verify.md §6 `Renderer`; uses T053's `store.py`)
      Verify:  bash scripts/gate.sh (no network: `httpx2.MockTransport` for ComfyUI and Storage, an in-memory `AssetStore`, a fake renderer and mocked audit for `build_storyboard`); then live on the real account and T003's GPU: `uv run python -m app.storyboard.run samples/<self-written>.pdf --out /tmp/sb` ends with every shot `passed`, `warned` or `withheld` and every attempt's frame in Supabase Storage; seconds per frame recorded in infra/nebius/README.md
      Done:    every shot of a self-written screenplay ends with an audited frame in Supabase Storage (or withheld), every attempt logged with its asset; a second run of the same script renders nothing new (every frame a Storage hit)
- [ ] T027 [US1] **Storyboard, part 3: the storyboard PDF and JSON.** Port from `storyboard_document.py` (layout; drawn with Pillow instead). Depends on T026. Lane `storyboard`.
      Design:  docs/design/storyboard.md §3.4, §6 (`document.py`, the storyboard JSON), §9 (Document)
      Files:   services/api/app/storyboard/{document,run}.py; services/api/app/api/v1/projects.py (`GET /projects/{id}/storyboard.pdf`, web.md §6); services/api/assets/fonts/{CourierPrime-Regular.ttf,CourierPrime-Bold.ttf,CourierPrime-OFL.txt}; docs/design/reference/storyboard/*.png; services/api/tests/storyboard/*; CHANGES-FROM-FRAMEFLOW.md (ported row)
      Contract:docs/design/storyboard.md §6 `document.py` and the storyboard JSON, verbatim (an export; the web pages read `frames` rows, web.md §6)
      Verify:  bash scripts/gate.sh (the document from generated PNGs, including a withheld card and a continued block); then `uv run python -m app.storyboard.run samples/<self-written>.pdf --out /tmp/sb` also writes the PDF to /tmp/sb and Storage
      Done:    a self-written screenplay becomes a storyboard PDF in a public style, one block per shot in plan order, each showing an audited frame (or the withheld card) above the shot's verbatim source and page/line span; the sample's pages are committed as the visual reference
- [x] T009 [US1] **Database foundation: the gate's test Postgres, Alembic, the `projects` and `jobs` tables, the restart sweep.** Split on 2026-10-02 from the original T009 (too big for one sitting); sign-in, storage and the upload are T053. Lane `web`. Changes `scripts/gate.sh` under Katlego's AGENTS.md §4 exception (STATUS.md Log, 2026-10-02).
      Design:  docs/design/deploy.md §6 (*Schema and migrations*, *Row-level security*, *Test Postgres*), §10; docs/design/web.md §3 (Project, Job), §4.1 (restart sweep), §6 (*API internals*: models, repos, the startup sweep)
      Files:   scripts/gate.sh (test Postgres); services/api/{alembic.ini,migrations/** (incl. `helpers.py` `lock_down`)}; services/api/app/db.py (engine and `async_sessionmaker` from Settings); services/api/app/{projects,jobs}/{model,repo}.py, app/jobs/__init__.py; services/api/app/main.py (lifespan: sessions, the sweep); services/api/app/core/config.py; services/api/tests/{conftest.py (the `db` fixture),db/*}; services/api/pyproject.toml (alembic; the `db` marker); services/api/Dockerfile (copies the migrations); docker-compose.yml (api runs `alembic upgrade head` first); docs/deploy.md (Railway's pre-deploy command)
      Contract:deploy.md §6 tables and constraints verbatim; web.md §6 `JobState`, `JobKind`, `RESTARTED`, `create_upload`, `list_summaries`, `fail_interrupted` verbatim
      Verify:  bash scripts/gate.sh with Docker running (tests first: the migration creates both tables with every constraint and RLS on; a bad state/kind/stage/progress is refused by the database; `create_upload` makes a QUEUED storyboard job; `list_summaries` is newest first, the owner's only, with the latest job; `fail_interrupted` fails QUEUED and RUNNING jobs, keeps DONE/FAILED and the stage; the gate fails, not skips, without Docker or TEST_DATABASE_URL; the fixture refuses a database not named `*_test`; every `public` table, `alembic_version` included, has RLS on); `alembic upgrade head` against the Supabase project (SUPABASE_DB_URL), then RLS on for every table (`alembic_version` too), nothing granted to `anon`/`authenticated`, and the publishable key refused through the Data API; Railway's pre-deploy log shows the migration (T037)
      Done:    the gate runs the database tests on a throwaway Postgres 17.11 locally and in CI; the Supabase project has both tables with RLS on, created by `alembic upgrade head`; a job left QUEUED or RUNNING reads FAILED with the restart message after the API starts
- [ ] T053 [US1] **API: sign-in check, storage and the upload endpoints.** A signed-in caller uploads a PDF; it is stored and a queued `Job` is created; the list shows only the caller's projects. Depends on T009. Lane `web`.
      Design:  docs/design/web.md §4.1 (upload), §6 (rows marked T053; *API internals*: auth, storage, `POST /projects` in order, settings); storyboard.md §6 `AssetStore`/`SupabaseStore`
      Files:   services/api/app/core/auth.py; services/api/app/storage/{__init__,store}.py; services/api/app/api/v1/projects.py; services/api/app/main.py (verifier, store, router); services/api/app/core/config.py; services/api/tests/{auth,storage,api}/*; services/api/pyproject.toml (pyjwt[crypto], python-multipart)
      Contract:web.md §6 rows marked T053, *API internals* and the `ProjectSummary`/`Job` types; storyboard.md §6 `AssetStore`/`SupabaseStore`; verbatim
      Verify:  bash scripts/gate.sh (tests first: the verifier on locally signed ES256 tokens — good, expired, no exp, wrong aud/iss/role, anonymous, no or unknown kid, HS256 and `none` refused; an unknown kid refetches at most once a minute across requests; a failed fetch serves the cache, and with none is 503 not 401; Storage with `httpx2.MockTransport`; the routes with a fake verifier and an in-memory `AssetStore`: 401 before the body is read, 411, 413 from Content-Length before parsing and for a file of `upload_max_bytes + 1` bytes inside a Content-Length under the cap, 503 storage_unavailable before the body is read, 400 no_file/not_a_pdf, 202 with a QUEUED job, the list only the caller's, newest first); live: the dev user's real token against the Supabase project uploads samples/the-red-kite.pdf to `panelwise-dev` and lists it, another user's token doesn't see it
      Done:    POST /api/v1/projects with a valid token stores the PDF and returns 202 with a queued job; GET /api/v1/projects lists only the caller's projects; a bad or missing token is 401

- [x] T043 [US1] **API: the pipeline core (no database).** `run_pipeline` turns PDF bytes into the parsed script, the grounded extraction and the shot plan, announcing each stage as it begins, and fails with web.md §4.1's copy. Lane `web`. Depends on T005, T006, T007 (done). Not on T009: the database half is T046.
      Design:  docs/design/web.md §3 (Stage, progress bands, page_starts, ScriptParseError.code), §4.1 (failure copy), §6 (the pipeline core, `on_advance` table)
      Files:   services/api/app/projects/{__init__,pipeline,run}.py; services/api/app/script/{__init__,model,parser}.py; services/api/app/grounding/{model,extract}.py (`ExtractionError.scene`); services/api/app/shots/{model,planner}.py (`ShotError.scene`); docs/design/{script,grounding,shots}.md §6; services/api/tests/projects/test_pipeline.py; services/api/tests/{script,samples,grounding,shots}/* (page_starts, codes, scene); services/api/tests/comic/test_layout.py (Screenplay's new field)
      Contract:web.md §6 `app/projects/pipeline.py`; script.md §6 `page_starts`, `ScriptParseError.code`; grounding.md §6 `ExtractionError.scene`; shots.md §6 `ShotError.scene`; verbatim
      Verify:  bash scripts/gate.sh (models via `httpx2.MockTransport`, no network, no database): a good PDF advances (PARSING, 0, None) → (EXTRACTING, 5, screenplay) → (PLANNING, 40, extraction) and returns the plan; each ScriptParseError code gives its copy at PARSING; an over-budget script gives the budget copy with zero model calls; a failed extraction chunk and a failed planning call give "Reading the script failed at scene {n}" with that scene's number; page_starts[0] == 1 and len == page_count on every sample. Then `uv run python -m app.projects.run samples/the-red-kite.pdf` on the real account
      Done:    T046 can call `await run_pipeline(pdf, model, on_advance=...)` and get the parse, extraction and plan with every stage announced in band order, or a `PipelineError` whose stage and message are exactly what the job row will show; the CLI prints the advances and a summary for the-red-kite on the real account
- [ ] T046 [US1] **API: run the pipeline as a Job.** The upload's queued job runs T043's `run_pipeline`, writing each stage's column in the same transaction as the job's advance. Lane `web`. Depends on T009, T053, T043.
      Design:  docs/design/web.md §3 (Project stage columns, Job stage and progress), §4.1 (the sequence, failures, the unexpected-error copy), §6 (`app/projects/job.py`, the `on_advance` table)
      Files:   services/api/app/projects/{job,codec}.py; services/api/app/projects/repo.py (`list_summaries` reads `pages`, `scenes`, `shots` from the stage columns); services/api/app/api/v1/projects.py (the POST schedules `run_job` after its commit); services/api/tests/projects/{test_job,test_codec}.py
      Contract:web.md §6 `run_job` and the `on_advance` table, verbatim; `codec.py` round-trips `Screenplay`, `Extraction`, `ShotPlan` to the jsonb columns losslessly (load(dump(x)) == x)
      Verify:  bash scripts/gate.sh with the Postgres T009's tests use, models via MockTransport and Storage behind T053's test double: a good PDF ends DONE at progress 60 with screenplay, extraction and plan columns written; each advance's column and the job's stage/progress land in one transaction (a failing job write leaves the column unwritten); a PipelineError leaves the earlier columns, FAILED, its stage and its message; an unexpected exception gives the "went wrong on our side" copy, never its text; codec round-trip on the three samples. Then the live upload check below
      Done:    uploading samples/the-red-kite.pdf through POST /api/v1/projects on the real account (Supabase and Token Factory) ends in a DONE job whose project holds the parsed script, the grounded extraction and the shot plan, with the stage and progress visible in GET /api/v1/projects while it runs, and its pages, scenes and shots there once planned
- [x] T044 [US1] **API: the §6 response schemas and pure view builders.** Every web.md §6 type as a Pydantic model, and the pure functions that turn a parsed script, an extraction and a shot plan into the scene, entity, report, lines and shot views. No database, no endpoints: T047 serves them. Lane `web`. Depends on T043 (`page_starts`).
      Design:  docs/design/web.md §6 (the response types, the view builders block), §4.2 (what the script page shows), §4.3 (shot lines and segments)
      Files:   services/api/app/api/v1/schemas.py; services/api/app/projects/views.py; services/api/tests/projects/{test_views,test_schemas}.py
      Contract:web.md §6 response types (Pydantic mirrors, field names identical, `Job` and `ProjectSummary` included though their data comes with T009/T047) and `app/projects/views.py`, verbatim. `FrameView`/`AuditView` are schemas only: their builders are T047's and T021's, which own the `frames` and `frame_audits` data
      Verify:  bash scripts/gate.sh (pure; no network, no database): every builder on the three self-written samples and the two-page fixture; `time_carried` on a CONTINUOUS scene and not on a scene with no clock at all; `segments` one per covered element, `on_screen` false for dialogue whose speaker (`match_speaker` against the extraction's characters) is not in the shot's characters, including a cue that matches no character; `id` is "{scene number}.{shot number}"; every model's JSON field names equal web.md §6's, read from the doc's TypeScript block
      Done:    T047 can build `Project`, `LinesView` and `ShotView[]` for any planned project by calling the builders on its loaded columns, and the JSON matches web.md §6's shapes field for field
- [ ] T047 [US1] **API: the read endpoints and the `frames` table.** A signed-in owner reads a project, its lines, its shots and its frames; nobody else can. Lane `web`. Depends on T009, T053, T044, T046.
      Design:  docs/design/web.md §3 (`Frame`, settled), §4.2, §4.3 (what each page reads), §6 (rows marked T047, `Project`, `ProjectSummary.frames`, `FrameView`)
      Files:   services/api/app/api/v1/projects.py (the four read endpoints); services/api/app/frames/{__init__,model,repo,views}.py + migration (the `frames` table, web.md §3; T021 writes it; `frame_view` builds `FrameView` from a row, `audits` [] until T021); services/api/tests/projects/test_read.py; services/api/tests/frames/*
      Contract:web.md §6 rows marked T047, verbatim; responses built with T044's `schemas.py` and `views.py` from the columns T046's `codec.py` loads
      Verify:  bash scripts/gate.sh with the Postgres T009's tests use (a fake token verifier; Storage behind T053's `AssetStore` test double): every §6 read type round-trips from a stored project (codec → builders → JSON); `…/lines` 409 while parsing and `…/shots` 409 before planning ends; another user's project 404; `…/frames` is [] with no `frames` rows; `image_url` null for every state but passed and warned, a signed URL otherwise; `ProjectSummary.frames` counts settled, withheld and active by web.md §3
      Done:    on the real account, after T046's live upload of samples/the-red-kite.pdf, GET /api/v1/projects/{id}, …/lines, …/shots and …/frames return exactly web.md §6's shapes for the owner and 404 for anyone else, and frames come back only from `frames` rows
- [ ] T040 [US1] **Web: tokens, sign-in, projects and upload.** Lane `web` (Claude). Depends on T053 (the API it calls); the Supabase project exists (2026-10-02).
      Design:  docs/design/web.md §2 (tokens, direction), §4.0, §4.1, §5, §6 (routes, components, copy)
      Files:   apps/web/app/globals.css; apps/web/components/ui/*; apps/web/lib/{supabase,api}/*; apps/web/middleware.ts; apps/web/app/(auth)/sign-in/*; apps/web/app/projects/page.tsx; apps/web/app/api/projects/route.ts; apps/web/components/AppBar.tsx (ProjectTabs inside); apps/web/components/SignInForm.tsx; apps/web/components/projects/*; apps/web/components/shared/{Verdict,SpanRef,Quote,Meter}.tsx; tests beside them
      Contract:docs/design/web.md §6 (types in apps/web/lib/api/types.ts, route handlers)
      Verify:  pnpm lint && pnpm test (every ProjectRow state, the upload errors); then the running app side by side with docs/design/web/signin.png and projects.png at 1440 px
      Done:    signed out redirects to sign-in; a signed-in user uploads a PDF and sees it in the list with its live job state or its failure message, matching the two references in layout, tokens and copy
- [ ] T041 [US1] **Web: script page.** Lane `web` (Claude). Depends on T040, T047.
      Design:  docs/design/web.md §4.2, §5, §6
      Files:   apps/web/app/projects/[id]/script/*; apps/web/components/script/*; tests beside them
      Contract:consumes GET /api/v1/projects/{id} → Project (web.md §6)
      Verify:  pnpm test (entity sources, report counts in words, dropped entities never listed, stacked on a phone); compare with docs/design/web/script.png
      Done:    every entity shows each quote in Courier with its page/line span, and faithfulness and recall always appear together with their counts, matching script.png
- [ ] T042 [US1] **Web: storyboard board (lined script and frame cards).** Lane `web` (Claude). Depends on T041. Frames appear only once T021 moves a frame to passed/warned; before that the cards show "Not rendered yet", the real state (web.md §3, §4.1).
      Design:  docs/design/web.md §4.3, §5, §6
      Files:   apps/web/app/projects/[id]/storyboard/*; apps/web/components/storyboard/{LinedScript,FrameBoard,FrameCard,FrameMedia,JobStrip,ExportButton}.tsx (sub-components per web.md §7); apps/web/app/api/projects/[id]/{status,frames,storyboard.pdf}/*; tests beside them
      Contract:consumes …/lines, …/shots, …/frames, …/status (web.md §6)
      Verify:  pnpm test (every card-table row; no <img> outside passed/warned; withheld source shown once; shot line top/height from spans; wavy off-screen segments; polling while any frame is active; Export PDF disabled with its tooltip until every frame has settled; lined script hidden below 1100 px); compare with docs/design/web/storyboard.png and storyboard-phone.png
      Done:    on a planned project every shot appears as a line over exactly its script lines and as a card with its verbatim source, and hovering or focusing either highlights the other, matching the two references
- [ ] T045 [US1] **Web: frame sheet.** Lane `web` (Claude). Depends on T042.
      Design:  docs/design/web.md §4.4 steps 1–4, §6
      Files:   apps/web/components/storyboard/{FrameSheet,SourceBlock,InFrame}*; tests beside them
      Contract:consumes ShotView and FrameView (web.md §6)
      Verify:  pnpm test (?shot= opens it; Esc closes and clears it; focus trapped; dialogue cue shown outside the quote; positions from the accepted audit); compare with docs/design/web/storyboard-frame.png (without the audit section, which is T021's)
      Done:    clicking any card or following a ?shot= link opens a sheet showing the frame or its text card, the verbatim source with page, lines and scene, and who is in frame, matching storyboard-frame.png

**Checkpoint:** US1 demoable in the browser on Nemotron + Nebius GPU. Waits on T021 and T026: no frame is shown unaudited (storyboard.md §10).

---

## Phase 3 — Design for the new work (markdown only)

- [x] T010 [P] [DSN] `docs/design/verify.md` — audit sequence, verdict schema, re-render limit, audit log. Built on vision option A (a Token Factory VLM describes the frame, Nemotron judges it); option B (self-hosted NVIDIA VLM) is a stretch. See `docs/nebius-findings.md` § The vision decision.
- [x] T011 [P] [DSN] `docs/design/comic.md` — page model, panel sizing by story beat, bubble placement, lettering, export.
- [x] T012 [P] [DSN] `docs/design/characters.md` — reference portraits and how they feed ComfyUI.

---

## Phase 4 — US2 frame audit · US3 comic · US4 consistent characters

- [x] T020 [US2] **Frame audit:** a vision model describes the frame blind, Nemotron judges it against the shot, code runs the checks and returns a verdict. Depends on T010. Lane `verify`.
      Design:  docs/design/verify.md §3 (model, the checks table), §4 (describe → judge → check), §6
      Files:   services/api/app/verify/{__init__,model,schema,prompts,audit,run}.py; services/api/tests/verify/*; docs/design/verify.md (§7 run.py row, §10 measured answers)
      Contract:docs/design/verify.md §6 `model.py`, `schema.py`, the renderer shapes and `audit.py`, verbatim
      Verify:  bash scripts/gate.sh (no network in tests: run_checks on hand-built descriptions for every check's pass and fail; audit_frame via MockTransport proves the describer call carries the image and no shot details); `uv run python -m app.verify.run <script.pdf> <scene>.<shot> <frame.png>` on the real account prints the description, the judgement, every check and the verdict
      Done:    T021 can call `await audit_frame(model, frame, shot, screenplay, extraction)` and get an `Audit` whose verdict is FAIL for an unscripted person or object, text in frame or a contradicted setting, and ERROR (never PASS) when either model call fails
- [ ] T021 [US2] **Re-render loop, frame state, audit log, and their UI.** Render → audit → re-render until accepted or withheld, keep every attempt, and show it. Lane `verify` (UI parts: Claude). Depends on T009, T020, T045, T047 (the `frames` table it writes). Builds against verify's `Renderer` Protocol, so not on T026 (T026 depends on this).
      Design:  docs/design/verify.md §4, §5 (incl. the sweep edges), §6 (`render_until_accepted`, `frame_audits`); docs/design/web.md §3 (`Frame`, `frame_attempt` jobs, settled), §4.1 (frame half of the sweep), §4.3 (card states, retry), §4.4 step 5, §6 (attempts row, `FrameView`, `AuditView`)
      Files:   services/api/app/verify/loop.py (with verify.md §6's `on_state` hook); services/api/app/frames/writer.py + migration (`frame_audits`; the `frames` writer for `on_state`/`on_frame`; the `frames` table itself is T047's); services/api/app/api/v1/projects.py (attempts endpoint); services/api/app/jobs/* (frame half of the sweep); apps/web/components/storyboard/AuditLog.tsx; apps/web/app/api/projects/[id]/frames/[scene]/[number]/attempts/route.ts; the "Try another render" action in FrameCard.tsx's WithheldCard (a later edit of T042's file); tests beside each
      Contract:verify.md §6 `render_until_accepted` and `frame_audits`; web.md §6 attempts row, `FrameView`, `AuditView`, verbatim
      Verify:  bash scripts/gate.sh: `render_until_accepted` with a fake renderer (pass first time; fail then pass; three fails → WITHHELD; audit error → WITHHELD; every attempt logged; deterministic seeds); a `frames` row never carries an asset outside passed/warned; attempts on a withheld frame → 202 under a new `frame_attempt` job, any other state → 409; the sweep fails rendering/auditing frames; pnpm test for AuditLog (attempts newest last, failed checks with details, "{k} other checks passed"); compare the sheet with docs/design/web/storyboard-frame.png
      Done:    with a scripted renderer serving real PNGs (like T020's live frames) and the real audit, a frame that fails its audit is re-rendered with a new seed up to three times and then withheld, never shown; every attempt is a `frame_audits` row visible in the frame sheet; "Try another render" on a withheld frame runs one more audited attempt
- [x] T022 [US3] **Comic page layout + panel sizing from the shot list.** Depends on T007, T011. Lane `comic`.
      Design:  docs/design/comic.md §3 (model), §4 steps 1–5 (weights, tiers, pages, panels, lettering budget), §6, §9 (Geometry)
      Files:   services/api/app/comic/{__init__,model,layout}.py; services/api/tests/comic/*; services/api/assets/fonts/{ComicNeue-Regular.ttf,OFL.txt} (the budget measures text with it); services/api/pyproject.toml + uv.lock (pillow); services/api/Dockerfile (copies assets/); docs/design/comic.md (clarifications)
      Contract:docs/design/comic.md §6 `app/comic/model.py` and `app/comic/layout.py`, verbatim (`PanelFrame` lands with T023, which consumes it)
      Verify:  bash scripts/gate.sh (pure, no images, no network); the tests lay out the self-written sample's plan and assert §9's geometry list
      Done:    T023 can call `layout_geometry(plan, screenplay)` and get a deterministic `ComicBook` whose pages hold one panel per shot in plan order, sized by story beat, tiers filling each page exactly inside the margins and gutters, every panel's lettering within its 35% area budget, or a `ComicError` naming the shot that can't fit
- [x] T023 [US3] **Speech bubbles and captions from the script's own dialogue, placed in the frame's empty space; comic page render, PDF and layout JSON.** Depends on T022. Lane `comic`. Real frames come from T026 (GPU); this builds on `PanelFrame` PNG bytes, so its tests draw frames with Pillow at that seam.
      Design:  docs/design/comic.md §3 (model, extension → kind, SCENE caption), §4 steps 5–8 (lettering, frames at panel size, the withheld card, placement, drawing, tails), §6, §8, §9 (Traceability, Extension mapping, Placement, Frames, Export, Visual)
      Files:   services/api/app/comic/{model,bubbles,render,__init__}.py; services/api/app/comic/layout.py (its wrap, box and font helpers made public for placement and drawing); services/api/tests/comic/{conftest,test_bubbles,test_render,test_reference}.py; services/api/tools/build_comic_reference.py; docs/design/comic/the-red-kite-page-*.png (the rendered reference); docs/design/comic.md (the rules T023 pinned down)
      Contract:docs/design/comic.md §6 `PanelFrame`, `WithheldCard`, `app/comic/bubbles.py`, `app/comic/render.py` and the Layout JSON, verbatim
      Verify:  bash scripts/gate.sh (no network, no GPU): every `Dialogue` of every shot lettered exactly once with `text` and `span` equal to the element's, parentheticals and action never lettered; the §9 extension table; boxes inside the inset grid, never overlapping, strictly in reading order, ≥ 28 px; a box lands in a Pillow-drawn frame's empty half, off the speaker's third; tails per §4 step 8; no admissible spot → `ComicError` naming the shot; a withheld frame's pixels never reach the page (a red PNG marked withheld leaves no red) and its card reads the failed hard checks in `Check` order or `audit error`; a frame not at its rect's size → `ComicError`; one PDF page per `Page` at 6.625 × 10.25 in; the JSON matches §6 and round-trips every span; the committed reference pages equal a fresh `render_pages`
      Done:    given a `ComicBook` from `layout_geometry` and a `PanelFrame` per panel, `place_lettering` letters every line of dialogue each shot covers, verbatim with its span, in the frame's emptiest admissible spot in reading order (or fails naming the shot, never cutting a word), and `render_pages` / `to_pdf` / `to_json` produce the pages, the PDF and T024's JSON, with a withheld frame shown only as its card. The reference pages of `the-red-kite` are committed and named in comic.md §2. Seeing it on real renders waits on T026 (GPU); the comic job that calls `render_until_accepted` per panel is T026's
- [ ] T024 [US3] Web comic reader. Lane `web`.
- [ ] T025 [US4] Reference portraits used across panels. Port from `portrait_service.py`, `portrait_jobs.py`. Depends on T012. Lane `characters`. Also (T052 deferred it here, characters.md rule 2): an animal character's portrait uses its `the <species>` label and passes with no person and one animal object.

---

## Phase 5 — Hardening and submission

- [ ] T030 [POL] Hosted demo on Vercel + Railway + Supabase (docs/design/deploy.md), seeded judge account (Supabase Auth), LLM + image spend caps, upload limits. Stays up to 15 Dec. Lane `infra`. Sign-up is **off** (Katlego, 2026-10-02; web.md §10): the judge account(s) come from an idempotent seed script using the secret key, with a pre-rendered sample project, and the credentials go only in Devpost's testing instructions. Whoever claims T030 expands it to the full Design/Files/Contract/Verify/Done form first, saying where usage is counted and what happens at a cap (`.env.example`'s two monthly caps are read by no code yet). Check the Devpost rules accept a login for the demo before relying on it.
- [x] T031 [P] [POL] Public-domain / self-written sample screenplays in `samples/`. Lane `eval+submission`.
      Design:  none (no new entities). Layout follows docs/design/script.md §2–§4 (action at the margin, dialogue ~2.5", parenthetical ~3.1", cue ~3.7", transitions right; page furniture the parser drops). No copyrighted script: every sample is self-written for this repo (Apache-2.0)
      Files:   samples/{the-red-kite,lost-property,sipho-and-siphokazi}.fountain + .pdf; samples/README.md; services/api/tools/{__init__,build_samples}.py; services/api/tests/samples/*; services/api/pyproject.toml (pyright includes tools)
      Contract:`cd services/api && uv run python -m tools.build_samples` rebuilds every `samples/<name>.pdf` from `samples/<name>.fountain` (a Fountain subset: title page, headings, action, cue/parenthetical/dialogue, transitions, `===` page break) in US-letter 12 pt Courier, paginated at 54 lines with automatic (MORE)/(CONT'D) splits, and prints pages / scenes / speaking characters as `parse_pdf` reads them
      Verify:  bash scripts/gate.sh (a test parses every committed PDF with `parse_pdf`, checks it matches a fresh build of its source, and checks the counts in samples/README.md); from services/api, `uv run python -m app.shots.run ../../samples/the-red-kite.pdf` on the real account
      Done:    three original screenplays of different shapes (a ~3-page demo script, a ~10-page larger cast, a tricky-formatting one) sit in `samples/` as source and PDF; each parses with the real parser into the scene and speaker counts samples/README.md states, and the README records provenance, licence and the live run on the demo script
- [x] T032 [P] [POL] **Extraction and shot-plan numbers for the README.** Grounding faithfulness and recall, and the shot plan's partition and verbatim checks, over the three samples, several runs each, on the real account. Frame-audit accuracy is split out to T049 (needs renders). Depends on T031, T048. Lane `eval+submission`.
      Design:  docs/design/eval.md §1, §3–§9
      Files:   services/api/tools/evaluate.py; services/api/tests/tools/test_evaluate.py; eval/README.md; eval/results/extraction-<date>.json
      Contract:eval.md §6 verbatim: `EvalRun`, `Stat`, `SampleSummary`, `EvalReport`, `check_run`, `summarise`, `table`, `to_json`/`from_json`, `main` (`uv run python -m tools.evaluate [--runs N] [--out PATH] [sample ...]`); a failed run is kept with `error` and counted; `ungrounded_kept` re-checks every kept quote and every shot's `source` and `span` against the script in code (a heading-only scene's shot cites its heading), and any non-zero value exits 1
      Verify:  bash scripts/gate.sh (tests first: `check_run` catches a moved quote and an edited shot source; `summarise`/`table` on fixed runs incl. a failed one and pooled micro averages; JSON round-trip; eval/README.md's table equals `table(from_json(<newest committed result>))`); `cd services/api && uv run python -m tools.evaluate --runs 5` on the real account, results committed
      Done:    eval/README.md shows, for each sample and pooled, faithfulness and recall (mean, min–max over 5 runs), shots, whether every element was in exactly one shot, and 0 ungrounded kept, with the date, model and command; the gate fails if the table and the committed JSON disagree
- [ ] T049 [POL] **Frame-audit accuracy.** Precision and recall of the audit's FAIL on a labelled set of rendered frames, some with a deliberately injected extra person or object, and the false-FAIL rate on correct frames (verify.md §8–§10). **Blocked on T026** (renders need T003's GPU). Lane `eval+submission`.
      Design:  docs/design/eval.md §1, §6 (T049 report shape); docs/design/verify.md §9
      Files:   services/api/tools/evaluate.py (an `audit` mode); eval/frames/ (labelled frames, self-rendered); eval/results/audit-<date>.json; eval/README.md
      Contract:eval.md §6 T049 shape: per frame `{frame, shot, label, verdict, failed_checks}`; precision/recall of FAIL against injected labels; false-FAIL rate on correct frames
      Verify:  bash scripts/gate.sh (table recomputed from the committed JSON); the audit run on the real account
      Done:    eval/README.md reports the audit's precision, recall and false-FAIL rate on at least 30 labelled frames from the samples, with the labels committed
- [ ] T033 [POL] README: setup, how Nemotron and Token Factory are used, feedback section. Lane `eval+submission`.
- [ ] T034 [POL] 3-minute video on YouTube; fill the ported-code table in CHANGES-FROM-FRAMEFLOW.md. Lane `eval+submission`.
- [ ] T035 [POL] gitleaks over history, make the repo public, submit on Devpost by 29 Oct. Lane `eval+submission`.
- [ ] T036 [POL] Sweep for placeholders: no `TODO`/`FIXME`/stub bodies/hard-coded sample data remain.
- [x] T038 [POL] Record each contributor's time zone and working hours in STATUS.md § Environment & access, with the overlap marked (PREP.md). Needs Katlego and Tumo's answers. Lane `eval+submission`.
