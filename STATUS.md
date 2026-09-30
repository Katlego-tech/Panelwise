# `Panelwise` — STATUS

> Source of truth for "what's going on right now." Read first, update last. Treat updating it as
> part of "done." (This is the blank template — copy to `STATUS.md` and keep that one live.)

_Last updated: 2026-09-30 — by Katlego (via Claude)_

---

## ⇄ HANDOFF: **none**

> Leave this block here even when dormant — it is the first thing every AI reads, and it only
> works as a signal if it always lives in the same spot. Set it to `ACTIVE` and fill the rows
> when handing work to another AI or another session. See
> [docs/cross-ai-protocol.md](docs/cross-ai-protocol.md) § Handoffs.

| Field | Value |
|---|---|
| Status | 🟢 **none** |
| Raised | — |
| Reason | — |
| Document | — |
| Branch | — |
| Resume at | — |
| Blocking | — |

---

## 🎯 Current focus — the taskboard (claim your lane here)

> **WIP limit: one lane in `🟡 Doing` per contributor, human or AI. Finish before you start.**
> Claim a lane by putting your name in Owner and moving it to `🟡 Doing`, in the same PR as your
> first commit on it. Status values: `⬜ To Do` · `🟡 Doing` · `🔵 In review` · `✅ Done` · `🔴 Blocked`.

