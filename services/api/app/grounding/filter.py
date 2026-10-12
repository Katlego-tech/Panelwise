"""The grounding filter: only what the script says survives, each quote at a located span.

docs/design/grounding.md §4. Ported from FrameFlow's extraction_service (merge, filter) and
governance_service (faithfulness, recall), and changed where they failed:

* Filtering is per quote, not per entity. FrameFlow dropped an entity if any one quote failed,
  and lost its lead character to a single quote broken by a line-break hyphen.
* A quote must sit inside one element, so every kept quote has a span a panel can cite.
* Recall matches cues with `match_speaker` ("THABO" finds "THABO MOLEFE"); FrameFlow compared
  exact names. Speaking characters the model missed are added from the cues, but don't count
  toward the model's recall.
* Locations come from the scene headings: the parser already knows them exactly.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field, replace

from app.characters.redact import NAME_STOP_WORDS, name_tokens
from app.characters.sex import CONFLICT_WORDS, PRONOUNS, SEX_WORDS, Sex
from app.grounding.model import Dropped, Entity, EntityKind, GroundingReport, Quote, Source
from app.grounding.schema import ProposedEntity
from app.grounding.text import (
    CueIndex,
    Index,
    build_cue_index,
    build_index,
    locate_quote,
    normalize_for_grounding,
)
from app.script import Action, Dialogue, Screenplay, Span, match_speaker, normalise


def ground(
    proposals: Sequence[ProposedEntity], screenplay: Screenplay
) -> tuple[tuple[Entity, ...], GroundingReport]:
    index = build_index(screenplay)
    cues = build_cue_index(screenplay)
    script = normalize_for_grounding(screenplay.text)

    # Merge across chunks on (kind, name), keeping the first spelling and every distinct quote,
    # every proposed species in order, and every proposed other name.
    groups: dict[tuple[str, str], _Group] = {}
    for p in proposals:
        key = (p.kind, normalise(p.name))
        if not key[1]:
            continue
        group = groups.setdefault(key, _Group(p.name.strip(), EntityKind(p.kind)))
        seen = {normalize_for_grounding(q) for q in group.quotes}
        group.quotes.extend(q for q in p.quotes if normalize_for_grounding(q) not in seen)
        if p.species is not None:
            group.species.append(p.species)
        group.other_names.extend(p.other_names)
        if p.sex_word is not None:
            group.sex_words.append(p.sex_word)
        if p.sex_pronoun_quote is not None:
            group.pronoun_quotes.append(p.sex_pronoun_quote)

    # What a species may not be: a word for a person, or a word of a different character's name.
    actions = {e.span for sc in screenplay.scenes for e in sc.elements if isinstance(e, Action)}
    character_names = [g.name for g in groups.values() if g.kind is EntityKind.CHARACTER] + [
        e.cue for sc in screenplay.scenes for e in sc.elements if isinstance(e, Dialogue)
    ]

    kept: list[_Kept] = []
    dropped: list[Dropped] = []
    fully_grounded = quotes_total = quotes_located = 0
    for group in groups.values():
        name, kind, quotes = group.name, group.kind, group.quotes
        found = [f for q in quotes if (f := locate_quote(index, cues, q)) is not None]
        quotes_total += len(quotes)
        quotes_located += len(found)
        located = _unique(found)
        name_found = _mentions(script, name)
        # Every quote located, counted before `_unique` folds repeats into one.
        if name_found and found and len(found) == len(quotes):
            fully_grounded += 1
        if not name_found:
            dropped.append(Dropped(name, kind, "name not found in the script"))
        elif not located:
            dropped.append(Dropped(name, kind, "no quote found in the script"))
        else:
            kept.append(
                _Kept(
                    kind,
                    name,
                    located,
                    _species(group, located, actions, _not_species(name, character_names))
                    if kind is EntityKind.CHARACTER
                    else None,
                    _other_names(group, script),
                )
            )

    characters, recall_found, cues_total = _characters(kept, screenplay)
    # T082: a person's sex from a copied word; needs the whole cast, so after _characters.
    sex_words = {
        normalise(g.name): g.sex_words for g in groups.values() if g.kind is EntityKind.CHARACTER
    }
    pronouns = {  # T088
        normalise(g.name): g.pronoun_quotes
        for g in groups.values()
        if g.kind is EntityKind.CHARACTER
    }
    characters = [
        _with_sex(
            c,
            sex_words.get(normalise(c.name), []),
            characters,
            actions,
            [
                found
                for q in pronouns.get(normalise(c.name), [])
                if (found := _pronoun_sex(q, c, characters, screenplay, index, cues)) is not None
            ],
        )
        for c in characters
    ]
    props = [
        Entity(
            EntityKind.PROP,
            k.name,
            tuple(k.quotes),
            _scenes(k.quotes),
            Source.MODEL,
            other_names=k.other_names,
        )
        for k in kept
        if k.kind is EntityKind.PROP
    ]
    entities = (
        *sorted(characters, key=_order),
        *sorted(props, key=_order),
        *_locations(screenplay),
    )
    proposed = len(groups)
    report = GroundingReport(
        entities_proposed=proposed,
        entities_grounded=fully_grounded,
        faithfulness=fully_grounded / proposed if proposed else 1.0,
        quotes_proposed=quotes_total,
        quotes_located=quotes_located,
        dropped=tuple(dropped),
        cues_total=cues_total,
        cues_found_by_model=recall_found,
        recall=recall_found / cues_total if cues_total else 1.0,
    )
    return entities, report


# A species names no person: the stop words (MAN, GIRL, OFFICER...) and these.
PERSON_WORDS = NAME_STOP_WORDS | frozenset(
    {
        "PERSON",
        "PEOPLE",
        "MEN",
        "WOMEN",
        "CHILD",
        "CHILDREN",
        "KID",
        "KIDS",
        "BABY",
        "TEENAGER",
        "FIGURE",
        "CROWD",
    }
)
_ARTICLE = re.compile(r"^(?:a|an|the)\s+", re.IGNORECASE)


@dataclass
class _Group:
    """One entity's proposals, merged across chunks."""

    name: str
    kind: EntityKind
    quotes: list[str] = field(default_factory=list[str])
    species: list[str] = field(default_factory=list[str])
    other_names: list[str] = field(default_factory=list[str])
    sex_words: list[str] = field(default_factory=list[str])
    pronoun_quotes: list[str] = field(default_factory=list[str])


