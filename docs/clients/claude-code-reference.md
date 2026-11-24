# Claude Code reference

Details for the terminal client after [setup](claude-code.md).

## How discovery works

With `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=true` set, the client lists
the router models in its `/model` picker. Claude Code 2.1.x fetches
`GET <base>/v1/models` on startup and caches
it at `~/.claude/cache/gateway-models.json`; entries whose `id`
contains `claude` or `anthropic` appear as `From gateway` options.
Restart Claude Code after changing the base URL so it refetches.
`ANTHROPIC_AUTH_TOKEN` must stay unset for the fetch: when it is set
the CLI sends it as the listing credential, and the router answers the
listing from its local registry without needing any credential.

## Choosing a model

Select a model by its vendor, model and provider label in `/model`. Other
vendors use stable SCG gateway IDs (`claude/scg/<hash>`) so Desktop can list
them. Router resolves each ID to the registered provider model before access
checks and forwarding; only actual Claude models carry `anthropic_family_tier`.
Direct provider IDs remain valid for saved settings and terminal commands.
Unknown or removed SCG IDs and older `claude/<vendor>/<name>` IDs are refused.
Managed client rules still apply to gateway IDs; Router independently checks
the canonical model against its access policy and key availability.

Anthropic documents compatible gateways but does not support non-Claude
models through Claude Code. SCG compatibility needs verification against each
client version. Native Claude requests still forward the signed-in client's
own authentication unchanged.

## Attachment contract

The installer owns `ANTHROPIC_BASE_URL`,
`CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY` and `ENABLE_TOOL_SEARCH`.
It records previous values and restores them on detach. A conflicting
hand-managed setting refuses attachment. A legacy first-party override is
removed only when an existing receipt proves that the installer added it;
otherwise attachment refuses and asks the operator to review it.
`CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS` also refuses attachment because it
forces deferred loading off.
`ANTHROPIC_AUTH_TOKEN` and
`ANTHROPIC_API_KEY` must stay unset: either one overrides the subscription
bearer, so subscription requests would stop reaching Anthropic with the
client's own login and the listing fetch would present the wrong credential.
Without a Claude subscription the installer owns the placeholder token, the
default model, the effort and the four tier settings as well; a hand-set value
for any of them refuses attachment before anything is written.
The attach records the listing ids, display names and tiers it was told
about, and `--doctor` compares that snapshot with the live `GET /v1/models`;
a change shows up as `drift` with the added and removed ids, and `unknown`
when the receipt is unreadable or the router is not answering. The comparison is by listing id, so a
display-name or tier edit alone does not report drift. Restart Claude Code
after a listing change so the client refetches.

A launcher that only routes when the user types a different command (or a
wrapper script) was considered and rejected: an alias breaks a plain `claude`
invocation, and the external-router pattern of setting
`ANTHROPIC_AUTH_TOKEN` to a router secret is exactly what breaks subscription
passthrough, which requires the client's own credential to reach the router
untouched. The settings merge writes only owned keys and refuses a
hand-edited conflict instead of overwriting it.

## Behaviour and limits

- OpenRouter-bound requests reach OpenRouter's Anthropic-compatible
  endpoint unchanged except for the repairs below, so thinking blocks and
  `cache_control` keep full fidelity, and `count_tokens` follows the same
  split. The router gives each streamed `tool_use` a fresh client-visible ID.
  DeepSeek V4.1 Flash otherwise returns `call_0` for every tool call; Claude
  Code collapses duplicate IDs and keeps only one earlier `tool_result`, which
  makes later reads look empty. The same repair applies to top-level tool calls
  in non-streaming JSON; nested tool-shaped input and unknown fields stay
  unchanged. The external route also hides Read's `pages` argument.
  Claude Code rejects a blank page range on an ordinary text file, and models
  that fill every advertised argument otherwise retry the same read. PDF page
  ranges stay available on the subscription route.
  The `system` block carrying
  the client's own `x-anthropic-billing-header` line is dropped, because
  `anthropic/claude-fable-5.1` refuses any turn that carries it with HTTP
  400 and the line only matters to Anthropic's billing, which this route
  does not use. A thinking block that arrives with a signature but no
  thinking is dropped from the stream, because Claude Code throws away the
  whole answer when one follows it. The subscription route keeps both shapes
  byte-identical.
  `GET /v1/models` answers rows with `id`, `display_name`, and a Claude-only family tier from
  the local registry without touching the network; unknown paths answer
  404.
- Subscription requests forward the client's `Authorization` or
  `x-api-key` plus version and beta headers, minus hop headers. The
  router key never accompanies them. In `none` mode the passthrough is
  refused; OpenRouter models still serve.
- The Claude path relays the upstream stream, so `/health` `served_models`
  does not track it and no compaction endpoint exists for it.
