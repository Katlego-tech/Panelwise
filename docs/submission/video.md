# The video (T034): script, 3 minutes

> Working script for the Devpost video: a public YouTube video, **180 s or shorter**, whose audio
> covers how we used **Nebius Token Factory** and **NVIDIA Nemotron** (DEMO.md). One presenter
> narrates. Record on the hosted demo, signed in as the judge account, with the-red-kite already in
> its list (copied 2026-10-20). Rehearse it timed at least five times (DEMO.md § Rehearsal log).
>
> About 430 words of narration at an easy 150 words a minute leaves room for the clicks. Times are
> targets; cut words, not the demo. Never click an unrehearsed path on camera.

---

## 0:00–0:20 · Hook

**On screen:** the comic reader, the-red-kite page 1 (Lerato on the roof, the bubbles).

> This is a comic page made from a screenplay, by Panelwise. Every panel, every speech bubble, every
> person in it traces back to a line of the script. Nothing is invented. Let me show you how.

## 0:20–0:50 · The problem

**On screen:** the script page beside a storyboard frame; then frame 1.1's card with its
"Passed with a warning" note.

> Before a film is shot, a storyboard shows everyone what it will look like. That takes an artist,
> time and money most small productions don't have. Image models can draw fast, but they make
> things up: extra people, props the script never mentions, the wrong character. For a storyboard,
> an invented detail is worse than no picture at all.

## 0:50–1:10 · What Panelwise does

**On screen:** the projects page; the upload panel.

> You upload a screenplay PDF. Panelwise reads it, plans the shots, draws one frame per shot, and
> then checks every frame against the script before it shows it to you. When a frame doesn't hold
> up, it draws it again. Then it lays the frames out as a comic, with the script's own dialogue in
> the bubbles.

## 1:10–2:20 · The demo

**On screen, in order** (pre-opened tabs; no waiting on camera):

1. **Script tab** (the-red-kite): the scenes and characters, each with its quote and page and line.
   > Nemotron on Nebius Token Factory reads the script and pulls out every scene, character and
   > place, each with the exact line it came from. Anything it can't point to in the script is
   > thrown away, in code.
2. **Storyboard tab:** the lined script beside the frames; click shot 1.1, then hover a shot line.
   > Each frame sits beside the lines it draws. Here, Lerato with her red kite, on the roof.
3. **Open frame 1.1's sheet, the audit log.**
   > Every frame is audited. Nemotron 3.5 Super VL, a vision model, describes what was actually
   > drawn, without seeing the script. Then Nemotron Super, the judge, compares that description
   > with the shot. Here it noticed a second child the script didn't ask for, and says so on the card.
4. **Export PDF:** the file saves as "the-red-kite storyboard.pdf".
   > The whole storyboard exports as a PDF.
5. **Comic tab:** page 1; click Mokgosi's bubble, "Is that my good shirt you are flying?"; the
   "From the script" card shows page 2, lines 93–94, off panel.
   > And the comic: the bubbles are the script's own words. Click any of them and you see the line
   > it came from. Mokgosi is off panel here, so his bubble points out of the frame.

## 2:20–2:40 · How we used Nebius and NVIDIA

**On screen:** the README's architecture diagram.

> Under the hood: Nemotron 3.5 Lightning on Token Factory extracts and plans the shots. FLUX.2 klein
> on fal.ai draws. Nemotron 3.5 Super VL describes each frame, and Nemotron Super judges it, with
> small agents asking follow-up questions: is that character really there, the right sex, drawn
> twice? It all runs on Token Factory's OpenAI-compatible API.

## 2:40–3:00 · Close

**On screen:** one slide with the numbers and the links.

> We scored the audit against frames we labelled by hand: it holds back two in three wrong frames
> while wrongly holding back one right frame in forty. A whole screenplay, storyboard and comic,
> costs about twenty cents. Panelwise: every panel traced to the script. Try it at
> panelwise.vercel.app.

**Slide text:**
- 38 of 57 wrong frames held back · 1 of 40 right frames held back (109 frames labelled by hand)
- 97% of shots accepted at the first drawing (two held-out scripts)
- About $0.20 a screenplay, storyboard and comic
- panelwise.vercel.app · the GitHub repo link

---

## Before recording

- The judge account shows the-red-kite with its storyboard and comic (done 2026-10-20).
- #231 is deployed, so Export PDF saves as "the-red-kite storyboard.pdf" (before it, the file is a hash).
- Frame 1.1's warning is still there (it is, from that run). If the hosted run is redone, re-check
  every line above against the new frames before recording: say only what is on screen.
- Only self-written or public-domain scripts on screen (DEMO.md; the-red-kite is self-written).
- The numbers on the slide match `docs/submission/about.md` and `eval/measurements/t124/`.
- Upload the video to YouTube as **public**, then put the link in `event.toml [links] video`.
