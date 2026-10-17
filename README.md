# Panelwise

**Script → storyboard → comic, grounded in the screenplay at every step.**

Panelwise turns a screenplay into a shot-by-shot storyboard and then into a comic book. Every panel
traces back to a verbatim span of the script. NVIDIA Nemotron on Nebius Token Factory extracts the
characters, props and locations and plans the shots. Code then checks every quote the model gives
against the script, and anything it can't find is dropped. Each frame is drawn by FLUX.2 [klein] 4B
on fal.ai, a vision model describes it, and Nemotron audits that description against the shot. A
frame that fails a check that withholds is re-rendered, and after the last try it is withheld,
never shown. Which checks withhold is a setting; on the hosted demo it is two of the five hard
checks, and a frame that fails one of the other three is shown with a warning naming it
([§ How it works](#how-it-works)).

Built for the [Nebius x NVIDIA Global AI Hackathon](https://nebiusglobalaihackathon.devpost.com/)
(Best Apps and Agents track). Panelwise builds on FrameFlow, an earlier private project by the same
team: [CHANGES-FROM-FRAMEFLOW.md](CHANGES-FROM-FRAMEFLOW.md) says what was ported and what is new.

## What works today

As of 2026-10-17, on `main`:

| Stage | State | Try it |
| --- | --- | --- |
| Parse a screenplay PDF into scenes, action and dialogue, each with its page and line span | built | [§ Run it](#run-it) |
| Grounded extraction on Nemotron: characters, props, locations, every quote located in the script | built, measured | `app.grounding.run` |
| Shot planning on Nemotron: every action paragraph and speech in exactly one shot | built, measured | `app.shots.run` |
| Frame prompts from the shot's own script words, names redacted | built | `app.storyboard.prompts` |
| Rendering: FLUX.2 [klein] 4B on fal.ai, at most one megapixel a drawing (T026) | built, run live on the samples | upload a script with `FAL_KEY` set |
| Frame audit: a vision model describes, Nemotron judges, two one-question vision agents check a character's sex and presence, code runs the checks (T020, T094, T095, T099) | built, run live on every run in [eval/runs/](eval/runs/README.md) | `app.verify.run`, `app.verify.report` |
| The re-render loop: up to 3 drawings a frame, withheld after the last; every attempt and its audit kept (T021) | built, run live | the storyboard's frame sheet |
| The storyboard PDF (T027) | built | *Export PDF* on the storyboard |
| The comic: panels drawn and audited at their own size, laid out by shot, dialogue lettered verbatim, a reader and a PDF (T022, T023, T064, T024) | built, run live on real renders | *Make the comic* on a project's comic tab |
| Web app: sign-in, the projects list with upload and each job's live state, the script page (every entity with its quotes and spans, faithfulness and recall), the storyboard (the script with a line over each shot's span beside a board of frame cards), the frame sheet with the audit log of every attempt and "Try another render", the comic reader | built, run live on Supabase (T040–T042, T045, T061, T024) | `docker compose up --build --wait`, then `localhost:3000` ([§ Run it](#run-it)) |
| The hosted demo: web on Vercel, API on Render, Supabase for Postgres, Storage and Auth | up since 2026-10-16, health checks green; still to do: the judge account and the first storyboard drawn on the hosted stack (T030, T037) | [§ The hosted demo](#the-hosted-demo) |
| Not built: reference portraits for consistent characters (T025); ComfyUI on a Nebius GPU (T003, optional since fal.ai); the audit's precision and recall on a labelled set (T049) | — | — |

[STATUS.md](STATUS.md) is the live board. The order of what's left is in its *Next action* section.

## How it works

```mermaid
flowchart LR
  PDF[Screenplay PDF] --> P[Parse scenes + dialogue<br/>page and line spans]
  P --> G[Grounded extraction<br/>Nemotron 3.5 Lightning]
  G --> F{Every quote<br/>found in the script?}
  F -- no --> X[Dropped, reported]
  F -- yes --> S[Shot planning<br/>Nemotron 3.5 Lightning]
  S --> R[Render frame<br/>FLUX.2 klein 4B on fal.ai]
  R --> D[Describe frame<br/>vision model, blind to the shot]
  D --> V{Audit<br/>Nemotron 3 Super judges,<br/>code runs the checks}
  V -- withheld check failed --> R
  V -- pass or warn --> B[Storyboard PDF]
  V -- pass or warn --> C[Comic pages<br/>dialogue lettered verbatim]
```

The rule behind every box, Non-negotiable I in [PLAN.md](PLAN.md): **a panel may never show a
character, prop, line of dialogue or event that isn't in the screenplay, and every panel traces to
a verbatim source span.** It is enforced in code after each model call, not asked for in a prompt:

- **Extraction.** Every entity the model proposes comes with quotes. Each quote must be found,
  word for word, inside one scene heading or element, and it keeps that page and line span. A quote
  that can't be found is dropped. An entity left with no found quote, or whose name the script never
  writes, is dropped too. Speaking characters the model misses are added from the script's own
  dialogue cues ([docs/design/grounding.md](docs/design/grounding.md)).
- **Shots.** Each shot covers a run of the scene's elements and cites their exact text and span.
  Character and prop names that weren't extracted for that scene are removed
  ([docs/design/shots.md](docs/design/shots.md)).
- **Frame prompts.** A prompt carries only the shot's own action lines, setting and time. Dialogue
  is left out, and character names are redacted. A character's sex reaches the prompt only when the
  script's own words give it (a pronoun, a title such as MR or MAMA, a noun such as "a boy")
  ([docs/design/storyboard.md](docs/design/storyboard.md) §3.1).
- **Frame audit.** The vision model describes the frame without seeing the shot. Nemotron matches
  that description to the shot, and code runs eleven checks
  ([docs/design/verify.md](docs/design/verify.md) §3). Five are hard: a person the script doesn't
  have, an animal or weapon it doesn't have, the wrong interior or exterior, none of the shot's
  characters drawn, and a character drawn as the other sex. The last two use the same vision model
  for one narrow question each: the sex agent asks about one matched person, and the presence agent
  asks which drawn person, if any, is a character the judge left unmatched. Six are soft and only
  warn: a missing character, the wrong light or framing, lettering or a signature in the frame, an
  everyday object the script didn't mention. An audit that errors never passes.
- **Which checks withhold.** A failed hard check withholds the frame only when it is on the rule
  ladder, `AUDIT_WITHHOLD_CHECKS` (T094). The code default is every hard check; the hosted demo
  withholds on `drawn_sex,no_character`. A frame that fails another hard check is shown, marked as
  warned, with the failed check named on its card and in its audit log, never presented as passing.
  So today Non-negotiable I's "never shown" holds for the checks on the ladder, and the rest are
  shown and named. Why: with every hard check withholding, the held-out script market-day showed 0
  of 15 shots though about 12 of the 15 final drawings were right (klein fills a market with
  shoppers, and each one failed as an unscripted person); with none withholding it showed 16 of 17
  ([eval/runs/](eval/runs/README.md), [docs/learning-log.md](docs/learning-log.md) L020). Each rule
  comes back on the ladder after it is measured.
- **Comic.** Every bubble is a line of dialogue from the shot, verbatim, carrying its span. Each
  panel is drawn and audited at its own size. A withheld frame is drawn as a card naming the failed
  checks, never as its pixels ([docs/design/comic.md](docs/design/comic.md)).

<p align="center">
  <img src="docs/design/comic/the-red-kite-page-1.png" width="420"
       alt="Comic page 1 of the sample the-red-kite: panels laid out by shot, with the dialogue lettered verbatim in bubbles. The frames are hatched test-fixture figures, not renders.">
  <br><sub>A comic reference page from the sample <code>the-red-kite</code>. The layout, captions and bubbles are produced by the real code; the
  frames are test fixtures, labelled as such, so the gate can compare the page pixel for pixel. In the app the frames are klein's drawings.</sub>
</p>

## How Nemotron and Token Factory are used

Every model call goes to **Nebius Token Factory**'s OpenAI-compatible API, through one client
(`services/api/app/llm`). Before writing any code we measured what the service actually does, with
real calls, in [docs/nebius-findings.md](docs/nebius-findings.md). Several answers differed from
the catalog, and the design follows the answers.

| Tier | Model | Used for | Why this model |
| --- | --- | --- | --- |
| fast | `nvidia/Nemotron-3_5-Lightning` | extraction, shot planning | Token Factory **enforces** a strict `json_schema` on it (U1), which schema-bound extraction needs. It allows 600 requests and 400K tokens a minute (U4) at $0.06 / $0.24 per million tokens. Thinking is switched off: that took a one-number answer from 271 output tokens to 4 (U2) |
| reasoning | `nvidia/nemotron-3-super-120b-a12b` | the frame-audit verdict | A judgement call over the shot's grounded spec and the frame's description, with thinking on |
| vision | `deepseek-ai/DeepSeek-V4.1-Flash` | describing a rendered frame, blind to the shot; the sex and presence agents' one-person questions | **No Nemotron model on Token Factory accepts images** (U7), so this non-NVIDIA model only describes and answers narrow questions. Nemotron judges; code applies the checks |

Images are drawn by FLUX.2 [klein] 4B on **fal.ai**, because Token Factory serves no
image-generation model (U5, re-checked 2026-10-08). ComfyUI on a Nebius AI Cloud GPU was the first
plan; a GPU kept up until judging ends would cost about $2,500, so it stays an optional backend we
don't use (T003, [docs/design/storyboard.md](docs/design/storyboard.md) §3.5). Every drawing is at
most one megapixel, $0.003 each.

Details that came out of measuring rather than reading the docs:

- Strict `json_schema` is enforced. `json_object` returns valid JSON in the wrong shape, and
  `guided_json` is ignored (U1). The client sends `json_schema` and keeps one repair retry as a
  backstop (`structured_chat`, [docs/design/llm.md](docs/design/llm.md)).
- Only two of the four switches we tried actually turn thinking off (U2).
- Rate limits are per model and come back on every response. The client honours `Retry-After`
  on 429 instead of backing off blindly (U4).
- The first vision model we chose silently stopped receiving images between two dates and began
  answering from text alone. A re-check caught it, and the describer moved to DeepSeek
  (findings § U7 re-check).
- The audit, not the extraction, is where the tokens go: two calls a drawing (the describer, then
  the judge), plus the agents' questions when they run, and up to 3 drawings a shot; a 30-shot
  script at 3 attempts can use about 500,000 tokens (docs/learning-log.md L007). One storyboard and
  comic of the-red-kite took 339,000 tokens and 44 drawings (2026-10-16, [STATUS.md](STATUS.md)).

## Measured results

### Extraction and shot planning

On the three self-written sample screenplays of [T031](samples/README.md), 5 live runs each on
Nemotron 3.5 Lightning (2026-10-01):

| | Result |
| --- | --- |
| Ungrounded quotes or shot citations kept, re-checked in code | **0** in all 15 runs |
| Every action paragraph and speech in exactly one shot | all 15 runs |
| Faithfulness: the model's proposals fully found in the script (the rest loses its unfound quotes, or is dropped whole if its name or every quote is missing) | 0.898 (246 of 274 entities) |
| Recall: speaking characters the model found itself (cues supply the rest) | 0.944 (85 of 90) |
| Tokens per run | about 9,700 in and 3,800 out (≈ $0.0015 at catalog prices) |

Per-sample numbers, the method and the raw results are in [eval/README.md](eval/README.md). Rerun
them with `uv run python -m tools.evaluate --runs 5` from `services/api`.

### The frame audit on real renders

Every live run is a report written by code from what the run stored
([eval/runs/](eval/runs/README.md)), and every shown frame was then looked at by hand; what each run
taught us is in [docs/learning-log.md](docs/learning-log.md). All on klein, 3 drawings a frame at
most:

| Date | Script | What withheld | Result |
| --- | --- | --- | --- |
| 2026-10-11 | the-red-kite | every hard check | 16 of 21 shots shown, 38 drawings |
| 2026-10-13 | market-day (held out) | every hard check | 0 of 15 shown, 44 drawings; about 12 of the 15 final drawings were right (L020) |
| 2026-10-13 | market-day, second run | none | 16 of 17 shown, 17 drawings: 9 right, 5 weak, 2 split panels, none of the wrong sex or age |
| 2026-10-14 | the-lighthouse-inspector (held out) | `drawn_sex,no_character` | 26 of 26 shown, 26 drawings: 14 right, 11 weak, 1 wrong (a man drawn as a woman: L022) |
| 2026-10-14 | the-borrowed-bicycle (held out) | `drawn_sex,no_character` | 18 of 18 shown, 19 drawings; the girl NALEDI drawn as a boy in about 11 frames, because her sex is only in a "Her" the code didn't read then (L023; T100 reads it now, not yet measured live); one frame shows an unscripted adult, warned |

The two agents, measured on stored drawings with Token Factory before they were switched on
([docs/design/verify.md](docs/design/verify.md) §3):

- **Sex agent** (2026-10-13): 175 matched people asked, 12 flagged, every one a real error, 0
  false alarms.
- **Presence agent** (2026-10-14): of 30 stored frames `no_character` would have withheld, 23 had
  the character plainly drawn. The agent found the character in 17 of those 23, and wrongly found
  one in 3 of the other 7.

Not measured: the audit's precision and recall on a labelled set (T049). Its labelled set was built
on a renderer we dropped; the run reports and `python -m app.verify.recheck` (today's checks re-run
on stored audits, free) measure it for now.

## The hosted demo

| Piece | Where |
| --- | --- |
| Web app | https://panelwise.vercel.app (Vercel, functions in `fra1`) |
| API | https://panelwise-api.onrender.com (Render, plan `1c-2g`, Frankfurt, from the [`render.yaml`](render.yaml) Blueprint) |
| Data | Supabase: Postgres via the session pooler, a private Storage bucket, Auth |

- **Sign-up is off.** Judges get a shared login in Devpost's testing instructions, never in the
  repo. The account and a ready-made copy of the sample project are made by
  `python -m app.demo.seed` (T069); seeding it on the hosted stack is T030, still to do.
- **Limits** ([docs/design/limits.md](docs/design/limits.md), deploy.md §6): 3 uploads a day per
  account, 15 pages a script, 2,800,000 Token Factory tokens a month (`LLM_MONTHLY_TOKEN_CAP`) and
  800 drawings a month (`IMAGE_MONTHLY_GENERATION_CAP`). At a cap, new work is refused with a
  message; a job already running finishes.
- **Migrations** run in the API image's start command before uvicorn, on Render and in compose
  alike; an API that can't reach its database exits instead of serving.
- **Keep-alive:** [`.github/workflows/keepalive.yml`](.github/workflows/keepalive.yml) pings the
  API's health check every 10 minutes; a failed run is our uptime alert.

Setup, step by step: [docs/deploy.md](docs/deploy.md); the design:
[docs/design/deploy.md](docs/design/deploy.md).

## Run it

You need Python 3.14 with [uv](https://docs.astral.sh/uv/), and a Nebius Token Factory API key.
Docker is needed for the local stack and the full gate (its database tests start their own
Postgres and it builds the API image), Node 24 with pnpm only for the web app, a fal.ai key
(`FAL_KEY`) only for drawing frames, and a Supabase project only for the web app.

```bash
git clone https://github.com/Katlego-tech/Panelwise.git && cd Panelwise
bash install-hooks.sh            # contributors: the pre-push gate
cp .env.example .env             # set NEBIUS_API_KEY
cd services/api && uv sync
```

Every command below runs from `services/api` on a self-written sample. Only use public-domain or
self-written scripts.

```bash
uv run python -m app.llm.smoke                                      # the key works; fast tier answers with 0 reasoning tokens
uv run python -m app.grounding.run ../../samples/the-red-kite.pdf   # entities with page/line spans, faithfulness, recall
uv run python -m app.shots.run ../../samples/the-red-kite.pdf       # shots with the verbatim text each one cites
uv run python -m app.projects.run ../../samples/the-red-kite.pdf    # the pipeline core, stage by stage
uv run python -m app.storyboard.prompts ../../samples/the-red-kite.pdf --style ink   # frame prompts, each part citing its line
uv run python -m app.verify.run ../../samples/the-red-kite.pdf 1.2 frame.png  # audit a PNG against shot 2 of scene 1
uv run python -m tools.evaluate --runs 5                            # the extraction results above
```

Offline, no key needed:

```bash
uv run python -m tools.build_samples           # rebuild the sample PDFs and print what the parser reads
uv run python -m tools.build_comic_reference   # re-render the comic reference pages in docs/design/comic/
bash ../../scripts/gate.sh                     # every check the pre-push hook runs
```

The local stack (Postgres, the API and the web app on pinned versions) runs with
`docker compose up --build --wait` from the repo root. Without a Supabase project in `.env` it
serves the health checks, `GET :8000/api/v1/health` and `GET :3000/api/health`. With one
(`SUPABASE_URL`, `SUPABASE_SECRET_KEY`, a private Storage bucket named in `SUPABASE_STORAGE_BUCKET`,
and the `NEXT_PUBLIC_SUPABASE_*` pair), open `localhost:3000`, sign in and upload a sample PDF. The
job reads, extracts and plans; with `FAL_KEY` set it then draws and audits every frame
(`RENDER_MAX_ATTEMPTS`, 3 by default, drawings a frame at most). Open the script page, the
storyboard (click a card for its frame sheet and audit log, *Export PDF* once every frame is
settled) and the comic tab (*Make the comic*). Without `FAL_KEY` the job ends at planning, and
"Try another render" and "Make the comic" answer 503: no renderer. The app has a sign-in
page only: sign-up is off, so users are created in the Supabase dashboard (Authentication > Users).

A run's report, free (no model call), in the API container:

```bash
docker compose exec api .venv/bin/python -m app.verify.report <project-id>
```

The samples: thirteen self-written screenplays in [`samples/`](samples/README.md), Fountain source
and PDF. `the-red-kite` is the demo script; the ten of the second set (T090) are ordinary spec
scripts, used as held-out scripts for the audit.

## Feedback on Nebius Token Factory and NVIDIA Nemotron

⟨TBD: written by the team.⟩

## Repository layout

| Path | What |
| --- | --- |
| `services/api/app/` | the FastAPI service: `llm`, `script`, `grounding`, `shots`, `storyboard`, `verify`, `comic`, `characters`, `projects`, `jobs`, `frames`, `storage`, `limits`, `demo`, `core`, `api` (with Alembic migrations) |
| `services/api/tools/` | `build_samples`, `build_comic_reference`, `evaluate` |
| `services/api/styles/` | public storyboard styles (`clean`, `ink`, `pencil`); `styles/` at the root links to it |
| `apps/web/` | the Next.js app: sign-in, the projects page with upload, the script page, the storyboard and its frame sheet, the comic reader |
| `samples/` | thirteen self-written screenplays (Fountain source and PDF) |
| `eval/` | measured results, the live run reports and how they were produced |
| `docs/design/` | a design doc per module: diagrams, contracts, decisions |
| `render.yaml`, `apps/web/vercel.json` | the hosted demo's API and web config |

Full tree: [docs/project-structure.md](docs/project-structure.md).

## How we work

This repo uses the Cultivation kit. [AGENTS.md](AGENTS.md) holds the rules,
[STATUS.md](STATUS.md) the live board and [TASKS.md](TASKS.md) the backlog. Every push runs
`scripts/gate.sh`: ruff, pyright, pytest (database tests on a throwaway Postgres 17.11), eslint and
tsc, vitest, next build, the API image build, and placeholder, secret, vulnerability and duplication
scans.

## License

[Apache 2.0](LICENSE). The sample screenplays are original and under the same licence.
