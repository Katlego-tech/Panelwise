"""T026: the Workers AI renderer (storyboard.md §3.5, §9). A scripted Workers AI over
httpx2.MockTransport, an in-memory store, the self-written lighthouse script. No network."""

import base64
import io
import logging
from typing import Any

import httpx2
import pytest
from PIL import Image
from pydantic import ValidationError

from app.core.config import Settings
from app.grounding import Extraction
from app.script import Screenplay, parse_text
from app.storyboard import StyleRegistry
from app.storyboard.render import RendererError, RenderQuotaExceeded
from app.storyboard.workers_ai import (
    DEFAULT_MODEL,
    NATIVE_AREA,
    WorkersAIAccount,
    WorkersAIRenderer,
    draw_size,
    workers_ai_factory,
    workers_ai_request,
)
from app.storyboard.workflow import fit, postprocess, render_key
from tests.fakes import MemoryStore
from tests.script.conftest import two_page_text
from tests.storyboard.conftest import STYLE, extraction_of, shot_of

TOKEN = "cf-secret-token"
ACCOUNT = WorkersAIAccount("acct", TOKEN)
URL = f"https://api.cloudflare.com/client/v4/accounts/acct/ai/run/{DEFAULT_MODEL}"


def jpeg(width: int, height: int, shade: int = 90) -> bytes:
    out = io.BytesIO()
    colour = (0, 0, 0) if shade == 0 else (shade, shade + 20, shade + 40)
    Image.new("RGB", (width, height), colour).save(out, format="JPEG")
    return out.getvalue()


def form(request: httpx2.Request) -> dict[str, str]:
    """The multipart body's fields, as Workers AI reads them."""
    body = request.content.decode()
    boundary = request.headers["content-type"].split("boundary=")[1]
    fields: dict[str, str] = {}
    for part in body.split(f"--{boundary}")[1:-1]:
        head, value = part.strip("\r\n").split("\r\n\r\n", 1)
        fields[head.split('name="')[1].split('"')[0]] = value
    return fields


class WorkersAI:
    """Workers AI as the renderer sees it: a POST answers a base64 JPEG at the size asked, plus
    the cf-ai-neurons header. `answers` scripts the next ones as (status, code); every request is
    kept."""

    def __init__(self) -> None:
        self.posts: list[httpx2.Request] = []
        self.answers: list[tuple[int, int | None]] = []
        self.network_errors = 0
        self.blacks: list[bool] = []  # the next drawings come back all black
        self.unreadable = 0  # the next 200s carry no decodable image

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.posts.append(request)
        if self.network_errors:
            self.network_errors -= 1
            raise httpx2.ConnectError("down", request=request)
        status, code = self.answers.pop(0) if self.answers else (200, None)
        if status != 200:
            return httpx2.Response(
                status, json={"success": False, "errors": [{"code": code, "message": "no"}]}
            )
        if self.unreadable:
            self.unreadable -= 1
            return httpx2.Response(200, json={"result": {"image": "bm90IGFuIGltYWdl"}})
        fields = form(request)
        black = self.blacks.pop(0) if self.blacks else False
        image = jpeg(int(fields["width"]), int(fields["height"]), shade=0 if black else 90)
        return httpx2.Response(
            200,
            json={"result": {"image": base64.b64encode(image).decode()}},
            headers={"cf-ai-neurons": "104.20"},
        )


@pytest.fixture
def lighthouse() -> Screenplay:
    return parse_text(*two_page_text())


@pytest.fixture
def cast(lighthouse: Screenplay) -> Extraction:
    return extraction_of(lighthouse, [("NANDI", "NANDI (60s, oilskin coat)")])


@pytest.fixture
def ai() -> WorkersAI:
    return WorkersAI()


@pytest.fixture
def slept() -> list[float]:
    return []


def renderer(
    ai: WorkersAI,
    store: MemoryStore,
    screenplay: Screenplay,
    extraction: Extraction,
    slept: list[float],
) -> WorkersAIRenderer:
    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    return WorkersAIRenderer(
        style=STYLE,
        store=store,
        screenplay=screenplay,
        extraction=extraction,
        client=httpx2.AsyncClient(transport=httpx2.MockTransport(ai)),
        account=ACCOUNT,
        sleep=sleep,
    )


