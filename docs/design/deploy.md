# Design — `infra` deploy (Vercel + Railway + Supabase)

**Status:** agreed · **Owner:** Katlego (Claude) · **Tasks:** T037 (stack), T009 (database), T053 (Storage, first for uploads; T026 adds frames), T053/T040/T030 (Auth)
· **Spec:** cross-cutting (hosting for every story in [SPEC.md](../../SPEC.md))
· **Decided:** 2026-09-29 by Katlego, adopting the Hackathon kit's REACT + FASTAPI stack

---

## 1. What this covers

Where Panelwise runs once it leaves a laptop, and what each hosted service is for. It replaces
PLAN.md's earlier target ("API + web on Nebius; Postgres + Redis self-hosted"). **Not covered:**
ComfyUI on the Nebius GPU (T003, `infra/nebius/`), which is unchanged.

| Piece | Runs on | Why |
|---|---|---|
| Web app (`apps/web`, Next.js 16) | **Vercel** | Next.js's native host; preview deploy per PR |
| API (`services/api`, FastAPI) | **Railway**, from `services/api/Dockerfile` | extraction runs for minutes; it needs a real container, not a serverless function |
| Database | **Supabase Postgres** | hosted Postgres; the SQLAlchemy + asyncpg code is unchanged |
| Images (frames, portraits, comic pages) | **Supabase Storage** | PLAN's "content-addressed file store", hosted |
| Sign-in, seeded judge account | **Supabase Auth** | T030 needs a judge login in the testing instructions |
| Job status and progress | **a Postgres table** | replaces Redis: one fewer service to host and pay for |
| Models | Nebius Token Factory | unchanged; this call is what satisfies "runs on Nebius" |
| Rendering | ComfyUI on a Nebius AI Cloud GPU (T003) | unchanged |

**Hackathon rules still hold:** "runs on Nebius" means a runtime Token Factory call *or* Nebius
compute. Panelwise makes both (Nemotron calls, ComfyUI GPU). Hosting the app elsewhere is allowed
(frameflow-nebius-hackathon/PLAN.md, rules). The demo must stay up, free, until 15 Dec.

## 2. Reference material

| Kind | Where |
| --- | --- |
| Source of the stack | `~/Documents/projects/personal/Hackathon/stacks/react-fastapi` and `stacks/_parts/{web-react,api-fastapi}` (`vercel.json`, `railway.json`, `db.py`, `supabase.ts`, the PREP steps) |
| Supabase connections | supabase.com/docs/guides/database/connecting-to-postgres (checked 2026-09-29): for a long-running server on IPv4, the **shared pooler, session mode**, port 5432 — IPv4 on every plan; transaction mode (6543) doesn't support prepared statements, which asyncpg uses |
| Current code | `services/api/app/main.py` (health checks Postgres **and Redis** today), `docker-compose.yml`, `.env.example` |

## 3. Domain model

One new entity, built with its first consumer (T009): a job row, so progress survives an API
restart and needs no Redis. `project_id` and `stage` (and the `Project` it belongs to) are defined in
[web.md](web.md) §3.

```mermaid
classDiagram
    class Job {
        +uuid id
        +uuid project_id
        +str kind
        +Stage|None stage
        +JobState state
        +int progress
        +str|None error
        +datetime created_at
        +datetime updated_at
    }
    class JobState {
        <<enum>>
        QUEUED
        RUNNING
        DONE
        FAILED
    }
    Job --> JobState
```

## 4. Flow

```mermaid
sequenceDiagram
    participant B as Browser
    participant W as Next.js on Vercel
    participant A as FastAPI on Railway
    participant S as Supabase (Postgres, Storage, Auth)
    participant N as Token Factory / ComfyUI
    B->>W: page, sign-in (Supabase Auth cookies via @supabase/ssr)
    W->>A: server-side fetch, API_URL, with the user's access token
    A->>S: SQL over the session pooler; Storage with the secret key
    A->>N: Nemotron calls; render calls
    A-->>W: JSON
    W-->>B: HTML / JSON
```

- **The browser never calls the API directly.** Next.js route handlers and server components call
  it server-side (`API_URL`, as `app/api/health` already does). So the API needs no CORS setup, and
  only the Supabase *publishable* key ever reaches a browser.
- **Secrets by place:** `SUPABASE_SECRET_KEY`, `DATABASE_URL`, `NEBIUS_API_KEY` live only on
  Railway. `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` live on Vercel.
  `API_URL` (server-only, Vercel) points at the Railway domain.

**Failure paths:** the API down → the web health route answers 502 (already built); Supabase
Postgres down → the API health answers 503 `degraded`; a Railway deploy fails its
`/api/v1/health` check → Railway keeps the previous deploy running.

## 5. State

```mermaid
stateDiagram-v2
    [*] --> QUEUED
    QUEUED --> RUNNING
    RUNNING --> DONE
    RUNNING --> FAILED
    QUEUED --> FAILED
    DONE --> [*]
    FAILED --> [*]
```

No transition out of `DONE` or `FAILED`: a retry is a new job.

