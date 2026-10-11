# `Panelwise` — Handoff

> The record of 2026-10-03's handoff (Katlego → Tumo) is in git history: `git log -- docs/HANDOFF.md`.

**Written:** 2026-10-11 · **Branch:** `main` (everything is merged) · **By:** Tumo (via Claude), for Katlego

---

## 1. What is done

All of this is on `main`, each change gated and independently reviewed. Run `bash scripts/gate.sh`: 11 checks, 1,042 API tests and 338 web tests on the day of writing.

- **The renderer (T026, #90/#91).** fal.ai, with **FLUX.2 [klein] 4B** as the default `FAL_MODEL`. Your klein choice in #97/#98 was right; fal won only because it was already built and live-tested. #97/#98 are closed with a note.
- **The storyboard.**
  - **T027 (#96/#99):** the PDF export.
  - **T066 (#100/#101):** one failed frame no longer stops the board.
  - **T070 (#110/#111):** Storage retries a transient error.
- **The comic.**
  - **T067 (#102/#103):** one failed panel no longer stops the comic.
  - **T073 (#112/#113):** panels render as many at once as the renderer allows; 5 min instead of 38.
  - **T065 (#94/#95):** lettering is placed as a set (your #92 repro).
- **The prompt (storyboard.md §3.1).**
  - **T074 (#118/#119):** each visible character's age from their introduction (`LERATO (10)` → "a 10-year-old").
  - **T079 (#127/#128):** their sex from the introduction's own pronouns ("a 10-year-old girl"); their look, verbatim ("braids tied back"); listeners on screen for a line spoken off screen.
- **The audit (verify.md).**
  - **T071 (#114/#115):** only legible text the script didn't write fails; `RENDER_MAX_ATTEMPTS`; `python -m app.verify.reaudit`.
  - **T072 (#116/#117):** the judge refuses a wrong age, knows set dressing, and treats weather as an event.
  - **T077 (#125/#126):** a signature only warns (Tumo's decision).
  - **T078 (#123/#124):** a part of a shot's prop counts as that prop ("kite string"); the describer skips the drawing's own marks.
  - **T080 (#129/#130):** the judge refuses a wrong sex or look; a frame with none of the people the prompt drew fails `NO_CHARACTER`.
- **Plumbing.**
  - **T075 (#120/#121):** model calls ride out a minute of dropped connections.
  - **T076 (#122):** the frame sheet sits above the board.
  - **T068 (#104/#105):** the gate builds the API image.
  - **T069 (#108/#109):** the hosted demo's caps and judge seed; migration `0006`.
- **Not started:** everything in §6.

## 2. Decisions already locked (do not relitigate)

- **fal.ai with klein** (Tumo, 2026-10-11). On the-red-kite at 3 attempts a frame it accepted **15 of 22** frames, against 3 of 21 for schnell. `FAL_MODEL` makes the model one setting.
- **A signature only warns** (T077, Tumo). It is no character, prop, line or event. Legible words read inside it still fail as text.
- **Every word in a prompt traces to the script.** The age, sex word and look come only from the line that introduces the character (storyboard.md §3.1's invariant, tested).
- **The audit is measured on stored drawings first.** Same prompt and seed give the same drawing, so `reaudit` and the scorecard test an audit change for free. Only a prompt or renderer change needs new drawings.

## 3. Environment — how to run it

```
bash scripts/gate.sh        # with TEST_DATABASE_URL=postgresql://…/panelwise_test PANELWISE_REQUIRE_DB=1
python -m app.verify.reaudit <project-id> [--target storyboard|comic] [--limit N]   # writes nothing
```

- **Live settings:** `FAL_KEY`; `FAL_MODEL` (default klein); `FAL_CONCURRENCY=2`; `RENDER_MAX_ATTEMPTS` (1–3, default 3); `NEBIUS_MODEL_VISION=deepseek-ai/DeepSeek-V4.1-Flash`; `LLM_MAX_ATTEMPTS` (default 5, so an old `.env` saying 3 overrides it).
- **Run gates one at a time.** Never run two DB test suites at once on one test Postgres: they collide.
- **New worktrees:** run `pnpm install --frozen-lockfile` in `apps/web`, or the gate's web checks don't run.

## 4. Verified facts

- **klein's sizes.** It draws in multiples of **32**, so 1280 × 720 comes back 1280 × 736. `fit` crops it, and the size check accepts up to 31 px more than asked.
- **Run-to-run noise.** The judge's verdicts move by about ±1–2 frames per run on everyday objects. Compare runs on the same stored drawings, not single numbers.
- **Cost.** A red-kite run at 3 attempts is about 49 drawings.
- **Where frames still fail** (klein run, after T077):
  - unscripted everyday objects (the judge), about two-thirds of withholds;
  - painted text;
  - an occasional invented person.
- **T080 on that run's stored drawings.** It caught the empty roof (1.3) and some boys drawn as Lerato. It still accepted the boy in 3.1, 4.1, 4.4 and 5.1: the judge only sees Lerato's extracted quotes. T079 fixes this at the source, but it is not yet measured live (§6, step 1).
- **The labelled frames.** On your 27 labelled frames (eval.md §6a) T078 gave 23/27 agreement. T077 lowers agreement by 2, because your labels count a signature as bad. Relabel those two as a note, or keep them and read the number knowing why.

## 5. Corrections

- I said #91 "runs klein with no code change". It didn't: the size check refused 736. Fixed in #91 before merging.

## 6. Next steps, in order

1. **The first live run of T079 + T080.** Upload the-red-kite (klein, 3 attempts, about $0.15–0.20) and check:
   - that Lerato is drawn as a girl with braids;
   - that shot 1.3 shows her;
   - how many of 22 frames are accepted (15 before).
2. **Re-point #107 (T049) at `main`.** Its base, `feat/t026-workers-ai`, is closed. Then re-run the scorecard with the new audit.
3. **The judge on everyday objects**, the biggest remaining lever. A wording that called everyday things set dressing gained nothing and let a wrong person through (verify.md §8). Measure any idea on stored drawings first.
4. **Lettering vs signature.** Since T077, gibberish lettering the describer calls a signature only warns (the klein run's 4.2).
5. **Props a shot needs but the frame lacks** ("the kite under her arm"). Nothing checks this yet.
6. **Weather.** "A storm" in the script doesn't yet support a drawn lightning bolt.
7. **Deploy.**
   - Hosted settings: `FAL_KEY`, `FAL_MODEL`, `RENDER_MAX_ATTEMPTS=3`.
   - Render vs Railway: your #80/#81, conflicting now.
   - Batch-sign frame URLs: the board takes 7–29 s to load.

## 7. Gotchas

- **Stacked PRs and STATUS/TASKS conflicts.** Every PR adds a row near the same anchors. Merge `main` in and keep both rows, checking for duplicates.
- **`_ACTION_FLOOR`.** Looks give way to the 55-word budget and keep 12 words for actions. Don't make `LOOK` a fixed part: a two-character shot would exceed 55 and fail to render.
- **The deferred import.** `audit_frame` imports `visible_characters` inside the function, because `app.storyboard`'s renderer modules import `app.verify`.

## 8. Open questions

- Should "every shot character missing" also count characters the prompt didn't draw? T080 says no, on purpose.
- Should the comic run at 3 attempts too? It does now (`RENDER_MAX_ATTEMPTS`); watch the spend.
