"""What the describer and the judge are told. docs/design/verify.md §3.

The describer never sees the shot: told what to expect, it would agree. The judge sees the shot's
grounded spec and the description, never the image, and may only call and quote.
"""

from app.grounding import EntityKind, Extraction
from app.script import Scene
from app.shots import Shot
from app.verify.schema import FrameDescription

DESCRIBE_PROMPT = (
    "Describe this image exactly as it is. Report only what is visible; never guess a story or "
    "name anyone. List every person you can see, including anyone partly visible or in the "
    "background, with where they stand (the left, centre or right third of the image) and a "
    "short phrase for what they look like. Say whether the scene is interior or exterior, and "
    "its light: day, night, dawn_or_dusk, or unclear. Give the shot size: wide (whole bodies "
    "and their surroundings), medium (people from the waist up), close (a head and shoulders) "
    "or extreme_close (part of a face, or one object filling the frame). List every notable "
    "object a viewer would notice, but not the walls, floor or sky themselves: each with a "
    "category from the list and whether someone in the image holds it. Set has_text to true if "
    "any letters, words, numbers or writing-like marks appear anywhere: on signs, screens, "
    "paper, clothing or anything else. When unsure, say unclear."
)

JUDGE_PROMPT = (
    "You check one storyboard frame against the screenplay. You are given the shot as the "
    "script writes it, and a description of the frame by someone who has not read the script. "
    "Call every described person and every described object exactly once, by its number.\n"
    "People: set `character` to the name from 'Characters in this shot' that the person is, or "
    "null if they are none of them. One character is at most one person. For a person who is "
    "no character, set `support` to a verbatim quote from the shot text or from a quote below "
    "that puts such a person there (for example 'a crowd gathers'), or null if nothing does.\n"
    "Objects: `scripted_prop` when the script puts it in this shot, with `support` a verbatim "
    "quote from the shot text or from a quote below that names it; `set_dressing` when it is an "
    "ordinary furnishing the location in the scene heading would hold, with `support` the "
    "heading's words for that location; `unscripted` otherwise.\n"
    "Quote exactly, never paraphrase. Anything you can't support with a quote is unscripted."
)


def _quoted(extraction: Extraction, kind: EntityKind, names: tuple[str, ...]) -> list[str]:
    lines: list[str] = []
    for name in names:
        entity = next((e for e in extraction.entities if e.kind is kind and e.name == name), None)
        quotes = "; ".join(f'"{q.text}"' for q in entity.quotes) if entity else ""
        lines.append(f"- {name}: {quotes}" if quotes else f"- {name}")
    return lines or ["- none"]


def render_spec(
    shot: Shot, scene: Scene, extraction: Extraction, description: FrameDescription
) -> str:
    lines = [
        f"Scene heading: {scene.heading}",
        f"Time of day: {shot.time_of_day or 'not stated'}",
        "",
        "Shot text:",
        shot.source,
        "",
        "Characters in this shot:",
        *_quoted(extraction, EntityKind.CHARACTER, shot.characters),
        "Props in this shot:",
        *_quoted(extraction, EntityKind.PROP, shot.props),
        "",
        "The frame, as described:",
        "People:",
        *(
            [f"[{i}] {p.position}: {p.appearance}" for i, p in enumerate(description.people)]
            or ["none"]
        ),
        "Objects:",
        *(
            [
                f"[{i}] {o.name} ({o.category}, {'held' if o.held else 'not held'})"
                for i, o in enumerate(description.objects)
            ]
            or ["none"]
        ),
    ]
    return "\n".join(lines)
