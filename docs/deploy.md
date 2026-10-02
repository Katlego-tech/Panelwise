# Deploying Panelwise

The one-time setup of the three hosted services, in the order they depend on each other. Design and
reasons: [docs/design/deploy.md](design/deploy.md). Every secret goes into a dashboard, never into
the repo. Each step ends with a check; don't start the next until it passes.

| Order | Service | Runs | Needs |
|---|---|---|---|
| 1 | Supabase | Postgres (+ Storage and Auth later) | an account |
| 2 | Railway | the API (`services/api`) | the GitHub repo, step 1's connection string, the Nebius key |
| 3 | Vercel | the web app (`apps/web`) | the GitHub repo, step 2's domain |

## 1. Supabase — the database

1. supabase.com → New project. Pick the region closest to Railway's (e.g. Frankfurt with Railway's
   EU region). Save the database password in a password manager.
2. **Connect** → **Session pooler** (port **5432**). Copy that connection string, with the password
   filled in. Not the *direct* connection: it's IPv6-only without the paid add-on. Not the
   *transaction* pooler (6543): it can't do prepared statements, which the API's driver uses.
3. Project Settings → API Keys: note the project URL and the **secret** key (for step 2, server
   only) and the **publishable** key (for step 3; the browser sign-in, T040, uses it).

**Check:** from your machine, with the session-pooler string in `DATABASE_URL`:

```bash
cd services/api && DATABASE_URL='postgresql://…pooler.supabase.com:5432/postgres' \
  uv run uvicorn app.main:app --port 8001 &
sleep 3 && curl -s localhost:8001/api/v1/health   # {"status":"ok","checks":{"postgres":"ok"}}
kill %1
```

## 2. Railway — the API

1. railway.com → New project → Deploy from GitHub repo → `Katlego-tech/Panelwise`.
2. Service → Settings (set these in the dashboard; there is deliberately no config file, see below):

   | Setting | Value |
   |---|---|
   | Root directory | `/services/api` |
   | Builder | Dockerfile (Railway detects `services/api/Dockerfile`) |
   | Healthcheck path | `/api/v1/health` (timeout 60 s) |
   | Restart policy | On failure, 3 retries |
   | Pre-deploy command | `/srv/api/.venv/bin/alembic -c /srv/api/alembic.ini upgrade head` (T009: migrations run before the new version starts; a failed one stops the deploy; check the deploy log shows them) |

   *Why no `railway.json`:* Railway deprecated Config as Code. New services can't opt into it, and
   existing files stop working on **2026-12-01**, before judging ends on 15 Dec
   (docs.railway.com/config-as-code/reference, checked 2026-09-29). Its replacement,
   `.railway/railway.ts`, would be unverified code for four settings.
3. Service → Variables:

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | step 1's session-pooler string, as copied. `postgresql://…` is fine (the API adds `+asyncpg`), and so is `?sslmode=require` (the API turns it into asyncpg's `?ssl=require`) |
   | `NEBIUS_API_KEY` | your Token Factory key |
   | `SUPABASE_URL`, `SUPABASE_SECRET_KEY` | step 1 (the token check and uploads from T053, frames from T026) |

   Everything else has a default in `app/core/config.py` (`NEBIUS_MODEL_*`, `LLM_*`). `PORT` is set
   by Railway, and the container listens on it.
4. Settings → Networking → **Generate domain**.

**Check:** `curl https://<railway-domain>/api/v1/health` →
`{"status":"ok","checks":{"postgres":"ok"}}`. A 503 names the failing check; a deploy that fails
this check never replaces the running one.

## 3. Vercel — the web app

1. vercel.com → Add New → Project → import `Katlego-tech/Panelwise`.
2. **Root directory** `apps/web`. The framework (Next.js), install and build commands come from
   `apps/web/vercel.json`.
3. Environment variables:

   | Variable | Value |
   |---|---|
   | `API_URL` | `https://<railway-domain>` from step 2, no trailing slash. Server-side only |
   | `ENABLE_EXPERIMENTAL_COREPACK` | `1`, so Vercel uses the pnpm version pinned in `package.json` |
   | `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | step 1, the **publishable** key only (the browser sign-in, from T040) |

**Check:** `curl https://<vercel-domain>/api/health` →
`{"web":"ok","api":{"status":"ok","checks":{"postgres":"ok"}}}` with HTTP 200. A 502 means Vercel
can't reach `API_URL`.

## When it's done

All three checks pass: T037 is done. Record the two URLs in STATUS.md § Environment & access. Every push to `main` now redeploys both; every PR gets a Vercel preview.
