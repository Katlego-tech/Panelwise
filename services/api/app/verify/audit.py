"""The frame audit: describe blind, judge against the shot, check in code. docs/design/verify.md §4.

New in Panelwise: FrameFlow had no image audit. What the judge says is only trusted as far as
code can check it; "supported by the script" needs a verbatim quote, found the way the grounding
filter finds one (verify.md §8). A failed call is an ERROR audit, never a pass.
"""

import asyncio
import base64
import hashlib
import logging
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace

from pydantic import ValidationError

from app.characters.labels import animals
from app.characters.sex import Sex
from app.grounding import EntityKind, Extraction, normalize_for_grounding
from app.llm import ChatResult, LLMError, NebiusChatModel, Tier, Usage, structured_chat
from app.script import Action, IntExt, Scene, Screenplay, match_speaker
from app.shots import Framing, Shot
from app.verify.model import (
    Audit,
    Check,
    CheckResult,
    Light,
    ObjectCategory,
    ObjectKind,
    PersonFound,
    PersonSeen,
    Position,
    RenderedFrame,
    Setting,
    Severity,
    ShotSize,
    Verdict,
)
from app.verify.prompts import (  # T099: the judge's own character lines, on purpose
    DESCRIBE_PROMPT,
    JUDGE_PROMPT,
    _quoted,  # pyright: ignore[reportPrivateUsage]
    _sexed,  # pyright: ignore[reportPrivateUsage]
    render_spec,
)
from app.verify.schema import FrameDescription, Judgement, PersonCheck, Presence

logger = logging.getLogger(__name__)

_SEVERITY = {
    Check.UNSCRIPTED_PERSON: Severity.HARD,
    # Since T089 only an animal or a weapon (`_filed`): a story choice the script must make.
    Check.UNSCRIPTED_OBJECT: Severity.HARD,
    # Painted words the script never wrote: named on the card, never withheld (T089).
    Check.TEXT_IN_FRAME: Severity.SOFT,
    Check.SETTING: Severity.HARD,
    Check.MISSING_CHARACTER: Severity.SOFT,
    Check.LIGHT: Severity.SOFT,
    Check.FRAMING: Severity.SOFT,
    # An artist's mark is no character, prop, line or event: shown, never withheld (T077).
    Check.SIGNATURE: Severity.SOFT,
    # None of the people the prompt drew is in the frame: it isn't this shot (T080).
    Check.NO_CHARACTER: Severity.HARD,
    # An everyday thing of the place the script didn't mention, nobody holding it (T083); since
    # T089 any object the script didn't put there that is no animal or weapon.
    Check.BACKGROUND_OBJECT: Severity.SOFT,
    # A character the script sexes drawn as the other sex, as the sex agent sees it (T095).
    Check.DRAWN_SEX: Severity.HARD,
}
# An unscripted animal or weapon is a story choice: it still withholds the frame (T089).
_STORY_OBJECTS: frozenset[ObjectCategory] = frozenset(
    {ObjectCategory.ANIMAL, ObjectCategory.WEAPON}
)


def _filed(category: ObjectCategory) -> Check:
    """Where an object's failure is filed (T089, pure): hard for an animal or a weapon, else the
    soft BACKGROUND_OBJECT with the same detail."""
    return Check.UNSCRIPTED_OBJECT if category in _STORY_OBJECTS else Check.BACKGROUND_OBJECT