## 6. Contracts

**Environment** (`.env.example` is the source; names are exact):

| Variable | Where | What |
|---|---|---|
| `DATABASE_URL` | API (Railway, local) | `postgresql+asyncpg://…` — locally the compose Postgres; deployed, the Supabase **session pooler** URL (port 5432) |
| `SUPABASE_URL`, `SUPABASE_SECRET_KEY` | API only | Storage (T053 for uploads, T026 for frames), verifying users (T053) |
| `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | web (Vercel) | Auth in the browser (T040) |
| `API_URL` | web, server-side only | the Railway domain, no trailing slash |
| `NEBIUS_*`, `LLM_*` | API only | unchanged (docs/design/llm.md) |
| `COMFYUI_MAX_WORDS` | API | the frame prompt's word budget, default 55 (storyboard.md §3.1, T008) |
| `PANELWISE_PRIVATE_STYLES` | API, optional | a directory of private style TOMLs outside the repo; **never set on the hosted demo** (storyboard.md §3.2, T008) |
| `REDIS_URL` | — | **removed** |

**Deploy configs:** `apps/web/vercel.json` (framework `nextjs`, pnpm, root directory `apps/web`).
Railway is configured in its dashboard (root `/services/api`, Dockerfile, health check
`/api/v1/health`, restart on failure), written down step by step in `docs/deploy.md`: Railway's
`railway.json` is deprecated, new services can't use it, and existing files stop working on
2026-12-01 (T037 review, checked against Railway's docs 2026-09-29).

**`DATABASE_URL`** may be `postgresql://`, `postgres://` or `postgresql+asyncpg://`; the API adds the
`+asyncpg` driver and rewrites libpq's `sslmode=` to asyncpg's `ssl=` (same values). asyncpg rejects
`sslmode` at connect time.

**API health** (`GET /api/v1/health`, T002 contract) keeps its shape; its checks become
`{"postgres": …}` only.

