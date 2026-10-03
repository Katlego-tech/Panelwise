# `Panelwise` — Handoff

**Written:** 2026-10-03 · **Branch:** `main` (everything merged; nothing unpushed) · **By:** Katlego (via Claude)

---

## 1. What is done

| Area | Status |
|---|---|
| Parser, grounding, shot planner, frame prompts, frame audit, comic layout + lettering, eval (T005–T008, T020, T022, T023, T031, T032, T039, T043, T044, T048, T050–T052) | ✅ merged |
| Supabase project (eu-west-1, Postgres 17.11): private buckets `panelwise` + `panelwise-dev`, email Auth, dev user, sign-up **off** decided | ✅ (Katlego must flip the dashboard switch; see §8) |
| **T009** database foundation: Alembic, `projects`/`jobs`, RLS on every table, restart sweep, the gate's own test Postgres | ✅ PR #51; migrated on Supabase |
| **T053** token check (local ES256 JWKS), `SupabaseStore`, `POST`/`GET /api/v1/projects` | ✅ PR #52 |
| **T046** `run_job`: the upload's job runs parse → extract → plan, `codec.py` | ✅ PR #53 |
| **T047** `GET /projects/{id}`, `/lines`, `/shots`, `/frames`; `frames` table (migration 0002) | ✅ PR #55; migrated on Supabase |
| **T040–T045** web screens (Next.js) | ❌ not started — **next** |
| T021 re-render loop, T024 comic reader | ❌ not started (after T045) |
| T003 GPU / T026 renderer / T027 storyboard PDF / T025 portraits / T049 audit accuracy | ❌ blocked on GPU access; interim renderer proposed (§8) |
| T037 deploy check / T030 hosted demo | ❌ blocked on Vercel + Railway accounts |
| T033 README | ⚠️ draft PR #36 waits on Katlego's feedback section |
| T055 `braces` advisory | ⚠️ accepted in `osv-scanner.toml` until 2026-10-31 |

**How to verify the current state is green:** `bash scripts/gate.sh` (Docker running) →
`== gate passed (10 check(s) run across 2 project(s))`, ~700 API tests including the `db` ones.

## 2. Decisions already locked (do not relitigate)

| Decision | Choice | Why |
|---|---|---|
| DB tests | the gate starts a throwaway `postgres:17.11-trixie`; CI uses the same path (runner has Docker); no Docker → gate **fails** | option A (Katlego 2026-10-01); one source for hook and CI |
| Postgres version | **17.11** everywhere (compose, PLAN, tests) | matches Supabase (Katlego 2026-10-02) |
| gate.sh change | merged under Katlego's AGENTS.md §4 lead exception (STATUS log, PR #51) | Katlego, 2026-10-02 |
| Sign-up | **off**; judges use T030's seeded account(s), credentials only in Devpost's testing instructions | Katlego 2026-10-02 (web.md §10) |
| Token check | local ES256/RS256 verification against the project JWKS (PyJWT); refetch ≤1/min behind a lock; outage → 503 never 401 | web.md §6 *API internals* |
| RLS | on for every `public` table incl. `alembic_version`, no policies, anon/authenticated revoked via `migrations/helpers.py::lock_down` — **every new migration that creates a table must call it** | deploy.md §6 |
| Migrations | Alembic; Railway pre-deploy `/srv/api/.venv/bin/alembic -c /srv/api/alembic.ini upgrade head`; never at app startup | deploy.md §6 |
| Errors | `{"error": "<code>"}` via `app/api/errors.py::ApiError`; one 404 `not_found` for malformed/missing/foreign ids | web.md §6 |
| Animals / named props in prompts | grounded `species` + `other_names`; labels `the <species>` / `the <prop>` / `it` | Katlego 2026-10-01 (T051/T052) |
| Design first | a design gap gets its own docs PR before code (CLAUDE.md) | every T0xx this session followed it |

**Non-negotiables still in force:** a panel never shows a character, prop, line or event not in
the screenplay — every panel traces to a verbatim span (PLAN.md Non-negotiable 1). No copyrighted
scripts anywhere.

## 3. Environment — how to run it

```bash
# API (services/api, Python 3.14, uv). Secrets live in the repo-root .env (gitignored).
cd services/api && uv sync
bash ../../scripts/gate.sh                       # everything; needs Docker running

# DB tests by hand: a Postgres whose database name ends in _test (the fixture refuses others)
docker run -d --rm --name pw-test -e POSTGRES_PASSWORD=t -e POSTGRES_DB=panelwise_test \
  -p 127.0.0.1:55433:5432 postgres:17.11-trixie
TEST_DATABASE_URL=postgresql://postgres:t@127.0.0.1:55433/panelwise_test uv run pytest -q tests/db

# Live against Supabase: SUPABASE_DB_URL is the session pooler (DATABASE_URL in .env stays local)
DATABASE_URL="$(grep ^SUPABASE_DB_URL= ../../.env | cut -d= -f2-)" uv run alembic upgrade head
DATABASE_URL="$(grep ^SUPABASE_DB_URL= ../../.env | cut -d= -f2-)" HEALTH_CHECK_TIMEOUT_S=10 \
  uv run uvicorn app.main:app --port 8013 &  echo $! > /tmp/api.pid   # stop with kill $(cat /tmp/api.pid)
```