# Things a location never "naturally holds": each is a story choice the script must make.
# A sign may be dressing (T071): its words are what could be unscripted, and TEXT_IN_FRAME
# checks them.
_NEVER_DRESSING = frozenset(
    {
        ObjectCategory.ANIMAL,
        ObjectCategory.VEHICLE,
        ObjectCategory.WEAPON,
        ObjectCategory.FOOD,
    }
)
# The place's everyday things: unmentioned and unheld, they warn rather than withhold (T083).
_BACKGROUND = frozenset(
    {
        ObjectCategory.OTHER,
        ObjectCategory.NATURE,
        ObjectCategory.FURNITURE,
        ObjectCategory.SCREEN_OR_SIGN,
    }
)
# A described person's age, from the describer's own words (T086), the earliest match wins: "a
# 10-year-old girl" is a child, "an older woman" old. Anything else gives no age and no check.
_DESCRIBED_AGES = (
    ("child", re.compile(r"\b(child|children|kids?|boys?|girls?|toddlers?|baby|babies|infant)\b")),
    ("teenager", re.compile(r"\b(teenagers?|teens?|teenage|adolescents?)\b")),
    (
        "old",
        re.compile(
            r"\bold (man|woman|person|adult)\b|\belderly\b"
            r"|\b(grandmother|grandfather|granny|grandma|grandpa)\b"
        ),
    ),
    (
        "adult",
        re.compile(
            r"\b(adults?|man|men|woman|women|mother|father|mum|mom|dad|lady|gentleman|guy)\b"
        ),
    ),
)
# Places that are themselves a vehicle (T086): inside one, its parts are the place's structure.
_VEHICLE_PLACES = frozenset(
    {
        "van",
        "car",
        "bus",
        "minibus",
        "kombi",
        "taxi",
        "cab",
        "truck",
        "lorry",
        "bakkie",
        "jeep",
        "ambulance",
        "train",
        "carriage",
        "tram",
        "coach",
        "boat",
        "ship",
        "ferry",
        "plane",
        "aeroplane",
        "airplane",
        "helicopter",
    }
)
# A vehicle's own parts (T086): the vehicle words of T083's part list, never an animal's,
# weapon's or food's ("barrel", "collar" and "crust" are parts, but not of a van).
_VEHICLE_PART_WORDS = frozenset(
    {
        "wheel",
        "door",
        "window",
        "windscreen",
        "bonnet",
        "boot",
        "bumper",
        "tyre",
        "tire",
        "engine",
        "roof",
        "seat",
        "mirror",
        "light",
    }
)
# A vehicle's inside that the part words don't already name (T086).
_INTERIOR_WORDS = frozenset(
    {
        "dashboard",
        "steering",
        "headrest",
        "seatbelt",
        "gearstick",
        "gear",
        "speedometer",
        "windshield",
        "visor",
        "glovebox",
        "upholstery",
    }
)
# Words that never name a thing (T083): `box of fish` is named by `fish`, never by `of`.
_FUNCTION_WORDS = frozenset(
    {
        "of",
        "the",
        "and",
        "with",
        "in",
        "on",
        "a",
        "an",
        "for",
        "from",
        "to",
        "at",
        "by",
        "into",
        "onto",
        "over",
        "under",
        "its",
        "his",
        "her",
        "their",
    }
)
# A part of a thing (T083): `boat masts` is named by the boat the scene names.
_PART_WORDS = frozenset(
    {
        "mast",
        "sail",
        "hull",
        "deck",
        "cabin",
        "bow",
        "stern",
        "oar",
        "wheel",
        "door",
        "window",
        "windscreen",
        "bonnet",
        "boot",
        "bumper",
        "tyre",
        "tire",
        "engine",
        "roof",
        "seat",
        "mirror",
        "light",
        "tail",
        "wing",
        "fin",
        "head",
        "leg",
        "paw",
        "hoof",
        "horn",
        "mane",
        "ear",
        "collar",
        "lead",
        "handle",
        "blade",
        "barrel",
        "trigger",
        "hilt",
        "sheath",
        "crust",
        "rind",
        "peel",
        "skin",
        "bone",
        "slice",
    }
)
# Costume and the place's own structure: never a story choice when nobody holds it (T071).
_NEVER_UNSCRIPTED = frozenset({ObjectCategory.CLOTHING, ObjectCategory.ARCHITECTURE})
_NIGHT_TIMES = frozenset({"NIGHT", "MIDNIGHT", "EVENING"})
_DAY_TIMES = frozenset({"DAY", "MORNING", "AFTERNOON"})
_FRAMING_STEP = {
    Framing.WIDE: 0,
    Framing.MEDIUM: 1,
    Framing.OVER_SHOULDER: 1,
    Framing.POV: 1,
    Framing.CLOSE_UP: 2,
    Framing.INSERT: 2,
    Framing.EXTREME_CLOSE_UP: 3,
}
_SIZE_STEP = {ShotSize.WIDE: 0, ShotSize.MEDIUM: 1, ShotSize.CLOSE: 2, ShotSize.EXTREME_CLOSE: 3}


def seed_for(shot: Shot, attempt: int) -> int:
    key = f"{shot.scene_index}:{shot.number}:{attempt}".encode()
    return int.from_bytes(hashlib.sha256(key).digest()[:4], "big")


def _found(support: str | None, haystacks: Sequence[str]) -> bool:
    needle = normalize_for_grounding(support or "")
    return bool(needle) and any(needle in h for h in haystacks)


def _in_words(needle: str, haystacks: Sequence[str]) -> bool:
    """`needle`, normalised, appears in a haystack as whole words (T071): a stray letter inside
    another word isn't the script's."""
    words = normalize_for_grounding(needle)
    pattern = re.compile(rf"(?<!\w){re.escape(words)}(?!\w)")
    return bool(words) and any(pattern.search(h) for h in haystacks)


