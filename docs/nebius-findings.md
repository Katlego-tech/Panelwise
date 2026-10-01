# Nebius Token Factory — findings (T001)

_Measured 2026-09-28 against our own account (trial tier, $1 credit) by Katlego (via Claude).
Every verdict below cites a response captured that day. Total spend for the whole probe: ~$0.004
(59 billed calls, priced from the catalog). U7 was re-checked on 2026-09-30 during T020
([§ U7 re-check](#u7-re-check-2026-09-30)): GLM-5.3-Flash no longer receives images._

Questions U1–U6 come from the FrameFlow Nebius plan (§3); U7 is Panelwise's own.

## Summary

| # | Question | Verdict | Consequence |
|---|---|---|---|
| U1 | Is `response_format: json_schema` enforced on Nemotron? | **Yes.** Schema-valid output even with no schema in the prompt. `json_object` gives valid JSON in the wrong shape; `guided_json` is ignored | T004 sends `json_schema` (strict) and keeps the schema in the prompt too; the repair retry stays as a backstop, not the plan |
| U2 | Can thinking be switched off? | **Yes**, two ways: `chat_template_kwargs: {enable_thinking: false}` or `reasoning_effort: "none"`. `"low"` and a `/no_think` system prompt do **not** switch it off | Fast tier defaults to thinking off. Reasoning arrives in a separate `reasoning_content` field, not as `<think>` in `content` — but `content` can start with `\n`, so strip it |
| U3 | Which host serves which model? | **All four Nemotron models answer on the default host** (`api.tokenfactory.nebius.com`) | One base URL. `NEBIUS_REASONING_BASE_URL` is not needed |
| U4 | Rate limits | Per model, from the catalog and confirmed by response headers. Lightning: **600 RPM / 400K TPM**. A burst of 20 concurrent calls: 20 × 200 | 17 extraction chunks in a burst is far inside the limit. Re-check once the paid credit lands (trial tier today) |
| U5 | Is an image-generation model served? | **No.** No model in either host's catalog has an image output modality | Rendering stays on ComfyUI on a Nebius GPU (T003). FrameFlow plan item N8 is dropped |
| U6 | Sampling for grounded extraction | **Not settled by this probe** — 3 runs at each setting on one short scene all grounded their evidence verbatim | Decide on the full-script baseline in T006. The one failure seen was a *shape* failure under `json_object` (see U1), not a sampling one |
| U7 | Is a vision model served, and does it take an image in a chat message? | **Yes — but none is NVIDIA.** Every Nemotron model is `text->text` and rejects images. Five non-NVIDIA models accept images and all five read our test image correctly on 2026-09-28; **on 2026-09-30 GLM-5.3-Flash no longer received images** ([re-check](#u7-re-check-2026-09-30)), so the describer is DeepSeek-V4.1-Flash | **Decided 2026-09-28: option A now, B as a stretch** — see [§ The vision decision](#the-vision-decision) |

## Settled configuration

These are the values in [`.env.example`](../.env.example).

| Variable | Value | Why |
|---|---|---|
| `NEBIUS_BASE_URL` | `https://api.tokenfactory.nebius.com/v1` | U3: every Nemotron model answers here |
| `NEBIUS_MODEL_FAST` | `nvidia/Nemotron-3_5-Lightning` | 1M context, $0.06 / $0.24 per 1M tokens, 600 RPM; `json_schema` enforced (U1) |
| `NEBIUS_MODEL_REASONING` | `nvidia/nemotron-3-super-120b-a12b` | 262K context, $0.30 / $0.90, 300 RPM |
| `NEBIUS_MODEL_VISION` | `deepseek-ai/DeepSeek-V4.1-Flash` | Was `zai-org/GLM-5.3-Flash` (cheapest correct VLM on 2026-09-28) until the [U7 re-check](#u7-re-check-2026-09-30) found it no longer receives images. DeepSeek read real storyboard frames correctly, 3000 RPM. It *describes* frames; Nemotron judges |
| `NEBIUS_REASONING_BASE_URL` | removed | U3 |

Other Nemotron models, both served on the default host: `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`
($0.06 / $0.24, **100 RPM** — a sixth of Lightning's, so a poor fast-tier fallback under load) and
`nvidia/Nemotron-3-Ultra-550b-a55b` ($1.00 / $3.00, 300 RPM, 1M context).

## How it was measured

A standard-library Python script sent each request and saved the full request and response (key
never written). The script is not committed: a `.py` file before T002 lands a manifest fails the
gate, and its reusable part becomes T004's startup check. The requests are reproduced below.

---

## U1 — JSON enforcement

The catalog lists `supported_features: ["tools", "reasoning"]` for every Nemotron model — no
`json_mode`, no `structured_outputs` — so the catalog alone suggested it would not work. It does.

Test scene (self-written, 7 lines) and schema:

```json
{"type": "object",
 "properties": {
   "characters": {"type": "array", "items": {"type": "object",
     "properties": {"name": {"type": "string"}, "evidence": {"type": "string"}},
     "required": ["name", "evidence"], "additionalProperties": false}},
   "location": {"type": "string"}},
 "required": ["characters", "location"], "additionalProperties": false}
```

Five variants × two models, `temperature: 0`, thinking off. "Bare prompt" means the user message
only said *"List the characters in this scene and the location."* — no schema, no mention of
`evidence`.

| Variant | Lightning | Nano |
|---|---|---|
| `json_schema` (strict) + schema in prompt | ✅ valid | ✅ valid |
| `json_schema` (strict), bare prompt | ✅ valid | ✅ valid |
| `json_object` + schema in prompt | ✅ valid | ✅ valid |
| `json_object`, bare prompt | ❌ wrong shape | ❌ wrong shape |
| `guided_json` (vLLM extra), bare prompt | ❌ ignored | ❌ ignored |

Request (the bare `json_schema` case):

```json
{"model": "nvidia/Nemotron-3_5-Lightning",
 "messages": [{"role": "user", "content": "List the characters in this scene and the location.\n\n<scene>"}],
 "response_format": {"type": "json_schema", "json_schema": {"name": "scene", "schema": <above>, "strict": true}},
 "temperature": 0, "chat_template_kwargs": {"enable_thinking": false}, "max_tokens": 1024}
```

Response `content` — note it produced an `evidence` field it was never asked for in words, so the
schema really is steering decoding:

```json
{"characters": [{"name": "Nandi", "evidence": "NANDI (60s, oilskin coat) pours tea into two chipped mugs."},
                {"name": "Thabo", "evidence": "THABO (20s) stands dripping in the doorway, holding a torn map."}],
 "location": "INT. LIGHTHOUSE KITCHEN - NIGHT"}
```

The same bare prompt under `json_object` — Lightning flattened the array to strings; Nano added
fields and **invented a description the scene never gives**:

```json
{"name": "NANDI", "age": "60s",
 "description": "Oilskin coat, weathered, likely a lighthouse keeper or someone connected to the sea"}
```

A second, quieter failure under `json_object` *with* the schema in the prompt (U6, one run in six):
Lightning echoed the schema's own wrapper — `{"type": "object", "properties": {"characters": [...]}}`.
Valid JSON, correct content, unusable shape.

**Consequence for T004:** send `json_schema` with `strict: true`. Keep the schema in the prompt as
well (it's cheap, and the docs recommend it). The repair retry stays, but it should rarely fire.
The grounding filter stays regardless: schema enforcement fixes *shape*, not *truth*.

## U2 — Switching thinking off

Prompt: *"What is 17 * 23? Answer with the number only."* All answers were `391`.

| Setting | Lightning completion / reasoning tokens | Super completion / reasoning tokens |
|---|---|---|
| default | 271 / 266 | 67 / 61 |
| `chat_template_kwargs: {enable_thinking: false}` | **4 / 0** | **4 / 0** |
| `reasoning_effort: "none"` | **4 / 0** | **4 / 0** |
| `reasoning_effort: "low"` | 236 / 231 | 44 / 38 |
| system message `/no_think` | 239 / 234 | 67 / 61 |

- Reasoning tokens are reported in `usage.completion_tokens_details.reasoning_tokens` and billed as
  completion tokens: on Lightning, thinking multiplied the output ~68× for a one-number answer.
- The reasoning text comes back in `message.reasoning_content`, not wrapped in `<think>` inside
  `content`. With thinking on, Super's `content` was `"\n391"` — a leading newline.

**Consequence for T004:** fast-tier calls send `chat_template_kwargs: {enable_thinking: false}` by
default; a caller can opt in per call. Record `reasoning_tokens` in the trace. Still strip a leading
`<think>…</think>` defensively and `.strip()` the content.

## U3 — Hosts

`"Reply with the single word: ok"`, thinking off, each model on each host:

| Model | default host | us-central1 host |
|---|---|---|
| `nvidia/Nemotron-3_5-Lightning` | 200, 1.49 s | 200, 2.40 s |
| `nvidia/nemotron-3-super-120b-a12b` | 200, 2.10 s | 200, 2.38 s |
| `nvidia/Nemotron-3-Ultra-550b-a55b` | 200, 1.33 s | 200, 3.04 s |
| `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | 200, 1.21 s | 200, 1.83 s |

The default host lists 25 models, us-central1 lists 18. Super and Ultra are *hosted* in
us-central1 (catalog `regions`) but the default host routes to them. Single-call latencies only —
not a benchmark.

## U4 — Rate limits

Limits are **per model**, published in `GET /v1/models?verbose=true` under `per_request_limits`,
and echoed on every response:

```
x-ratelimit-limit-requests: 600          x-ratelimit-limit-tokens: 400000
x-ratelimit-remaining-requests: 587      x-ratelimit-remaining-tokens: 399944
x-ratelimit-reset-requests: 2s           x-ratelimit-reset-tokens: 1s
x-ratelimit-dynamic-scale-requests: 1.00 x-ratelimit-dynamic-period-remaining: 827s
```

| Model | RPM | TPM |
|---|---|---|
| Lightning | 600 | 400K |
| Super | 300 | 200K |
| Ultra | 300 | 200K |
| Nano | 100 | 800K |

Burst test: 20 concurrent Lightning calls → 20 × `200`, no `429`.

Caveats: measured on the **trial** tier; the `dynamic-scale` headers suggest limits can move. On the
us-central1 host, Super/Ultra/Kimi report `1e10` RPM — treat that as "not reported", not unlimited.
**Consequence for T004:** read `x-ratelimit-remaining-*` and honour `Retry-After` on 429 rather
than fixed backoff. TPM, not RPM, is the binding limit for extraction (17 chunks × ~8K tokens ≈
136K tokens, a third of Lightning's minute).

## U5 — Image generation

No model on either host has an image output modality (`architecture.modality` is `text->text` or
`text+image->text` for all 25). `flux-schnell` and `sdxl` are gone. **Consequence:** images render on
ComfyUI on a Nebius AI Cloud GPU (T003), which still satisfies "runs on Nebius AI Cloud".

## U6 — Sampling for grounded extraction

Lightning, `json_object` + schema in prompt, thinking off, 3 runs per setting on the test scene:

| Setting | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| `temperature: 0` | NANDI, THABO — evidence verbatim ✅ | same ✅ | schema-wrapper echo (U1) ❌ |
| `temperature: 1.0, top_p: 0.95` | NANDI, THABO ✅ | same ✅ | Nandi, Thabo ✅ |

Note: temperature 0 was **not deterministic** (run 3 differs from runs 1–2).

**Not settled.** Six runs on a 7-line scene can't separate the two settings. NVIDIA's
temp 1.0 / top_p 0.95 recommendation is for reasoning *on*; we run extraction with it off. Decide on
the full-script faithfulness + recall baseline in T006, with `json_schema` (which removes the one
failure seen here).

## U7 — Vision

Test image: a 256×256 PNG, white, with a red square top-left and a blue circle bottom-right, sent
as a base64 `data:` URL in an OpenAI-style content part:

```json
{"role": "user", "content": [
  {"type": "text", "text": "Describe the shapes in this image: for each, its colour and its position (which corner). Be brief."},
  {"type": "image_url", "image_url": {"url": "data:image/png;base64,<…>"}}]}
```

| Model | Maker | $/1M in · out | RPM | Result |
|---|---|---|---|---|
| `nvidia/Nemotron-3_5-Lightning` (control) | NVIDIA | 0.06 · 0.24 | 600 | **400** `"This model does not support image input"` |
| `zai-org/GLM-5.3-Flash` | Z.ai | 0.15 · 0.50 | 600 | ✅ "Red square — top-left corner / Blue circle — bottom-right corner" |
| `deepseek-ai/DeepSeek-V4.1-Flash` | DeepSeek | 0.30 · 1.20 | 3000 | ✅ "a red square in the top-left corner and a blue circle in the bottom-right corner" |
| `openbmb/MiniCPM-V-4_5` | OpenBMB | 0.66 · 1.11 | 300 | ✅ "A red square is positioned in the top-left corner. A blue circle is located in the bottom-right corner." Only 32K context |
| `moonshotai/Kimi-K2.6` | Moonshot | 0.95 · 4.00 | 200 | ✅ "Red square: top-left. Blue circle: bottom-right." |
| `moonshotai/Kimi-K3` | Moonshot | 3.00 · 15.00 | 1000 | ✅ correct ("bottom-right (right of center)") |

All four Nemotron models are `text->text` in the catalog. **No NVIDIA vision model is served on
Token Factory.** A two-shape test proves the plumbing works, not that a model can audit a storyboard
frame — frame-audit accuracy is measured in T049.

### U7 re-check (2026-09-30)

T020's first live audit (`app.verify.run`) came back describing a person "with one visible eye" in a
frame that shows two adults and a child in a kitchen. The same request shape as U7, sent again on
2026-09-30 with our key:

| Request | Model | `prompt_tokens` | Answer |
|---|---|---|---|
| The U7 two-shape PNG (256×256, re-drawn), U7's prompt | `zai-org/GLM-5.3-Flash` | 37 | ❌ "Red blob top-left, dark green blob top-right, red blob bottom-centre, yellow blob bottom-right" |
| A 448×256 storyboard frame (kitchen, three people), "how many people…?" | `zai-org/GLM-5.3-Flash` | 31 | ❌ "no people… a dark scene… like stars in a night sky" |
| same frame at 1344 px (the original, 1.9 MB) and 448 px (0.18 MB) | `zai-org/GLM-5.3-Flash` | 31 | ❌ invented scenes at both sizes ("a conference room"; "eight young adults on a sofa"); the 448 px call took ~90 s, and 672 px calls timed out at 110 s |
| same frame | `deepseek-ai/DeepSeek-V4.1-Flash` | 238 | ✅ "three people… a man and a woman… a young girl watches from an open doorway" |
| same frame | `openbmb/MiniCPM-V-4_5` | 94 | ✅ three people, the girl at the door |
| same frame | `moonshotai/Kimi-K2.6` | 189 | ✅ three people, the girl peeking through the doorway |

**Verdict:** GLM-5.3-Flash on Token Factory now answers image requests **without receiving the image**:
a text-only prompt's token count, and a confident invented description. No error is returned, so
nothing upstream can tell. The audit would have judged made-up frames.

**Consequence:** `NEBIUS_MODEL_VISION` is now `deepseek-ai/DeepSeek-V4.1-Flash` ($0.30 · $1.20,
3000 RPM), the cheapest model that read both the U7 image and a real storyboard frame correctly.
Its structured output held on every describer call in T020's live runs (`json_schema`, no repair
needed). Option A is unchanged: only the describer's model moved. T049 should re-check whichever
describer is configured, since this changed silently between two dates.

### The vision decision

SPEC, README and the pitch say "a **Nemotron** vision auditor". That can't be true on Token Factory
as-is. Options, for the team to decide before T010 (`docs/design/verify.md`):

| | Option | Nemotron's role in the audit | Cost / effort | Risk |
|---|---|---|---|---|
| **A** | **Perceive + judge split** — a Token Factory VLM (GLM-5.3-Flash) describes the frame as structured JSON (who is in frame, count, framing, time of day, props); Nemotron compares that description to the shot spec and issues the verdict | **Nemotron makes every audit decision** | Two cheap calls per frame; no new infra | The VLM's description is a lossy middle step; audit accuracy is only as good as it |
| **B** | Self-host an NVIDIA VLM (e.g. Nemotron Nano VL) with vLLM on the same Nebius GPU as ComfyUI | Nemotron sees the image directly | New serving work on T003's box; GPU memory shared with ComfyUI | Schedule — this is new infrastructure in a 5-week project |
| **C** | A Token Factory VLM does the whole audit | None | One call per frame | "Nemotron vision auditor" becomes false; wording in SPEC/README/pitch must change |

**Decided 2026-09-28 (Katlego): A now, B as a stretch.** Build A for the deadline; try B only if
T003's GPU has headroom once US1 works. A keeps the claim honest in a narrower form — *"a vision
model describes each frame; Nemotron audits it against the script"* — needs no new infrastructure,
and makes the audit's reasoning inspectable, since the description is logged next to the verdict.

## Follow-ups this creates

- T004: `json_schema` strict by default; thinking off by default on the fast tier; trace
  `reasoning_tokens`; honour `Retry-After` and the ratelimit headers; one base URL.
- T006: settle U6 on the full-script baseline.
- T010: build `verify.md` on option A (perceive with `NEBIUS_MODEL_VISION`, judge with Nemotron).
- SPEC, README and `docs/submission/about.md` say "Nemotron vision auditor": correct them to the
  option A wording, in their own PR.
- U4: re-read the limits once the Builder Program credit lands.
