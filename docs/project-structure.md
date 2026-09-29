# Project structure

## The tree

```
panelwise/
├── LICENSE                      # Apache-2.0
├── README.md                    # setup, Nemotron + Token Factory usage, demo link
├── CHANGES-FROM-FRAMEFLOW.md    # the "what was significantly updated" disclosure
├── .env.example                 # key names only
├── docker-compose.yml           # local: postgres, api, web (+ comfyui profile, T003); deployed: docs/design/deploy.md
├── infra/
│   ├── nebius/                  # GPU VM / serverless endpoint for ComfyUI
│   └── comfyui/workflows/       # public node graphs (JSON)
├── services/api/                # FastAPI
│   ├── app/
│   │   ├── core/                # config, auth, budget (+ LLM spend cap), tracing
│   │   ├── llm/                 # nebius provider, model tiers, structured_chat
│   │   ├── script/              # parser, scene_time, dialogue_linker
│   │   ├── grounding/           # extraction, grounding filter, faithfulness
│   │   ├── shots/               # shot planner
│   │   ├── storyboard/          # frame gen, styles registry, PDF        (headline)
│   │   ├── verify/              # Nemotron vision frame auditor + re-render loop
│   │   ├── comic/               # page layout, panel sizing, bubbles, lettering
│   │   ├── characters/          # reference portraits for consistent characters
│   │   ├── images/              # provider chain + cache
│   │   └── api/v1/              # projects, script, shots, storyboard, comic, audit log
│   └── tests/
├── apps/web/                    # Next.js: upload → shots → storyboard → comic reader
├── packages/shared/             # types + api client
├── styles/                      # public storyboard + comic styles
├── samples/                     # public-domain / self-written screenplays ONLY
├── eval/                        # faithfulness + frame-audit benchmarks
└── (Cultivation kit)            # AGENTS/STATUS/SPEC/PLAN/TASKS, docs/, scripts/gate.sh, .githooks/, .claude/
```

## Why this shape

- **A modular monolith, not microservices.** The hackathon runs five weeks and has two builders.
  One FastAPI service split into modules gives the same boundaries without the deploy overhead.
  The modules talk through plain Python interfaces, so any one can be split out later.
- **The storyboard pipeline is the spine.** `script → grounding → shots → storyboard` is the chain
  every feature depends on; `verify` and `comic` sit on top of it.
- **The public/private line is `styles/`.** The style registry loads the public styles in `styles/`
  and, if `PANELWISE_PRIVATE_STYLES` points somewhere, a private pack from outside the repo. The
  hosted demo uses only public styles, so judges can reproduce everything they see.
- **No copyrighted scripts.** `samples/` holds public-domain or self-written screenplays only.

## Run it

Not runnable yet. Target: `cp .env.example .env && docker compose up`.

## Status

Scaffold only: module folders hold a README describing their responsibility and no code yet.