def _names_any(support: str | None, names: Sequence[str]) -> bool:
    """The support names one of `names` (T072): a quote about a character excuses no stranger."""
    return any(_in_words(name, [normalize_for_grounding(support or "")]) for name in names)


# A word that points back at someone already introduced, a character (T084). Possessives and
# reflexives usually belong to the sentence's own subject ("A WOMAN folds her umbrella").
_PERSON_PRONOUNS = frozenset({"he", "him", "she"})


def shot_action_text(shot: Shot, scene: Scene) -> str:
    """The text of the shot's covered Action elements, in order (T084): a stranger's support must
    be in it. A line someone says puts no one on screen."""
    return normalize_for_grounding(
        " ".join(
            element.text for i in shot.elements if isinstance(element := scene.elements[i], Action)
        )
    )


def _points_elsewhere(support: str | None) -> bool:
    """The support has `he`, `him` or `she` (T084): it is about someone already introduced."""
    return bool(_PERSON_PRONOUNS & set(re.findall(r"[a-z]+", (support or "").lower())))


def _named_prop(name: str, props: Sequence[frozenset[str]]) -> bool:
    """Every word of `name` is a word of one prop the extraction names (T072): `kite` against
    `RED KITE`. Such a thing is a story choice, never set dressing."""
    words = frozenset(normalize_for_grounding(name).split())
    return bool(words) and any(words <= prop for prop in props)


# Words that make a thing another copy of a prop rather than a part of it (T078).
_COPY_WORDS = frozenset(
    {"second", "another", "other", "extra", "spare", "two", "three", "more", "duplicate"}
)


def part_of_prop(
    name: str, category: ObjectCategory, shot: Shot, extraction: Extraction
) -> str | None:
    """The shot prop whose part `name` is (T078): the prop's head noun (its name's last word) is
    the name's second-to-last word, with no copy word, and never an animal, vehicle, weapon or
    food. `kite string` is part of `RED KITE`; `kite`, `blue kite`, `second kite` and
    `map of the town` are judged as before."""
    words = normalize_for_grounding(name).lower().split()
    if len(words) < 2 or _COPY_WORDS & set(words) or category in _NEVER_DRESSING:
        return None
    for prop in shot.props:
        quoted = any(
            e.kind is EntityKind.PROP and e.name == prop and e.quotes for e in extraction.entities
        )
        if quoted and normalize_for_grounding(prop).lower().split()[-1:] == words[-2:-1]:
            return prop
    return None


_SIBILANT = ("s", "x", "z", "ch", "sh")


def _forms(word: str) -> set[str]:
    """The word, its plural and, for a plural, its singular (T083): horse/horses, pony/ponies,
    box/boxes, boats/boat. `es` only after a sibilant, so no form is a stray word: `bees` is
    never "be", `car` never "cares". Irregular plurals (wolves) are not forms."""
    forms = {word, word + "s"}
    if word.endswith(_SIBILANT):
        forms.add(word + "es")
    if word.endswith("y"):
        forms.add(word[:-1] + "ies")
    if word.endswith("ies"):
        forms.add(word[:-3] + "y")
    elif word.endswith("es") and word[:-2].endswith(_SIBILANT):
        forms.add(word[:-2])
    elif word.endswith("s") and not word.endswith("ss"):
        forms.add(word[:-1])
    return forms


def named_in_scene(name: str, category: ObjectCategory, scene: Scene) -> str | None:
    """The word of the scene's action text that names this animal, vehicle, weapon or food
    (T083): its own noun (the name's last word) or, when that is a part word, its whole's
    (`boat masts` against "fishing-boats"), and then only its whole's. The name splits on
    spaces, so `off-road` stays one
    word; the scene's text on anything but letters. None for any other category, with a copy
    word, or for a word only in the heading or in dialogue."""
    if category not in _NEVER_DRESSING:
        return None
    words = [w.strip(".,;:!?'\"()") for w in name.lower().split()]
    if not words or _COPY_WORDS & set(words):
        return None
    # A part is named by its whole only: a `car door` by a car, never by the scene's doors.
    part = len(words) >= 2 and bool(_forms(words[-1]) & _PART_WORDS)
    candidates = [words[-2]] if part else [words[-1]]
    text = " ".join(e.text for e in scene.elements if isinstance(e, Action)).lower()
    scene_words = set(re.findall(r"[a-z]+", text))
    for candidate in candidates:
        if len(candidate) >= 3 and candidate not in _FUNCTION_WORDS:
            if found := sorted(_forms(candidate) & scene_words):
                return found[0]
    return None


