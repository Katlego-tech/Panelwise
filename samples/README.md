# `samples`

Sample screenplays. Public-domain or self-written scripts only; never a copyrighted script, not
even an excerpt.

Each sample is a source file in a small subset of [Fountain](https://fountain.io)
(`<name>.fountain`) and the PDF built from it (`<name>.pdf`): US-letter, 12 pt Courier, standard
screenplay columns, 54 lines a page, a title page, page numbers, and (MORE)/(CONT'D) where a speech
runs over a page. Rebuild the PDFs after editing a source:

```bash
cd services/api && uv run python -m tools.build_samples
```

It prints what the real parser (`app.script.parse_pdf`) reads back. The gate's
`tests/samples/test_samples.py` checks that each committed PDF is a fresh build of its source and
that the table below matches what the parser reads.

## The samples

All three are original, written for this repository by Katlego (via Claude) on 2026-09-30, and
licensed under Apache-2.0 like the rest of the repo ([LICENSE](../LICENSE)). Place names
(Park Station, Pretoria, Mngazana, Hole in the Wall) are real places; every character and event is
invented.

| Sample | Shape | Pages | Scenes | Speaking characters |
| --- | --- | --- | --- | --- |
| [`the-red-kite`](the-red-kite.fountain) | Demo script: a girl, her grandfather and a kite | 5 | 5 | 3 |
| [`lost-property`](lost-property.fountain) | Larger cast, for recall: one night in a station's lost-property office | 10 | 12 | 11 |
| [`sipho-and-siphokazi`](sipho-and-siphokazi.fountain) | Deliberately awkward formatting | 6 | 10 | 4 |

Pages include the title page. Scenes and speaking characters are what `parse_pdf` reads, which is
not always what the source says: see [Parser findings](#parser-findings).

### `the-red-kite` — the demo script

Four script pages. LERATO (10) flies a red kite from a tin roof; her grandfather MOKGOSI mends
radios in his workshop below. The string snaps in a storm, and she finds the kite at night on a
streetlight. Clear, drawable props (the red kite with yellow ribbons, a spool of blue string, a
soldering iron, a torch, a black umbrella), a day-to-night change, and one of everything the
pipeline has to handle:

- `INT.` and `EXT.` headings, times `DAY`, `CONTINUOUS`, `LATER`, `NIGHT`;
- parentheticals, `(O.S.)` and `(V.O.)` cues (the V.O. is a radio announcer, heard, never seen);
- a speech split across PDF pages 4 and 5 (printed 3. and 4.) with (MORE) / `LERATO (CONT'D)`;
- `FADE IN:` / `FADE OUT.`, scene numbers at both edges of each heading.

### `lost-property` — the larger cast

Nine script pages, twelve scenes, eleven speaking characters (ZANELE, MR. DUBE, PRIYA, KOOS, TEBOGO,
OFFICER MOLOI, OFFICER VAN WYK, GRACE, AMAHLE, SAM and a station ANNOUNCER heard in V.O.), plus
characters who never speak: a ginger cat called Marmalade, a sleeping commuter, a pigeon. A
student's lost violin, a toy giraffe called Gerald and an unclaimed cake turn up over one rainy
night, ending at dawn. No scene numbers. Characters are introduced in capitals with an age, two
cues share the word OFFICER, and several characters are referred to in action before
they speak, which is what a recall measurement (T032) needs.

### `sipho-and-siphokazi` — the tricky one

A fisherman, SIPHO, and his niece, SIPHOKAZI, sheltering from a storm with her grandmother's tide
book. Built to find the parser's edges:

- two cues where one name is a prefix of the other (SIPHO / SIPHOKAZI), and a nickname (Kazi) used
  only in dialogue;
- hyphenated compounds that break at the hyphen at the end of a line, in action (`sea-` / `green`)
  and in dialogue (`south-` / `westerly`);
- six scenes with no dialogue at all;
- an `INT./EXT.` heading, a heading with two dashes (`INT. SIPHO'S HOUSE - KITCHEN - NIGHT`), a
  heading with no time (`INT. BAIT SHOP`), `--` as the time separator, scene numbers `4A` / `4B`;
- `(CONTINUED)` / `CONTINUED:` page furniture, two parentheticals that wrap (three and four lines), a
  shouted all-caps line of dialogue (`NO! THE ROPE!`), a cue typed with `(CONT'D)`, and
  `SMASH CUT TO:`, `MATCH CUT TO:`, `CUT TO BLACK.`

## Parser findings

Found by these samples on 2026-09-30 and not fixed here (lane `script+grounding` owns the parser):

1. **`INT./EXT.` headings are not recognised.** `SCENE_HEADING_RE` accepts `INT/EXT` and
   `INT/EXT.` but not `INT./EXT.`, the form most screenwriting software writes. Scene 3 of
   `sipho-and-siphokazi` is read as an action line inside scene 2, so the parser counts 10 scenes
   where the source has 11.
2. **A blank line between two action paragraphs is sometimes lost.** pdfplumber's layout text
   uses `y_density=13` points a row; a screenplay's lines are 12 points apart, so a one-line gap
   sometimes rounds away and two paragraphs parse as one `Action`. Spans stay exact; only the
   paragraph boundary is lost. Counts: 2 of 21 paragraph breaks in `the-red-kite`, 6 of 50 in
   `lost-property`, 5 of 31 in `sipho-and-siphokazi`. With `y_density=12` every boundary survives
   in all three samples.
3. **A heading with two dashes splits at the first.** `INT. SIPHO'S HOUSE - KITCHEN - NIGHT` gives
   location `SIPHO'S HOUSE` and time `KITCHEN - NIGHT`, which `resolve_times` does not recognise, so
   the scene borrows the previous scene's clock. Here that is also `NIGHT`, by luck.
4. **A parenthetical that wraps is read as dialogue** (already an open question in
   [docs/design/script.md](../docs/design/script.md) §10). Two such speeches in
   `sipho-and-siphokazi` have `parenthetical=None` and the parenthetical's words at the start of
   their text.
5. **A line-break hyphen stays in the element text** (`sea- green`, `south- westerly`). Grounding
   already joins it when it locates a quote (`app/grounding/text.py`); comic lettering (T023) will
   need to join it too before a bubble shows it.

Handled correctly: (MORE) / (CONT'D) splits, `(CONTINUED)` / `CONTINUED:`, page numbers,
transitions, `4A` scene numbers, a heading with no time (`None`, not an invented `DAY`), `--` as
the separator, the shouted all-caps dialogue line, and SIPHO / SIPHOKAZI kept apart as cues.

## Live run — `the-red-kite` on the real account (2026-09-30)

Nemotron 3.5 Lightning on Token Factory (`nvidia/Nemotron-3_5-Lightning`, thinking off), one
extraction chunk, a few thousand tokens in all.

| Check | Command | Result |
| --- | --- | --- |
| Shots | `uv run python -m app.shots.run ../../samples/the-red-kite.pdf` | 19 shots over 5 scenes; **every element in exactly one shot: yes**; 0 ranges repaired; 0 character and 4 prop names dropped as not in their scene. Planning 4,244 in / 1,377 out, extraction 1,389 in / 749 out, 0 reasoning tokens |
| Grounding, run 1 | `uv run python -m app.grounding.run ../../samples/the-red-kite.pdf` | faithfulness **0.625** (5/8 entities, 11/26 quotes located); recall **0.000** (0/3 speakers) |
| Grounding, run 2 | same | faithfulness **0.143** (1/7 entities, 8/30 quotes located); recall **0.000** (0/3 speakers) |

Every character still reaches the shot plan (the cue fallback adds LERATO, MOKGOSI and RADIO
ANNOUNCER from their cues), and nothing ungrounded is kept. But the numbers are far below the
Phase 1 sample's 1.000 / 1.000, and the cause is visible in the raw model output: **Lightning
starts almost every dialogue quote with the speaker's cue line** (`"LERATO\nI promise."`,
`"MOKGOSI (smiling)\nAnd we watch the sky."`). The cue is not inside the dialogue element's span,
so `locate` rejects the whole quote, and a character quoted only through dialogue is dropped from
the model's list. A few quotes also stitch a heading or a second paragraph onto an action line. For
lane `script+grounding` (T032 will measure it): either tell the model to leave the cue out, or let
`locate` accept a leading cue line that matches the element's own cue.
