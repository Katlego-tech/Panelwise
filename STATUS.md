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
| `llm` | Nebius Token Factory provider, model tiers, structured_chat | T001, T004 | Katlego | Claude | 🔵 In review (T001) |
| `infra` | Pinned versions, docker-compose, ComfyUI on a Nebius GPU, hosted demo | T002, T003, T030 | | | ⬜ To Do |
| `script+grounding` | Parser, scene time, dialogue linker, extraction, grounding filter | T005, T006 | | | ⬜ To Do |
| `shots` | Shot planner | T007 | | | ⬜ To Do |
| `storyboard` | Frames, style registry (public/private split), image chain, PDF | T008 | | | ⬜ To Do |
| `web` | Next.js app: upload → shots → storyboard → comic reader | T009, T024 | | | ⬜ To Do |
| `verify` | Nemotron vision frame audit, re-render loop, audit log | T010, T020, T021 | | | ⬜ To Do |
| `comic` | Page layout, panel sizing, speech bubbles, comic export | T011, T022, T023 | | | ⬜ To Do |
| `characters` | Reference portraits for consistent characters | T012, T025 | | | ⬜ To Do |
| `eval+submission` | Samples, benchmarks, video, disclosure table, go public | T031–T035 | | | ⬜ To Do |

## ⏭️ Next action

1. **T004** — Nebius provider with tiers, built to [docs/nebius-findings.md](docs/nebius-findings.md)
   (T001 answers are in; no exploratory calls needed). `infra` (T002) can run in parallel.

## 🗓️ Timeline to 2026-10-30 10:00 PDT (19:00 SAST)

| Week | What | Target window | Status |
|-------|------|---------------|--------|
| 1 | Token Factory check; versions + compose; ComfyUI on Nebius GPU; port llm, script, grounding | 28 Sep – 4 Oct | ⬜ |
| 2 | **US1**: script → grounded storyboard on Nemotron, end to end in the web app. Design docs for verify + comic | 5 – 11 Oct | ⬜ |
| 3 | **US2**: frame audit + re-render + audit log. **US4**: reference portraits | 12 – 18 Oct | ⬜ |
| 4 | **US3**: comic pages + reader. Hosted demo live | 19 – 25 Oct | ⬜ |
| 5 | Hardening, eval numbers, video, README, repo public, **submit by 29 Oct** (one day of buffer) | 26 – 30 Oct | ⬜ |

## 🧱 What's built so far

- Scaffold only (Cultivation kit, folder structure, licence, disclosure note). No code yet.

## 🛠️ Environment & access

- FrameFlow (private, `Katlego-tech/FrameFlow`) is the source for every ported module. Both of us have access.
- Nebius Token Factory: $25 promo (`NEBIUS-DEVPOST-GLOBAL26`) + $25 from the AI Builder Program. Keys go in `.env`, never in the repo.
- The original Nebius migration plan (unknowns U1–U6, model tiers, costs) is in
  `~/Documents/projects/personal/frameflow-nebius-hackathon/PLAN.md` on Katlego's machine.

## ⚠️ Open decisions / risks

- **No NVIDIA vision model on Token Factory** (T001). Decided: a Token Factory VLM (GLM-5.3-Flash) *describes* each frame and Nemotron *judges* it; self-hosting an NVIDIA VLM on the Nebius GPU is a stretch. SPEC, README and the Devpost draft still say "Nemotron vision auditor" and must be corrected.
- **Which styles stay private?** Decide before T008 moves styles over. The demo may only use public styles.
- **Repo is private.** It must be public before submission (T035).
- **No copyrighted scripts** in the repo, demo or video. Only public-domain or self-written samples.
- GPU cost: $50 of credit covers Token Factory calls, not a GPU VM. Check the cost of the ComfyUI box in T003.

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
- 2026-09-28 — Katlego (via Claude) — T001 done: `docs/nebius-findings.md` (json_schema enforced, thinking off works, one host, no image gen, no NVIDIA vision → option A). ~$0.004 of trial credit. Next: T004. Blocked on: nothing.
