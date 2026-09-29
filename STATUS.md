# `Panelwise` — STATUS

> Source of truth for "what's going on right now." Read first, update last. Treat updating it as
> part of "done." (This is the blank template — copy to `STATUS.md` and keep that one live.)

_Last updated: 2026-09-28 — by Katlego (via Claude)_

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
| `script+grounding` | Parser, scene time, dialogue linker, extraction, grounding filter | T005, T006 | | | ✅ T005, T006 done |
| `shots` | Shot planner | T007 | | | ⬜ To Do |
| `storyboard` | Frames, style registry (public/private split), image chain, PDF | T008 | | | ⬜ To Do |
| `web` | Next.js app: upload → shots → storyboard → comic reader | T009, T024 | | | ⬜ To Do |
| `verify` | Nemotron vision frame audit, re-render loop, audit log | T010, T020, T021 | | | ⬜ To Do |
| `comic` | Page layout, panel sizing, speech bubbles, comic export | T011, T022, T023 | | | ⬜ To Do |
| `characters` | Reference portraits for consistent characters | T012, T025 | | | ⬜ To Do |
| `eval+submission` | Samples, benchmarks, video, disclosure table, go public | T031–T035 | | | ⬜ To Do |

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
- **Web** (`apps/web`, Next.js 16, pnpm): `GET /api/health` reports web + API health; 502 when the API is unreachable. No pages yet (T009).
- **Gate:** 10 checks across 2 projects (ruff, pyright, pytest, eslint+tsc, vitest, next build, placeholder, secrets, osv-scanner, jscpd).
- **Token Factory findings (T001):** [docs/nebius-findings.md](docs/nebius-findings.md).
- **Script module (T005):** `app/script` — `parse_pdf` → ordered scenes; every action/dialogue element carries its page and line span. `resolve_times`, `match_speaker`. Design: [docs/design/script.md](docs/design/script.md).
- **Grounded extraction (T006):** `app/grounding` — scene-chunked extraction on Lightning; every kept quote located to a page/line span; faithfulness + recall; locations from headings, missed speakers from cues. Checkpoint: `uv run python -m app.grounding.run <script.pdf>`.
- **LLM seam (T004):** `app/llm` — `NebiusChatModel` (fast / reasoning / vision tiers, retries with `Retry-After`, thinking off on fast) and `structured_chat` (strict `json_schema`, one repair retry). Design: [docs/design/llm.md](docs/design/llm.md). Live check: `cd services/api && uv run python -m app.llm.smoke`.

## 🛠️ Environment & access

- FrameFlow (private, `Katlego-tech/FrameFlow`) is the source for every ported module. Both of us have access.
- Nebius Token Factory: $25 promo (`NEBIUS-DEVPOST-GLOBAL26`) + $25 from the AI Builder Program. Keys go in `.env`, never in the repo.
- The original Nebius migration plan (unknowns U1–U6, model tiers, costs) is in
  `~/Documents/projects/personal/frameflow-nebius-hackathon/PLAN.md` on Katlego's machine.

## ⚠️ Open decisions / risks

- **No NVIDIA vision model on Token Factory** (T001). Decided: a Token Factory VLM (GLM-5.3-Flash) *describes* each frame and Nemotron *judges* it; self-hosting an NVIDIA VLM on the Nebius GPU is a stretch. SPEC, README and the Devpost draft still say "Nemotron vision auditor" and must be corrected.
- **Which styles stay private?** Decide before T008 moves styles over. The demo may only use public styles.
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
- 2026-09-29 — Katlego (via Claude) — T037 code: Redis removed (health checks postgres only), `railway.json` + `vercel.json` (both schema-validated), API honours `PORT`, Supabase `postgresql://` URLs accepted; compose healthy without Redis; `docs/deploy.md` account steps. Next: T007. Blocked on: Katlego's Supabase, Railway and Vercel accounts for T037's deploy check.
- 2026-09-29 — Katlego (via Claude) — T037 review fixes: `?sslmode=` → asyncpg `?ssl=` (proven live: raw sslmode fails with TypeError, rewritten connects); `railway.json` dropped (Railway deprecated it, new services can't use it, cutoff 2026-12-01) for documented dashboard settings; Next standalone off on Vercel. Next: T007. Blocked on: accounts for T037's deploy check.
