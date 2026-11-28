# Agent plugins

This repo hosts the `scg-agent-plugins` marketplace. Browse
[plugins and skills by domain](../../plugins/README.md) for sales, development,
finance, operations, customer success, support, documentation and agent tools.
Every plugin works in Codex and Claude Code.

Plugin source lives under `plugins/<domain>/<plugin-name>/`. Department briefs
share the agent plugin and are linked from their domain pages. Installed plugin
names, skill names and client paths stay the same.

The router is the delivery channel. Its release bundle carries the plugin
trees, and each install or scheduled update that lands a new release
materialises a router-owned local marketplace and registers it with the
attached clients, so on a router host the plugins arrive and refresh with the
router and need no Git account, GitHub access or marketplace command. On Windows,
updates also find Codex in the app's own CLI directories under `%LOCALAPPDATA%`,
even when those directories are missing from the scheduled job's PATH. Once
Codex runs from that copy, the same pass retires any earlier Git-backed plugin
runner it recognises, with its macOS LaunchAgent or Linux systemd timer, since
that runner only ever refreshes Codex. A refused Linux scheduler operation
keeps the old files and reports retirement as pending, so a later install can
retry. A host without the router can still install the plugins from the Git
marketplace:

```sh
codex plugin marketplace add software-combined/SC_AI --ref main
codex plugin add scg-ponytail@scg-agent-plugins
codex plugin add scg-review@scg-agent-plugins
codex plugin add scg-optimise-ci@scg-agent-plugins
codex plugin add scg-codebase-readiness@scg-agent-plugins
```

SCG Review uses the single `scg-ponytail:ponytail` skill for its simplifier
and every review lane. Install Ponytail before Review; a missing, disabled or
unreadable Ponytail blocks the review. Claude Code users install the same
dependency with `claude plugin install scg-ponytail@scg-agent-plugins` before
installing or updating `scg-review`. Client inventories resolve the installed
skill path, so a cache version is never part of the instructions. Plugin caches
are delivery copies; the authored skill lives in this repository.

SCG Review is model agnostic. Each user sets preferred reviewer models and
fallbacks in their local Git hook configuration; see
[reviewer preferences](../../plugins/development/scg-review/references/setup.md#reviewer-preferences).
The shared skill keeps the same review and secret-scanning gates.

Installing the router later moves that Codex registration to the router's own
copy. Router updates refresh enabled plugins in both clients. A plugin you
turned off in Codex or Claude Code stays off.

Router hosts receive a plugin change with the next Router release
([versions and changelogs](../release/releasing.md#versions-and-changelogs)).

Small skill and reference updates use the shared
[`plugin_verification.py`](../../router/tools/plugin_verification.py) entry point locally
and in CI. It prints the comparison base, changed paths, selected suites and
reason. The narrow path keeps plugin contracts, paired manifests, public-content
checks and packaged delivery tests. Strict manifest and skill validation,
secret scans and independent reviews remain required.

Executable plugin changes and uncertain or mixed scope retain full Router tests.
Changes to the selector or its workflow wiring also require full verification;
the policy cannot exempt its own update. See
[testing](../TESTING.md#before-every-commit) for commands.

## Plugin rules

Author under `plugins/<domain>/<name>` and link skills from their
[domain page](../../plugins/README.md). The root `scg-openrouter` plugin stays
outside the marketplace. Keep the marketplace name and plugin names stable.

Before coding or reviewing code, read the installed
[`scg-ponytail:ponytail` skill](../../plugins/development/scg-ponytail/skills/ponytail/SKILL.md)
in full. Resolve its current absolute path from the active client's skill
catalogue or plugin inventory; never pin a cache version. Ponytail owns
solution simplicity; the repository rules and the review skill keep all
verification gates.

- Every plugin works in Codex and Claude Code: ship both `.codex-plugin` and
  `.claude-plugin` manifests at the same version, keep skill content
  client-agnostic, and read system state through whichever MCP or connector
  tools the active client exposes.
- Shipped plugins carry no updater of their own. Keep the retained
  `scripts/updater.py` and `scheduling.py` byte-identical across the plugins
  (tests pin it); the release bundle withholds them. Link every skill to its
  shared update guide.
- Release a plugin by bumping both manifests' version and adding a
  `plugins/CHANGELOG.md` entry. Validate Claude manifests and skills with
  `claude plugin validate --strict`, run the installed skill-creator's
  `scripts/quick_validate.py` for a new or changed skill, and run the plugin
  test modules for paired Codex/Claude manifests and package contracts.
  Require actual Codex installation and skill availability in a new session
  before claiming local delivery.

## Scoped plugin release to main

Integrate plugin fixes through `development` first. If `development` contains
unrelated unreleased Router changes, reuse the owned worktree for a release
branch based on current `main` and cherry-pick only the reviewed plugin
commits. The release pull request targets `main`. Its diff may contain only
`plugins/`, directly related plugin verification tests, marketplace
registration in `.agents/plugins/marketplace.json`, the README's agent-plugin
documentation, and directly related plugin-release instructions on this page.

Plugin verification-policy updates may also promote only
`tools/plugin_verification.py`, `.github/workflows/check.yml`, their regression
tests, `CONTRIBUTING.md`, `docs/ARCHITECTURE.md` and this page through this
scoped procedure. These policy changes require full verification.

Verify the complete diff against current `main`, run all required checks and
reviews on that exact candidate, and use the normal pull-request gates. Do not
include Router code, `packaging/VERSION`, Router tags or release-workflow
changes. Reconcile the release into `development` afterwards without
discarding either side.