| Lane | Covers | Tasks | Owner | AI | Status |
|------|--------|-------|-------|----|--------|
| `llm` | Nebius Token Factory provider, model tiers, structured_chat | T001, T004 | | | ✅ T001, T004 done |
| `infra` | Pinned versions, docker-compose, ComfyUI on a Nebius GPU, hosted demo | T002, T003, T030, T037 | Katlego | Claude | 🔵 T037 code in review · 🔴 its deploy check blocked on accounts · T003 needs GPU access |
| `script+grounding` | Parser, scene time, dialogue linker, extraction, grounding filter | T005, T006, T039 | Katlego | Claude | ✅ T005, T006, T039 done |
| `shots` | Shot planner | T007 | | | ✅ T007 done |
| `storyboard` | Frames, style registry (public/private split), image chain, PDF | T008, T026, T027 | Katlego | Claude | ✅ T008 done (PR #27) · 🔴 T026 (renderer, Storage) blocked on T003 (GPU) and T021 · T027 (PDF) after T026 |
| `web` | Next.js app: upload → shots → storyboard → comic reader | T009, T043, T046, T044, T047, T040–T042, T045, T024 | Katlego | Claude | ✅ design (docs/design/web.md, PR #24) · ✅ T043 pipeline core (no database, PR #26) · ✅ T044 schemas and view builders (PR #28) · ⏸️ T009 suspended until the Supabase account/project exists (user, 2026-09-30); gate/CI have no Postgres for its DB tests; T046 (the pipeline as a job) follows it · T040+ need a Supabase project (T037) |
| `verify` | Frame audit (vision model describes, Nemotron judges), re-render loop, audit log | T010, T020, T021 | Katlego | Claude | ✅ T010 design done · ✅ T020 done (PR #22) · T021 waits on T009, T045, T047 (full scope in TASKS.md; builds against verify's `Renderer`, so not on T026) |
| `comic` | Page layout, panel sizing, speech bubbles, comic export | T011, T022, T023 | Katlego | Claude | ✅ T022 done · ✅ T023 done (PR #29; on `PanelFrame` bytes; seeing it on real renders waits on T026, GPU) |
| `characters` | Reference portraits for consistent characters | T012, T025 | | | ✅ T012 design done · T025 waits on T003 |
| `eval+submission` | Samples, benchmarks, video, disclosure table, go public | T031–T035 | Katlego | Claude | ✅ T031 done (PR #21) · T032 next |

## ⏭️ Next action

1. **T037** — deploy stack (Vercel + Railway + Supabase, Redis out): the code now; the deploy check needs Katlego's three accounts ([docs/design/deploy.md](docs/design/deploy.md)).
2. **T007** — shot planner (Phase 2), on the grounded entities from T006.
3. **T003** — ComfyUI on a Nebius GPU: blocked on GPU access (Katlego). Every rendering task waits on it.

## 🗓️ Timeline to 2026-10-30 10:00 PDT (19:00 SAST)

| Week | What | Target window | Status |
|-------|------|---------------|--------|
| 1 | Token Factory check; versions + compose; ComfyUI on Nebius GPU; port llm, script, grounding | 28 Sep – 4 Oct | ⬜ |
| 2 | **US1**: script → grounded storyboard on Nemotron, end to end in the web app. Design docs for verify + comic | 5 – 11 Oct | ⬜ |
| 3 | **US2**: frame audit + re-render + audit log. **US4**: reference portraits | 12 – 18 Oct | ⬜ |
| 4 | **US3**: comic pages + reader. Hosted demo live | 19 – 25 Oct | ⬜ |
| 5 | Hardening, eval numbers, video, README, repo public, **submit by 29 Oct** (one day of buffer) | 26 – 30 Oct | ⬜ |

## 🧱 What's built so far

- **Local stack (T002, T037):** `docker compose up --build --wait` runs postgres, api and web on pinned versions (PLAN.md § Technical Context); no Redis since T037. Host ports default to 5432/8000/3000 and can be overridden in `.env` (FrameFlow's containers hold 5432 on Katlego's machine). Deploy config: `apps/web/vercel.json`; Railway is set in its dashboard (`docs/deploy.md`: `railway.json` is deprecated, closed to new services, dead on 2026-12-01).
- **API** (`services/api`, FastAPI, uv): `GET /api/v1/health` pings Postgres and Redis; 503 + exception type on failure, with a timeout.
- **Web** (`apps/web`, Next.js 16, pnpm): `GET /api/health` reports web + API health; 502 when the API is unreachable. No pages yet (T040).
- **Gate:** 10 checks across 2 projects (ruff, pyright, pytest, eslint+tsc, vitest, next build, placeholder, secrets, osv-scanner, jscpd).
- **Token Factory findings (T001):** [docs/nebius-findings.md](docs/nebius-findings.md).
- **Script module (T005):** `app/script` — `parse_pdf` → ordered scenes; every action/dialogue element carries its page and line span. `resolve_times`, `match_speaker`. Design: [docs/design/script.md](docs/design/script.md).
- **Shot planner (T007):** `app/shots` — each scene becomes shots that cover every element exactly once, cite their page/line span and verbatim text, and name only extracted characters/props present in the scene; time of day from `resolve_times`. Live: `uv run python -m app.shots.run <script.pdf>`.
- **Comic layout (T022):** `app/comic` — `layout_geometry(plan, screenplay)` → pages of panels, one per shot in plan order, sized by framing, establishing beat and lettered text; tiers fill each 1988 × 3075 page exactly; every panel's lettering (Comic Neue, measured) within 35% of its area, or `ComicError` naming the shot. Pure: no frames yet. Design: [docs/design/comic.md](docs/design/comic.md).
- **Frame prompts and styles (T008):** `app/storyboard` — `load_styles` (public `styles/clean|ink|pencil.toml`, optional private pack, every storyboard.md §3.2 rule checked at start-up) and `build_frame_prompt`: tagged parts (style, framing, setting, time, figure count, the covered action lines) where every script part cites this shot's heading, its clock's heading or a covered element; no dialogue, parentheticals, movement or rationale; names redacted by `app/characters/redact.py`; a word budget that only drops or cuts script words. Live: `uv run python -m app.storyboard.prompts <script.pdf> [--style KEY]`.
- **Grounded extraction (T006):** `app/grounding` — scene-chunked extraction on Lightning; every kept quote located to a page/line span; faithfulness + recall; locations from headings, missed speakers from cues. Checkpoint: `uv run python -m app.grounding.run <script.pdf>`.
- **Samples (T031):** `samples/` — three self-written screenplays (demo `the-red-kite`, 11-speaker `lost-property`, tricky-format `sipho-and-siphokazi`) as Fountain source + PDF, rebuilt by `uv run python -m tools.build_samples`; parser findings in `samples/README.md`.
- **Pipeline core (T043):** `app/projects/pipeline.py` — `run_pipeline(pdf, model, on_advance=...)` parses, extracts and plans, announcing each stage with its web.md §3 progress band and the result before it; every failure is a `PipelineError(stage, message)` with web.md §4.1's copy, chosen by code or type (the chunk budget is checked before any model call). No database: T046 runs it as a job. `Screenplay.page_starts`, `ScriptParseError.code`, `ExtractionError.scene`, `ShotError.scene`. Live: `uv run python -m app.projects.run <script.pdf>`.
- **API schemas and views (T044):** `app/api/v1/schemas.py` — every web.md §6 response type as a Pydantic model (a test parses the doc's TypeScript and compares fields, nesting, nullability and unions); `FrameView` refuses an image outside passed/warned. `app/projects/views.py` — pure builders for lines, scenes (`time_carried`), entities, report and shots (`segments`, off-screen dialogue marked). T047 serves them.
- **LLM seam (T004):** `app/llm` — `NebiusChatModel` (fast / reasoning / vision tiers, retries with `Retry-After`, thinking off on fast) and `structured_chat` (strict `json_schema`, one repair retry). Design: [docs/design/llm.md](docs/design/llm.md). Live check: `cd services/api && uv run python -m app.llm.smoke`.

## 🛠️ Environment & access

- FrameFlow (private, `Katlego-tech/FrameFlow`) is the source for every ported module. Both of us have access.
- Nebius Token Factory: $25 promo (`NEBIUS-DEVPOST-GLOBAL26`) + $25 from the AI Builder Program. Keys go in `.env`, never in the repo.
- The original Nebius migration plan (unknowns U1–U6, model tiers, costs) is in
  `~/Documents/projects/personal/frameflow-nebius-hackathon/PLAN.md` on Katlego's machine.

## ⚠️ Open decisions / risks

- **No NVIDIA vision model on Token Factory** (T001). Decided: a Token Factory VLM (DeepSeek-V4.1-Flash since 2026-09-30; GLM-5.3-Flash stopped receiving images) *describes* each frame and Nemotron *judges* it; self-hosting an NVIDIA VLM on the Nebius GPU is a stretch. Wording corrected everywhere to "a vision model describes each frame; Nemotron audits it against the script" (2026-09-30, `docs/spec`), and in `services/api/app/verify/README.md` by T020.
- ~~**Which styles stay private?**~~ **Closed 2026-09-30, decided by the user in session:** none. `clean` (the default), `ink` and `pencil` are public in `styles/`; `classic` is dropped (storyboard.md §8); the private pack is empty. Built by T008.
- **Repo is private.** It must be public before submission (T035).
- **`main` is unprotected on the server** (private + GitHub Free; decided 2026-09-28 to leave it). Only the pre-push hook and AGENTS.md §4 guard it; Tumo must run `bash install-hooks.sh`. Once the repo is public (T035), protection is free — turn it on then.
- **No copyrighted scripts** in the repo, demo or video. Only public-domain or self-written samples.
- GPU cost: $50 of credit covers Token Factory calls, not a GPU VM. Check the cost of the ComfyUI box in T003.
- **Stack changed 2026-09-29** (Katlego): web on Vercel, API on Railway, Supabase for Postgres/Storage/Auth, Redis removed — the Hackathon kit's stack. [docs/design/deploy.md](docs/design/deploy.md). Needs Katlego's Vercel, Railway and Supabase accounts (T037).

## 🔄 Retrospectives (one per phase boundary)

> Prime directive: *every person did the best they could, given what was known at the time.* The
> useful question is what the **written process** failed to say — a design doc that skipped a
> diagram, a `Done:` that wasn't observable, a contract two lanes read differently. Blaming an AI
> is especially useless: it will agree and then repeat the mistake next session. Only a change to a
> file changes the outcome. Format: [docs/iteration-rituals.md](docs/iteration-rituals.md).

### `<Phase N>` — YYYY-MM-DD

- **What happened:** `<from the Log, the merged PRs, the tasks that slipped>`
- **Why:** `<the system cause, not the person>`
- **Committed change:** `<the specific edit to AGENTS.md / a template / scripts/gate.sh — and done>`

## 🗒️ Log

> This is the standup. Every session ends with a line here: **done / next / blocked.** Two or three
> lines — if it needs more, it's a handoff document. Name blockers, don't solve them here.

- 2026-09-27 — Katlego (via Claude) — scaffold, disclosure note, lanes and Phase 1 task list. Next: T001 + T002. Blocked on: nothing.
- 2026-09-28 — Katlego (via Claude) — drafted the Devpost story in `docs/submission/about.md` (`eval+submission`, unclaimed; ⟨TBD⟩s filled by T033–T035). Next: T001 probe. Blocked on: Token Factory key in `.env`.
- 2026-09-28 — Katlego (via Claude) — T001 done: `docs/nebius-findings.md` (json_schema enforced, thinking off works, one host, no image gen, no NVIDIA vision → option A). ~$0.004 of trial credit. Next: T004. Blocked on: nothing.
- 2026-09-28 — Katlego (via Claude) — AGENTS.md §4: fresh-AI-review fallback when the other contributor is unavailable; `main` left unprotected. Next: T002. Blocked on: nothing.
- 2026-09-28 — Katlego (via Claude) — T002: pinned Python 3.14 / Node 24.21 / Next 16.3.6 / PG 18.6 / Redis 8.10.2; compose stack healthy; gate now runs 10 checks. Next: T004 (llm). Blocked on: nothing.
- 2026-09-28 — Katlego (via Claude) — T002 merged (PR #5). T004: `app/llm` client + structured_chat, 32 tests, live smoke passes (fast 0 reasoning tokens, reasoning 62). Next: T005/T006. Blocked on: nothing.
- 2026-09-28 — Katlego (via Claude) — **Lead authorization (AGENTS.md §4 exception):** Katlego authorized PR #4, which changes AGENTS.md itself, to merge without Tumo's review. Reason: Tumo is often unavailable and the deadline is 2026-10-30; Katlego's instruction on 2026-09-28 was "merge all open pull requests and merge PRs once their review is clean". Tumo was not asked. The fresh AI review is still required before merging, and Tumo should read §4 when back. Next: T005/T006. Blocked on: nothing.
- 2026-09-28 — Katlego (via Claude) — Ported the kit's merged-branch cleanup (Cultivation PR #4): `scripts/prune-branches.sh` runs after `git pull` on main; `install-hooks.sh` sets fetch.prune and checks the server setting. Tumo: re-run `bash install-hooks.sh`. Next: T005. Blocked on: nothing.
- 2026-09-28 — Katlego (via Claude) — T005: `app/script` parser with source spans, scene time, speaker matching; 40 script tests incl. a real 2-page PDF. PR #7 merged; PR #8 (Devpost draft) in re-review. Next: T006. Blocked on: nothing.
- 2026-09-28 — Katlego (via Claude) — **Phase 1 checkpoint passed on the real account** (self-written 3-scene sample): faithfulness 1.000 (5/5, 8/8 quotes located), recall 1.000 (2/2 speakers), Lightning, 509 in / 157 out / 0 reasoning tokens. Tiny sample; feature-length recall needs T031. Note: SPEC.md is still the unfilled template. Next: T007 / T031. Blocked on: nothing.
- 2026-09-29 — Katlego (via Claude) — Plan change: adopt the Hackathon kit's stack (Vercel, Railway, Supabase; Redis removed); `docs/design/deploy.md`, T037 added; Hackathon-kit layers being ported on a separate branch. Next: T037 code. Blocked on: hosting accounts for T037's deploy check.
- 2026-09-29 — Katlego (via Claude) — Brought in Hackathon-kit layers (event.toml, ./hack, judged, long) on docs/hackathon-kit-layers. Next: review. Blocked on: nothing.
- 2026-09-29 — Katlego (via Claude) — T037 code: Redis removed (health checks postgres only), `railway.json` + `vercel.json` (both schema-validated), API honours `PORT`, Supabase `postgresql://` URLs accepted; compose healthy without Redis; `docs/deploy.md` account steps. Next: T007. Blocked on: Katlego's Supabase, Railway and Vercel accounts for T037's deploy check.
- 2026-09-29 — Katlego (via Claude) — T037 review fixes: `?sslmode=` → asyncpg `?ssl=` (proven live: raw sslmode fails with TypeError, rewritten connects); `railway.json` dropped (Railway deprecated it, new services can't use it, cutoff 2026-12-01) for documented dashboard settings; Next standalone off on Vercel. Next: T007. Blocked on: accounts for T037's deploy check.
- 2026-09-29 — Katlego (via Claude) — **Lead authorization (AGENTS.md §4 exception):** Katlego authorized **PR #14**, adding the Hackathon kit's judged and long rules to AGENTS.md (new §9, §10). Reason: they come with the Hackathon kit Katlego adopted for this event on 2026-09-29 (PRs #11–#13), Tumo is often unavailable, and the deadline is 2026-10-30. Two corrections: the gate does not check mock imports, and hand-offs use docs/HANDOFF.template.md. Katlego's words: "yes, apply the AGENTS.md rules with your corrections". Tumo was not asked. The fresh AI review is still required before merging; Tumo should read §9–§10 when back. Next: T007. Blocked on: nothing.
- 2026-09-29 — Katlego (via Claude) — T007 shot planner: 23 tests; live on the sample: 7 shots over 3 scenes, every element in exactly one shot, 0 invented names. First live runs showed 8 range repairs (the model padded a 1-element scene with 6 shots); stating the element bounds in the prompt took it to 0 in two runs and halved output tokens. Next: T008 (needs T003's GPU). Blocked on: GPU access for rendering.
- 2026-09-29 — Katlego (via Claude) — T010: `docs/design/verify.md` — blind describer (GLM) + Nemotron judge + code checks; "supported by the script" needs a verified verbatim quote; hard/soft checks; failed frames withheld, never shown; audit log per attempt. Next: T012. Blocked on: GPU (T003).
- 2026-09-29 — Katlego (via Claude) — T012: `docs/design/characters.md` — portraits from action-paragraph quotes only (no names in any image prompt; undescribed stays undescribed), audited; IP-Adapter references (≤2 per frame, left/right masks), Apache-licensed adapter over insightface-based FaceID. Phase 3 designs all in review. Next: merge reviews. Blocked on: GPU (T003).
- 2026-09-29 — Katlego (via Claude) — T007 merged (PR #15). T011: `docs/design/comic.md` — verbatim-only lettering with spans, deterministic tiers/weights, ≤20% crop, bubbles by image detail + reading order, grow-don't-shrink fit. Next: T010, T012. Blocked on: GPU (T003) for any rendering.
- 2026-09-30 — Katlego (via Claude) — SPEC.md filled from PLAN.md and the agreed design docs (US1 P1; US2–US4 P2; Given/When/Then per story incl. withheld text card, unscripted person → re-render, verbatim lettering, undescribed stays undescribed; 8 open questions); "Nemotron vision auditor" corrected to the option A wording in README, PLAN, CLAUDE/GEMINI/AI_ENTRYPOINT, CHANGES-FROM-FRAMEFLOW, project-structure, RUBRIC, TASKS (T020). Next: review + merge (docs/spec). Blocked on: nothing.
- 2026-09-30 — Katlego (via Claude) — T022 comic layout: `app/comic` model + `layout_geometry`/`panel_weight`/`scene_caption`, 30 tests (158 total); Comic Neue Regular + Pillow added (the budget measures text); comic.md clarified (wrapping, passes, forced solo tier, font moved to T022, reference page with T023). Gate 10 checks green. PR #20, reviewed clean, merged. Next: T023 (needs frames). Blocked on: nothing for T022; T023 on T008/T003.
- 2026-09-30 — Katlego (via Claude) — T031: three self-written samples + `tools/build_samples.py` + tests; gate 10 checks green. Found: `INT./EXT.` headings not parsed, pdfplumber `y_density=13` loses ~13% of action-paragraph breaks (13/102), two-dash headings split wrong; live on `the-red-kite`: 19 shots, every element once, but grounding faithfulness 0.625/0.143 and recall 0/3 because Lightning prefixes dialogue quotes with the cue. Next: review, then T032. Blocked on: nothing (the parser/grounding fixes belong to `script+grounding`).
- 2026-09-30 — Katlego (via Claude) — T020 frame audit: `app/verify` (blind describer, Nemotron judge, 7 checks in code, ERROR never passes), 92 tests; live on 3 real storyboard frames against the lighthouse kitchen shot: 3 correct FAILs. **GLM-5.3-Flash no longer receives images** (answers from a 31-token text-only prompt, invents scenes); describer switched to DeepSeek-V4.1-Flash (findings § U7 re-check). Local `.env` sets `NEBIUS_MODEL_VISION=` empty, which overrides the default: set it or delete the line. Next: T008 design doc. Blocked on: nothing.
- 2026-09-30 — Katlego (via Claude) — T039 parser + grounding fixes (PR #25): `INT./EXT.`, 12 pt layout rows (every paragraph break kept), two-dash heading time, wrapped parentheticals; dialogue quotes led by the speech's own cue/parenthetical are kept without it, nothing else loosened. Live on Lightning: the-red-kite faithfulness 0.333→1.000, recall 0/3→3/3; sipho-and-siphokazi 0.333→0.750, 0/4→4/4; lost-property 0.793→0.846, 10/11. Gate 10 checks green; code-reviewer clean. Next: T032. Blocked on: nothing. Open: line-break hyphen in element text (`sea- green`) still drops a copied quote.
- 2026-09-30 — Katlego (via Claude) — `docs/design/storyboard.md` (T008 design): frame prompts from tagged grounded parts only (no dialogue, names redacted, span-checked invariant), TOML style registry with a validated public/private split, ComfyUI-only renderer implementing verify's `Renderer`, content-addressed Supabase Storage as the render cache, Pillow PDF with verbatim source and the withheld card; T008 split in TASKS.md into T008 (styles, prompts: no GPU), T026 (renderer, Storage) and T027 (PDF). Next: team answers §10 (private styles, T003 model, GPU cost). Blocked on: T003 for T026.
- 2026-09-30 — Katlego (via Claude) — `docs/design/web.md` + visual reference (`docs/design/web/*.png`, HTML mockups, `tokens.css`): the storyboard is a lined script (a line per shot over exactly its span, wavy while the speaker is off screen); Project table + Job `project_id`/`stage`; §6 API types; T009 re-scoped to the API and split (T009, T043, T044); T040–T042 and T045 added for the screens. Next: T009. Blocked on: a Supabase project for T040's sign-in check.
- 2026-09-30 — Katlego (via Claude) — T009 suspended by the user until the Supabase account/project exists. Found while starting it: gate.sh and CI run no Postgres, so its DB tests need a gate/CI change (AGENTS.md §4 authorization) or a Supabase-backed test DB, to be decided then. Doc notes for T009: page_starts is T043's (web.md §3 wording to fix); T009 must add SUPABASE_STORAGE_BUCKET; RLS on for projects/jobs with no policies, private bucket. Next: T008. Blocked on: Supabase project (user).
- 2026-09-30 — Katlego (via Claude) — T008 (PR #27): `app/storyboard` styles + `build_frame_prompt`, `app/characters/redact.py`, `styles/clean|ink|pencil.toml` (all public, clean default: decided by the user). 114 new tests (417 in the API); the §9 invariant runs over every consecutive element run of all three samples × 3 styles × 2 budgets, and 6 hand mutations of prompt.py each fail it. Live on the-red-kite: 22 shots, every script part cites this shot, 0 names; lost-property (pencil) 48 shots, same. Two code-reviewer passes; fixed: TIME no longer redacted (a DAWN character), U+02BC apostrophe, finite emphasis. Gate 10 checks green. Open: the API image lacks `styles/` (T026 must ship it); scripted signage ("LOST PROPERTY - PLATFORM 9") reaches prompts and will meet verify's hard TEXT_IN_FRAME (T032); named props ("Gerald") aren't redacted. Next: T032 / T026 when T003 lands. Blocked on: nothing for T008; T026 on T003 (GPU).
- 2026-09-30 — Katlego (via Claude) — T043 pipeline core (no database; T009 suspended by Katlego until a Supabase project exists): `run_pipeline` + `PipelineError` with §4.1 copy by code/type, chunk budget pre-checked, `on_advance` per stage (one hook so T046 writes a stage's column with the job's advance in one transaction); `page_starts`, `ScriptParseError.code`, `.scene` on extraction/plan errors; T046 added for the job half. 332 tests, gate 10 checks green. Live on the-red-kite: 10.1 s, 5 pages / 5 scenes / 43 elements, 8 entities (faithfulness 1.000, recall 3/3), 21 shots, every element once. Next: review, then T044 (view layer). Blocked on: nothing for T043; T046 on T009.
- 2026-09-30 — Katlego (via Claude) — T044 rescoped to the §6 schemas and pure view builders (no database); T047 added for the read endpoints and the `frames` table (T041, T021 now depend on it). `schemas.py` + `views.py`, 46 new tests (492 in the API), gate 10 checks green; code-reviewer clean (PR #28). Next: then T040 or T032 while T009 waits. Blocked on: nothing for T044; T046, T047 on T009 (a Supabase project).
- 2026-09-30 — Katlego (via Claude) — T023 comic lettering + export (PR #29): `place_lettering` (verbatim `Dialogue.text` + span per bubble/caption, 12×8 inset grid, detail + speaker cost, reading order hard, 32→28 px, else `ComicError`), `panel_frame`/`withheld_checks`/withheld card (withheld pixels never decoded), `render_pages`, `to_pdf`, `to_json`; reference `docs/design/comic/the-red-kite-page-1..6.png` (fixture frames marked, one card) re-rendered by the gate. comic.md pinned: hyphen lettered as the element has it, rounded-rect bubbles, no SPEECH tail on a card, missing glyph → `ComicError`, drawing order. 52 new tests (544 in the API); gate 10 checks green; code-reviewer clean. Next: T032. Blocked on: nothing for T023; the comic job and a check on real renders wait on T026 (GPU, T003). Open: sound effects (comic.md §10); parser join of line-break hyphens.
