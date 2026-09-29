# Contracts

Anything that two people, two lanes or two AIs build against is written down before the code:
endpoints, function signatures, schemas, component props. Then each side can build in parallel and
still fit together. One `###` heading per contract; `./hack preflight` counts them.

In Panelwise the contract text itself lives in **one place only**: §6 of the lane's design doc in
[docs/design/](docs/design/), which the task's `Contract:` field quotes verbatim (TASKS.md
§ Anatomy). This file is the index across lanes, so nothing here is a second copy that can drift.
A new contract gets its heading here in the same PR that merges its design doc.

### `GET /api/v1/health` and web `GET /api/health`
Where:    TASKS.md T002 `Contract:` (200 / 503 / 502 bodies)
Owner:    `infra` · Consumer: `web`, docker-compose healthchecks, the hosted demo (T030)
Status:   built (T002)

### `app/llm`: `NebiusChatModel`, `Tier`, `structured_chat`
Where:    [docs/design/llm.md](docs/design/llm.md) §6, including the exact request body and the thinking defaults per tier
Owner:    `llm` · Consumers: `script+grounding` (T006), `shots` (T007), `verify` (T020)
Status:   built (T004)

### `app/script`: `Screenplay`, `Scene`, `Span`, `parse_pdf`, `resolve_times`, `match_speaker`
Where:    [docs/design/script.md](docs/design/script.md) §6
Owner:    `script+grounding` · Consumers: grounding (T006), shots (T007), comic bubbles (T023)
Status:   built (T005)

### `app/grounding`: `Entity`, `Quote`, `GroundingReport`, `Extraction`, `extract`, `ground`, `locate`
Where:    [docs/design/grounding.md](docs/design/grounding.md) §6
Owner:    `script+grounding` · Consumers: shots (T007), storyboard (T008), verify (T020), characters (T025)
Status:   built (T006)

### Not yet written (each lands with its design doc, before its code)
- `shots`: the shot spec the renderer and the auditor both read. T007: whoever claims it writes the design doc first (PLAN.md Non-negotiable 4).
- `verify`: the verdict schema, re-render limit and audit-log entry. T010.
- `comic`: page model, panel sizing and bubble placement. T011.
- `characters`: reference portraits and how they feed ComfyUI. T012.
- `web` ↔ API: the upload, shots, storyboard and comic endpoints the app calls. T009 (with T008), T024.
