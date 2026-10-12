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

### L016 · A pronoun's action goes to whoever the prompt draws · open

- **Seen:** 2026-10-12, the-bread-van, second run ([run report](../eval/runs/2026-10-12-the-bread-van-2.md)). Accepted **5.3** draws
  THEO saluting: the script's "He salutes and goes." is DANIEL leaving, but the shot's characters
  are NOMSA and THEO, and the prompt keeps the sentence with its "He". Attempt 1 of **1.3** draws a
  round biscuit stuck to THEO's cheek: "Biscuit opens both." is the dog.
- **Cause:** the prompt replaces names with "a person" and keeps action sentences whole, so a
  sentence whose subject is a pronoun or an unintroduced name is read by klein as being about
  whoever is drawn. The audit can't see it: a salute is no object and no person.
- **Action:** none yet. To consider, measured free on the stored prompts: drop an action sentence
  whose subject is a pronoun or a name not in the shot's drawn cast. That needs a new resolver:
  T088's `_pronoun_evidence` only links a pronoun to a name opening the sentence before it, so
  it doesn't cover 5.3 (its "He" follows a line of dialogue), and "Biscuit opens both." has no
  pronoun at all.
- **Measured:** not yet.

### L015 · klein draws two panels in one frame · open

- **Seen:** 2026-10-12, while looking at every frame the L014 what-if would accept: the-bread-van
  (second run) 1.3 attempt 1, sipho-and-siphokazi 6.1 attempt 1 and lost-property 11.5 attempt 1
  are each two side-by-side panels, the shot's people split across them (11.5 with a different
  cast in each half).
- **Cause:** klein, on a "storyboard sketch" prompt, sometimes lays out a strip of panels. The
  describer lists the people of both halves as one frame, so nothing checks the layout.