@dataclass(frozen=True)
class _Kept:
    kind: EntityKind
    name: str
    quotes: list[Quote]
    species: str | None
    other_names: tuple[str, ...]


def _words(text: str) -> str:
    """Normalised, padded with spaces, so a whole-word test is a substring test."""
    return f" {' '.join(re.findall(r'[^\W_]+', normalize_for_grounding(text)))} "


def _not_species(name: str, character_names: Sequence[str]) -> frozenset[str]:
    """PERSON_WORDS, and the name tokens of every *other* character: a speaking animal cued CAT
    keeps `cat` (grounding.md §3)."""
    own = normalise(name)
    others = [
        n for n in character_names if match_speaker(n, [name]) is None and normalise(n) != own
    ]
    return PERSON_WORDS | name_tokens(others)


def _species(
    group: _Group, located: Sequence[Quote], actions: set[Span], not_species: frozenset[str]
) -> str | None:
    """The first proposed species that, without a leading article, is 1-3 words with a letter,
    names no person (`PERSON_WORDS`, any character's name token), and is whole words inside one
    of this entity's located quotes that sits in an Action element: a description, not someone's
    speech (grounding.md §3, T051)."""
    descriptions = [_words(q.text) for q in located if q.span in actions]
    for proposed in group.species:
        species = _ARTICLE.sub("", proposed.strip())
        words = _words(species)
        has_letter = any(c.isalpha() for c in words)
        if not has_letter or not 1 <= len(words.split()) <= 3 or set(words.split()) & not_species:
            continue
        if any(words in d for d in descriptions):
            return species
    return None


def _tokens(entity: Entity) -> frozenset[str]:
    return name_tokens([entity.name]) | name_tokens(entity.other_names)


def _quote_sex(word: str, quote: Quote, entity: Entity, cast: Sequence[Entity]) -> Sex | None:
    """The sex `word` gives in `quote` when every rule of grounding.md §3 (sex_word, 2a-e) holds:
    the word is a whole word of it; it names this character and no other (aliases, one's tokens
    containing the other's, excepted); a pronoun comes after this character's first mention;
    and every sex word in it agrees."""
    words = normalise(quote.text).split()
    own = _tokens(entity)
    mentions = [i for i, w in enumerate(words) if w in own]
    if not mentions:
        return None
    for other in cast:
        if other is entity or other.kind is not EntityKind.CHARACTER:
            continue
        theirs = _tokens(other)
        if theirs and not (theirs <= own or own <= theirs) and theirs & set(words):
            return None
    lower = word.strip().rstrip(".").lower()
    sex = SEX_WORDS.get(lower)
    found = [i for i, w in enumerate(words) if w.lower() == lower]
    if sex is None or not found:
        return None
    if lower in PRONOUNS and not any(i > mentions[0] for i in found):
        return None
    if {CONFLICT_WORDS[w.lower()] for w in words if w.lower() in CONFLICT_WORDS} != {sex}:
        return None
    return sex


