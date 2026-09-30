# Rubric map

The weights live in `event.toml [rubric]`: Devpost's four judging criteria, **equal weights**
(25 each). Two of them, **Technological Implementation** and **Quality of the Idea**, name
"Nebius Token Factory or AI Cloud model(s), and NVIDIA Nemotron" in their own text, so Nemotron on
Token Factory has to be visibly load-bearing, not a footnote. Judging runs 1–15 Dec, from the
repo, the hosted demo and the video, with no live pitch.

Judges' scores are normalised across panels, and that punishes polarised scores: a steady 8 from
every judge beats a 10 and a 2. Build for stability before flourishes.

"Built" below means listed under *What's built so far* in [STATUS.md](STATUS.md). Everything else
is planned, with the task that delivers it.

| Criterion (Devpost's question) | Evidence built today | Planned (task) |
|---|---|---|
| **Technological Implementation** — "How well is the project built, and how effectively does it use Nebius Token Factory or AI Cloud model(s), and NVIDIA Nemotron as part of the solution?" | Token Factory measured before any code: U1–U7 in [docs/nebius-findings.md](docs/nebius-findings.md) (strict `json_schema` enforced on Nemotron; thinking switched off takes Lightning from 271 to 4 completion tokens). `app/llm`: `NebiusChatModel` with fast / reasoning / vision tiers, `Retry-After` retries, `structured_chat` with one repair retry (T004). `app/script` parser with a page/line span on every element (T005). `app/grounding`: scene-chunked extraction on Nemotron 3.5 Lightning, every kept quote located to a span, faithfulness and recall reported together (T006). Pinned local stack (T002). Gate: 10 checks across 2 projects | Shot planner on Nemotron (T007). Frames on ComfyUI on a Nebius AI Cloud GPU (T003, T026). Frame audit: a vision model describes, Nemotron judges, re-render on mismatch (T020, T021). Hosted demo on Vercel + Railway + Supabase with spend caps (T030) |
| **Design** — "Does the project deliver a complete, coherent product experience not just a technical proof of concept?" | Not yet: the web app has only its health route (T002); the flow exists as the Phase 1 CLI checkpoint | Upload → shots → storyboard in the web app (T009). Audit log visible in the app (T021). Comic reader (T024). Storyboard PDF (T027) and comic PDF (T023). Characters that stay consistent across panels (T025) |
| **Potential Impact** — "Does the project make a credible, specific case for solving a real problem for a real audience and does the solution actually address it based on what's demonstrated?" | The problem and persona are written down ([SCOPE.md](SCOPE.md)); the Devpost story draft is [docs/submission/about.md](docs/submission/about.md) | Evidence the solution works, on public-domain or self-written scripts only: samples (T031), faithfulness, recall and frame-audit accuracy numbers (T032), a video showing it end to end (T034) |
| **Quality of the Idea** — "Is this a creative, non-obvious use of Nebius Token Factory or AI Cloud model(s), and NVIDIA Nemotron and does the team show genuine understanding of the problem space?" | The non-obvious part is grounding enforced in code after generation, not asked for in the prompt: a quote that can't be located in the script is dropped (T006). Recall reported beside faithfulness, because FrameFlow's perfect precision hid a recall of at most ~6% ([docs/submission/about.md](docs/submission/about.md) § Challenges). Findings that contradicted the catalog (U1, U2, U7) | Nemotron as the judge in an image-audit loop: a vision model describes each frame, Nemotron compares it with the shot spec (T010, T020). Measured audit accuracy (T032). Tool feedback for the Devpost form (T033) |

A feature that appears in no row is a candidate to cut ([SCOPE.md](SCOPE.md) § Out of scope).

**Honesty line for every row:** no Nemotron model on Token Factory accepts images
(findings U7), so the frame audit's *describe* step runs on `deepseek-ai/DeepSeek-V4.1-Flash`, a
non-NVIDIA model. Every claim a judge reads uses the approved wording, *"a vision model describes each
frame; Nemotron audits it against the script"* (docs/design/verify.md §8), never "Nemotron vision
auditor" (README, SPEC and the Devpost draft corrected 2026-09-30).
