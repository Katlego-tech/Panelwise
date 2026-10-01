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

# Forms of address: stop words on their own, but redacted with the name they precede, so
# "MR. DUBE" becomes "a person", not "MR. a person" (T050, storyboard.md §3.1).
TITLE_WORDS = frozenset(
    {"MR", "MRS", "MS", "MISS", "DR", "SIR", "LADY", "OFFICER", "NURSE", "DOCTOR"}
)
# Only abbreviations take a full stop: "the OFFICER. Moloi turns" is a sentence end, not a title.
_ABBREVIATIONS = frozenset({"MR", "MRS", "MS", "DR"})

# Word characters except U+02BC, the modifier-letter apostrophe that \w counts as a letter:
# NANDI\u02bcS must tokenise as NANDI then S, like NANDI'S (PR #27 review).
_WORD = re.compile(r"[^\W\u02bc]+")
_APOSTROPHES = frozenset({"'", "\u2019", "\u02bc"})


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
        start = _title_start(text, words, i, pos)
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
        out += [text[pos:start], replacement]
        pos, i = end, after
    out.append(text[pos:])
    return "".join(out)


def _title_start(text: str, words: list[re.Match[str]], i: int, floor: int) -> int:
    """Where the name run at word `i` starts once the titles directly before it join it: each a
    capitalised title word (an abbreviation optionally with a ".") separated by whitespace, and
    never reaching back before `floor`, the end of the last replacement. (Defensive: titles are
    stop words, never name tokens, so a walk back stops at the previous run anyway.)"""
    start = words[i].start()
    k = i - 1
    while k >= 0 and words[k].start() >= floor:
        word = words[k].group()
        gap = text[words[k].end() : start]
        if gap.startswith(".") and word.upper() in _ABBREVIATIONS:
            gap = gap[1:]
        if not (word[0].isupper() and word.upper() in TITLE_WORDS and gap and gap.isspace()):
            break
        start = words[k].start()
        k -= 1
    return start