def described_age(appearance: str) -> str | None:
    """The age class the describer gave a person (T086): child, teenager, old or adult; None when
    its words give none."""
    words = appearance.lower()
    # The earliest age word is this person's: "an old man looking toward the girl" is old.
    found = [(m.start(), age) for age, pattern in _DESCRIBED_AGES if (m := pattern.search(words))]
    return min(found)[1] if found else None


def age_contradicts(years: int, described: str | None) -> bool:
    """A described age that plainly isn't a character introduced at `years` (T086): under 13 not
    an adult or old; 13 to 19 not old; 20 to 49 not a child or old; 50 and over not a child or a
    teenager. No described age is no contradiction."""
    if years < 13:
        return described in ("adult", "old")
    if years < 20:
        return described == "old"
    if years < 50:
        return described in ("child", "old")
    return described in ("child", "teenager")


def inside_vehicle(scene: Scene) -> frozenset[str]:
    """The vehicle a non-EXT scene is inside (T086): the location's head noun, the last word of its
    first part, when it is a vehicle. INT. VAN - MOVING -> {"van"}, SIPHO'S BAKKIE -> {"bakkie"}; a
    place named after one is not inside it: BUS STATION, CAR PARK, TAXI RANK -> empty."""
    if scene.int_ext is IntExt.EXT:
        return frozenset()
    words = re.findall(r"[a-z]+", scene.location.split(" - ")[0].lower())
    return frozenset(words[-1:]) & _VEHICLE_PLACES


def part_of_vehicle(name: str, category: ObjectCategory, scene: Scene) -> bool:
    """A part of the vehicle the scene is inside (T086): inside INT. VAN a dashboard, a rearview
    mirror, a held steering wheel, the seats. Only part and interior words: a bare vehicle (a
    sailboat through the window, the van itself) is judged as before; never with a copy word."""
    words = [w.strip(".,;:!?'\"()") for w in name.lower().split()]
    if not inside_vehicle(scene) or not words or _COPY_WORDS & set(words):
        return False
    if category in (ObjectCategory.ANIMAL, ObjectCategory.WEAPON, ObjectCategory.FOOD):
        return False
    parts = _VEHICLE_PART_WORDS | _INTERIOR_WORDS
    return bool(_forms(words[-1]) & parts or set(words) & _INTERIOR_WORDS)


def shot_ages(
    shot: Shot, screenplay: Screenplay, years: Callable[[str, Screenplay], int | None]
) -> dict[str, int]:
    """Each shot character's introduced age in years (T086), for run_checks' `ages`. `years` is
    storyboard's introduced_years, passed in: app.storyboard imports app.verify."""
    return {c: y for c in shot.characters if (y := years(c, screenplay)) is not None}


def shot_sexes(
    shot: Shot,
    screenplay: Screenplay,
    extraction: Extraction,
    sex_of: Callable[[str, Screenplay, Extraction], tuple[Sex, str] | None],
) -> dict[str, str]:
    """Each person character's sex the script gives (T095), for run_checks' `sexes`. `sex_of` is
    storyboard's character_sex, passed in: app.storyboard imports app.verify."""
    beings = animals(extraction)
    return {
        c: found[0].value
        for c in shot.characters
        if c not in beings and (found := sex_of(c, screenplay, extraction)) is not None
    }


def matched_people(
    shot: Shot,
    description: FrameDescription,
    judgement: Judgement,
    extraction: Extraction,
    ages: Mapping[str, int] | None = None,
) -> dict[int, str]:
    """Described person -> the character run_checks accepts them as (T095): the judge's name as
    `match_speaker` resolves it among the shot's people, not refused for their age (T086), and the
    first person called for that name. Pure; the sex agent asks only about these."""
    beings = animals(extraction)
    people = tuple(c for c in shot.characters if c not in beings)
    out: dict[int, str] = {}
    for call in sorted(judgement.people, key=lambda c: c.person):
        if not call.character or not 0 <= call.person < len(description.people):
            continue
        name = match_speaker(call.character, people)
        if name is None or name in out.values():
            continue
        years = (ages or {}).get(name)
        appearance = description.people[call.person].appearance
        if years is not None and age_contradicts(years, described_age(appearance)):
            continue
        out[call.person] = name
    return out


def apply_ladder(audit: Audit, withholding: frozenset[Check] | None) -> Audit:
    """The rule ladder (T094): every hard check off `withholding` becomes soft in the audit, so a
    FAIL with no failed check left on the ladder is WARN, and a withheld frame names only a check
    that withheld it. None keeps the audit as it is (every hard check withholds)."""
    if withholding is None or audit.verdict is not Verdict.FAIL:
        return audit
    checks = tuple(
        replace(c, severity=Severity.SOFT)
        if c.severity is Severity.HARD and c.check not in withholding
        else c
        for c in audit.checks
    )
    hard = any(not c.ok and c.severity is Severity.HARD for c in checks)
    return replace(audit, checks=checks, verdict=Verdict.FAIL if hard else Verdict.WARN)


