"""The default renderer: FLUX.1 [schnell] on fal.ai (storyboard.md §3.5; T026).

One synchronous call per drawing, at most a megapixel in multiples of 16 (fal bills each started
megapixel), fitted to exactly the size asked for and post-processed in the style. Every drawing is
stored by its render key before `render` returns, so the store is the cache and the record is there
for the frame writers. A frame fal's safety checker blacks out never reaches the audit: it is drawn
again with a derived seed.
"""

import asyncio
import io
import logging
import math
import time
from collections.abc import Awaitable, Callable
from typing import Any, cast

import httpx2
from PIL import Image

from app.core.config import Settings
from app.frames.attempt import RendererFactory
from app.grounding import Extraction
from app.script import Screenplay
from app.shots import Shot
from app.storage import AssetStore
from app.storyboard.prompt import PromptError, build_frame_prompt
from app.storyboard.render import RendererError, RenderRecord
from app.storyboard.styles import Style, StyleRegistry
from app.storyboard.workflow import fit, png_bytes, postprocess, render_key
from app.verify.model import RenderedFrame

log = logging.getLogger(__name__)

MAX_PIXELS = 1_000_000  # fal bills each started megapixel: a drawing never starts a second
FAL_URL = "https://fal.run/{model}"
STEPS = 4  # FLUX.1 [schnell] is distilled for 1-4 steps
TRIES = 3  # one call and two retries on a 429, a 5xx or a network error
REDRAWS = 3  # the seed, then two derived seeds when the safety checker blacks a drawing out
GOLDEN = 0x9E3779B1  # spreads the derived seeds across the 32-bit range


def fal_draw_size(width: int, height: int) -> tuple[int, int]:
    """Scaled down (never up) to at most MAX_PIXELS, each side floored to a multiple of 16."""
    scale = min(1.0, math.sqrt(MAX_PIXELS / (width * height)))
    return max(16, int(width * scale) // 16 * 16), max(16, int(height * scale) // 16 * 16)


def fal_request(prompt: str, seed: int, draw: tuple[int, int]) -> dict[str, Any]:
    """The canonical body (§3.5): a plain prompt (no weights, escapes or negative), seed, PNG."""
    return {
        "prompt": prompt,
        "image_size": {"width": draw[0], "height": draw[1]},
        "seed": seed,
        "num_inference_steps": STEPS,
        "num_images": 1,
        "output_format": "png",
    }


def derived_seed(seed: int, redraw: int) -> int:
    return (seed + redraw * GOLDEN) % 2**32


class FalRenderer:
    """verify.md's RecordingRenderer on fal.ai, in one style, for one screenplay."""

    def __init__(
        self,
        *,
        style: Style,
        store: AssetStore,
        screenplay: Screenplay,
        extraction: Extraction,
        client: httpx2.AsyncClient,
        key: str,
        model: str = "fal-ai/flux/schnell",
        max_words: int = 55,
        timeout_s: float = 60.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.style = style
        self.store = store
        self.screenplay = screenplay
        self.extraction = extraction
        self.client = client
        self.key = key
        self.model = model
        self.max_words = max_words
        self.timeout_s = timeout_s
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
        text = prompt.text()
        draw = fal_draw_size(width, height)
        step = "grayscale" if self.style.grayscale else "none"
        started = time.perf_counter()
        for redraw in range(REDRAWS):
            drawn_seed = derived_seed(seed, redraw)
            body = fal_request(text, drawn_seed, draw)
            address = render_key({"model": self.model, "request": body}, width, height, step)
            path = f"frames/{address}.png"
            if await self.store.exists(path):  # stored drawings were never blacked out
                png, cached = await self.store.get(path), True
                break
            answer = await self._call(body)
            flags = answer.get("has_nsfw_concepts") or [False]
            if flags[0]:
                log.warning("fal.ai flagged shot %s attempt %d (redraw %d)", key, attempt, redraw)
                continue
            raw = await self._image(answer, draw)
            png = png_bytes(postprocess(fit(raw, width, height), self.style.grayscale))
            await self.store.put(path, png, "image/png")  # a content address: put is idempotent
            cached = False
            break
        else:
            raise RendererError("fal.ai's safety checker blocked every drawing of this shot")
        seconds = None if cached else time.perf_counter() - started
        self.records[(key, attempt)] = RenderRecord(
            key, attempt, address, path, prompt, cached, seconds
        )
        return RenderedFrame(key, attempt, drawn_seed, png, width, height, text)

    async def _call(self, body: dict[str, Any]) -> dict[str, Any]:
        response = await self._send("POST", FAL_URL.format(model=self.model), json=body)
        try:
            answer: object = response.json()
        except ValueError as exc:
            raise RendererError(f"fal.ai answered {self.model} with something not JSON") from exc
        if not isinstance(answer, dict):
            raise RendererError(f"fal.ai answered {self.model} with something not an object")
        return answer  # pyright: ignore[reportUnknownVariableType]

    async def _image(self, answer: dict[str, Any], draw: tuple[int, int]) -> bytes:
        images: object = answer.get("images")
        listed = cast(list[object], images) if isinstance(images, list) else []
        first: object = listed[0] if listed else None
        if not isinstance(first, dict) or not cast(dict[str, Any], first).get("url"):
            raise RendererError(f"fal.ai answered {self.model} with no image")
        image = cast(dict[str, Any], first)
        if (image.get("width"), image.get("height")) != draw:
            raise RendererError(
                f"fal.ai drew {image.get('width')} x {image.get('height')} for {self.model}, "
                f"not the {draw[0]} x {draw[1]} asked for"
            )
        raw = (await self._send("GET", str(image["url"]))).content
        try:
            with Image.open(io.BytesIO(raw)) as decoded:
                decoded.verify()
        except (OSError, ValueError) as exc:
            raise RendererError(f"fal.ai's image for {self.model} is not readable") from exc
        return raw

    async def _send(self, method: str, url: str, **kwargs: Any) -> httpx2.Response:
        """One request, retried twice on a network error, a 429 or a 5xx; any other failure at once.
        No message carries the key, the URL's query or the prompt."""
        headers = {"Authorization": f"Key {self.key}"} if method == "POST" else {}
        status: int | None = None
        for tried in range(TRIES):
            if tried:
                await self.sleep(float(tried))  # 1 s, then 2 s
            try:
                response = await self.client.request(
                    method, url, headers=headers, timeout=self.timeout_s, **kwargs
                )
            except httpx2.TransportError:
                status = None
                continue
            status = response.status_code
            if 200 <= status < 300:
                return response
            if status != 429 and status < 500:
                raise RendererError(f"fal.ai answered {status} for {self.model}")
        what = "no answer" if status is None else f"{status}"
        raise RendererError(f"fal.ai failed for {self.model} after {TRIES} tries ({what})")


def fal_factory(
    registry: StyleRegistry, store: AssetStore, client: httpx2.AsyncClient, settings: Settings
) -> RendererFactory:
    """A fresh renderer per job or attempt, in the registry's default style (§3.5)."""
    style = registry.get(None)

    def factory(screenplay: Screenplay, extraction: Extraction) -> FalRenderer:
        return FalRenderer(
            style=style,
            store=store,
            screenplay=screenplay,
            extraction=extraction,
            client=client,
            key=settings.fal_key,
            model=settings.fal_model,
            max_words=settings.comfyui_max_words,
            timeout_s=settings.fal_timeout_s,
        )

    return factory