**Schema and migrations (T009).** SQLAlchemy 2 async models; **Alembic** migrations in
`services/api/migrations/` (`alembic.ini` beside `pyproject.toml`; an async `env.py` that reads
`Settings().database_url`). Tables live in Supabase's `public` schema. Enumerations are `text` with a
`CHECK` constraint, not Postgres enums, so a later state (T021's) is one migration that swaps a
constraint. Migration `0001` creates:

| Table | Columns | Constraints and indexes |
|---|---|---|
| `projects` | `id uuid pk`, `owner uuid not null`, `title text not null`, `pdf_path text not null`, `screenplay jsonb`, `extraction jsonb`, `plan jsonb`, `created_at timestamptz not null default clock_timestamp()` | index `(owner, created_at desc)` |
| `jobs` | `id uuid pk`, `project_id uuid not null references projects(id) on delete cascade`, `kind text not null`, `state text not null`, `stage text`, `progress int not null default 0`, `error text`, `created_at`, `updated_at timestamptz not null default clock_timestamp()` | `kind in ('storyboard','frame_attempt')`; `state in ('queued','running','done','failed')`; `stage in ('parsing','extracting','planning','rendering')` or null; `progress between 0 and 100`; index `(project_id, created_at desc)` |

Timestamps default to `clock_timestamp()`, not `now()`: `now()` is the transaction's start, so rows inserted in one transaction would tie and "newest first" would be arbitrary. `owner` is not a foreign key to `auth.users`: that schema exists only on Supabase, and the compose
Postgres and the test Postgres must run the same migration. **Who runs migrations:** never the app
at startup (two replicas would race). Railway runs `/srv/api/.venv/bin/alembic -c /srv/api/alembic.ini upgrade head` as its
**pre-deploy command** (dashboard, `docs/deploy.md` step 2; absolute paths, since Railway runs it in
a separate container from the built image and documents no working directory; `alembic` is a main
dependency, so `uv sync --no-dev` installs it), so a failed migration stops the
deploy; compose's `api` runs it before uvicorn; the DB tests run it once per test session, which
also tests the migration.

**Row-level security (T009; closes §10).** Every table in `public` — the API's and Alembic's own
`alembic_version` — gets `ENABLE ROW LEVEL SECURITY` and **no policies**, and its privileges are
revoked from Supabase's `anon` and `authenticated` roles when those roles exist (a `DO` block; they
don't exist in the compose or test Postgres). Supabase's default privileges grant those roles every
new table, so this is not automatic: each migration that creates a table calls the shared helper
`lock_down(table)` (`migrations/helpers.py`), and a test (`db`) fails if any table in `public` has
RLS off or grants anything to `anon`/`authenticated` (on the test Postgres it checks RLS; the grant
check is live, against the Supabase project, in T009's Verify). So the publishable key reads nothing through Supabase's Data API. The API connects
as the tables' owner, which RLS does not restrict unless forced, and enforces ownership itself
(web.md §6: another user's project is a 404). Storage: the bucket is private and has no policies;
only the secret key reads or writes it, and the browser sees images only through signed URLs
(storyboard.md §8).

**Test Postgres (T009; option A, decided by Katlego 2026-10-01, Postgres 17.11 on 2026-10-02).**
`scripts/gate.sh` provides it, so the hook and CI run the same thing (CI's `ubuntu-latest` runner
has Docker; `ci.yml` needs no service of its own):
- `TEST_DATABASE_URL` set → use it.
- else Docker available → `docker run -d --rm -p 127.0.0.1::5432 postgres:17.11-trixie` with a
  throwaway password, wait for `pg_isready` (60 s at most), export `TEST_DATABASE_URL`, and stop the
  container on exit (a `trap`).
- else → the gate **fails** ("no Postgres for the database tests: start Docker or set
  TEST_DATABASE_URL"). Never a silent skip.
- The gate exports `PANELWISE_REQUIRE_DB=1`. Tests marked `db` use `TEST_DATABASE_URL`; without it
  they **skip** when run by hand and **fail** under the gate. The `db` fixture upgrades a fresh
  database to `head` once per session and truncates every table before each test.
- **Safety:** the fixture refuses (fails) any `TEST_DATABASE_URL` whose database name doesn't end
  in `_test`, so pointing it at Supabase or the dev database can never wipe it. The gate's container
  creates `panelwise_test`.
- **Where in the gate:** started once, before the per-project checks (so every `pyrun` subshell
  inherits the export), and only when a Python project has tests to run: never for `--list` or
  `--install-deps`. The host port is Docker's choice (`-p 127.0.0.1::5432`), read back with
  `docker port`. One `trap … EXIT` stops the container on every exit path, including the early
  `exit 1`s.

## 7. Structure

| Path | New? | Responsibility | Task |
|---|---|---|---|
| `apps/web/vercel.json` | new | Vercel build settings | T037 |
| `services/api/app/main.py`, `app/core/config.py`, `docker-compose.yml`, `.env.example`, `pyproject.toml` | changed | Redis out; Supabase settings in | T037 |
| `docs/deploy.md` | new | the account steps (Supabase, Railway, Vercel), in order, with checks | T037 |
| `services/api/app/storage/` | new | Supabase Storage: uploaded PDFs (T053), frame images (T026) | T053, T026 |
| `services/api/app/jobs/` + migration | new | the `Job` table (with web.md §3's `project_id`, `stage`) | T009 |
| `apps/web` auth (`@supabase/ssr`) + API token check | new | sign-in (T040), the token check (T053), judge account (T030) | T040 / T053 / T030 |

## 8. Decisions & alternatives

| Decision | Chosen | Rejected, and why |
|---|---|---|
| API host | Railway | Nebius VM: more setup, not covered by credit; the GPU box: couples API uptime to the GPU (Katlego, 2026-09-29). Railway isn't free either: a trial credit, then a small monthly minimum; budget it for the demo's life to 15 Dec |
| Railway config | dashboard settings, documented in `docs/deploy.md` | `railway.json` (the kit's): deprecated, closed to new services, dead on 2026-12-01; `.railway/railway.ts`: unverified code for four settings |
| Postgres client | SQLAlchemy + asyncpg over the session pooler | the `supabase` REST client for data (the kit's `db.py`): we already have SQL code, and REST can't do transactions |
| Pooler mode | session (5432) | transaction (6543): no prepared statements, which asyncpg relies on; direct connection: IPv6-only without the paid add-on |
| Redis | removed; job state in Postgres | keep Redis: a second hosted service for one table's worth of state |
| Browser → API | always through Next.js server-side | direct browser calls: CORS, and the API URL and tokens in the browser |
| Local development | compose Postgres, no Supabase needed for tests | the Supabase CLI locally: heavier, and tests never touch the network |
| Storage and Auth timing | built with their first consumer (Storage: T053's upload; Auth: T053/T040/T030) | now: a module with no caller is a placeholder (AGENTS.md §2a) |

Deviations from [docs/architecture-defaults.md](../architecture-defaults.md): "Docker for every
service" still holds (both services have Dockerfiles; Vercel builds the web app itself). No
message broker, as before.

## 9. How this is verified

- T037: the gate green with Redis gone (health tests updated test-first); `docker compose up` still
  healthy locally; `vercel.json` validated against its schema; Railway's dashboard settings written
  down in `docs/deploy.md`.
- T037 done means deployed: the Railway URL answers `/api/v1/health` `ok` against Supabase, and the
  Vercel URL's `/api/health` answers 200 through it. That needs Katlego's accounts, so the task is
  **blocked on accounts** until they exist, and says so.

## 10. Open questions

- [x] Storage in local development: a dev bucket in the same Supabase project, or a local
  filesystem adapter behind the same interface? **Decided (storyboard.md §8):** a dev bucket through
  the same `SupabaseStore`; tests use an in-memory fake.
- [x] Row-level security policies for Storage and the `Job` table: **decided in T009's design
  (2026-10-02):** RLS on, no policies, privileges revoked from `anon`/`authenticated`; private bucket,
  secret key only (§6 *Row-level security*).