- A routed row inherits whatever tools the client has loaded, but with
  deferred loading on it inherits only the names until a search releases one.
  OpenRouter implements no part of Anthropic's deferred-tool protocol, so the
  external route rewrites that one shape before forwarding it rather than
  relying on it being tolerated: the
  `DeferredToolPlaceholder` and the server-side search tool entry go, the
  `defer_loading` flag goes (the released definition is already in the same
  request's tool list, so the model keeps the tool), and a `tool_reference`
  content block becomes the plain text naming the tool it stood for, which
  keeps every `tool_use` and `tool_result` paired. The subscription route is
  left byte-identical. Without deferred loading a long connector list can
  still exceed a row's context window, and the session workaround is
  `--strict-mcp-config --mcp-config '{"mcpServers": {}}'`.
- Historical verification with earlier discovery IDs, 2026-09-21:
  Claude Code `2.1.223` completed a
  Read-tool round trip on all 18 advertised rows plus a subscription
  model, with those connector servers excluded. Before the two repairs
  above, `anthropic/claude-fable-5.1` refused every turn and
  `google/gemini-3.8-flash` returned an empty answer after its tool
  call. The Git history of `docs/release/compatibility.md` keeps the versions, the
  failures and the run.
- Historical deferred-tool verification with earlier discovery IDs,
  2026-09-22: a synthetic 700-tool MCP server,
  `z-ai/glm-5.3-flash`, Claude Code `2.1.223` and a router built from the
  working tree. Both legs passed; the deferred leg took three turns, meaning
  the search ran, the client released the tool and the model called it. The
  same two legs then passed against the installed release, unchanged, which
  is why the rewrite above is described as hardening: OpenRouter tolerates
  the raw shape today, and the routed path no longer depends on that. The
  shape the client sends is captured offline by
  `tools/capture_claude_shapes.py`, and the Git history of
  `docs/release/compatibility.md` keeps the run record, including the first,
  rate-limited control attempt.

### Bounded Claude Code verification

`tools/probe_claude_code.py --home <router-home>` drives the installed
`claude` binary against a running router, one Read-tool round trip per
advertised row, and reports the rows that failed. Each row gets a synthetic
marker file named for that model, connector MCP servers are excluded so the
request stays at the client's own tool set, and a row is never retried. A row
passes when the marker comes back in the answer, not only when it is the whole
answer: some rows narrate it, and that is a finished turn rather than a fault.
An empty or refused turn still fails. The probe leaves the caller's Claude
settings alone: it names the router in the client's private process environment
and never prints the loopback URL. The environment
matters: Claude Code lets its own environment override a settings file, and a
probe started from a Claude Code session inherits that session's first-party
`ANTHROPIC_BASE_URL`, which sent every turn to Anthropic on the user's own
login instead of the router under test. The client also runs with an empty
per-run config folder, so none of the owner's instructions, skills, plugins,
hooks, permissions or login apply, and it sends a synthetic bearer that
`PROBE_AUTH_TOKEN` can replace. The probe therefore covers routed rows; the
subscription leg of the AGENTS.md section 7 check runs as a real Claude Code
session with the owner's own login and settings, started from a terminal
rather than from inside another Claude Code session. `--deferred` adds the leg an attached client
actually runs: a synthetic MCP server advertising 700 stub tools. A pass requires
ToolSearch followed by the released tool, matching result IDs, no tool errors,
and the returned marker. An answer that only echoes the marker fails.
`--candidate <slug>` boots an isolated router from this working tree with a shared
12-attempt cap, 512 KiB input and 2,048 output tokens per attempt, then tears it
down. Repairs and replays consume that same cap. Pass `--models` to
narrow it, `--max-rows` to raise the cap, or `--json` for a machine-readable
report, and set `CLAUDE_BIN` to drive a different client binary. For the
multi-turn history check, `--read-count 2` makes two sequential synthetic
Read calls in the exact `probe-1.txt` then `probe-2.txt` order and requires
`--max-budget-usd` as a hard spend cap; it reports the
client version, requested and served model, effort, call count and result.
It also requires exactly one `tool_result` for each rewritten `tool_use` id,
so stale or duplicate result ids fail the gate.
The report labels served identity `matched`, `mismatched` or `unverified`;
a known mismatch fails the probe, while absent identity remains unverified.
Hashed listing aliases resolve to their registry upstream id before that
comparison, so a valid routed row is not rejected for using a client-safe
discovery id.
Budgeted runs accept exactly one row and one leg, so the cap cannot be
multiplied across models.

Both the probe and the zero-paid shape capture use a fresh empty client config
and remove inherited Claude routing, authentication, effort and retry variables.
Each client invocation limits agentic turns to three and output to 2,048 tokens;
an explicit effort overrides the parent's setting. SDK retries are disabled, but
Claude Code 2.1.284 still makes one separate recovery request after a 503. The
isolated router's attempt cap therefore remains the paid-call boundary; these
client settings alone are not a hard upstream-call cap on the installed router.

Verify the embedded client's limits separately, without calling a model:

```sh
SCG_TEST_CLAUDE_CLIENT=1 CLAUDE_BIN="<tested-client-path>" \
  python3.14 -m unittest tests.test_claude_client_limits -v
```

That check uses a local fake upstream and disposable history, tests turn and
output limits after resume, and measures the bounded 503 recovery. It is opt-in
and does not run an installed client during the ordinary unit suite. It does
not establish that the desktop app propagates the same settings.