def _with_sex(
    entity: Entity,
    proposed: Sequence[str],
    cast: Sequence[Entity],
    actions: set[Span],
    pronoun_sexes: Sequence[tuple[Sex, Quote]] = (),
) -> Entity:
    """The entity with the sex its copied words ground, all agreeing (grounding.md §3, T082);
    T088: and its checked pronoun sentences, after them. Unchanged for an animal, a CUE backfill
    or no proposal."""
    if entity.species is not None or entity.source is not Source.MODEL:
        return entity
    kept: list[tuple[Sex, Quote]] = []
    for word in proposed:
        for quote in entity.quotes:
            if quote.span in actions and (sex := _quote_sex(word, quote, entity, cast)):
                kept.append((sex, quote))
                break
    kept.extend(pronoun_sexes)
    if not kept or len({sex for sex, _ in kept}) != 1:
        return entity
    return replace(entity, sex=kept[0][0], sex_quote=kept[0][1])


# The third-person singular pronouns a sex_pronoun_quote is read by (T088), and the words that
# stop the antecedent scan: another possible referent stands between the name and the pronoun.
_PERSON_PRONOUNS = frozenset({"he", "him", "his", "himself", "she", "her", "hers", "herself"})
_POSSESSIVES = frozenset({"his", "her", "hers", "their", "theirs", "my", "your", "our"})
_DETERMINERS = frozenset({"a", "an", "the", "this", "that", "these", "those", "another", "some"})
# A sentence ends at . ! ? and whitespace, never after a title's abbreviation ("Mr. Dube").
_SENTENCE_END = re.compile(r"(?<=[.!?])(?<!\bMr\.)(?<!\bMrs\.)(?<!\bMs\.)(?<!\bDr\.)(?<!\bSt\.)\s+")
_WORD = re.compile(r"[A-Za-z']+")


def _sentences(text: str) -> list[list[str]]:
    """An element's sentences, each as its words in their own case (T088)."""
    return [_WORD.findall(s) for s in _SENTENCE_END.split(text) if _WORD.search(s)]


def _title_case(word: str) -> bool:
    """A word written as a name is ("Lerato"): a capital, then lower case. A prop in capitals
    (RED KITE) is not one."""
    return word[:1].isupper() and word[1:].islower()


def _stretch(
    scene_elements: Sequence[Action | Dialogue], at: int, text: str
) -> tuple[list[str], list[str]] | None:
    """The words before the quote's first pronoun in its own sentence, and the sentence before
    that one (for an element's first sentence: the previous element's last sentence, or a
    speech's cue). None when the quote isn't found in the element."""
    sentences = _sentences(scene_elements[at].text)
    flat = [(k, word) for k, words in enumerate(sentences) for word in words]
    quoted = [w.lower() for w in _WORD.findall(text)]
    lowered = [w.lower() for _, w in flat]
    n = len(quoted)
    begin = next((i for i in range(len(flat) - n + 1) if lowered[i : i + n] == quoted), None)
    if begin is None:
        return None
    pronoun = next(i for i in range(begin, begin + n) if lowered[i] in _PERSON_PRONOUNS)
    k = flat[pronoun][0]
    own = [w for j, (kk, w) in enumerate(flat) if kk == k and j < pronoun]
    if k > 0:
        return own, sentences[k - 1]
    if at > 0:
        previous = scene_elements[at - 1]
        if isinstance(previous, Action):
            return own, (_sentences(previous.text) or [[]])[-1]
        return own, previous.cue.split()
    return own, []


def _pronoun_sex(
    text: str,
    entity: Entity,
    cast: Sequence[Entity],
    screenplay: Screenplay,
    index: Index,
    cues: CueIndex,
) -> tuple[Sex, Quote] | None:
    """The sex a sex_pronoun_quote gives this character (grounding.md §3, T088), with the quote:
    located in an Action element; its singular pronouns all one sex; and its first pronoun's
    antecedent is plainly this character, named in the pronoun's own sentence or the one before,
    with no other possible referent between. Else None."""
    found = locate_quote(index, cues, text)
    if found is None:
        return None
    _, scene_index, span = found
    elements = screenplay.scenes[scene_index].elements
    at = next((i for i, e in enumerate(elements) if e.span == span and isinstance(e, Action)), None)
    said = [w.lower() for w in _WORD.findall(text) if w.lower() in _PERSON_PRONOUNS]
    if at is None or not said or len({CONFLICT_WORDS[w] for w in said}) != 1:
        return None
    stretch = _stretch(elements, at, text)
    if stretch is None:
        return None
    sex = CONFLICT_WORDS[said[0]]
    owners: dict[str, list[Entity]] = {}
    beings: set[str] = set()
    for other in cast:
        if other.kind is EntityKind.CHARACTER:
            for token in _tokens(other):
                if other.species is None:
                    owners.setdefault(token, []).append(other)
                else:
                    beings.add(token)
    own, before = stretch
    for sentence, opening in ((own, own[:1]), (before, before[:1])):
        for pos in range(len(sentence) - 1, -1, -1):
            word = sentence[pos]
            low, key = word.lower(), normalise(word)
            named = word[:1].isupper()
            if named and key in beings:
                return None  # an animal: the pronoun may be its own
            if named and key in owners:
                return (sex, Quote(text, scene_index, span)) if owners[key] == [entity] else None
            if low in _POSSESSIVES or (low in _PERSON_PRONOUNS and CONFLICT_WORDS[low] != sex):
                return None  # "his mother", or someone of the other sex
            if low in SEX_WORDS and low not in PRONOUNS:
                return None  # "a woman": an unnamed person
            if pos > 0 and _title_case(word) and key not in NAME_STOP_WORDS:
                return None  # a name the extraction doesn't have
        if opening and opening[0].lower() in _DETERMINERS:
            return None  # "The cashier smiles.", "A small dog, BISCUIT, …": someone unnamed
    return None


