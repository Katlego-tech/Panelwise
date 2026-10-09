# Deploying Panelwise

The one-time setup of the three hosted services, in the order they depend on each other. Design and
reasons: [docs/design/deploy.md](design/deploy.md). Every secret goes into a dashboard, never into
the repo. Each step ends with a check; don't start the next until it passes.

| Order | Service | Runs | Needs |
|---|---|---|---|
| 1 | Supabase | Postgres (+ Storage and Auth later) | an account |
| 2 | Render | the API (`services/api`, from `render.yaml`) | the GitHub repo, step 1's connection string and keys, the Nebius key |
| 3 | Vercel | the web app (`apps/web`) | the GitHub repo, step 2's domain |

## 1. Supabase — the database

1. supabase.com → New project. Pick an EU region near Render's `frankfurt` (`render.yaml`); ours is
   eu-west-1, Ireland. Save the database password in a password manager.
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

## 2. Render — the API

The service is defined in `render.yaml` at the repository root (a Render Blueprint: a Docker web
service on the **free** instance, Frankfurt; design: [deploy.md §6](design/deploy.md)). Change settings there, in a
PR, not in the dashboard: a dashboard edit to a field the Blueprint sets may be overwritten the next time it syncs.

1. render.com → sign in with GitHub → give Render access to `Katlego-tech/Panelwise`.
2. **New → Blueprint** → pick the repo, branch `main`, Blueprint path `render.yaml`. Render lists
   one service, `panelwise-api`, and asks for the four secrets (`sync: false`):

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | step 1's session-pooler string, as copied. `postgresql://…` is fine (the API adds `+asyncpg`), and so is `?sslmode=require` (the API turns it into asyncpg's `?ssl=require`) |
   | `NEBIUS_API_KEY` | your Token Factory key |
   | `SUPABASE_URL`, `SUPABASE_SECRET_KEY` | step 1 (the token check and uploads from T053, frames from T026) |

   Everything else has a default in `app/core/config.py` (`NEBIUS_MODEL_*`, `LLM_*`,
   `SUPABASE_STORAGE_BUCKET=panelwise`). `PORT` is set by Render (10000), and the container listens
   on it. Never set `PANELWISE_PRIVATE_STYLES` here.
3. **Apply.** Render builds `services/api/Dockerfile` and starts
   it; the image's start command runs `alembic upgrade head`, then uvicorn. Render switches traffic
   once `/api/v1/health` answers 200. A failed migration exits the container, so the deploy never
   turns healthy and Render cancels it. The service's URL is `https://panelwise-api.onrender.com` (or with
   a suffix if the name is taken; it's on the service's page).
4. **Keep it awake.** A free instance sleeps after 15 idle minutes and takes about a minute to wake.
   On GitHub: the repo's Settings → Secrets and variables → Actions → **Variables** → New repository
   variable `API_HEALTH_URL` = `https://<render-domain>/api/v1/health`. The `keep-alive` workflow
   (`.github/workflows/keepalive.yml`) then pings it every 10 minutes, which also keeps the free
   Supabase project from pausing. Keep no other free service in this Render workspace: this one
   uses ~744 of its 750 free hours a month.

From then on, a push to `main` that touches `services/api/**` deploys after its GitHub checks pass
(`autoDeployTrigger: checksPass`). A deploy that fails its migration or isn't healthy within
15 minutes is cancelled, and the previous one keeps serving.

**Check:** `curl https://<render-domain>/api/v1/health` →
`{"status":"ok","checks":{"postgres":"ok"}}`; the service's Logs show Alembic's
`Context impl PostgresqlImpl` line before uvicorn starts; and on GitHub, Actions → keep-alive →
**Run workflow** passes. A 503 names the failing check. Render also checks the running service: after
60 s of failures it restarts it (design §4).

## 3. Vercel — the web app

1. vercel.com → Add New → Project → import `Katlego-tech/Panelwise`.
2. **Root directory** `apps/web`. The framework (Next.js), install and build commands come from
   `apps/web/vercel.json`.
3. Environment variables:

   | Variable | Value |
   |---|---|
   | `API_URL` | `https://<render-domain>` from step 2, no trailing slash. Server-side only |
   | `ENABLE_EXPERIMENTAL_COREPACK` | `1`, so Vercel uses the pnpm version pinned in `package.json` |
   | `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | step 1, the **publishable** key only (the browser sign-in, from T040) |

**Check:** `curl https://<vercel-domain>/api/health` →
`{"web":"ok","api":{"status":"ok","checks":{"postgres":"ok"}}}` with HTTP 200. A 502 means Vercel
can't reach `API_URL`.

## When it's done

All three checks pass: T037 is done. Record the two URLs in STATUS.md § Environment & access. Every push to `main` now redeploys the web app, and the API when `services/api/**` changed; every PR gets a Vercel preview.
