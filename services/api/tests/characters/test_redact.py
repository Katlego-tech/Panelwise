"""Name redaction: characters.md §3 rules 1 and 2 and §9, storyboard.md §3.1 and §9. Pure."""

import pytest

from app.characters import NAME_STOP_WORDS, name_tokens, redact_all, redact_names


def test_name_tokens_are_the_normalised_words_minus_stop_words() -> None:
    assert name_tokens(["Nandi Molefe", "MR. DUBE", "OFFICER VAN WYK"]) == {
        "NANDI",
        "MOLEFE",
        "DUBE",
        "VAN",
        "WYK",
    }


@pytest.mark.parametrize("cue", ["THE STRANGER", "OLD MAN", "THE NURSE", "A BOY"])
def test_a_cue_made_only_of_stop_words_has_no_name_token(cue: str) -> None:
    assert name_tokens([cue]) == frozenset()


def test_stop_words_are_the_designed_list() -> None:
    assert frozenset(
        {
            "THE", "A", "AN", "OLD", "YOUNG", "LITTLE", "BIG", "MR", "MRS", "MS", "MISS", "DR",
            "SIR", "LADY", "MAN", "WOMAN", "BOY", "GIRL", "STRANGER", "OFFICER", "NURSE",
            "DOCTOR",
        }
    ) == NAME_STOP_WORDS  # fmt: skip


def test_this_character_becomes_a_person_and_keeps_everything_else() -> None:
    assert (
        redact_names("NANDI (60s, oilskin coat) pours tea", "NANDI", ["THABO"])
        == "a person (60s, oilskin coat) pours tea"
    )


def test_another_character_becomes_another_person() -> None:
    assert (
        redact_names("THABO hands Nandi the map.", "NANDI", ["THABO"])
        == "another person hands a person the map."
    )


def test_a_multi_word_name_is_one_person_and_each_token_alone_is_too() -> None:
    assert redact_names("NANDI MOLEFE pours.", "NANDI MOLEFE", []) == "a person pours."
    assert redact_names("Molefe nods. Nandi smiles.", "NANDI MOLEFE", []) == (
        "a person nods. a person smiles."
    )


def test_possessives_keep_their_s() -> None:
    assert redact_all("NANDI'S KITCHEN", ["NANDI"]) == "a person's KITCHEN"
    assert redact_all("Nandi\u2019s coat", ["NANDI"]) == "a person\u2019s coat"
    assert redact_names("NANDI MOLEFE'S map", "THABO", ["NANDI MOLEFE"]) == ("another person's map")


def test_lower_case_common_words_are_untouched_but_a_title_case_one_is_not() -> None:
    assert redact_all("she will stay", ["WILL"]) == "she will stay"
    # The known cost: a sentence-initial common word that is also a name fails safe.
    assert redact_all("Will stays.", ["WILL"]) == "a person stays."


def test_stop_words_are_left_alone() -> None:
    assert redact_all("The kettle screams.", ["THE STRANGER"]) == "The kettle screams."
    assert redact_all("Old nets hang there.", ["OLD MAN"]) == "Old nets hang there."
    assert redact_all("MR. DUBE (50s) waits.", ["MR. DUBE"]) == "MR. a person (50s) waits."


def test_only_whole_words_match() -> None:
    assert redact_all("NANDIWE and SIPHOKAZI wait.", ["NANDI", "SIPHO"]) == (
        "NANDIWE and SIPHOKAZI wait."
    )


def test_redact_all_turns_every_run_of_every_character_into_one_person() -> None:
    assert redact_all("NANDI and THABO MOLEFE run.", ["NANDI", "THABO MOLEFE"]) == (
        "a person and a person run."
    )
    assert redact_all("LERATO-MOKGOSI waves.", ["LERATO", "MOKGOSI"]) == "a person waves."


def test_redaction_only_removes_words() -> None:
    text = "Rain hammers the window. NANDI (60s, oilskin coat) pours tea."
    redacted = redact_all(text, ["NANDI", "THABO"])
    kept = [w for w in text.split() if w != "NANDI"]
    assert [w for w in redacted.split() if w not in {"a", "person"}] == kept


def test_no_names_leaves_the_text_as_is() -> None:
    assert redact_all("DOORS SLAM.", []) == "DOORS SLAM."


def test_every_apostrophe_form_splits_a_possessive_and_joins_a_run() -> None:
    # U+02BC is a letter to \w; it must still end the name (PR #27 review).
    assert redact_all("NANDI\u02bcS coat", ["NANDI"]) == "a person\u02bcs coat"
    assert redact_all("O\u2019BRIEN waits.", ["O'BRIEN"]) == "a person waits."
    assert redact_all("O'Brien waits.", ["O'BRIEN"]) == "a person waits."


def test_non_latin_capitals_are_names_too() -> None:
    assert redact_all("\u00c9MILE sits. \u00c9mile's cap.", ["\u00c9MILE"]) == (
        "a person sits. a person's cap."
    )
