"""T088: a person's sex from a pronoun sentence the extraction picks, kept only when code finds it
the plain reading (grounding.md §3 sex_pronoun_quote, §9). A self-written script, one scene per
trap so no line is another's antecedent; no model."""

import pytest

from app.characters.sex import Sex
from app.grounding import Entity, EntityKind, ProposedEntity, ground
from app.script import Screenplay, parse_text
from tests.script.conftest import ACTION, CUE, DIALOGUE, Row, heading, layout


def _scene(number: str, *rows: Row) -> list[Row]:
    """A scene: its heading, then each row with a blank line after it, except a cue, which its
    speech follows directly."""
    out: list[Row] = [heading(number, f"INT. ROOM {number} - DAY"), None]
    for row in rows:
        out += [row] if row is not None and row[0] == CUE else [row, None]
    return out


ROWS: list[Row] = [
    (CUE - 4, "PRONOUN TESTS"),
    None,
    *_scene(
        "1",
        (ACTION, "DANIEL (40s), a tall driver, climbs out. He stretches until his back cracks."),
    ),
    *_scene("2", (ACTION, "THEO (9) stumbles out with a bag held against his chest.")),
    *_scene(
        "3", (CUE, "PRIYA"), (DIALOGUE, "No. No, no, no."), (ACTION, "She spots the sign and runs.")
    ),
    *_scene("4", (ACTION, "SIPHOKAZI (17) waits. Siphokazi takes his hand.")),
    *_scene("5", (ACTION, "DANIEL laughs and takes the bag from him.")),
    *_scene("6", (ACTION, "ZOLA (30s) laughs. She hands him the cup.")),
    *_scene("7", (ACTION, "SIPHO (50s) waves to a woman. She smiles.")),
    *_scene("8", (ACTION, "THABO (30s) pays. The cashier smiles. She bags the items.")),
    *_scene("9", (ACTION, "PETER (30s) hugs his mother. She smiles.")),
    *_scene("10", (ACTION, "THEO (9) sleeps. A small brown dog, BISCUIT, licks her paws.")),
    *_scene("11", (ACTION, "THABO (30s) dances with grace. He nods.")),
    *_scene("12", (ACTION, "MR. DUBE (60s) and MRS. DUBE (60s) wait. Dube enters. She sits.")),
    *_scene("13", (ACTION, "THABO (30s) hugs Lerato. She smiles.")),
    *_scene("14", (ACTION, "LINDA (40s) lifts a RED KITE. She grins.")),
    *_scene("15", (CUE, "NOMSA"), (DIALOGUE, "Theo. Up."), (ACTION, "He hasn't moved.")),
    *_scene("16", (ACTION, "Mr. Dube takes off his cap.")),
]


def screenplay() -> Screenplay:
    return parse_text(layout(ROWS), [])


def person(name: str, quotes: list[str], pronoun_quote: str | None = None, word: str | None = None):
    return ProposedEntity.model_validate(
        {
            "kind": "character",
            "name": name,
            "quotes": quotes,
            "sex_word": word,
            "sex_pronoun_quote": pronoun_quote,
        }
    )


def animal(name: str, quote: str) -> ProposedEntity:
    return ProposedEntity.model_validate(
        {"kind": "character", "name": name, "quotes": [quote], "species": "dog"}
    )


def grounded(*proposals: ProposedEntity) -> dict[str, Entity]:
    entities, _ = ground(list(proposals), screenplay())
    return {e.name: e for e in entities if e.kind is EntityKind.CHARACTER}


def test_a_he_right_after_the_sentence_naming_him() -> None:
    quote = "He stretches until his back cracks."
    e = grounded(person("DANIEL", ["DANIEL (40s), a tall driver, climbs out."], quote))["DANIEL"]
    assert e.sex is Sex.MALE
    assert e.sex_quote is not None and e.sex_quote.text == quote


def test_his_own_possessive_in_his_own_sentence() -> None:
    quote = "THEO (9) stumbles out with a bag held against his chest."
    assert grounded(person("THEO", [quote], quote))["THEO"].sex is Sex.MALE


