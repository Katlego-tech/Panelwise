# `Panelwise` — Handoff

> Earlier handoffs (2026-10-03 Katlego → Tumo, 2026-10-11 Tumo → Katlego) are in git history:
> `git log -- docs/HANDOFF.md`.

**Written:** 2026-10-17 (evening, SAST) · **By:** Tumo (via Claude), for Katlego · **Why:** Tumo is
taking a break. Katlego (or Tumo, coming back) picks up from here, and updates STATUS.md and
anything else that needs it. **Branch of this note:** `docs/handoff-1017` (PR into main).

---

## 1. What is done (2026-10-17)

- **§ U8's lighthouse table is complete** (Katlego's ask on #194): people 25 of 25, the sex agent
  23 of 23, the judge's matches 23 of 25, presence 2 against 0. Commit `e64d095` on
  `docs/audit-labels` (#194).
- **Two held-out runs on Super VL, every frame looked at.** Reports and eye verdicts:
  `eval/runs/2026-10-17-rooftop-tomatoes.md` (main: 21 of 21 shown, 11 right, 6 weak, 4 wrong) and
  `eval/runs/2026-10-17-gogos-recipe.md` (Katlego's `feat/bubbles-t098`: 17 of 17 shown, 8 right,
  4 weak, 5 wrong; its comic's bubbles looked at too). **Every wrong frame in both is one person
  drawn twice or an extra person.**
- **T109 designed, reviewed:** PR **#199** (`docs/describer-caps-t109`). Every Super VL describer
  `ERROR` is a loop at temperature 0 cut off at 4,096 tokens. Length limits sent in the decoding
  grammar only end 7 of 7 loops, and 10 of 10 other frames answer byte for byte as before. A fresh
  review found nothing blocking; its fixes are pushed (gate passed). The code is not started.
- **T110 measured:** `eval/measurements/t110/README.md`. **Proposed: no code change.** The 6 absent
  frames slip through because of the stored extraction (no sex for TEBOGO, a sexless FORTUIN
  before T101, CROWD as a character) and drawn-twice frames, not the presence agent. Tumo hasn't
  confirmed yet.

**Not started:** T109's code; the two runs' labels in `eval/frame-labels.json`; the-choir (the
last held-out script, unread); T108; re-measuring T102/T104 on Super VL; T030.

## 2. Decisions already locked (don't reopen)

- T109's fix is **limits in `response_format` only**, the prompt's schema text unchanged. Rejected
  with numbers (verify.md §8): limits in the prompt too (changed 7 of 10 answers that hit no limit),
  `frequency_penalty` (fewer objects on every frame), a prompt sentence (2 of 7), temperature 0.3
  (2 of 7), a larger `max_tokens`, salvaging cut-off JSON.
- T109's limits: 24 people, 40 objects, 40 text entries of up to 100 characters, appearance up to
  200, object name up to 60. A list **at** its limit is never passed silently: 24 people fail
  `UNSCRIPTED_PERSON`, 40 objects `BACKGROUND_OBJECT`, each with a limit detail (the review's
  Non-negotiable I point).
- **Nothing merges into main without Tumo's go-ahead, per PR** (Vercel deploys main).

## 3. Open PRs and the merge order (when Tumo says go)

Ours: #181 → #183 (T102), #186 → #187 (T104, migration 0009), #184 → #185 (T103), #194 (eval),
#199 (T109 design). Order: #181, retarget #183 to main, merge; retarget #186, merge; retarget #187,
merge (only then may `render.yaml` carry `split_panels`); #184, retarget #185, merge; #194; #199.
Retarget each child to main **before** merging its base (the repo auto-deletes merged branches).
Check CI on each after retargeting. Katlego's #193 (T097 code, 0010) follows #187, then #195 (T098).

## 4. Decisions waiting on Tumo

1. **The reply on #194** (drafted, not posted): agree to Katlego's paid-run rule (post on the PR
   before any paid run), T109 and T110 are Tumo's, and note that Tumo's rooftop-tomatoes run
   (17:46–17:52 UTC) overlapped Katlego's T098 run unannounced (0 errors, no 404s).
2. **Close T110 as measured, no change?**
3. **Where the two runs' labels go:** proposed, a branch stacked on #194 (`frame-labels.json` is
   only there), with `eval/tools/make_labels.py`.
4. **T098's tails** (Katlego's lane, for #195): on gogos-recipe's comic, 3.1 and 5.4's tails point
   away from their speaker because the head box carries no name (the judge left the person
   unmatched). Not yet posted on #195.

