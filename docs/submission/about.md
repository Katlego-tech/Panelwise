# Devpost — "About the project" (draft)

> Working copy of the Devpost story. Paste **everything below the line** into Devpost.
>
> Before submitting (T034/T035): every `⟨TBD⟩` is either filled with a measured number or cut, the
> Inspiration paragraph is rewritten in our own words, and every claim is checked against what the
> demo actually does. FrameFlow figures come from FrameFlow's STATUS.md; the ~6% recall is an upper
> bound computed from those counts (FrameFlow lists both 202 and 170 locations; we use the lower).

---

## Inspiration

⟨TBD — replace with your real story. Draft:⟩ A storyboard is how a director shows everyone what
the film will look like before a single day is shot, and for small productions it is often the
first thing cut: it takes an artist, time and money. We had already built **FrameFlow**, a
pre-production assistant that reads a screenplay and breaks it down into characters, locations and
shots. The obvious next step was to *draw* those shots — and then to go one step further and turn
the same script into a comic book.

The catch is that image models love to invent. Ask for "a kitchen at night" and you get a cat, a
third person, a window that isn't in the scene. For a storyboard that is worse than useless: it
tells the crew something the writer never wrote. So Panelwise is built around one rule —
**no panel may show a character, prop, line or event that is not in the screenplay.**

## What it does

⟨TBD: each step true once US1, T005–T009, ships; on main today the Nemotron client (T004) and the screenplay parser (T005) exist; extraction onward does not⟩
Upload a screenplay. Panelwise parses it into scenes and dialogue, extracts the characters and
locations with **NVIDIA Nemotron on Nebius Token Factory**, plans a shot list, renders one frame per
shot, and lays the frames out as storyboard pages or as comic pages with speech bubbles taken from
the script's dialogue. Every panel links back to the verbatim lines it came from.

Every rendered frame is audited. ⟨TBD: true once T020/T021 ship⟩ No Nemotron model on Token Factory
accepts images, so the audit is split in two: a vision model describes the frame — who is in it,
the framing, the time of day — and **Nemotron compares that description with the shot spec** and
sends the frame back for a re-render when they disagree. The description and the verdict are both
logged, so you can see why a frame was accepted.

## How we built it

- **Grounded extraction.** The screenplay is split on scene boundaries and each chunk goes to
  Nemotron with a strict JSON schema. Every extracted entity must carry a verbatim quote from the
  script; a grounding filter drops anything whose quote can't be found in the source.
  ⟨TBD: true once T006 ships; the filter is ported from FrameFlow⟩
- **Model tiers.** Every model call goes through one client with two text tiers: the fast tier,
  **Nemotron 3.5 Lightning** with thinking switched off, and **Nemotron 3 Super** with thinking on
  for judgement calls. Every result records which model answered and how many tokens it spent
  thinking. High-volume, schema-bound work (extraction, shot planning) goes on the fast tier.
  ⟨TBD: "goes" is true once T006/T007 call it⟩
- **Rendering.** ComfyUI on a **Nebius AI Cloud** GPU, with character reference portraits so the same
  person looks the same from panel to panel. ⟨TBD: true once T003 and T025 ship⟩
- **The audit loop.** Each frame may be rendered at most \(k+1\) times. If a single render passes
  the audit with probability \(p\), the expected number of renders per frame is

  $$\mathbb{E}[N] \;=\; \sum_{i=0}^{k} (1-p)^i \;=\; \frac{1-(1-p)^{k+1}}{p},$$

  which is how we plan to budget GPU time ⟨TBD: true once T020/T021 ship⟩: at \(p = ⟨TBD⟩\) and \(k = ⟨TBD⟩\), a frame costs
  \(⟨TBD⟩\) renders on average.
- **Stack.** A Next.js app on Vercel in front of a FastAPI service on Render, with Supabase for
  Postgres, image storage and sign-in. ⟨TBD: true once T037 deploys; today it runs in Docker locally⟩

## Challenges we ran into

**Measuring the right thing.** In FrameFlow we tracked a *faithfulness* score — the share of
extracted entities that really appear in the script:

