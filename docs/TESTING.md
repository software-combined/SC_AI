# Testing

Run Router commands from `router/`. The unit suite runs offline.

## Before every commit

Run all four checks. The shared selector runs the full core suite unless every
change qualifies for the narrow plugin documentation path:

```sh
python3.14 tools/plugin_verification.py --base origin/development --run
python3.14 -m compileall -q ai_router tools tests packaging
python3.14 tools/check_source_limits.py
python3.14 tools/check_policy_scans.py
```

For a scoped release based on `main`, use `--base origin/main`. Use the actual
integration base, never `HEAD` to hide committed changes. `--full --run` keeps
explicit full discovery available.

The narrow path permits Markdown skills and references in registered marketplace
plugins, `plugins/CHANGELOG.md`, and existing paired manifests whose only changed
field is `version`. It runs plugin, package, delivery and public-content contracts.
Strict Claude manifest validation and skill-creator validation
([agent plugins](plugins/agent-plugins.md#plugin-rules)) remain separate
required gates. Keep the secret scan and all four review lanes.

Mixed Router changes, executable plugin changes, unknown paths, policy or workflow
changes, deletions, renames, symlinks, mode changes and uncertain history retain
full verification. The selector examines committed, staged, unstaged and untracked
changes separately; opposing edits cannot cancel out of selection. Missing expected
plugin suites fail. This verification policy itself always requires full checks.

Then run the installed
[pre-commit-review skill](../plugins/development/scg-review/skills/pre-commit-review/SKILL.md).
Its [setup guide](../plugins/development/scg-review/skills/review-setup/SKILL.md) covers the
required hooks and scanner. Commit subjects use `<type>: <short summary>` with
type `feat`, `fix`, `refactor`, `test`, `chore` or `docs`.

## In continuous integration

Test discovery runs the fast core suite. Installer tests are opt-in with
`SCG_RUN_INSTALLER_TESTS=1`; native CI runners cover them on scope for release
pull requests into `main`. Before a beta tag that changes `packaging/`, run
them as [releasing](release/releasing.md#how-to-test-first) describes.

Development continuous integration (CI) runs fast static checks. Main
acceptance runs on pull requests into `main`, uses the same selector and
retains full remote regression outside the narrow plugin documentation path.
A push to `main` runs no second copy. The tag gates that reuse these runs are in
[releasing](release/releasing.md#how-to-ship). Local pre-commit requirements
still apply.

## Test layers

| Layer | Where it is described |
|---|---|
| Main acceptance and Windows standard-user acceptance | [Verification pipeline](release/ci-pipeline.md) |
| Native installer acceptance on each platform | [Acceptance matrix](release/native-installers.md#acceptance-matrix) |
| Captured Codex request shapes and replay goldens | [Verification after a Codex upgrade](release/compatibility.md#verification-after-a-codex-upgrade) |
| New model rows: offline conformance and the real-client probe | [Adding a model](models/adding-a-model.md) |
| Claude Code limits with a fake upstream | [Bounded Claude Code verification](clients/claude-code-reference.md#bounded-claude-code-verification) |
| Claude desktop probes | [Bounded desktop verification](clients/claude-desktop-limits.md#bounded-desktop-verification) |
| Media routes | [Media generation verification](models/media-generation.md#verification) |
| Context recovery | [Context recovery verification](clients/context-recovery.md#verification) |
| Client versions and the latest release checks | [Compatibility](release/compatibility.md) |

## Live probes

When a regression depends on real client or model behaviour that offline tests
cannot prove, add a separately invoked live probe using synthetic task data.
Paid probes are permitted when necessary for authorised work. Keep the unit
suite offline; require hard caps on call count and token or cost spend, and
never add unbounded retries.

Use the cheapest suitable model and low reasoning effort where supported.
Prefer Luna, DeepSeek Flash or GLM Flash; use Sonnet at low effort when the
Anthropic-specific contract needs it. Resolve current IDs and supported effort
from the catalogue; expand model coverage only for a demonstrated need.
Record the client version, requested model and effort, served identity when
exposed, call count, and result. Reuse passing evidence for unchanged paths;
rerun only after a relevant change or failure. These probe defaults do not
change explicit pre-commit model or effort requirements or waive the
[compatibility rule](release/compatibility.md#compatibility-rule).
