# Saved tool declarations after a model switch

Router 1.3.51 candidate checks, 11 November 2026 AEDT.
Clients remain Codex desktop `26.1103.60933` (build `25894`), bundled CLI
`0.167.0-alpha.3.2`, and Claude Code `2.1.318`, unchanged from Router 1.3.50.
The preceding unchanged-path compatibility evidence remains applicable,
including the unverified Codex ChatGPT-subscription leg.

The synthetic saved-tool reproducer rejected the legacy request with HTTP 400
and completed a tool call, result replay and final marker after projection:

| Requested model and effort | Requests | Provider-reported model | Result |
| --- | --- | --- | --- |
| `meta/muse-ember`, Low | 3 | `meta/muse-ember` | Passed |
| `google/gemini-4-carbon`, Low | 3 | `google/gemini-4-carbon` | Passed |

`tools/probe_duplicate_tools.py` caps each request at 32 KiB input and 2048
output tokens, without retries. The legacy comparison includes both repeated
tools and a saved native declaration block. Duplicate tools alone were accepted
by Muse; deduplication alone still failed while the native block remained.
Provider-reported effort was not exposed. These direct provider checks establish
candidate projection and replay, not installed delivery or existing-chat acceptance.

The real bundled Codex CLI also passed `tools/probe_history_switch.py` against
a simulated upstream. Its external-to-subscription-to-external sequence preserved
the synthetic history marker in three requests. Permanent rejection stopped after
one request, and transient failure recovered in two. No live model calls or
installed client changes occurred in that check.

Current and saved declarations merge by namespace and name before aliases are
assigned. Current schemas win; saved schemas can complete a schema-less declaration.
Promoted `additional_tools` blocks leave external input so native schemas cannot
bypass adaptation or the exposed-tool limit. Saved client history stays whole.