def _calls_each_once(indexes: Sequence[int], n: int) -> bool:
    return sorted(indexes) == list(range(n))


def run_checks(
    shot: Shot,
    scene: Scene,
    description: FrameDescription,
    judgement: Judgement,
    extraction: Extraction,
    *,
    on_screen: tuple[str, ...] = (),
    ages: Mapping[str, int] | None = None,
    seen: Sequence[PersonSeen] = (),
    sexes: Mapping[str, str] | None = None,
    found: Sequence[PersonFound] = (),
) -> tuple[tuple[CheckResult, ...], Verdict, dict[str, Position]]:
    if not (
        _calls_each_once([c.person for c in judgement.people], len(description.people))
        and _calls_each_once([c.object for c in judgement.objects], len(description.objects))
    ):
        return (), Verdict.ERROR, {}

    # An animal character is described as an object: people are matched to people only (T052).
    beings = animals(extraction)
    people = tuple(c for c in shot.characters if c not in beings)
    in_shot = {(EntityKind.CHARACTER, n) for n in shot.characters} | {
        (EntityKind.PROP, n) for n in shot.props
    }
    supports = [normalize_for_grounding(shot.source)] + [
        normalize_for_grounding(q.text)
        for e in extraction.entities
        if (e.kind, e.name) in in_shot
        for q in e.quotes
    ]
    action = [shot_action_text(shot, scene)]
    heading = [normalize_for_grounding(scene.heading)]
    props = [
        frozenset(normalize_for_grounding(e.name).split())
        for e in extraction.entities
        if e.kind is EntityKind.PROP
    ]
    failures: dict[Check, list[str]] = {check: [] for check in Check}

    positions: dict[str, Position] = {}
    for call in sorted(judgement.people, key=lambda c: c.person):
        person = description.people[call.person]
        who = f"person {call.person} ({person.position}, {person.appearance})"
        name = match_speaker(call.character, people) if call.character else None
        years = (ages or {}).get(name) if name is not None else None
        if years is not None and age_contradicts(years, age := described_age(person.appearance)):
            # T086: refused as that character, and never then excused as a stranger.
            failures[Check.UNSCRIPTED_PERSON].append(
                f"{who}: described as {age}, but {name} is introduced at {years}"
            )
        elif name is not None and name in positions:
            failures[Check.UNSCRIPTED_PERSON].append(f"{who}: {name} is already another person")
        elif name is not None:
            positions[name] = person.position
        elif not _found(call.support, supports):
            failures[Check.UNSCRIPTED_PERSON].append(f"{who}: no shot character, no support")
        elif _names_any(call.support, people):
            failures[Check.UNSCRIPTED_PERSON].append(f"{who}: its support is about a character")
        elif not _found(call.support, action):
            failures[Check.UNSCRIPTED_PERSON].append(f"{who}: its support is not an action line")
        elif _points_elsewhere(call.support):
            failures[Check.UNSCRIPTED_PERSON].append(f"{who}: its support points at someone else")

    # T095: a matched character the script sexes, drawn as the other sex.
    accepted = matched_people(shot, description, judgement, extraction, ages)
    for answer in seen:
        want = (sexes or {}).get(answer.character)
        if (
            want is not None
            and accepted.get(answer.person) == answer.character
            and answer.sex in ("male", "female")
            and answer.sex != want
        ):
            person = description.people[answer.person]
            failures[Check.DRAWN_SEX].append(
                f"person {answer.person} ({person.position}, {person.appearance}): drawn "
                f"{answer.sex}, but {answer.character} is {want}"
            )

    for call in sorted(judgement.objects, key=lambda c: c.object):
        obj = description.objects[call.object]
        what = f"object {call.object} ({obj.name}, {obj.category})"
        if obj.category in _NEVER_UNSCRIPTED and not obj.held:
            continue
        if part_of_prop(obj.name, obj.category, shot, extraction):
            continue  # T078: whatever the judge said; its support is the prop's quote
        if named_in_scene(obj.name, obj.category, scene):
            continue  # T083: the script put it in this scene, whatever the judge said
        if part_of_vehicle(obj.name, obj.category, scene):
            continue  # T086: inside the scene's vehicle, its parts are the place itself
        # T086: unheld food the scene doesn't name warns, as the place's everyday things do.
        background = (
            (obj.category in _BACKGROUND or obj.category is ObjectCategory.FOOD)
            and not obj.held
            and not _named_prop(obj.name, props)
        )
        food = background and obj.category is ObjectCategory.FOOD
        filed = _filed(obj.category)  # T089: where a would-be hard failure goes
        match call.kind:
            case ObjectKind.SET_DRESSING if food:  # T086: food is never quietly the place's
                failures[Check.BACKGROUND_OBJECT].append(f"{what}: not in the script")
            case ObjectKind.UNSCRIPTED if background:
                failures[Check.BACKGROUND_OBJECT].append(f"{what}: not in the script")
            case ObjectKind.UNSCRIPTED:
                failures[filed].append(f"{what}: unscripted")
            case ObjectKind.SCRIPTED_PROP if not _found(call.support, supports):
                failures[filed].append(f"{what}: prop without support")
            case ObjectKind.SET_DRESSING if obj.held:
                failures[filed].append(f"{what}: held, so not set dressing")
            case ObjectKind.SET_DRESSING if _named_prop(obj.name, props):
                failures[filed].append(f"{what}: the script names it")
            case ObjectKind.SET_DRESSING if obj.category in _NEVER_DRESSING and not background:
                failures[filed].append(f"{what}: never set dressing")
            case ObjectKind.SET_DRESSING if not _found(call.support, heading) and background:
                failures[Check.BACKGROUND_OBJECT].append(f"{what}: not in the script")
            case ObjectKind.SET_DRESSING if not _found(call.support, heading):
                failures[filed].append(f"{what}: not in the heading")
            case _:
                pass

    # Only legible words the script never wrote (T071): the shot's own text or the scene's place.
    # The heading's time of day isn't a haystack, so a painted "NIGHT" warns (T089: soft).
    words = [normalize_for_grounding(shot.source), normalize_for_grounding(scene.location)]
    if description.signature:  # T077: soft; any words read in it are still `text`, below
        failures[Check.SIGNATURE].append("a signature or artist's mark")
    failures[Check.TEXT_IN_FRAME] += [
        f"text {t!r} isn't the script's"
        for t in description.text
        if normalize_for_grounding(t) and not _in_words(t, words)  # "" is no text read
    ]

    contradicts = {IntExt.INT: Setting.EXTERIOR, IntExt.EXT: Setting.INTERIOR}
    if contradicts.get(scene.int_ext) == description.setting:
        failures[Check.SETTING].append(f"{description.setting} in a {scene.int_ext} scene")

    failures[Check.MISSING_CHARACTER] += [
        f"{name} not seen" for name in people if name not in positions
    ]
    # T080; T099: or one the presence agent found the judge left unmatched.
    present = present_characters(on_screen, found, accepted, description, ages)
    if on_screen and not any(name in positions or name in present for name in on_screen):
        failures[Check.NO_CHARACTER].append(f"none of {', '.join(on_screen)} in frame")

    time = (shot.time_of_day or "").upper()
    if (description.light is Light.DAY and time in _NIGHT_TIMES) or (
        description.light is Light.NIGHT and time in _DAY_TIMES
    ):
        failures[Check.LIGHT].append(f"{description.light} light at {time}")

    size = _SIZE_STEP.get(description.shot_size)
    if size is not None and abs(size - _FRAMING_STEP[shot.framing]) >= 2:
        failures[Check.FRAMING].append(f"{description.shot_size} for a {shot.framing} shot")

    checks = tuple(
        CheckResult(check, _SEVERITY[check], not failed, "; ".join(failed))
        for check, failed in failures.items()
    )
    if any(not c.ok and c.severity is Severity.HARD for c in checks):
        verdict = Verdict.FAIL
    elif any(not c.ok for c in checks):
        verdict = Verdict.WARN
    else:
        verdict = Verdict.PASS
    return checks, verdict, positions


