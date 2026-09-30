# `storyboard`

One frame per shot, the style registry (public styles plus an optional private pack), and the storyboard PDF.
Design: [docs/design/storyboard.md](../../../../docs/design/storyboard.md).

- `styles.py` (T008): `load_styles` reads `styles/*.toml` and the private pack, and rejects a bad file at start-up.
- `prompt.py` (T008): `build_frame_prompt`, a pure function; every script part is tagged with the span it came from.
- `prompts.py` (T008): `uv run python -m app.storyboard.prompts <script.pdf> [--style KEY]` prints every shot's prompt, part by part, on the real account.
- The renderer and the storyboard job come with T026, the PDF with T027.
