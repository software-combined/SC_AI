# Glossary

Terms these pages use, with the page that defines each one.

| Term | Meaning |
|---|---|
| Router home | The router's state directory, `~/.codex/mixed-model-router` by default; `ROUTER_HOME` overrides it. See [data](DATA.md). |
| Path token | The token in the path of the router's loopback URL. It is unique to each installation. See [API](API.md). |
| Responses protocol | The wire protocol Codex uses. See [architecture](ARCHITECTURE.md). |
| Messages protocol | The wire protocol Claude uses. See [architecture](ARCHITECTURE.md). |
| Registry | The model rows. Live model metadata refreshes weekly into it. See [product decisions](DESIGN.md). |
| Catalogue | A generated snapshot from the registry that the client's model picker reads. See [product decisions](DESIGN.md). |
| Picker | The client's model list. Labels read `<Vendor>: <Model> <Version?>`. See [model naming](models/naming.md). |
| Subscription row | A picker row served by the person's ChatGPT or Claude subscription. See [product decisions](DESIGN.md). |
| OpenRouter twin | The OpenRouter-billed row listed beside a subscription row. See [product decisions](DESIGN.md). |
| Preview tier | A new model row lands as `tier: preview` and `listed: false` until its probe passes. See [adding a model](models/adding-a-model.md). |
| Receipt | The record of what setup attached and the original values it replaced, kept in `activation.json`. See [installation ownership](architecture/installation.md) and [data](DATA.md). |
| Switch Codex | Changes Codex between its ChatGPT connection and an OpenRouter connection through the router. See [Codex](clients/codex.md#switch-codex). |
| First-party and third-party mode | The Claude desktop app's two connection modes, kept in separate profiles. See [Claude desktop limits](clients/claude-desktop-limits.md). |
| Beta and Express | Release tags: `-beta` marks a pre-release and `-express` an urgent release. See [releasing](release/releasing.md#how-to-ship) and [updates](operations/updates.md#express-updates). |
| Main acceptance | The full verification that runs on pull requests into `main`. See [verification pipeline](release/ci-pipeline.md). |
| Acceptance ledger | `release/acceptance-ledger.json`, one object per acceptance cell run. See [compatibility](release/compatibility.md). |
| Jev | The opt-in compaction evidence consumer. It sends selected history text to TypeSafe. See [compaction](architecture/compaction.md). |
