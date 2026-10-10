"""T071: the describer's instructions and schema, and RENDER_MAX_ATTEMPTS (verify.md §3, §4, §6)."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.verify.loop import MAX_RENDERS
from app.verify.prompts import DESCRIBE_PROMPT
from app.verify.schema import FrameDescription


def test_the_describer_leaves_out_costume_and_structure_and_writes_down_what_it_reads() -> None:
    prompt = DESCRIBE_PROMPT.lower()
    assert "wear" in prompt and "appearance" in prompt
    for part in ("windows", "doors", "roofs", "chimneys", "stairs"):
        assert part in prompt
    assert "word for word" in prompt and "can read" in prompt
    assert "signature" in prompt


def test_the_describer_must_always_return_its_text() -> None:
    schema = FrameDescription.model_json_schema()
    assert "text" in schema["required"]
    assert schema["properties"]["text"]["type"] == "array"


@pytest.mark.parametrize("attempts", [1, 2, 3])
def test_render_max_attempts_takes_one_to_three(attempts: int) -> None:
    assert Settings(render_max_attempts=attempts).render_max_attempts == attempts


@pytest.mark.parametrize("attempts", [0, 4])
def test_render_max_attempts_refuses_anything_else(attempts: int) -> None:
    with pytest.raises(ValidationError):
        Settings(render_max_attempts=attempts)


def test_render_max_attempts_defaults_to_the_loop_s_three(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RENDER_MAX_ATTEMPTS", raising=False)
    assert Settings(_env_file=None).render_max_attempts == MAX_RENDERS == 3  # type: ignore[call-arg]
    monkeypatch.setenv("RENDER_MAX_ATTEMPTS", "1")
    assert Settings(_env_file=None).render_max_attempts == 1  # type: ignore[call-arg]