async def describe_frame(model: NebiusChatModel, png: bytes) -> tuple[FrameDescription, ChatResult]:
    image = f"data:image/png;base64,{base64.b64encode(png).decode()}"
    messages = [
        {"role": "system", "content": DESCRIBE_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this image."},
                {"type": "image_url", "image_url": {"url": image}},
            ],
        },
    ]
    result = await structured_chat(model, messages, FrameDescription, Tier.VISION, max_tokens=4096)
    return result.value, result.chat


SEX_AGENT_PROMPT = (
    "You look at one person in a storyboard drawing and say how that person is drawn, from the "
    "drawing alone: male, female, or unclear when the drawing doesn't show it. Answer only about "
    "the person described; ignore everyone else."
)


async def check_person(
    model: NebiusChatModel, image: str, description: FrameDescription, index: int
) -> tuple[PersonCheck, ChatResult]:
    """The sex agent (T095): one vision question about described person `index` on the image
    (a data URL), naming the others so the answer is about the right one."""
    person = description.people[index]
    text = f"The person: {person.position}, {person.appearance}."
    others = [p for i, p in enumerate(description.people) if i != index]
    if others:
        text += " Not these others: " + "; ".join(f"{p.position}, {p.appearance}" for p in others)
    messages = [
        {"role": "system", "content": SEX_AGENT_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": text},
                {"type": "image_url", "image_url": {"url": image}},
            ],
        },
    ]
    result = await structured_chat(model, messages, PersonCheck, Tier.VISION, max_tokens=1024)
    return result.value, result.chat