- **Action:** none yet. A prompt change (fal money, ask first) or a describer question ("is this
  one picture or several panels?") that fails a split frame.
- **Measured:** not yet.

### L014 · Painted lettering and everyday objects hold back most shots · open

- **Seen:** 2026-10-12, measured free on the stored audits of five runs with today's code
  (`recheck`), then counting the shots that would have an accepted attempt if `unscripted_object`
  and `text_in_frame` only warned (people stay hard):

  | run | today's code | objects and lettering warn |
  |---|---|---|
  | the-bread-van, second run | 3 of 20 | 9 |
  | the-bread-van, first run | 2 of 19 | 5 |
  | lost-property (held out) | 9 of 49 | 33 |
  | sipho-and-siphokazi | 14 of 30 | 26 |
  | the-red-kite (T079 + T080) | 19 of 21 | 20 |

  On lost-property klein paints "LOST PROPERTY" as LOST POVERTY, LOST PORRY, LOST PPARERERY on
  almost every sign, and each fails `text_in_frame`.
- **Cause:** every word klein paints is checked against the script, and klein can't spell. Every
  unscripted everyday object (a bag, a pen in a hand, a plate) fails the frame too.
- **Action:** none yet. Every one of the **46** newly accepted drawings was looked at: **34
  right**, **12 wrong**, and every wrong one is wrong in its *people*, never in an object or a
  lettering: 7 girls drawn as boys (sipho-and-siphokazi 2.2, 2.4, 4B.1, 4B.3, 6.1 SIPHOKAZI;
  lost-property 11.1 AMAHLE, 3.2 PRIYA), two split panels (L015: lost-property 11.5, the-bread-van
  1.3), MR. DUBE drawn young (lost-property 12.2), THEO at a steering wheel holding Biscuit as a
  soft toy (the-bread-van 3.1), and a rowboat for Sipho's fishing boat (sipho 5.2). So L009 again:
  relaxing objects is safe only where people are checked. The stored extractions of the two older
  runs have no sex (they predate T088); T088 now finds SIPHOKAZI and AMAHLE, not PRIYA (L010).
- **Measured:** not yet live.

### L013 · The place's own things fail: bread in a bakery, a van's dashboard inside the van · fixed (T086, measured free)

- **Seen:** 2026-10-12, the-bread-van (a test script Claude wrote for pronouns, not held out),
  [run report](../eval/runs/2026-10-12-the-bread-van.md). In failures: `food · never set dressing` 26 (bread loaves, loaves of bread, dough in INT.
  NOMSA'S BAKERY), `vehicle · never set dressing` 14 (rearview mirror, dashboard, headrests, car
  seats in INT. VAN - MOVING), held objects 10 (`held, so not set dressing`: 4 a steering wheel as a
  vehicle, 6 others, a steering wheel and a broom).
- **Cause:** `verify/audit.py` never lets food or a vehicle be set dressing (`_NEVER_DRESSING`), and
  T083's `named_in_scene` reads only the scene's action text and the object's own noun. The
  heading's place (BAKERY, VAN) is never asked, and a driver holding the van's wheel is a held object
  like any other.
- **Action:** none yet. To consider, measured free with `recheck`: a scene whose location is itself
  a vehicle (VAN, CAR, BUS, TAXI, BOAT, TRAIN) treats that vehicle's parts as the place's structure;
  food a heading's place sells or makes stays a question for Tumo (T072 made food always scripted).
- **Measured:** live, 2026-10-12, the-bread-van second run ([run report](../eval/runs/2026-10-12-the-bread-van-2.md)): `food · never set dressing` 26 → 0 and `vehicle · never set dressing` 14 → 8 (left: a car in the street, seat belts, a door handle; `held, so not set dressing` 10 → 1, a baking tray). Food still fails as `not in the script` 13 times (a tray of buns, baskets of bread at the spaza shop, where the heading names no bakery).

### L012 · The judge puts a character's name on someone it can't check · partly fixed (T086; T087 next)

- **Seen:** 2026-10-12, the-bread-van, [run report](../eval/runs/2026-10-12-the-bread-van.md): **1 of 19 shots accepted.** `unscripted_person` failed 35
  attempts, "a child" 21 times, in shots that have THEO, aged 9. Of the judge's 24 matches to THEO, 17
  were a person described as no child (an adult seen from behind, an adult man, an adult woman), and
  in 13 of those a drawn child was left unmatched and failed as a stranger. Counted the same way on
  every stored run with a child character: at most 1 such match a run on the eight runs since T074
  (0 on six, 1 on two; the-red-kite and lost-property). Two more attempts (4.2, 4.3) were `ERROR`: the judge didn't call each
  described person once. And DANIEL (40s) was drawn and matched as "an old man" (3.2, 3.3).
- **Cause:** klein drew Theo in a t-shirt, not his look "in pyjamas and a school jersey". The judge
  is told (T080) that a person whose look plainly contradicts a character's is not that character,
  so it moved the name to a person whose look it can't see, and code never checks that the matched
  person's age fits the introduction's.
- **Action:** none yet. To consider, measured free with `recheck`: a code age check (a character
  introduced under 13 matched to a person described as an adult, old or a teenager fails as that
  character; one introduced as an adult matched to "a child" too; "old" for a character under 50);
  and whether clothing of the moment ("in pyjamas") should be a reason to refuse a match at all.
- **Measured:** live, 2026-10-12, the-bread-van second run ([run report](../eval/runs/2026-10-12-the-bread-van-2.md)): of the judge's 19 matches to THEO, **0** went to a person described as no child (17 of 24 on the first run), and DANIEL drawn "an old man" now fails on his age (T086). But the judge now leaves the drawn boy unmatched instead: "a child" fails `unscripted_person` 17 times, and AUNTIE BETTY (4.1 attempt 3) and NOMSA (5.2 attempt 3) were left unmatched as "an old woman" and "an adult woman" in attempts whose only hard failure that was. **3 of 20 accepted** (1 of 19 on the first run). T087 next.

### L011 · A stranger excused by a line of dialogue · fixed (measured free)

- **Seen:** 2026-10-12, lost-property (held out: no fix was designed on it), [run report](../eval/runs/2026-10-12-lost-property.md). Of 12
  accepted shots, three show a person the shot doesn't have, and the audit's hard
  `unscripted_person` passed each one:
  - **7.4:** the prompt draws one figure, Officer Moloi. The frame has three people: an old man
    (matched to Moloi), "an adult man seen from behind, walking away" (matched to TEBOGO, a character
    of the shot whom the prompt didn't draw), and "a small distant adult figure", supported by
    "Somebody might have." (dialogue).
  - **10.3:** "an adult bent forward at the waist in the far background", supported by "Sorry, my
    friend. He's already got a home." (dialogue).
  - **10.2:** "an adult standing small in the distance" and "a child, tiny and partly visible",
    both supported by "A pigeon glares at him." ("him" is Koos).
- **Cause:** a person's support is checked to be a verbatim quote of the shot's text. That text
  includes the shot's dialogue. T072 refuses a support that **names** a shot character, but "him"
  names no one. A line someone says puts nobody on screen, as verify.md §3 already says for things
  (`named_in_scene` reads only action text). In 7.4, matching a figure to TEBOGO is what the design
  allows (he is in `shot.characters`, addressed in the dialogue), though the prompt drew only
  Moloi.
- **Action:** T084 (verify.md §3): an unmatched person's support must be found in the shot's own
  action text, and must have no `he`, `him` or `she`. Whether a character the prompt didn't draw may
  be matched (7.4's TEBOGO) is still a separate question.
- **Measured:** free, `recheck` on every stored audit with T084's code. lost-property 12 → 9 shots
  with an accepted attempt: 7.4, 10.2 and 10.3 now fail `unscripted_person`. **Not designed on:**
  sipho-and-siphokazi (2026-10-11) 12 → 11 (9.3, an old woman for Siphokazi excused by "He takes the
  tide book from her"; 6.1, a man excused by another shot's quote), the-red-kite runs 35 → 33, 16 → 15
  and 10 → 9 (strangers excused by "my girl", "Is that my good shirt you are flying?" and "He
  switches off the soldering iron."), every other project unchanged. Every newly failed attempt was
  read; none is a person the shot's action introduces. Still to see: a new drawing run on the
  held-out script.

### L010 · T082 finds a sex for a third of the characters on a script it wasn't designed on · improved (T088)

- **Seen:** 2026-10-12, lost-property (held out), [run report](../eval/runs/2026-10-12-lost-property.md). Scored free on the run's own stored
  extraction against `eval/sex-labels.json`: **WRONG 0, INVENTED 0**, RIGHT 6 (Zanele, Mr. Dube,
  Grace, and Officer Van Wyk, Sam and the Announcer, whom the script never sexes; Marmalade, the
  cat, isn't labelled), **MISS 6** (Priya, Koos, Tebogo, Amahle, Officer
  Moloi, the sleeping commuter). So 3 of the 9 characters whose sex the script states got it.
  Two misses reached the board: **4.1** draws Priya as a young man (the describer: "a teenager
  with dark hair") and **6.2** draws Amahle (8) as a boy ("child, a young boy"), and both were
  accepted. The describer wrote "a teenager" and "a young boy"; with no
  `sex (from the script)` line, the judge matched them to the girls.
- **Cause:** T082 fails closed on purpose (storyboard.md §6, grounding.md §3): "she"/"he" count
  only in the introducing sentence, "her"/"his" only inside the introduction's own look, and
  `sex_word` is a noun (woman, fisherman…), never a pronoun. Here the sex sits outside all three:
  "She spots the hand-painted sign" (Priya, shot 3.3, after her introducing sentence in 3.1), "He
  wears headphones" (Koos, the sentence after his), and only "his"/"her" outside a look for Tebogo
  ("at his feet"), Amahle ("her mother's scrubs"), Moloi ("(closing his notebook)") and the
  sleeping commuter ("under his newspaper"). None of them has a sex noun or a title.
- **Action:** none yet. The six misses are the held-out test set, so no fix is tuned to them: a
  fix is designed on the samples' own patterns and scored here again, separately. The rule that
  WRONG and INVENTED stay at 0 holds.
- **Measured:** T088 (2026-10-12, #149 design, #150 code), Token Factory, three extractions of each
  sample: **WRONG 0, INVENTED 0** in all twelve; lost-property 6 → 7 of 12 a run, the-bread-van 2 → 3 of
  4 (DANIEL), sipho-and-siphokazi every extracted person (SIPHO, SIPHOKAZI). The model's `sex_word` was
  right for every person; only the quotes it gave were bad, so it is now a claim the script's own
  subject pronouns must support. Still missed: PRIYA, TEBOGO and KOOS (no claim, or "She" only after
  her speeches), MOLOI (a parenthetical), THEO, the sleeping commuter. Held-out script next.
  Live, 2026-10-12, the-bread-van second run: NOMSA, DANIEL and AUNTIE BETTY right, 0 wrong, **3 of 5** found: THEO missed again, and TAXI
  DRIVER (labelled now: "leans on his taxi", a possessive outside a look).
- **Before T088:** this is the held-out baseline: 3 of 9 found, 0 wrong. Also 2026-10-12, the-bread-van
  (Claude's test script, every sex stated the conventional way; [run report](../eval/runs/2026-10-12-the-bread-van.md)): Nomsa (her look) and Auntie
  Betty (the title) right, **Theo and Daniel missed** ("sleeps across his feet", "He stretches"), 0
  wrong. T085's code-only design was stopped on review: surface rules can't tell whose "his" or "her"
  it is ("Siphokazi takes his hand", "Sipho turns to her"). The Token Factory
  measurement on the three samples (several extractions each) is still to run.

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
- **Measured:** T083's first version on the stored audits (`recheck --target storyboard`):
  sipho-and-siphokazi 7 → 13 of 30 shots with an accepted attempt, the-red-kite 16 → 19 of 21; of
  the 10 flipped attempts looked at as drawings, 7 correct (the-red-kite 2.1, 2.2, 3.1, 4.4; sipho
  4A.1, 7.1, 9.2) and 3 wrong, all the wrong sex (sipho 4B.1, 5.1, 8.2). After the code review's
  stricter matching (a part is named by its whole only), sipho is 7 → 12: 4B.1's "steering
  wheel" is no longer excused, so that wrong frame stays withheld; 5.1 and 8.2 still pass.

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
- **Action:** T083 (Tumo's call, 2026-10-11): an everyday thing nobody holds and the script
  doesn't mention (other, nature, furniture, sign) warns as `background_object` instead of
  withholding. (docs/HANDOFF.md §6 step 3: a judge wording that called everyday things set
  dressing gained nothing and let a wrong person through; this is a code rule instead.)
- **Measured:** with T083, sipho-and-siphokazi 7 → 12 of 30 and the-red-kite 16 → 19 of 21 shots
  with an accepted attempt (`recheck`, stored audits); see L009 for the wrong-sex frames it let
  through, and L003.

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
- **Measured:** `recheck` on the stored audits: sipho-and-siphokazi 7 → 12 of 30 shots, the-red-kite
  16 → 19 of 21. 2 of the 9 newly accepted attempts are wrong-sex frames (L009), so T083 goes
  live after T082. Held out (earlier the-red-kite runs, stored verdicts from older code): 12 → 18
  and 15 → 16. Not yet on a script T083 wasn't designed from (held out).

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
