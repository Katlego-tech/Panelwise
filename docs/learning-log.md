# Learning log

What our live runs taught us, one lesson per entry, newest first. Every entry has the numbers it
was seen with, its cause in the code, what we did, and what that measured before and after. Read
it before changing the prompt or the audit; add to it after every live run.

- **How:** run the report (`python -m app.verify.report <project-id>`, free) and save it under
  [eval/runs/](../eval/runs/README.md). Then read its Causes, Characters and Shots and write or
  update entries here.
- **Measure fixes on stored drawings first.** The same prompt and seed give the same drawing, so
  `python -m app.verify.reaudit` tests an audit change with no new drawings: Token Factory calls
  only, two per drawing. Only a prompt or renderer change needs new drawings, and that costs fal
  money (ask first).
- **Format** ([docs/design/learning.md](design/learning.md) §6): `### L<nnn> · <name> · <open |
  fixed | won't fix>`, then Seen, Cause, Action, Measured.

---

### L009 · Object failures were catching wrong people by accident · open

- **Seen:** 2026-10-11, measuring T083 with `recheck` on the stored audits of
  [sipho-and-siphokazi](../eval/runs/2026-10-11-sipho-and-siphokazi.md). Of the attempts T083
  turns from fail to accepted, three show Siphokazi wrong: 4B.1 attempt 3 and 8.2 attempt 1 as a
  boy, 5.1 attempt 3 as a grown man hauling the rope she grabs in the script. Their scripted things
  (4B.1's compass, radio, taped photograph and wheel) or everyday background used to fail as
  objects, and that alone kept the wrong person off the board.
- **Cause:** with no sex in the prompt or the spec (L002), the judge can't refuse a girl drawn as
  a boy; a strict object check withheld such frames for an unrelated reason.
- **Action:** T083 waits for T082 before it goes live (merge order T082, then T083), so a wrong
  sex is refused for its own reason. Lesson: when a strict check is relaxed, look at every frame
  it lets through, not only the count.
- **Measured:** T083 on the stored audits (`recheck --target storyboard`): sipho-and-siphokazi 7 →
  13 of 30 shots with an accepted attempt, the-red-kite 16 → 19 of 21; of the 10 flipped attempts
  looked at as drawings, 7 correct (the-red-kite 2.1, 2.2, 3.1, 4.4; sipho 4A.1, 7.1, 9.2) and 3
  wrong, all the wrong sex (sipho 4B.1, 5.1, 8.2).

### L008 · The word budget drops what the characters do · open

- **Seen:** 2026-10-11, sipho-and-siphokazi,
  [run report](../eval/runs/2026-10-11-sipho-and-siphokazi.md). Shot 2.1's prompt keeps the
  setting ("A tin-roofed shack… Buckets of sardines on ice. A calendar… curls on the wall.") and
  the two ages, but not the line that says what they do ("SIPHOKAZI (17)… counts coins onto the
  counter. MAMA THEMBI (60s)… watches her…").
- **Cause:** `build_frame_prompt`'s 55-word budget (`storyboard/prompt.py` `_fit`) keeps the
  action parts in order and cuts from the end, so a shot whose text opens with setting loses its
  people's actions first.
- **Action:** none yet. To consider: rank a sentence that names a visible character before one
  that doesn't when cutting.
- **Measured:** not yet.

### L007 · The audit is the expensive part of a run · open

- **Seen:** 2026-10-11, the-red-kite and sipho-and-siphokazi,
  [run report](../eval/runs/2026-10-11-the-red-kite.md) and
  [run report](../eval/runs/2026-10-11-sipho-and-siphokazi.md). the-red-kite: 38 audits, 143,679
  prompt and 80,697 completion tokens. sipho-and-siphokazi: 82 audits, 295,459 prompt and 190,974
  completion tokens, about 2,300 completion tokens an audit.
- **Cause:** two Token Factory calls an audit (the describer, then the judge), and up to 3
  drawings a shot.
- **Action:** none yet. Size the hosted demo's `LLM_MONTHLY_TOKEN_CAP` (T030) from these numbers:
  a 30-shot script at 3 attempts can use about 500,000 tokens.
- **Measured:** not yet.

### L006 · A storm doesn't support lightning · open

- **Seen:** 2026-10-11, the-red-kite and sipho-and-siphokazi,
  [run report](../eval/runs/2026-10-11-the-red-kite.md) and
  [run report](../eval/runs/2026-10-11-sipho-and-siphokazi.md). the-red-kite 3.2 withheld for
  "lightning bolts" in a storm; sipho-and-siphokazi's `nature · unscripted` (23 failures) includes
  "lightning bolt" and "storm clouds".
- **Cause:** the judge reads weather as an event (T072) but not what the event shows.
- **Action:** none yet (docs/HANDOFF.md §6 step 6).
- **Measured:** not yet.

### L005 · Everyday things of a place fail as unscripted · open

- **Seen:** 2026-10-11, sipho-and-siphokazi and the-red-kite,
  [run report](../eval/runs/2026-10-11-sipho-and-siphokazi.md) and
  [run report](../eval/runs/2026-10-11-the-red-kite.md). sipho-and-siphokazi, in failures:
  `other · unscripted` 36 (pen, rope, life ring, wristwatch), `nature · unscripted` 23 (grass,
  moon, rocks), `food · never set dressing` 8 (apples, a basket of food, a bowl of fruit).
  the-red-kite: 3 of its 5 withheld frames (a picture frame, a toaster, a mug).
- **Cause:** the judge calls a thing set dressing only when the heading's location would hold it,
  and code never lets food, vehicles, animals or weapons be set dressing
  (`verify/audit.py` `_NEVER_DRESSING`).
- **Action:** none yet (docs/HANDOFF.md §6 step 3: a wording that called everyday things set
  dressing gained nothing and let a wrong person through, verify.md §8). Measure any idea on the
  stored drawings first.
- **Measured:** not yet.

### L004 · Painted text the script didn't write · open

- **Seen:** 2026-10-11, sipho-and-siphokazi,
  [run report](../eval/runs/2026-10-11-sipho-and-siphokazi.md): `text_in_frame` failed 42 attempts and withheld 12
  shots in the end: boat names, shop signs ("MILK", "Café"), numbers ("7.5.82", "9:15").
  `signature` warned on 55 attempts.
- **Cause:** klein letters signs and hulls on its own; only legible words the script didn't
  write fail (T071).
- **Action:** none yet.
- **Measured:** not yet.

### L003 · Parts of things the shot's text names fail · open

- **Seen:** 2026-10-11, sipho-and-siphokazi: `vehicle · never set dressing` 31 failures (boats,
  boat masts, a dashboard). Shot 1.1's text is "a single row of forty-year-old wooden
  fishing-boats", and its frame's "fishing boats" passed while its "boat masts" failed.
- **Cause:** `verify/audit.py` `part_of_prop` (T078) counts a part only of an extracted prop of
  the shot, and never of a vehicle, animal, weapon or food. The judge called the masts set
  dressing, which a vehicle never is.
- **Action:** T083: an animal, vehicle, weapon or food the scene's action text names is scripted
  (its own noun, or a part's whole: `boat masts`); everyday unheld background objects warn
  (Tumo's call). The rule over all categories was measured first and rejected: it excused
  "small pills", "power lines" (the script's washing lines) and "tripod stand".
- **Measured:** `recheck` on the stored audits: sipho-and-siphokazi 7 → 13 of 30 shots, the-red-kite
  16 → 19 of 21. 3 of the 10 newly accepted attempts are wrong-sex frames (L009), so T083 goes
  live after T082. Not yet on a script T083 wasn't designed from (held out).

### L002 · No sex from the script: wrong people drawn, and one accepted · open

- **Seen:** 2026-10-11, sipho-and-siphokazi: 7 of 30 accepted. The report's Characters table
  gives no sex for any of the five characters. `unscripted_person` failed 28 attempts: "an old
  man" 10, "a teenager" 8, "an adult man" 6. **8.3 was accepted (warn) with an old woman and a
  boy** where the script has Sipho (50s) taking the tide book from Siphokazi (17).
- **Cause:** `storyboard/prompt.py` `introduced_sex` (T079) reads only "she"/"he" in the
  introducing sentence and "her"/"his" in its look. Here: `SIPHOKAZI (17), in a school jersey…
  MAMA THEMBI (60s), the shop's owner, watches her…` (no pronoun of their own), and `a
  salt-and-pepper-bearded fisherman… This is SIPHO (50s).` (the noun is in the sentence before).
  With no sex, the judge (T080) can't refuse a wrong one, so 8.3 passed. Also seen: that
  introduction reaches the prompt as "This is a person (50s)".
- **Action:** T082 (planned; Tumo chose, 2026-10-11): code rules for a title (MAMA, MR, MRS…) and
  a sex noun in the introduction (fisherman, woman, girl…), plus a grounded extraction field
  whose quote code checks.
- **Measured:** not yet. Re-extract (Token Factory) and re-audit the stored drawings, then one new
  run (about $0.40 on fal, ask first).

### L001 · Lerato drawn as a boy · fixed

- **Seen:** 2026-10-11, the-red-kite before T079: klein drew Lerato as a short-haired boy in 9 of
  11 accepted frames (storyboard.md §8), and 1.3 was an empty roof.
- **Cause:** the prompt gave her age (T074) but no sex or look.
- **Action:** T079 (#127, #128): the sex from the introduction's pronouns and the look verbatim;
  T080 (#129, #130): the judge refuses a wrong sex or look, and a frame with none of the drawn
  people fails.
- **Measured:** after, 2026-10-11 ([run report](../eval/runs/2026-10-11-the-red-kite.md)): 16 of
  21 accepted (15 of 22 before), Lerato a girl with braids in every frame looked at, 1.3 shows
  her.
