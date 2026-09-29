# Prep

A long event is won by the team that's still shipping at the last milestone. Most teams in
multi-week online events never submit: they sign up everywhere and only work where they get
traction early. Set up so this team gets traction in the first days.

The kit calls this "the week before"; Panelwise started in week 1 of its own timeline (28 Sep), so
this is the setup checklist as of 2026-09-29, ticked only where STATUS.md shows it done. The event's
times are already in `event.toml [time]` with their source; `./hack kickoff` is not used here.

## Team and time

- [x] Roles decided: Katlego Thapelo Tlhapiso, project leader (Claude, Gemini); Tumo Olorato
      Mogame, co-builder (Claude). AGENTS.md §1 and `event.toml [team]`.
- [ ] Everyone's time zone and working hours written in STATUS.md, with the overlap marked. The
      timeline is in SAST; working hours are not recorded yet (open item, no task).
- [x] One place for decisions: this repo (STATUS.md, TASKS.md, AGENTS.md). Lanes are claimed in
      STATUS.md's taskboard.
- [ ] Both members registered on Devpost and in one team there (frameflow-nebius-hackathon/PLAN.md
      §7 step 5). Confirmed before T035.

## Stack and pipeline

- [x] Boilerplate scaffolded and CI running the gate: the Cultivation kit, then T002's pinned stack;
      `.github/workflows/ci.yml` runs `scripts/gate.sh` (10 checks across 2 projects).
- [ ] A deploy pipeline producing a live URL: the hosted demo on Nebius, up until 15 Dec (T030).
- [x] `event.toml [checks]` points at real commands (`bash scripts/gate.sh`, which runs every check
      itself), and the gate passes. `[checks] smoke` is set by T009.
- [x] Keys in `.env` (never committed), names in `.env.example` (T001 settled every `NEBIUS_*` value).
- [x] Token Factory credit: the $25 event promo (`NEBIUS-DEVPOST-GLOBAL26`) and $25 from the AI
      Builder Program (STATUS.md § Environment).
- [ ] The cost of the ComfyUI GPU box checked against the credit, which covers Token Factory calls,
      not a GPU VM (T003).

## Rules of the event

- [ ] IP terms read on [/rules](https://nebiusglobalaihackathon.devpost.com/rules) and recorded
      here (open item, needed before T035).
- [x] Submission requirements noted (Devpost "What to Submit"): a working project on NVIDIA
      Nemotron via Token Factory or AI Cloud; the track (Best Apps and Agents); a project
      description (draft: docs/submission/about.md); a working demo URL (T030); a public YouTube
      video of 3 minutes or less, with audio on how Token Factory and Nemotron were used (T034);
      a public repo with an open-source licence visible at the top (Apache 2.0, in `LICENSE`) and a
      README with setup instructions that highlights Nemotron and Token Factory use (T033, T035);
      feedback on Token Factory and NVIDIA tools (T033); and, for a project that existed before
      the submission period, what was significantly updated (CHANGES-FROM-FRAMEFLOW.md, T034).
      Deadline 30 Oct 2026 10:00 PDT (19:00 SAST); the team submits by 29 Oct.
- [ ] The milestone dates from `./hack schedule` added to everyone's calendar.
