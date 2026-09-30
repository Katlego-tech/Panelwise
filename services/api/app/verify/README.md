# `verify`

Frame audit: a vision model (DeepSeek-V4.1-Flash on Token Factory) describes each rendered frame without seeing the shot; Nemotron judges the description against the shot's grounded spec; code runs the checks and gives the verdict. Re-render on failure and the audit log are T021. Design: [docs/design/verify.md](../../../../docs/design/verify.md).

Live check: `uv run python -m app.verify.run <script.pdf> <scene>.<shot> <frame.png>`.
