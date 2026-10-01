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
from dataclasses import dataclass, field

from app.characters.redact import NAME_STOP_WORDS, name_tokens
from app.grounding.model import Dropped, Entity, EntityKind, GroundingReport, Quote, Source
from app.grounding.schema import ProposedEntity
from app.grounding.text import (
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
        if not 1 <= len(words.split()) <= 3 or set(words.split()) & not_species:
            continue
        if any(words in d for d in descriptions):
            return species
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
