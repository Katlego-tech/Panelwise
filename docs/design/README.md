# Design documents

One per non-trivial lane, named after it, so `feat/<lane>` <-> `docs/design/<lane>.md`.
Start from [DESIGN-DOC.template.md](../../DESIGN-DOC.template.md); rules and the
which-diagram-when table are in [../design-documentation.md](../design-documentation.md).

Diagrams are **Mermaid in fenced code blocks**, never images -- they diff in a PR and every
assistant can read and write them.

| Lane | Doc | Status | Covers |
| --- | --- | --- | --- |
| `llm` | [llm.md](llm.md) | agreed | class, sequence (retry + repair), contracts, settings |
| `script+grounding` | [script.md](script.md) | agreed | class (scenes, elements, spans), parse sequence + classification rules, contracts |
| `script+grounding` | [grounding.md](grounding.md) | agreed | class (entities, quotes, report), extraction + filter sequence, faithfulness/recall, contracts |
