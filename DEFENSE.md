# Q&A defence

Judges use the Q&A to decide whether this is real engineering or a concept pitch. There is no live
Q&A at this event: judges read the README, the Devpost story and the repo, so these answers belong
there too (T033, and [docs/submission/about.md](docs/submission/about.md)). Each answer says what
is true **today** and what a named task will make true; update it as tasks land.

### 1. "Which part of what we just saw is real, and which part is mocked?"
State the boundary plainly: the core runs live, and the peripherals in MOCKS.md are mocked for
stability.

**Answer:** Nothing in the pipeline is mocked. Every model call is a live call to Nebius Token
Factory, and nothing is listed in [MOCKS.md](MOCKS.md). The unit tests replace the network with
`httpx2.MockTransport` so they run offline, but those are tests, not the demo. The one thing a judge
may see that isn't computed on the spot is the seeded judge project, rendered in advance so the
demo costs nothing to open (T030); uploading a script of your own runs the whole pipeline live.
And one plain fact about models: the frame audit's *describe* step runs on `deepseek-ai/DeepSeek-V4.1-Flash`,
because no Nemotron model on Token Factory accepts images (findings U7); Nemotron makes the
verdict (T020).

### 2. "Can we try it with an input of our own?"
Accept straight away. If it breaks, give a calm post-mortem of the case it didn't handle.

**Answer:** Yes: upload any screenplay PDF to the hosted demo, within its upload limits (T030).
The parser expects standard screenplay layout (scene headings, character cues, dialogue). A
scanned PDF with no text layer, or a text with no `INT.`/`EXT.` scene heading, raises
`ScriptParseError` with that reason instead of returning an empty screenplay that looks like
success (docs/design/script.md § Failure paths). Grounding fails safe: a quote the model proposes that can't
be located in the script is dropped and reported, never shown, so an unusual script gives fewer
entities, not invented ones (docs/design/grounding.md).

### 3. "Why this database, framework or model?"
Defend it with a concrete constraint (latency, payload size, a guarantee), not popularity.

**Answer:** The fast tier is Nemotron 3.5 Lightning: 600 requests and 400K tokens a minute, $0.06
in / $0.24 out per million tokens, and Token Factory **enforces** a strict `json_schema` on it
(findings U1), which schema-bound extraction needs. Thinking is switched off on that tier, which
took a one-number answer from 271 completion tokens to 4 (U2). Nemotron 3 Super, with thinking on,
is the reasoning tier for judgement calls. Images render on ComfyUI on a Nebius AI Cloud GPU
because Token Factory serves no image-generation model (U5, T003). The vision step uses DeepSeek-V4.1-Flash:
the cheapest model we first chose (GLM-5.3-Flash) stopped receiving images, and DeepSeek read our
storyboard frames correctly (findings § U7 re-check, 2026-09-30).

### 4. "How did you check that it's accurate, safe or reliable?"
Cite your evaluation: even 5–10 deterministic test cases with measured results.

**Answer:** Today: the Phase 1 checkpoint on the real account, on a self-written 3-scene sample,
scored faithfulness 1.000 (5/5 entities, 8/8 quotes located) and recall 1.000 (2/2 speakers),
spending 509 input and 157 output tokens with 0 reasoning tokens (STATUS.md log, 2026-09-28). That
sample is tiny; feature-length numbers come from T031 and T032. We report precision and recall
together because FrameFlow once scored a perfect 1.0 faithfulness while its recall was at most ~6%.
Every push runs the gate: ruff, pyright, pytest, eslint + tsc, vitest, next build, and placeholder,
secret, vulnerability and duplication scans (10 checks). Frame-audit accuracy is measured in T032.

### 5. "What did you deliberately cut, and why?"
Frame it as scope control: pruned at the midpoint so the golden path has no defects.

**Answer:** FrameFlow's multi-provider fallback chain (Gemini, Ollama): Panelwise calls one
provider, so an error names the model that failed instead of the last one in the chain
(`app/llm/client.py`). Self-hosting an NVIDIA vision model on the Nebius GPU is a stretch, not the
plan (findings § The vision decision). Private style packs are never needed for the demo
(Non-negotiable 2). Editable panels, animatics and shot-list export to scheduling tools are after
the event ([SCOPE.md](SCOPE.md) § Out of scope).

## Appendix material (in the README or the Devpost story, after the main content)

- [ ] The data model: the class diagrams in [docs/design/script.md](docs/design/script.md) and [docs/design/grounding.md](docs/design/grounding.md), plus verify and comic (T010, T011)
- [ ] Edge cases, and how they're handled: dropped quotes, parse errors, audit retry cap (T021)
- [ ] Unit economics: measured Token Factory cost per full script (the Devpost draft's catalog-price estimate is ~$0.05; measured on a full script in T032) and expected renders per frame from the audit loop (T021)