async def _ask_sexes(
    model: NebiusChatModel,
    image: str,
    description: FrameDescription,
    matched: Mapping[int, str],
    sexes: Mapping[str, str],
    chats: list[ChatResult],
) -> tuple[PersonSeen, ...]:
    """The sex agent on every matched person the script sexes, at once (T095). A failed question
    checks nothing for that person: logged, never an ERROR."""
    asks = [(i, name) for i, name in sorted(matched.items()) if name in sexes]
    if not asks:
        return ()
    answers = await asyncio.gather(
        *(check_person(model, image, description, i) for i, _ in asks), return_exceptions=True
    )
    seen: list[PersonSeen] = []
    for (i, name), answer in zip(asks, answers, strict=True):
        if isinstance(answer, BaseException):
            if not isinstance(answer, LLMError | ValidationError):
                raise answer
            detail = str(answer) if isinstance(answer, LLMError) else type(answer).__name__
            logger.warning("sex agent on person %d (%s) failed: %s", i, name, detail)
            continue
        check, chat = answer
        chats.append(chat)
        seen.append(PersonSeen(i, name, check.sex))
    return tuple(seen)


async def _judge(
    model: NebiusChatModel,
    shot: Shot,
    scene: Scene,
    screenplay: Screenplay,
    extraction: Extraction,
    description: FrameDescription,
) -> tuple[Judgement, ChatResult]:
    messages = [
        {"role": "system", "content": JUDGE_PROMPT},
        {"role": "user", "content": render_spec(shot, scene, screenplay, extraction, description)},
    ]
    result = await structured_chat(model, messages, Judgement, Tier.REASONING, max_tokens=16384)
    return result.value, result.chat


PRESENCE_AGENT_PROMPT = (
    "You check whether a storyboard drawing shows one character from a screenplay. You get what "
    "the script says about the character, the shot's text, and a numbered list of the people a "
    "describer saw in the drawing. Look at the drawing and answer which numbered person is that "
    "character, or null when none of them can be. Pick a person when the drawing fits what the "
    "script says: their age group, their sex if the script gives it, and what the shot has them "
    "doing. A detail the drawing leaves out (a hat, a colour) doesn't rule anyone out. A person "
    "who is plainly someone else in the shot text (a bystander, a vendor, another character) is "
    "not this character. Give a short reason."
)


async def find_character(
    model: NebiusChatModel,
    image: str,
    character: str,
    shot: Shot,
    screenplay: Screenplay,
    extraction: Extraction,
    description: FrameDescription,
) -> tuple[Presence, ChatResult]:
    """The presence agent (T099): one vision question, which described person (if any) is
    `character`, given the judge's own line about them, the shot text and the numbered people."""
    about = _sexed(
        _quoted(extraction, EntityKind.CHARACTER, (character,)),
        (character,),
        screenplay,
        extraction,
    )
    people = [f"[{i}] {p.position}: {p.appearance}" for i, p in enumerate(description.people)]
    text = "\n".join(
        [
            "The character:",
            *about,
            "",
            "Shot text:",
            shot.source,
            "",
            "People in the drawing:",
            *(people or ["none"]),
        ]
    )
    messages = [
        {"role": "system", "content": PRESENCE_AGENT_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": text},
                {"type": "image_url", "image_url": {"url": image}},
            ],
        },
    ]
    result = await structured_chat(model, messages, Presence, Tier.VISION, max_tokens=4096)
    return result.value, result.chat


def present_characters(
    on_screen: Sequence[str],
    found: Sequence[PersonFound],
    accepted: Mapping[int, str],
    description: FrameDescription,
    ages: Mapping[str, int] | None,
) -> frozenset[str]:
    """The drawn characters the presence agent finds (T099, pure): an answer naming a person who
    exists, whom `matched_people` doesn't accept as another character, and whose described age
    doesn't contradict the character's introduced years."""
    out: set[str] = set()
    for answer in found:
        i = answer.person
        if answer.character not in on_screen or i is None:
            continue
        if not 0 <= i < len(description.people) or i in accepted:
            continue
        years = (ages or {}).get(answer.character)
        if years is not None and age_contradicts(
            years, described_age(description.people[i].appearance)
        ):
            continue
        out.add(answer.character)
    return frozenset(out)


