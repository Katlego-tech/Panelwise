"""Taking character names out of text before it enters an image prompt. docs/design/characters.md
§3 rules 1 and 2, storyboard.md §3.1.

An image model reads a name as a likeness cue, and screenplays introduce characters by name inside
the very lines a frame is drawn from ("NANDI (60s, oilskin coat) pours tea"). So every name is
replaced, and nothing else changes: redaction only removes words. Names are matched the way
screenplays write them, in UPPER or Title case as whole words; a lower-case "will" is a verb, not
WILL. A cue made only of words that aren't names on their own (THE STRANGER) redacts nothing, or
every "The" would become a person.
"""

import re
from collections.abc import Callable, Collection, Sequence

from app.script import normalise

NAME_STOP_WORDS = frozenset(
    {
        "THE",
        "A",
        "AN",
        "OLD",
        "YOUNG",
        "LITTLE",
        "BIG",
        "MR",
        "MRS",
        "MS",
        "MISS",
        "DR",
        "SIR",
        "LADY",
        "MAN",
        "WOMAN",
        "BOY",
        "GIRL",
        "STRANGER",
        "OFFICER",
        "NURSE",
        "DOCTOR",
    }
)

_WORD = re.compile(r"\w+")
_APOSTROPHES = frozenset({"'", "\u2019"})


def name_tokens(names: Sequence[str]) -> frozenset[str]:
    return frozenset(
        t for name in names for t in normalise(name).split() if t not in NAME_STOP_WORDS
    )


def redact_names(text: str, character: str, others: Sequence[str]) -> str:
    """This character's names become "a person", any other character's "another person"."""
    own = name_tokens([character])
    return _redact(
        text,
        own | name_tokens(others),
        lambda run: "a person" if set(run) <= own else "another person",
    )


def redact_all(text: str, characters: Sequence[str]) -> str:
    """Every character's names become "a person"."""
    return _redact(text, name_tokens(characters), lambda _: "a person")


def _is_name(word: str, tokens: Collection[str]) -> bool:
    # UPPER or Title case: a capital first letter. "McDONALD" counts too; "will" never does.
    return word[0].isupper() and word.upper() in tokens


def _redact(text: str, tokens: Collection[str], label: Callable[[list[str]], str]) -> str:
    """Each maximal run of name tokens (joined by whitespace, a hyphen or an apostrophe, as in
    O'BRIEN, with an optional possessive 's on the last) becomes one label."""
    if not tokens:
        return text
    words = list(_WORD.finditer(text))
    out: list[str] = []
    pos = i = 0
    while i < len(words):
        if not _is_name(words[i].group(), tokens):
            i += 1
            continue
        j = i
        while j + 1 < len(words) and _is_name(words[j + 1].group(), tokens):
            gap = text[words[j].end() : words[j + 1].start()]
            if not (gap == "-" or gap in _APOSTROPHES or (gap and gap.isspace())):
                break
            j += 1
        replacement = label([w.group().upper() for w in words[i : j + 1]])
        end = words[j].end()
        after = j + 1
        # "NANDI'S": the tokeniser sees NANDI, then S after an apostrophe.
        if (
            after < len(words)
            and words[after].group() in ("s", "S")
            and text[end : words[after].start()] in _APOSTROPHES
        ):
            replacement += text[end] + "s"
            end = words[after].end()
            after += 1
        out += [text[pos : words[i].start()], replacement]
        pos, i = end, after
    out.append(text[pos:])
    return "".join(out)