$$F = \frac{|E_{\text{grounded}}|}{|E|}.$$

After prompt tuning we hit \(F = 1.0\) (15 of 15 grounded), and it looked like we were done. We
weren't. Faithfulness is precision; it says nothing about what was *missed*. The same screenplay
has 77 speaking characters and at least 170 distinct locations, so the recall of that run was at
most

$$R = \frac{|E \cap G|}{|G|} \;\le\; \frac{15}{77 + 170} \approx 6\%.$$

A perfect score on a sixth of the cast is a failure. Now we report precision and recall together,
and only on a full parse.

**Measuring on a fragment — twice.** An earlier score of 0.778 turned out to be computed on a PDF
parse that silently dropped about two-thirds of the screenplay. We threw the number away and
switched parsers.

**Infrastructure walls.** Chunked extraction needs 17 requests per feature-length script. A free
API tier capped at 20 requests a day died at chunk 7 of 17, and a local 3B model timed out on a
single 20K-character chunk. On Nebius Token Factory a full-script run is finally cheap enough to
finish: at catalog prices, an estimated 0.3M tokens in and 0.15M out per screenplay comes to about

$$0.3 \times \$0.06 + 0.15 \times \$0.24 \approx \$0.05 .$$

⟨TBD: replace the estimate with the measured cost once T006 runs a full script, and say it finished.⟩

**Errors that lied.** In FrameFlow, when one provider in the fallback chain hit its quota, the chain
fell through to a local endpoint that wasn't running and reported only that last error — a 404
from `localhost:11434` — pointing us at Ollama when the cause was the quota. FrameFlow's chain now
reports every provider's failure; Panelwise has no chain at all. It calls one provider, so the
error names the model that failed.

**Reading the catalog versus measuring the API.** Before writing any code we spent under half a cent
probing Token Factory, and several answers contradicted what the documentation suggested:

- The model catalog lists no JSON mode for any Nemotron model, yet strict `json_schema` output
  **was enforced**, even when the prompt never mentioned the schema. The looser `json_object` mode
  returned JSON in the wrong shape, and in one run it added a detail the scene never gave — a
  character "likely a lighthouse keeper". That is exactly the kind of invention grounding has to
  catch.
- Nemotron reasons by default. For a one-number answer, thinking took Lightning from 4 output
  tokens to 271. Only two of the four switches we tried actually turned it off.
- No Nemotron model on Token Factory accepts images, so the frame audit had to be redesigned
  around a vision model that describes and a Nemotron model that judges.

## Accomplishments that we're proud of

- Across 15 live runs on three self-written screenplays (5 each), **no ungrounded quote or shot
  citation survived into the shot plan**: every kept quote and every shot's cited text was re-checked
  in code against the script lines it names, and all 15 runs came back at 0. Every action paragraph
  and speech landed in exactly one shot, in every run. (That is the text side; whether a rendered
  image shows only what the shot says is the frame audit's job, measured once frames render.)
- Nemotron 3.5 Lightning's own proposals were 89.8% faithful (246 of 274 entities fully grounded);
  the filter dropped what didn't ground (the unlocated quotes, or the whole entity). It found 85 of
  the 90 speaking-character appearances itself; the only miss was the same one in each run of
  the largest script, a station announcer heard in voice-over, whom the script's dialogue cues
  supply. Numbers and method:
  [`eval/`](../../eval/README.md).

⟨TBD: frame-audit accuracy from `eval/` (T049, needs renders).⟩

## What we learned

- A metric you can't break down is a metric you can't trust. A perfect precision score hid the fact
  that we were missing at least 94% of what was in the script.
- Grounding has to be enforced *after* generation, in code, not asked for in the prompt. Models agree
  to "only use what's in the script" and then don't.
- Vision models make good critics of image models: checking a frame against a spec is far easier
  than generating it correctly the first time.
  ⟨TBD: confirm with the audit numbers, or cut.⟩

## What's next for Panelwise

Editable panels (redraw a single frame with a note), animatics with scratch audio, and exporting
shot lists straight into scheduling tools.
