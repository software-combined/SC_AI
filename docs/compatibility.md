# Compatibility

This page records the client versions the router is checked against and the
result of the latest release checks. After any Codex desktop or Claude Code
upgrade, run the compatibility checks in the repository's `AGENTS.md`
section 7 and replace the versions and results below.

## Current clients

| Client | Version |
| --- | --- |
| Codex desktop | Codex desktop `26.1117.41037` (build `29803`, bundled CLI `0.171.0-alpha.13`) |
| Claude Code | Claude Code `2.1.318` |

`tools/check_acceptance_ledger.py` reads the highest backticked version of each
client on this page. Keep the `Codex desktop` and `Claude Code` labels beside
each recorded version.

## Latest release checks

Router 1.3.65 passed these checks with the clients above. Each route requested
Low effort.

| Client and route | Model requested | Result |
| --- | --- | --- |
| Codex picker | None (metadata only) | Native and OpenRouter models listed. |
| Codex through OpenRouter | `deepseek/deepseek-v4.1-flash-1017` | Two upstream requests, one tool call; final message passed. |
| Codex through ChatGPT | `gpt-6-luna` | Two upstream requests, one tool call, with the signed-in subscription. |
| Claude Code through OpenRouter | `deepseek/deepseek-v4.1-flash-1017` | Three turns, two sequential Reads; final marker passed. |
| Claude Code through its subscription | Sonnet | Two turns, one Read; exact marker returned. The client reported `claude-sonnet-5-5`. |

The picker check used `tools/probe_model_discovery.py` with zero inference
calls. The Codex legs used `tools/probe_codex_runtime.py --effort low`. The
Claude OpenRouter leg used `tools/probe_claude_code.py --candidate` with a
0.10 USD cap. Both OpenRouter legs ran an isolated candidate listener; the
ChatGPT leg used `--live-home` through the installed router. The Claude
subscription leg ran as a real session from a terminal.

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
  [adding a model](adding-a-model.md).
- Auto Code and Auto Router report the provider's selection, which is not a
  fixed-model identity match. The checks do not cover multimodal input on
  those routes.
