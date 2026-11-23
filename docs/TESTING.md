# Testing

Run Router commands from `router/`. The unit suite runs offline.

## Before every commit

Run the four checks that AGENTS.md section 5
and the set-up section of CONTRIBUTING.md name:

```sh
python3.14 tools/plugin_verification.py --base origin/development --run
python3.14 -m compileall -q ai_router tools tests packaging
python3.14 tools/check_source_limits.py
python3.14 tools/check_policy_scans.py
```

The selector runs the full core suite unless every change qualifies for the
narrow plugin documentation path. Installer tests are opt-in with
`SCG_RUN_INSTALLER_TESTS=1`. Before a beta tag that changes `packaging/`, run
them as [releasing](release/releasing.md#how-to-test-first) describes.

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

Live probes run separately from the unit suite, use synthetic task data and
keep hard caps on call count and spend. See
bounded live regression probes (AGENTS.md section 5)
and the compatibility rule (AGENTS.md section 7).
