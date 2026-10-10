"""The default renderer: FLUX.2 [klein] 4B on Cloudflare Workers AI (storyboard.md §3.5; T026).

One multipart call per try, at about a megapixel in multiples of 16 (never a fifth billed tile),
fitted to exactly the size asked for and post-processed in the style. Every drawing is stored by its
render key before `render` returns, so the store is the cache and the record is there for the frame
writers. Workers AI's free allocation is 10,000 neurons a day; a drawing costs 104.2.
"""

import asyncio
import base64
import binascii
import io
import logging
import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, cast

import httpx2
from PIL import Image

from app.core.config import Settings
from app.frames.attempt import RendererFactory
from app.grounding import Extraction
from app.script import Screenplay
from app.shots import Shot
from app.storage import AssetStore
from app.storyboard.prompt import FramePrompt, PromptError, build_frame_prompt
from app.storyboard.render import RendererError, RenderQuotaExceeded, RenderRecord
from app.storyboard.styles import Style, StyleRegistry
from app.storyboard.workflow import fit, png_bytes, postprocess, render_key
from app.verify.model import RenderedFrame

log = logging.getLogger(__name__)

NATIVE_AREA = 1024 * 1024  # klein's native area: 4 billed 512 x 512 tiles
STEP = 16
DEFAULT_MODEL = "@cf/black-forest-labs/flux-2-klein-4b"
API_URL = "https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"
TRIES = 3  # one call and two retries (§3.5's table)

# Workers AI's error codes (§3.5)
REFUSED = 8007  # the NSFW filter refused the prompt; not deterministic, so retried
OUT_OF_CAPACITY = 3040
# The day's free neurons are used; resets 00:00 UTC. klein answers 4006 (live run, 2026-10-10);
# 3036 is the code Workers AI documents.
DAILY_ALLOCATION = frozenset({3036, 4006})