# --- sizes and the request ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("asked", "drawn"),
    [((1280, 720), (1360, 768)), ((1748, 986), (1360, 768)), ((930, 789), (1104, 928)),
     ((2000, 2000), (1024, 1024)), ((40, 30), (1168, 880))],
)  # fmt: skip
def test_a_drawing_is_about_a_megapixel_never_a_fifth_tile_and_in_sixteens(
    asked: tuple[int, int], drawn: tuple[int, int]
) -> None:
    assert draw_size(*asked) == drawn
    w, h = drawn
    assert w * h <= NATIVE_AREA and w % 16 == 0 and h % 16 == 0


def test_the_request_is_four_plain_fields() -> None:
    assert workers_ai_request("a person pours tea", 7, (1360, 768)) == {
        "prompt": "a person pours tea",
        "width": "1360",
        "height": "768",
        "seed": "7",
    }


def test_fit_makes_exactly_the_size_asked_for() -> None:
    assert fit(jpeg(1360, 768), 1748, 986).size == (1748, 986)
    assert fit(jpeg(1360, 768), 1280, 720).size == (1280, 720)
    assert postprocess(fit(jpeg(64, 64), 32, 32), grayscale=True).mode == "L"


# --- render ---------------------------------------------------------------------------------------


async def test_a_render_calls_workers_ai_once_and_stores_the_fitted_frame_before_returning(
    ai: WorkersAI, lighthouse: Screenplay, cast: Extraction, slept: list[float]
) -> None:
    store = MemoryStore()
    r = renderer(ai, store, lighthouse, cast, slept)
    shot = shot_of(lighthouse, 0, [0])
    frame = await r.render(shot, 1, 1234, 1748, 986)

    (post,) = ai.posts
    assert str(post.url) == URL
    assert post.headers["Authorization"] == f"Bearer {TOKEN}"
    assert post.headers["content-type"].startswith("multipart/form-data")
    fields = form(post)
    assert fields == workers_ai_request(frame.prompt, 1234, (1360, 768))
    # the script's own words, unescaped and unweighted (FLUX reads no ComfyUI syntax); no names
    assert "a person (60s, oilskin coat) pours tea" in frame.prompt
    assert r"\(" not in frame.prompt and ":1." not in frame.prompt and "NANDI" not in frame.prompt
    assert (frame.width, frame.height, frame.seed, frame.attempt) == (1748, 986, 1234, 1)
    assert Image.open(io.BytesIO(frame.png)).size == (1748, 986)

    record = r.record((0, 1), 1)
    key = render_key({"model": DEFAULT_MODEL, "request": fields}, 1748, 986, "grayscale")
    assert (record.key, record.asset, record.cached) == (key, f"frames/{key}.png", False)
    assert record.neurons == 104.2
    assert store.objects[record.asset] == (frame.png, "image/png")
    assert record.prompt.text() == frame.prompt and slept == []


async def test_a_stored_drawing_is_never_drawn_twice(
    ai: WorkersAI, lighthouse: Screenplay, cast: Extraction, slept: list[float]
) -> None:
    store = MemoryStore()
    shot = shot_of(lighthouse, 0, [0])
    first = await renderer(ai, store, lighthouse, cast, slept).render(shot, 1, 99, 1280, 720)
    again = renderer(ai, store, lighthouse, cast, slept)
    second = await again.render(shot, 1, 99, 1280, 720)
    assert len(ai.posts) == 1 and second.png == first.png
    record = again.record((0, 1), 1)
    assert record.cached and (record.seconds, record.neurons) == (None, None)


async def test_capacity_down_and_a_refusal_are_retried_a_bad_request_is_not(
    ai: WorkersAI, lighthouse: Screenplay, cast: Extraction, slept: list[float]
) -> None:
    shot = shot_of(lighthouse, 0, [0])
    ai.answers = [(429, 3040)]
    await renderer(ai, MemoryStore(), lighthouse, cast, slept).render(shot, 1, 1, 1280, 720)
    assert slept == [1.0] and len(ai.posts) == 2

    slept.clear()
    ai.answers = [(503, None), (502, None), (500, None)]
    with pytest.raises(RendererError, match="after 3 tries \\(500, code None\\)") as failed:
        await renderer(ai, MemoryStore(), lighthouse, cast, slept).render(shot, 1, 2, 1280, 720)
    assert slept == [1.0, 2.0]

    ai.answers = [(400, 8007)] * 3
    with pytest.raises(RendererError, match="refused the prompt \\(8007\\)") as refused:
        await renderer(ai, MemoryStore(), lighthouse, cast, slept).render(shot, 1, 3, 1280, 720)

    ai.answers = [(401, 10000)]
    posts = len(ai.posts)
    with pytest.raises(
        RendererError, match=f"answered 401, code 10000, for {DEFAULT_MODEL}"
    ) as bad:
        await renderer(ai, MemoryStore(), lighthouse, cast, slept).render(shot, 1, 4, 1280, 720)
    assert len(ai.posts) == posts + 1
    for error in (failed.value, refused.value, bad.value):  # never the token, never the script
        assert TOKEN not in str(error) and "pours" not in str(error)

    ai.network_errors = 3
    with pytest.raises(RendererError, match="ConnectError"):
        await renderer(ai, MemoryStore(), lighthouse, cast, slept).render(shot, 1, 5, 1280, 720)


