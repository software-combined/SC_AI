# Compatibility

This page records the client versions the router is checked against and the
result of the latest release checks. After any Codex desktop or Claude Code
upgrade, follow the compatibility rule and replace the versions and results
below.

## Compatibility rule

After any Codex desktop or Claude Code upgrade, and before publishing a
release, run the paid probe from `tools/probe_codex_runtime.py` on one
OpenRouter model and one OpenAI model. Also run one OpenRouter model and one
subscription model through a real Claude Code session (see
[Claude Code reference](../clients/claude-code-reference.md)). Record both
client versions on this page.

## Current clients

| Client | Version |
| --- | --- |
| Codex desktop | Codex desktop `26.1120.41243` (build `30607`, bundled CLI `0.171.0-alpha.13.2`) |
| Claude Code | Claude Code `2.1.318` |

`tools/check_acceptance_ledger.py` reads the highest backticked version of each
client on this page. Keep the `Codex desktop` and `Claude Code` labels beside
each recorded version.

## Latest release checks

The Router 1.5.2 release candidate passed the OpenRouter checks below. The
subscription checks used the signed-in clients on the same machine. Each
route requested Low effort.

| Client and route | Model requested | Result |
| --- | --- | --- |
| Codex through OpenRouter | `deepseek/deepseek-v4.1-flash-1017` | Two upstream requests and one tool call. The final marker matched. |
| Codex through ChatGPT | `gpt-6-luna` | One tool call through the signed-in subscription. The final marker matched. |
| Claude Code through OpenRouter | `deepseek/deepseek-v4.1-flash-1017` | Two turns and one Read. The final marker matched. |
| Claude Code through its subscription | Sonnet | Two turns and one Read. The final marker matched. The client reported `claude-sonnet-5-5`. |

The Codex legs used `tools/probe_codex_runtime.py --effort low`. The
OpenRouter leg used an isolated custom-provider configuration. The ChatGPT
leg used `--live-home` through the installed Router 1.5.1 beta. The Claude
OpenRouter leg used `tools/probe_claude_code.py --candidate` with a 0.10 USD
cap. Both OpenRouter legs ran bounded candidate listeners. The Claude
subscription leg ran from a terminal.

The [acceptance ledger](acceptance-ledger.json) binds OpenRouter results to
the model and the Router runtime fingerprint.

## What these checks do not show

- Served effort is unverified on every route. Claude routes do not expose it.
- Provider reports name the model but do not attest model weights or
  reasoning compute.
- Probes use synthetic data and isolated listeners. They do not prove
  installed delivery, fleet uptake or desktop switching.
- Native desktop acceptance on each platform follows the
  [native acceptance matrix](native-installers.md#acceptance-matrix).
- AWS Bedrock rows have offline route checks only. They stay preview and
  unlisted until a bounded live probe passes for each row's protocol; see
  [adding a model](../models/adding-a-model.md).
- Auto Code and Auto Router report the provider's selection, which is not a
  fixed-model identity match. The checks do not cover multimodal input on
  those routes.

## Verification after a Codex upgrade

Capture what the new client sends before anything else:

```sh
python3.14 tools/capture_codex_shapes.py
```

It drives the installed app-server through a dynamic-tool turn, a model
switch and a V2 compaction against an in-process router and a fake
upstream, so it is free, makes no network call and reads no credential.
The sanitised request bodies land in
`tests/fixtures/replay/captured/<codex version>/`, and the drift report
lists the item types, top-level request fields and developer-message
openings added or removed since the newest earlier capture. Read that
report first and check the new files for personal paths or text (the
report compares only names), then commit the new directory;
`tests/test_switch_marker.py`
checks that the router still finds the switch marker in every capture.

Next, run the suite, then the base probe against the installed router and
confirm discovery, one exact callback, and the marker in the final
answer. If the app-server protocol changed, probes fail before any
user task does; do not ship model changes until the base probe passes.

`tests/test_replay_golden.py` pins the exact body each route sends for a
set of synthetic histories. Regenerating those goldens with
`REPLAY_GOLDEN_UPDATE=1` changes behaviour on purpose: explain the golden
diff in the PR, and in `CHANGELOG.md` when users see the change.