def draw_size(width: int, height: int) -> tuple[int, int]:
    """Scaled up or down to at most NATIVE_AREA at the same aspect, each side floored to a multiple
    of 16 and at least 16."""
    scale = math.sqrt(NATIVE_AREA / (width * height))
    return (
        max(STEP, int(width * scale) // STEP * STEP),
        max(STEP, int(height * scale) // STEP * STEP),
    )


def workers_ai_request(prompt: str, seed: int, draw: tuple[int, int]) -> dict[str, str]:
    """The four form fields (§3.5): a plain prompt (no weights, escapes or negative), the draw
    size and the seed."""
    return {"prompt": prompt, "width": str(draw[0]), "height": str(draw[1]), "seed": str(seed)}


@dataclass(frozen=True)
class WorkersAIAccount:
    account_id: str
    api_token: str = field(repr=False)  # never in a repr, a log line or a test failure
    model: str = DEFAULT_MODEL
    timeout_s: float = 120.0

    @classmethod
    def from_settings(cls, settings: Settings) -> WorkersAIAccount | None:
        """None unless both CLOUDFLARE_* are set."""
        if not (settings.cloudflare_account_id and settings.cloudflare_api_token):
            return None
        return cls(
            settings.cloudflare_account_id,
            settings.cloudflare_api_token,
            settings.render_model,
            settings.render_timeout_s,
        )

    def url(self) -> str:
        return API_URL.format(account=self.account_id, model=self.model)


class _Retry(Exception):
    """A try that another try may fix; `code` is Workers AI's, when it gave one."""

    def __init__(self, what: str, code: int | None = None) -> None:
        super().__init__(what)
        self.code = code


def _error(response: httpx2.Response) -> int | None:
    """Workers AI's first error code, from its JSON envelope when it has one."""
    try:
        body: Any = response.json()
        return int(body["errors"][0]["code"])
    except ValueError, TypeError, AttributeError, IndexError, KeyError:
        return None


def _finish(raw: bytes, width: int, height: int, style: Style) -> tuple[bytes, bool]:
    """CPU work, run in a thread: fitted and post-processed PNG, and whether it is all black."""
    image = postprocess(fit(raw, width, height), style.grayscale)
    _, brightest = image.convert("L").getextrema()
    return png_bytes(image), brightest == 0


class WorkersAIRenderer:
    """verify.md's RecordingRenderer on Workers AI, in one style, for one screenplay."""

    def __init__(
        self,
        *,
        style: Style,
        store: AssetStore,
        screenplay: Screenplay,
        extraction: Extraction,
        client: httpx2.AsyncClient,
        account: WorkersAIAccount,
        max_words: int = 120,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.style = style
        self.store = store
        self.screenplay = screenplay
        self.extraction = extraction
        self.client = client
        self.account = account
        self.max_words = max_words
        self.sleep = sleep
        self.records: dict[tuple[tuple[int, int], int], RenderRecord] = {}

    def record(self, shot: tuple[int, int], attempt: int) -> RenderRecord:
        return self.records[(shot, attempt)]

    async def render(
        self, shot: Shot, attempt: int, seed: int, width: int, height: int
    ) -> RenderedFrame:
        key = (shot.scene_index, shot.number)
        try:
            prompt = build_frame_prompt(
                shot, self.screenplay, self.extraction, self.style, max_words=self.max_words
            )
        except PromptError as exc:  # a style or budget problem: configuration, never a cut prompt
            raise RendererError(f"shot {key}: {exc}") from exc
        return await self.render_text(shot, attempt, seed, width, height, prompt.text(), prompt)

    async def render_text(
        self,
        shot: Shot,
        attempt: int,
        seed: int,
        width: int,
        height: int,
        text: str,
        prompt: FramePrompt,
    ) -> RenderedFrame:
        """`render` with the prompt's text given: the frame prompt's own, or T049's with one
        sentence injected (eval.md §6a.3). `prompt` is what the record keeps."""
        key = (shot.scene_index, shot.number)
        draw = draw_size(width, height)
        fields = workers_ai_request(text, seed, draw)
        step = "grayscale" if self.style.grayscale else "none"
        address = render_key({"model": self.account.model, "request": fields}, width, height, step)
        asset = f"frames/{address}.png"
        if await self.store.exists(asset):
            png = await self.store.get(asset)
            self.records[(key, attempt)] = RenderRecord(
                key, attempt, address, asset, prompt, True, None, None
            )
        else:
            started = time.perf_counter()
            png, neurons = await self._draw(fields, width, height)
            await self.store.put(asset, png, "image/png")
            seconds = time.perf_counter() - started
            self.records[(key, attempt)] = RenderRecord(
                key, attempt, address, asset, prompt, False, seconds, neurons
            )
            log.info(
                "drew shot %s attempt %d in %.1f s, %s neurons", key, attempt, seconds, neurons
            )
        return RenderedFrame(key, attempt, seed, png, width, height, text)

    async def _draw(
        self, fields: dict[str, str], width: int, height: int
    ) -> tuple[bytes, float | None]:
        """Up to TRIES tries (§3.5's table): the fitted PNG and the neurons it cost."""
        last: _Retry | None = None
        for tried in range(TRIES):
            if tried:
                await self.sleep(float(tried))  # 1 s, then 2 s
            try:
                raw, neurons = await self._try(fields)
                png, black = await asyncio.to_thread(_finish, raw, width, height, self.style)
                if black:  # the audit would pass it (T062): never stored, never audited
                    raise _Retry("an all-black drawing")
            except _Retry as retry:
                last = retry
                log.warning(
                    "Workers AI %s for %s (try %d of %d)",
                    retry,
                    self.account.model,
                    tried + 1,
                    TRIES,
                )
                continue
            return png, neurons
        assert last is not None
        if last.code == REFUSED:
            raise RendererError(
                f"Workers AI refused the prompt ({REFUSED}) for {self.account.model} "
                f"on all {TRIES} tries"
            )
        raise RendererError(
            f"Workers AI failed for {self.account.model} after {TRIES} tries ({last})"
        )

    async def _try(self, fields: dict[str, str]) -> tuple[bytes, float | None]:
        """One call. No message carries the token or the prompt."""
        try:
            response = await self.client.post(
                self.account.url(),
                headers={"Authorization": f"Bearer {self.account.api_token}"},
                files={name: (None, value) for name, value in fields.items()},
                timeout=self.account.timeout_s,
            )
        except httpx2.TransportError as exc:
            raise _Retry(type(exc).__name__) from exc
        status = response.status_code
        if status == 200:
            try:
                image: object = cast(dict[str, Any], response.json())["result"]["image"]
                raw = base64.b64decode(cast(str, image), validate=True)
                with Image.open(io.BytesIO(raw)) as decoded:
                    decoded.verify()
            except (ValueError, KeyError, TypeError, OSError, binascii.Error) as exc:
                raise _Retry("200 without a readable image") from exc
            neurons = response.headers.get("cf-ai-neurons")
            return raw, float(neurons) if neurons else None
        code = _error(response)
        if code in DAILY_ALLOCATION:
            raise RenderQuotaExceeded(
                f"the day's free Workers AI neurons are used ({code}); they reset at 00:00 UTC"
            )
        if status >= 500 or (status == 429 and code == OUT_OF_CAPACITY) or code == REFUSED:
            raise _Retry(f"{status}, code {code}", code)
        raise RendererError(f"Workers AI answered {status}, code {code}, for {self.account.model}")


def workers_ai_factory(
    registry: StyleRegistry,
    store: AssetStore,
    client: httpx2.AsyncClient,
    account: WorkersAIAccount,
    settings: Settings,
) -> RendererFactory:
    """A fresh renderer per job or attempt, in the registry's default style (§3.5)."""
    style = registry.get(None)

    def factory(screenplay: Screenplay, extraction: Extraction) -> WorkersAIRenderer:
        return WorkersAIRenderer(
            style=style,
            store=store,
            screenplay=screenplay,
            extraction=extraction,
            client=client,
            account=account,
            max_words=settings.render_max_words,
        )

    return factory
