# Research

Background reading the team brought in, and what each one changes in our work. These are compiled
research reports, not peer-reviewed papers: each cites web pages and papers by number. **A figure
from them is a lead, not a fact.** Check the primary source (the arXiv paper, the letterer's own
guide) before a design doc relies on it or the pitch quotes it.

| File | Added | Applies to |
|---|---|---|
| [speech-bubble-placement.pdf](speech-bubble-placement.pdf): *The Architecture of Sequential Reading: Visual Syntax, Compositional Dynamics, and Dialogue Engineering in Comic Book Lettering* (10 pp.) | 2026-10-18, Katlego | `comic`: T098, T112, T114 ([comic.md](../design/comic.md) §4 steps 7–8, §10) |
| [anatomical-fidelity.pdf](anatomical-fidelity.pdf): *Anatomical Fidelity in Latent Diffusion and Flow Models: Architectural, Conditioning, and Post-Hoc Mechanisms for Digit and Limb Rectification* (15 pp.) | 2026-10-18, Katlego | `verify`: T111 the limb agent ([limb-agent.md](../design/limb-agent.md)) |

## Speech bubble placement

What it says, against what we do (comic.md §4 steps 7–8):

| The report says | We do | Where it goes |
|---|---|---|
| The tail aims at the speaker's **mouth**, as if a line ran on from its tip to the face (§3, from Evan Waterman's lettering guide) | T098 aims at the nearest point of the head box | **T114** (Katlego, 2026-10-18): aim at the centre of the head box's lower third, stopping at the grown head rect |
| The tail stops at about 50–60% of the way from the balloon to the head, never touching the figure (§3, the tail table) | stops 12 px outside the head box (T098's `HEAD_MARGIN`) | comic.md §10: a shorter tail is a later choice, judged by eye |
| Tails never cross one another (§3, from Graphixly) | T112 | done |
| A tail never crosses another character's face, throat or line of sight (§3) | not checked | comic.md §10, with the hidden-tail rule |
| Faces are never covered (§2) | T098: a box over any head costs 2.0 | done; soft, as designed |
| Hands doing something stay visible (§2) | not known: no check sees hands | comic.md §10: only if T111 gives hand boxes |
| The tail leaves the balloon near its middle, not its far edge (§3, from Blambot) | from the point of the box, shrunk by its corner radius, nearest the tip | comic.md §10 |
| The first speaker sits left; when the art has them right, link balloons or re-stage (§3) | the reading order is hard (T023); T112 keeps tails from crossing | no change: we can't re-stage a drawn frame |
| 20–25 words a balloon, 35 a panel; a long speech is split into linked balloons at its breaks (§3, §5) | one balloon per dialogue element, never cut (Non-negotiable I) | comic.md §10: splitting at sentence ends keeps every word, in order |
| Lines stacked as an oval (short, long, short), not a block (§3) | greedy wrap, centred | comic.md §10 |
| Balloons can butt against the panel border (§2) | 16 px inset | no change |

## Anatomical fidelity

What it says, for the limb agent (limb-agent.md):

- **Four kinds of anatomy fault** (from Distortion-5K, arXiv [2503.00811](https://arxiv.org/abs/2503.00811)):
  - *proliferation*: an extra limb or finger;
  - *absence*: a limb or digit missing;
  - *deformation*: a joint bent the wrong way, an impossible twist;
  - *fusion*: two structures grown into one, **including a limb merged into clothing or an
    object**.

  The 14 Oct prototype's `Defect` list covers the first three and fused *bodies*, but not a limb
  fused into an object. It goes to limb-agent.md §10 for a second prompt. The first run stays on
  the prototype's prompt (§8).
- **How common it is:** the report says about half of human figures from current models have a
  measurable fault, citing Distortion-5K. That is not our rate: Tumo's 109 labelled frames have no
  anatomy fault (#194). T111's labels measure our own.
- **Small hands are where it goes wrong.** At 512 px a hand gets about 6 × 6 latent tokens. Faults
  should cluster in wide shots, where the vision model also sees least. So T111 reports recall by
  framing.
- **Answers that point at the fault:** the report's diagnostic model (ARGUS, in Diagnose-to-Generate,
  arXiv 2610.17882) names the fault *and its box*, and is scored on whether the box lands. A box
  per defect makes the agent's answers checkable by eye. It goes to limb-agent.md §10 for a second
  prompt.
- **Fixing instead of redrawing:** the report describes two ways to repair a fault without a full
  redraw:
  - detect the hand, crop it with about 30 px of margin, upscale and inpaint it at denoise
    0.35–0.55 (the ADetailer method);
  - fit a 3D hand mesh and inpaint from its depth map (HandRefiner, arXiv
    [2311.17957](https://arxiv.org/abs/2311.17957)).

  Our loop redraws the whole frame. A regional fix would need an inpainting endpoint and a hand
  box. It's out of T111's scope and recorded as a later option.
- **Not for us:**
  - Negative prompts and negative embeddings: the report finds them unreliable for counts, and our
    fal klein request sends none (storyboard.md §3.5).
  - Pose or depth ControlNets (DWPose, DensePose, SMPL-X): these need the ComfyUI GPU path, which
    is blocked (T003).