def test_a_she_opening_an_action_after_her_own_speech() -> None:
    e = grounded(person("PRIYA", ["No. No, no, no."], "She spots the sign and runs."))["PRIYA"]
    assert e.sex is Sex.FEMALE


@pytest.mark.parametrize(
    ("name", "quotes", "pronoun_quote", "others"),
    [
        # The nearest name is Siphokazi's: "his" isn't hers, and it isn't SIPHO's either.
        ("SIPHO", ["SIPHO (50s) waves to a woman."], "Siphokazi takes his hand.", ["SIPHOKAZI"]),
        ("THEO", ["THEO (9) sleeps."], "DANIEL laughs and takes the bag from him.", ["DANIEL"]),
        ("ZOLA", ["ZOLA (30s) laughs."], "She hands him the cup.", []),  # two sexes
        ("SIPHO", ["SIPHO (50s) waves to a woman."], "She smiles.", []),  # a sex noun between
        ("THABO", ["THABO (30s) pays."], "She bags the items.", []),  # "The cashier smiles."
        ("PETER", ["PETER (30s) hugs his mother."], "She smiles.", []),  # "his mother"
        ("THEO", ["THEO (9) sleeps."], "A small brown dog, BISCUIT, licks her paws.", []),
        ("THABO", ["THABO (30s) hugs Lerato."], "She smiles.", []),  # a name not extracted
    ],
)
def test_no_sex_when_another_referent_could_be_meant(
    name: str, quotes: list[str], pronoun_quote: str, others: list[str]
) -> None:
    proposals = [person(name, quotes, pronoun_quote)]
    proposals += [
        person(o, [f"{o} (17) waits."] if o == "SIPHOKAZI" else [f"{o} laughs"]) for o in others
    ]
    proposals.append(animal("BISCUIT", "A small brown dog, BISCUIT, licks her paws."))
    assert grounded(*proposals)[name].sex is None


def test_a_common_word_is_no_name() -> None:
    # "grace" in lower case is not GRACE: the nearest name is THABO's, so GRACE gets nothing.
    found = grounded(
        person("THABO", ["THABO (30s) dances with grace."]),
        person("GRACE", ["THABO (30s) dances with grace."], "He nods."),
    )
    assert found["GRACE"].sex is None


def test_a_shared_name_token_names_no_one() -> None:
    quotes = ["MR. DUBE (60s) and MRS. DUBE (60s) wait."]
    found = grounded(
        person("MR. DUBE", quotes, "She sits."), person("MRS. DUBE", quotes, "She sits.")
    )
    assert found["MR. DUBE"].sex is None and found["MRS. DUBE"].sex is None


def test_a_prop_in_capitals_is_no_name() -> None:
    e = grounded(person("LINDA", ["LINDA (40s) lifts a RED KITE."], "She grins."))["LINDA"]
    assert e.sex is Sex.FEMALE


def test_a_name_spoken_in_dialogue_is_no_antecedent() -> None:
    found = grounded(person("THEO", ["THEO (9) sleeps."], "He hasn't moved."))
    assert found["THEO"].sex is None  # the nearest name is the cue, NOMSA's


def test_a_title_abbreviation_does_not_end_the_sentence() -> None:
    e = grounded(person("MR. DUBE", ["Mr. Dube takes off his cap."], "Mr. Dube takes off his cap."))
    assert e["MR. DUBE"].sex is Sex.MALE


def test_a_quote_not_found_or_in_dialogue_gives_nothing() -> None:
    assert grounded(person("PRIYA", ["No. No, no, no."], "She flies away."))["PRIYA"].sex is None
    assert grounded(person("PRIYA", ["No. No, no, no."], "No. No, no, no."))["PRIYA"].sex is None


def test_with_a_sex_word_too_both_agree_and_the_sex_words_quote_is_kept() -> None:
    whole = "DANIEL (40s), a tall driver, climbs out. He stretches until his back cracks."
    e = grounded(person("DANIEL", [whole], "He stretches until his back cracks.", word="He"))
    assert e["DANIEL"].sex is Sex.MALE
    assert e["DANIEL"].sex_quote is not None and e["DANIEL"].sex_quote.text == whole
