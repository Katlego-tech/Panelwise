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
- **Model tiers.** High-volume, schema-bound calls (extraction, shot planning) run on the fast tier,
  **Nemotron 3.5 Lightning**, with thinking switched off; judgement calls use **Nemotron 3 Super**
  with thinking on. Every result records which model answered and how many tokens it spent
  thinking.
- **Rendering.** ComfyUI on a **Nebius AI Cloud** GPU, with character reference portraits so the same
  person looks the same from panel to panel.
- **The audit loop.** Each frame may be rendered at most \(k+1\) times. If a single render passes
  the audit with probability \(p\), the expected number of renders per frame is

  $$\mathbb{E}[N] \;=\; \sum_{i=0}^{k} (1-p)^i \;=\; \frac{1-(1-p)^{k+1}}{p},$$

  which is how we budget GPU time: at \(p = ⟨TBD⟩\) and \(k = ⟨TBD⟩\), a frame costs
  \(⟨TBD⟩\) renders on average.
- **Stack.** FastAPI + Postgres + Redis behind a Next.js app, all in Docker.

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
single 20K-character chunk. Nebius Token Factory is what finally made a full-script run cheap enough
to finish: roughly 0.3M tokens in and 0.15M out per screenplay comes to about

$$0.3 \times \$0.06 + 0.15 \times \$0.24 \approx \$0.05 .$$

⟨TBD: replace with the measured cost from the trace report.⟩

**Errors that lied.** When one provider in our fallback chain hit its quota, the chain reported only
the *last* provider's error, "connection refused on localhost" — pointing us at the wrong service
entirely. Now an exhausted chain reports every provider's failure.

**Reading the catalog versus measuring the API.** Before writing any code we spent under half a cent
probing Token Factory, and several answers contradicted what the documentation suggested:

- The model catalog lists no JSON mode for any Nemotron model, yet strict `json_schema` output
  **was enforced**, even when the prompt never mentioned the schema. The looser `json_object` mode
  returned JSON in the wrong shape, and in one run it added a detail the scene never gave — a
  character "likely a lighthouse keeper". That is exactly the kind of invention our grounding
  filter exists to catch.
- Nemotron reasons by default. For a one-number answer, thinking took Lightning from 4 output
  tokens to 271. Only two of the four switches we tried actually turned it off.
- No Nemotron model on Token Factory accepts images, so the frame audit had to be redesigned
  around a vision model that describes and a Nemotron model that judges.

## Accomplishments that we're proud of

⟨TBD: faithfulness and recall on the full sample script; frame-audit accuracy from `eval/`.⟩

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