- `.env` keys: everything in `.env.example`, plus local-only `SUPABASE_DB_URL`,
  `PANELWISE_DEV_EMAIL`, `PANELWISE_DEV_PASSWORD` (the dev user for live checks).
  `SUPABASE_STORAGE_BUCKET=panelwise-dev` locally.
- Port **5432** on Katlego's machine belongs to another project's container (`alfred-postgres-1`):
  use `POSTGRES_HOST_PORT` for compose; don't stop alfred.
- Web (`apps/web`, Next.js 16, pnpm): only `/api/health` exists so far.

## 4. Verified facts

| Fact | Value | How confirmed |
|---|---|---|
| Supabase token format | ES256, `kid` in header, JWKS at `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`; claims aud `authenticated`, iss `{url}/auth/v1`, `role`, `is_anonymous`, 1 h lifetime | decoded the dev user's token, 2026-10-02 |
| Storage quirks | duplicate upload → **400** with body `"statusCode":"409"`; missing object GET → 400 with `"404"`; HEAD missing → bare 400 | live probe, 2026-10-02 (encoded in `SupabaseStore`) |
| Supabase DB from South Africa | cold connection 2–4 s (> the 2 s health timeout) — use `HEALTH_CHECK_TIMEOUT_S=10` locally | live, 2026-10-02 |
| RLS on Supabase | Data API: anon 401, signed-in user 403 on `projects`, `jobs`, `frames`, `alembic_version` | live, 2026-10-02/03 |
| Full live run | `the-red-kite` via the real API: queued → parsing → extracting 5 → planning 40 → done 60 in ~40 s; 5 pages, 5 scenes, 22 shots, faithfulness 1.0 | live, 2026-10-03 |
| Token Factory image models | **none** (catalog and `/images/generations` both checked) | live, 2026-10-03 |
| Cloudflare FLUX.1 [schnell] price | 1024×576 @ 4 steps = 48 neurons ≈ $0.0005; ~200 frames/day free | Cloudflare's own pricing page, 2026-10-03 |
| Supabase is empty | 0 projects, 0 jobs, 0 frames; test users deleted (the dev user remains) | after the T047 live check |

## 5. Corrections

- **Previously said:** the gate passing locally means a PR is complete. **Actually:** an
  unanchored `storage/` rule in `.gitignore` hid `app/storage/` from PR #52, and ruff skips ignored
  files. **Impact:** fixed (`/storage/`); check `git check-ignore -v` on new directories.
- **Previously said (STATUS, 2026-10-01):** PR #31 merged after review. **Actually:** merged before
  its CI finished (CI passed after). Recorded in STATUS.

## 6. Next steps, in order

1. **T040** (web: tokens, sign-in, projects list, upload). Read TASKS.md T040 and web.md §4
   (sign-in, §4.1 upload), §5–§7 and the visual references `docs/design/web/signin.png`,
   `projects.png` + `tokens.css`. Load the `frontend-design` skill first (CLAUDE.md). The API it
   calls is merged: `POST`/`GET /api/v1/projects` with `Authorization: Bearer <Supabase token>`;
   the browser never calls the API directly (Next.js route handlers do, server-side).
2. T041 script page → T042 storyboard board → T045 frame sheet, each against its PNG reference.
3. If Katlego approves the Cloudflare renderer: a design PR for an interim `Renderer` (verify.md's
   Protocol) beside ComfyUI, a plan-change note, then T026's pieces that don't need the GPU.
4. Then T021 (needs T045) and T024.

## 7. Gotchas

- **Never `pkill -f "<pattern>"` in a command whose text contains the pattern** — it kills the
  shell (exit 144) and the rest silently doesn't run. Kill by PID.
- **A new table needs `lock_down()`** in its migration, or Supabase exposes it to the publishable
  key. `tests/db/test_schema.py` fails if any public table has RLS off.
- **Models must match migrations**: `Base.type_annotation_map` maps `str`→TEXT,
  `datetime`→timestamptz; a drift test compares models and the migrated DB.
- **Timestamps use `clock_timestamp()`**, not `now()` (rows in one transaction would tie).
- **POST /projects has no `UploadFile`/`Form` parameter on purpose** — FastAPI would read the body
  before auth. Order: auth → storage → Content-Length → `request.form` → size → `%PDF-`.
- **Route ids are `str`** parsed by hand (a typed UUID gives FastAPI's 422, not our 404).
- Code reviewers need their own detached worktree; never switch branches under them.
- STATUS/TASKS conflicts: see the memory notes; grep for duplicates before committing.

## 8. Open questions

- **Interim renderer:** FLUX.1 [schnell] on Cloudflare Workers AI recommended; needs Katlego's
  Cloudflare account (token + account ID in `.env`) and a plan change (the locked stack names
  ComfyUI on a Nebius GPU). Not started.
- **Sign-up switch:** decided off, but Katlego still has to disable "Allow new users to sign up"
  in the Supabase dashboard; nobody has confirmed it. Check with a sign-up call (expect a refusal).
- **Devpost rules** must accept a login for the demo ("free and unrestricted"): unchecked (T030).
- **T033 feedback section** (PR #36) and the two wording calls in STATUS ⚠️: Katlego's.
- **T055:** if no `braces` fix exists by 2026-10-31 the exemption expires and the gate fails.
