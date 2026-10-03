"""frame_view: one `frames` row as web.md §6's FrameView (T047). Pure."""

import uuid
from datetime import UTC, datetime

import pytest

from app.frames.model import FrameRow
from app.frames.views import MAX_RENDERS, frame_view
from app.script import parse_pdf
from tools.build_samples import SAMPLES

SCREENPLAY = parse_pdf((SAMPLES / "the-red-kite.pdf").read_bytes())


def row(state: str, asset: str | None = None, withheld: str | None = None) -> FrameRow:
    return FrameRow(
        project_id=uuid.uuid4(),
        scene_index=1,
        shot_number=3,
        state=state,
        attempt=2,
        job_id=uuid.uuid4(),
        asset=asset,
        withheld_check=withheld,
        updated_at=datetime(2026, 10, 3, tzinfo=UTC),
    )


@pytest.mark.parametrize("state", ["passed", "warned"])
def test_an_accepted_frame_carries_its_signed_url(state: str) -> None:
    view = frame_view(row(state, asset="frames/abc.png"), SCREENPLAY, "https://signed/abc")
    assert view.shot_id == f"{SCREENPLAY.scenes[1].number}.3"
    assert (view.state, view.attempt, view.max_renders) == (state, 2, MAX_RENDERS)
    assert view.image_url == "https://signed/abc" and view.audits == []


@pytest.mark.parametrize("state", ["rendering", "auditing", "withheld", "failed"])
def test_no_other_state_ever_has_an_image(state: str) -> None:
    view = frame_view(
        row(state, withheld="unscripted_person" if state == "withheld" else None), SCREENPLAY, None
    )
    assert view.image_url is None
    assert view.withheld_check == ("unscripted_person" if state == "withheld" else None)


def test_max_renders_is_verify_mds_three() -> None:
    assert MAX_RENDERS == 3


def test_max_renders_grows_with_a_users_extra_attempt() -> None:
    late = row("rendering")
    late.attempt = 5
    assert frame_view(late, SCREENPLAY, None).max_renders == 5