def _other_names(group: _Group, script: str) -> tuple[str, ...]:
    """Other names the script mentions as whole words, not the entity's name, with a name token
    (grounding.md §3, T051). In first-proposed order, once each."""
    kept: dict[str, str] = {}
    for other in group.other_names:
        key = normalise(other)
        if (
            key
            and key != normalise(group.name)
            and key not in kept
            and name_tokens([other])
            and _mentions(script, other)
        ):
            kept[key] = other.strip()
    return tuple(kept.values())


def _unique(found: Sequence[tuple[str, int, Span]]) -> list[Quote]:
    """One Quote per text and span: `"LERATO\\nI promise."` and `"I promise."` keep the same
    text at the same speech once the cue is stripped."""
    seen: set[tuple[str, Span]] = set()
    quotes: list[Quote] = []
    for text, scene_index, span in found:
        key = (normalize_for_grounding(text), span)
        if key not in seen:
            seen.add(key)
            quotes.append(Quote(text, scene_index, span))
    return quotes


def _mentions(script: str, name: str) -> bool:
    needle = normalize_for_grounding(name)
    return bool(needle) and re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", script) is not None


def _scenes(quotes: Sequence[Quote], extra: Sequence[int] = ()) -> tuple[int, ...]:
    return tuple(sorted({q.scene_index for q in quotes} | set(extra)))


def _order(entity: Entity) -> tuple[int, str]:
    return (entity.scenes[0] if entity.scenes else 0, entity.name)


def _characters(kept: Sequence[_Kept], screenplay: Screenplay) -> tuple[list[Entity], int, int]:
    """Grounded model characters with the scenes they speak in, plus the speakers the model
    missed. Returns (characters, cues found by the model, cues in the script)."""
    names = [k.name for k in kept if k.kind is EntityKind.CHARACTER]

    # Every speech: which distinct cue it is, and which model character (if any) it belongs to.
    speaking: dict[str, list[tuple[int, Dialogue]]] = {}
    for scene in screenplay.scenes:
        for element in scene.elements:
            if isinstance(element, Dialogue) and normalise(element.cue):
                speaking.setdefault(normalise(element.cue), []).append((scene.index, element))
    owner = {cue: match_speaker(cue, names) for cue in speaking}

    characters: list[Entity] = []
    for k in kept:
        if k.kind is not EntityKind.CHARACTER:
            continue
        spoke = [
            i for cue, speeches in speaking.items() if owner[cue] == k.name for i, _ in speeches
        ]
        characters.append(
            Entity(
                EntityKind.CHARACTER,
                k.name,
                tuple(k.quotes),
                _scenes(k.quotes, spoke),
                Source.MODEL,
                species=k.species,
                other_names=k.other_names,
            )
        )

    for cue, speeches in speaking.items():
        if owner[cue] is not None:
            continue
        scene_index, first = speeches[0]
        quote = Quote(first.text, scene_index, first.span)
        characters.append(
            Entity(
                EntityKind.CHARACTER,
                first.cue,
                (quote,),
                tuple(sorted({i for i, _ in speeches})),
                Source.CUE,
            )
        )
    found = sum(1 for cue in speaking if owner[cue] is not None)
    return characters, found, len(speaking)


def _locations(screenplay: Screenplay) -> list[Entity]:
    groups: dict[str, tuple[str, list[Quote]]] = {}
    for scene in screenplay.scenes:
        key = normalise(scene.location)
        if not key:
            continue
        heading = Quote(
            scene.heading,
            scene.index,
            Span(scene.span.page, scene.span.line_start, scene.span.line_start),
        )
        groups.setdefault(key, (scene.location, []))[1].append(heading)
    return [
        Entity(EntityKind.LOCATION, name, tuple(quotes), _scenes(quotes), Source.HEADING)
        for name, quotes in groups.values()
    ]
