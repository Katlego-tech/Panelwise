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
- [ ] T008 [US1] **Storyboard.** Port from `storyboard_service.py`, `storyboard_styles.py`, `storyboard_document.py`, `image_provider.py`, `image_cache.py`, `image_postprocess.py`. Style registry loads `styles/` plus optional `PANELWISE_PRIVATE_STYLES`. Images go to Supabase Storage (docs/design/deploy.md §7). Depends on T003, T007. Lane `storyboard`.
- [ ] T009 [US1] **Web: upload → shots → storyboard.** Includes Supabase Auth sign-in and the `Job` table for progress (docs/design/deploy.md §3–§5). Lane `web` (UI goes to Claude users per AGENTS.md §1).

**Checkpoint:** US1 demoable in the browser on Nemotron + Nebius GPU.

---

## Phase 3 — Design for the new work (markdown only)

- [x] T010 [P] [DSN] `docs/design/verify.md` — audit sequence, verdict schema, re-render limit, audit log. Built on vision option A (a Token Factory VLM describes the frame, Nemotron judges it); option B (self-hosted NVIDIA VLM) is a stretch. See `docs/nebius-findings.md` § The vision decision.
- [x] T011 [P] [DSN] `docs/design/comic.md` — page model, panel sizing by story beat, bubble placement, lettering, export.
- [x] T012 [P] [DSN] `docs/design/characters.md` — reference portraits and how they feed ComfyUI.

---

## Phase 4 — US2 frame audit · US3 comic · US4 consistent characters

- [ ] T020 [US2] Frame audit: a vision model describes the frame; Nemotron judges it against the shot spec and returns a verdict. Depends on T010. Lane `verify`.
- [ ] T021 [US2] Re-render on mismatch, cap retries, log every verdict; show the log in the web app. Lane `verify`.
- [ ] T022 [US3] Comic page layout + panel sizing from the shot list. Depends on T011. Lane `comic`.
- [ ] T023 [US3] Speech bubbles from linked dialogue, placed in empty space; comic PDF export. Lane `comic`.
- [ ] T024 [US3] Web comic reader. Lane `web`.
- [ ] T025 [US4] Reference portraits used across panels. Port from `portrait_service.py`, `portrait_jobs.py`. Depends on T012. Lane `characters`.

---

## Phase 5 — Hardening and submission

- [ ] T030 [POL] Hosted demo on Vercel + Railway + Supabase (docs/design/deploy.md), seeded judge account (Supabase Auth), LLM + image spend caps, upload limits. Stays up to 15 Dec. Lane `infra`.
- [ ] T031 [P] [POL] Public-domain / self-written sample screenplays in `samples/`. Lane `eval+submission`.
- [ ] T032 [P] [POL] `eval/`: faithfulness and frame-audit accuracy numbers for the README. Lane `eval+submission`.
- [ ] T033 [POL] README: setup, how Nemotron and Token Factory are used, feedback section. Lane `eval+submission`.
- [ ] T034 [POL] 3-minute video on YouTube; fill the ported-code table in CHANGES-FROM-FRAMEFLOW.md. Lane `eval+submission`.
- [ ] T035 [POL] gitleaks over history, make the repo public, submit on Devpost by 29 Oct. Lane `eval+submission`.
- [ ] T036 [POL] Sweep for placeholders: no `TODO`/`FIXME`/stub bodies/hard-coded sample data remain.
- [ ] T038 [POL] Record each contributor's time zone and working hours in STATUS.md § Environment & access, with the overlap marked (PREP.md). Needs Katlego and Tumo's answers. Lane `eval+submission`.
