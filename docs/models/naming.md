# Model naming

How model rows are named in the picker, the client's model list. Paths are
relative to `router/`. To add a row, see [Adding a model](adding-a-model.md).

## Picker labels

Picker labels read `<Vendor>: <Model> <Version?>`, for example
`Z.ai: GLM 5.3 Flash`. The prefix always equals the row's `vendor` field, with
one redundant leading vendor word dropped: `DeepSeek: DeepSeek V4 ...` becomes
`DeepSeek: V4 ...`.

`display_name` is stored fully qualified with a ` · <Provider label>` suffix.
The built-in external provider uses ` · OpenRouter`, from
`provider_defs.label_for`.

## Pinned rows and aliases

The roster pins exact upstream ids, such as `anthropic/claude-opus-5.5` and
`google/gemini-3.8-flash`. A new version is a registry edit: add the new pinned
row and retire the superseded slug through `RETIRED_SLUGS`. Pinned rows keep any
version or snapshot token exactly as upstream writes it.

Add a tilde alias row only when the roster deliberately tracks upstream. It
tracks with `Latest`, never a pinned snapshot. Merge dated snapshots into a
tracking alias only when upstream actually serves the `~` id; never invent one.

## Checks

`models add` and `live_refresh` must produce conforming rows. The registry
naming test enforces this convention.
