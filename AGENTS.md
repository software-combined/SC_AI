# SC_AI agent instructions

SC_AI holds SCG Router (`router/`), the `scg-agent-plugins` marketplace
(`plugins/`) and shared documentation (`docs/`). Run Router commands from
`router/`; plugin paths are repository-relative. The runtime needs Python 3.14+
and the standard library only. See [README.md](README.md) for setup.

## Always-on rules

- This repository is public. Never add secrets, credentials, personal or
  customer details, account identifiers, internal URLs or local user paths
  ([public repository rules](docs/RULES.md#public-repository-and-security)).
- Use one writable worktree per agent session, based on `development`. Never
  edit the primary checkout or push to `main` ([agent sessions](CONTRIBUTING.md#agent-sessions)).
- Never run `git reset --hard` or `git checkout --` without explicit approval.
- Read the installed `scg-ponytail:ponytail` skill in full before coding or
  reviewing code.
- Before each commit, run the [four checks](docs/TESTING.md#before-every-commit)
  and the installed `pre-commit-review` skill.

## Read first by task

| If the task touches | Read |
|---|---|
| Router code: where it goes and which way imports point | [Architecture](docs/ARCHITECTURE.md), [Rules](docs/RULES.md) |
| A recurring code pattern | [Patterns](docs/PATTERNS.md) |
| A route, provider, error or the command line | [API](docs/API.md) |
| A dialog, page or menu people see | [UI and UX](docs/UI-UX.md) |
| Files or records the router keeps | [Data](docs/DATA.md) |
| A standing product decision | [Product decisions](docs/DESIGN.md) |
| Tests, CI or live probes | [Testing](docs/TESTING.md) |
| A model row or its picker label | [Adding a model](docs/models/adding-a-model.md), [Model naming](docs/models/naming.md) |
| Branches, commits and pull requests | [Contributing](CONTRIBUTING.md) |
| A release, version or changelog | [Releasing](docs/release/releasing.md) |
| A Codex or Claude Code upgrade | [Compatibility](docs/release/compatibility.md#compatibility-rule) |
| A plugin or skill under `plugins/` | [Agent plugins](docs/plugins/agent-plugins.md) |
| Anything else | [Documentation index](docs/README.md), [Glossary](docs/GLOSSARY.md) |