async def _find_characters(
    model: NebiusChatModel,
    image: str,
    on_screen: Sequence[str],
    shot: Shot,
    screenplay: Screenplay,
    extraction: Extraction,
    description: FrameDescription,
    chats: list[ChatResult],
) -> tuple[PersonFound, ...]:
    """The presence agent on every drawn character, at once (T099). A failed question finds no
    one: logged, never an ERROR."""
    answers = await asyncio.gather(
        *(
            find_character(model, image, c, shot, screenplay, extraction, description)
            for c in on_screen
        ),
        return_exceptions=True,
    )
    found: list[PersonFound] = []
    for character, answer in zip(on_screen, answers, strict=True):
        if isinstance(answer, BaseException):
            if not isinstance(answer, LLMError | ValidationError):
                raise answer
            detail = str(answer) if isinstance(answer, LLMError) else type(answer).__name__
            logger.warning("presence agent on %s failed: %s", character, detail)
            continue
        presence, chat = answer
        chats.append(chat)
        found.append(PersonFound(character, presence.person, presence.reason))
    return tuple(found)


async def audit_frame(
    model: NebiusChatModel,
    frame: RenderedFrame,
    shot: Shot,
    screenplay: Screenplay,
    extraction: Extraction,
) -> Audit:
    scene = screenplay.scenes[shot.scene_index]
    chats: list[ChatResult] = []
    description: FrameDescription | None = None
    judgement: Judgement | None = None
    seen: tuple[PersonSeen, ...] = ()
    found: tuple[PersonFound, ...] = ()
    step = "describe"
    try:
        description, chat = await describe_frame(model, frame.png)
        chats.append(chat)
        step = "judge"
        judgement, chat = await _judge(model, shot, scene, screenplay, extraction, description)
        chats.append(chat)
    except (LLMError, ValidationError) as exc:
        # Which step failed, and an LLMError's message: it names the model, status and finish
        # reason, never the request (llm.md §4). A ValidationError's type only: it quotes the
        # output, which can quote the script.
        detail = str(exc) if isinstance(exc, LLMError) else type(exc).__name__
        logger.warning(
            "audit of shot %s attempt %d failed at %s: %s",
            frame.shot,
            frame.attempt,
            step,
            detail,
        )
        checks: tuple[CheckResult, ...] = ()
        verdict, positions = Verdict.ERROR, {}
    else:
        # T080: against the people the prompt drew. Imported here: T026's renderer modules in
        # app.storyboard import app.verify, so a module-level import would be a cycle there.
        from app.storyboard.prompt import character_sex, introduced_years, visible_characters

        on_screen = visible_characters(shot, screenplay, extraction)
        ages = shot_ages(shot, screenplay, introduced_years)
        sexes = shot_sexes(shot, screenplay, extraction, character_sex)
        matched = matched_people(shot, description, judgement, extraction, ages)
        image = f"data:image/png;base64,{base64.b64encode(frame.png).decode()}"
        seen = await _ask_sexes(model, image, description, matched, sexes, chats)
        # T099: none of the drawn characters matched, on a judgement run_checks will read.
        well_formed = _calls_each_once(
            [c.person for c in judgement.people], len(description.people)
        ) and _calls_each_once([c.object for c in judgement.objects], len(description.objects))
        if well_formed and on_screen and not set(on_screen) & set(matched.values()):
            found = await _find_characters(
                model, image, on_screen, shot, screenplay, extraction, description, chats
            )
        checks, verdict, positions = run_checks(
            shot,
            scene,
            description,
            judgement,
            extraction,
            on_screen=on_screen,
            ages=ages,
            seen=seen,
            sexes=sexes,
            found=found,
        )

    return Audit(
        shot=frame.shot,
        attempt=frame.attempt,
        seed=frame.seed,
        description=description,
        judgement=judgement,
        checks=checks,
        verdict=verdict,
        positions=positions,
        models=tuple(dict.fromkeys(c.model for c in chats)),
        usage=Usage(
            prompt_tokens=sum(c.usage.prompt_tokens for c in chats),
            completion_tokens=sum(c.usage.completion_tokens for c in chats),
            reasoning_tokens=sum(c.usage.reasoning_tokens for c in chats),
        ),
        seen=seen,
        found=found,
    )