## 5. Next steps, in order

1. Tumo's answers to §4.
2. **T109 code** to #199's contract (verify.md § T109 contracts, llm.md §6): tests first
   (`tests/verify/test_t109.py`, the llm body test), a worktree from main, a fresh reviewer. Then
   `eval/tools/score_labels.py` on the 109 labelled frames with Super VL (about $0.25, Tumo's go-ahead).
3. Label rooftop-tomatoes and gogos-recipe into `eval/frame-labels.json` from the two reports'
   tables (§1), then `score_labels.py --stored`.
4. **Drawn-twice frames** (T104 is ours, on #187): measure for free on today's stored frames why the
   layout agent passes 3 of 5 copies ("different faces, hair") before any design. It's the fault
   behind most wrong frames today.
5. **the-choir**, the last held-out script: arm the watcher, Tumo uploads, report, look at every
   frame, label.
6. T108 (the look match: "pigtails" for "braids"); T102/T104 re-measured on Super VL once merged.
7. T030: the judge seed on the hosted Supabase (Tumo's go-ahead), the hosted end-to-end run; check
   the hosted API reached migration 0009 after the merges.
8. The tail: T036, T055, README feedback (the team's words), T034, gitleaks since 2026-10-05,
   Devpost text, the final hosted smoke, submit on 29 Oct. **fal top-ups: $10 before 1 Nov, $5
   before 1 Dec.**

## 6. How to run it (Tumo's machine)

- **The local stack runs Katlego's branch, not main:** the API is built from the worktree
  `../pw-t098` (detached at `eed335d`) through a compose override that also sets Super VL with
  thinking off, klein, 3 attempts and the ladder `drawn_sex,no_character,split_panels` (Tumo's
  `.env` still names DeepSeek). **The local database is at migration 0010.** main's code doesn't
  know 0010: to run main again, `alembic downgrade 0008` first (or reset the local database).
- **Test database** (`pw-t062-pg`, 127.0.0.1:55432): at main's migrations (no 0009) since the last
  gate. Before pushing a branch with 0009 nothing is needed; after a T104 gate, drop every
  `panelwise*_test` database and recreate `panelwise_test` before pushing a branch without it.
- **Worktrees:** `../pw-t103`, `../pw-t104`, `../pw-labels` (#194), `../pw-t098` (Katlego's code,
  detached), `../pw-t109` (#199), `../pw-handoff` (this note). A new worktree needs `uv sync` in
  `services/api` and `pnpm install --frozen-lockfile` in `apps/web` before its first gate.
- **Running a probe in the API container:** copy it in (`docker cp` with forward-slash Windows paths
  and `MSYS_NO_PATHCONV=1`), then `cd /srv/api && PYTHONPATH=/srv/api .venv/bin/python /tmp/x.py`.
  `/work` doesn't exist and `/` isn't writable: use `/tmp`. Pull results out with `docker cp`.
- **Pulling a run's frames:** `eval/measurements/2026-10-16/fetch_shots.py` (on #194; change
  `/work/fs` to `/tmp/fs`); a comic's pages: `eval/measurements/2026-10-17-runs/fetch_comic.py`;
  contact sheets: `sheets.py` there. Watchers: `wait_comic.sh` there; `wait_run.sh` polls the
  newest project after a cutoff.
- **Gate:** push with `TEST_DATABASE_URL=postgresql://postgres:pw@127.0.0.1:55432/panelwise_test
  PANELWISE_REQUIRE_DB=1`. 11 checks on a code change; **10 on a docs-only push** (the secret sweep
  has nothing to sweep and isn't counted). That's expected, not a skipped check.

## 7. Verified facts

- Token Factory's strict `json_schema` decoding **enforces `maxItems` and `maxLength`** on Super VL.
- Super VL is near-deterministic at temperature 0: the unchanged describer call reproduced the
  stored answer on 9 of 10 frames.
- The describer's stored answers never exceed 21 people / 32 objects (DeepSeek, 1,352) or
  33 text entries (Super VL, 79: a calendar's dates).
- T104 live (gogos-recipe): `split_panels` withheld 1.4's strip and the redraw was shown; on the
  comic it withheld 3.4 after 3 strips.

## 8. Gotchas

- Never read the repo-root `.env` or `apps/web/.env.local` (a deny rule blocks it anyway).
- Don't open the-choir's script until its run has finished.
- The scorer's labels and bundles live on #194's branch only, until it merges.

## 9. Corrections

None.