@pytest.mark.parametrize("code", [3036, 4006])  # 4006: klein's answer in the live run
async def test_the_days_budget_spent_is_raised_at_once(
    ai: WorkersAI, lighthouse: Screenplay, cast: Extraction, slept: list[float], code: int
) -> None:
    ai.answers = [(429, code)]
    store = MemoryStore()
    with pytest.raises(RenderQuotaExceeded, match="00:00 UTC"):
        await renderer(ai, store, lighthouse, cast, slept).render(
            shot_of(lighthouse, 0, [0]), 1, 6, 1280, 720
        )
    assert len(ai.posts) == 1 and slept == [] and store.objects == {}


async def test_every_retry_is_logged_without_the_token_or_the_prompt(
    ai: WorkersAI,
    lighthouse: Screenplay,
    cast: Extraction,
    slept: list[float],
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="app.storyboard.workers_ai")
    ai.answers = [(503, None)]
    ai.network_errors = 1  # the first try; the 503 is the second
    await renderer(ai, MemoryStore(), lighthouse, cast, slept).render(
        shot_of(lighthouse, 0, [0]), 1, 7, 1280, 720
    )
    lines = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(lines) == 2
    assert "ConnectError" in lines[0] and "try 1 of 3" in lines[0] and DEFAULT_MODEL in lines[0]
    assert "503" in lines[1] and "try 2 of 3" in lines[1]
    assert all(TOKEN not in line and "pours" not in line for line in lines)


async def test_an_unreadable_or_all_black_drawing_is_retried_and_never_stored(
    ai: WorkersAI, lighthouse: Screenplay, cast: Extraction, slept: list[float]
) -> None:
    ai.unreadable = 1
    ai.blacks = [True]
    store = MemoryStore()
    frame = await renderer(ai, store, lighthouse, cast, slept).render(
        shot_of(lighthouse, 0, [0]), 1, 8, 1280, 720
    )
    assert len(ai.posts) == 3 and len(store.objects) == 1
    brightest = Image.open(io.BytesIO(frame.png)).convert("L").getextrema()[1]
    assert isinstance(brightest, int) and brightest > 0

    ai.blacks = [True, True, True]
    store = MemoryStore()
    with pytest.raises(RendererError, match="all-black"):
        await renderer(ai, store, lighthouse, cast, slept).render(
            shot_of(lighthouse, 0, [0]), 1, 9, 1280, 720
        )
    assert store.objects == {}


@pytest.mark.parametrize("value", [0, -1])
def test_a_concurrency_below_one_is_refused_at_startup(value: int) -> None:
    # Semaphore(0) would leave every shot waiting forever, silently (review of #91).
    with pytest.raises(ValidationError, match="render_concurrency"):
        Settings(render_concurrency=value)


def test_the_account_needs_both_credentials() -> None:
    def settings(**values: Any) -> Settings:  # never the developer's .env
        return Settings(_env_file=None, **values)  # pyright: ignore[reportCallIssue]

    assert WorkersAIAccount.from_settings(settings(cloudflare_account_id="a")) is None
    assert WorkersAIAccount.from_settings(settings(cloudflare_api_token="t")) is None
    both = settings(
        cloudflare_account_id="a", cloudflare_api_token="t", render_model="m", render_timeout_s=9
    )
    assert WorkersAIAccount.from_settings(both) == WorkersAIAccount("a", "t", "m", 9)
    assert "secret" not in repr(WorkersAIAccount("a", "secret"))  # nor in a failing test's output


def test_the_factory_makes_a_renderer_in_the_default_style(
    lighthouse: Screenplay, cast: Extraction
) -> None:
    registry = StyleRegistry({STYLE.key: STYLE}, STYLE.key)
    client = httpx2.AsyncClient()
    settings = Settings(render_max_words=40)
    made = workers_ai_factory(registry, MemoryStore(), client, ACCOUNT, settings)(lighthouse, cast)
    assert isinstance(made, WorkersAIRenderer)
    assert (made.style, made.account, made.max_words) == (STYLE, ACCOUNT, 40)
