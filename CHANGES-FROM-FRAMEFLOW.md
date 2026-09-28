# Disclosure: Panelwise and FrameFlow

The hackathon rules ask projects that existed before the submission period (26 August 2026) to
explain what was significantly updated during it. This is that explanation.

## What existed before 26 August 2026

Panelwise builds on **FrameFlow**, a private, never-published project by the same team
(Katlego Tlhapiso and Tumo Mogame). Its first commit is dated 14 June 2026.

Before 26 August, FrameFlow was a **text-only pre-production pipeline built on IBM watsonx / Granite
and IBM Docling**. It had:

- screenplay parsing (via IBM Docling);
- LLM scene breakdowns, shot suggestions and casting profiles;
- a Day-Out-of-Days schedule and a film-commission compliance report;
- a first version of the grounding filter and faithfulness score;
- web and mobile scaffolds with auth.

It had **no image generation, no storyboards, no portraits and no comic output**, and it ran on no
open models.

## What changed in FrameFlow between 26 August and the start of Panelwise

197 commits: 322 files changed, +30,956 / −4,747 lines.

| Area | Change |
| --- | --- |
| Model layer | IBM watsonx / Granite removed; replaced with a provider seam for OpenAI-compatible endpoints |
| Parsing | IBM Docling removed; replaced with a pdfplumber parser |
| Grounding | Extraction chunked on scene boundaries; verbatim source spans; recall metric; line-break fixes |
| **Storyboards** | **New:** one frame per shot, selectable styles, scene PDF (6–13 September) |
| Image generation | **New:** provider chain (ComfyUI, A1111, Gemini), record/replay cache |
| Cast portraits | **New:** grounded reference portraits as polled jobs |
| Infrastructure | Asset store, lineage, budget ceilings, tracing |

## What is new in Panelwise (during the submission period)

Panelwise is a **new repository** focused on storyboards and comics. It ports only the pieces the
storyboard pipeline needs, and drops scheduling, compliance, auditions, voice and mobile.

| Area | New work |
| --- | --- |
| Models | NVIDIA Nemotron on Nebius Token Factory for every text call, with fast and reasoning tiers |
| Frame audit | Nemotron vision model checks each frame against its shot spec, re-renders on mismatch, and logs every verdict |
| Comic mode | Panel layout by story beat, speech bubbles from linked dialogue, lettering, comic page export |
| Character consistency | Portraits used as image references across panels |
| Rendering | ComfyUI on Nebius AI Cloud GPUs (FrameFlow rendered on CPU) |
| Evaluation | Benchmarks for faithfulness and frame-audit accuracy |

## Code ported from FrameFlow

Each ported module is listed here with the FrameFlow file it came from and whether it predates
26 August. Anything marked *pre-26 Aug* is earlier work, not hackathon work.

| Panelwise module | Ported from (FrameFlow) | Origin |
| --- | --- | --- |
| `services/api/app/llm/client.py` | `services/api/app/services/openai_compat.py` (retry on 429/5xx with backoff; the reasoning-but-no-content error) | 28 Aug 2026 (`dceba8d`, T257), during the submission period. Rewritten for Panelwise: async, Nebius-only, three tiers, `Retry-After`, thinking toggle, `<think>` stripping, usage with reasoning tokens |
| `services/api/app/llm/structured.py` | `services/api/app/services/llm_provider.py::structured_chat` (strict `json_schema` + one repair retry) | 28 Aug 2026 (`dceba8d`, T261), during the submission period. Rewritten: async, schema inlined in the system prompt, returns the answering model and usage |
