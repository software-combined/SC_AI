# SC_AI architecture

SC_AI groups the local Router and reusable agent plugins in one repository.
`router/` owns runtime, installation, build, tests, and infrastructure.
`plugins/` owns the marketplace packages; `skills/manage-router` and the root
plugin manifests retain the separate `scg-openrouter` setup identity.
Shared guides live in `docs/`. Plugins define task instructions; provider
adapters and transport stay in Router. Plugins have their own release versions.

The Router builder includes shared plugins, licences, and guides while keeping
the installed flat layout. Source paths never become installed-state paths.
GitHub workflows run Router commands in `router/`; local action paths
resolve from the repository root. `.agents/plugins/marketplace.json` registers
the marketplace packages, and delivery generates the Claude marketplace
manifest in the local installed marketplace. Source builds work without
filesystem links. Installed Python module names, launch commands, plugin IDs,
preferences, keys and saved state keep their installed names.

The canonical source is `software-combined/SC_AI`. Evidence links point
to `software-combined/SC_AI_Router-archive`, the private archive of the
`software-combined/SC_AI_Router` source; reading it needs authorised access.
Router's local-marketplace migration recognises existing marketplace source
registrations.
A clone of `software-combined/SC_AI_Router` cannot fast-forward to this source,
because the histories differ. Keep local work and use a fresh clone; do not
force-reset an existing checkout.

## Router domain ownership

Paths below are relative to `router/` unless they name shared documentation.

Map of where new work goes; the [detailed pages](#detailed-pages) hold each
domain's module ownership. The dependency direction is inward:
leaves know nothing about their consumers. Verified against current source;
transitional owners name the plan that will move them.

`ai_router` is the shared runtime package for Codex and Claude. Codex uses the
Responses protocol adapter; Claude uses the Messages protocol adapter. Both
share the service, model registry and transport. Client-specific modules own
only their client's integration, not another router.

`auto_routing` owns the two adaptive OpenRouter identities and their automatic
effort projection. Both protocol adapters retain their normal tool and credential
boundaries. Evidence records the provider's selection separately from a fixed-model match.

The unused `codex_router` source import alias was removed after the 29 October
2026 consumer check. Repository source, available source checkouts, installed
scripts and indexed external code had no active imports of that package.
Release bundles already contained only `ai_router`.

The stable launcher still recognises actual older releases whose runtime is
named `codex_router`, so updates and rollback do not depend on the removed
source alias. Existing router-home paths, service and task identities, state
filenames, the `codex_router` logger and Windows task ownership markers stay
unchanged. These are installed compatibility identifiers, not runtime packages.

## Domains and direction

```
provider_defs (one definition per upstream, imports nothing) + errors,
redaction, sse, tool_merge, image_items, turn_budget, atomic_write, dialog_tool, state,
events, history_items (leaves: no module-level local imports; events' one
call-time state lookup is the only exception)
  ^
  |
registry / capabilities (model facts) + request_context (one request's
registry snapshot) + wire_shape (the learnt wire contract): stdlib plus the
provider table and registry only
  ^
  |
transport (Prepared, hop-header rules, raw stream, header relay) + upstream
(failure policy) + outcome / attempt_policy (terminal verdicts and sends) +
stream_errors / messages_events (classification) + stream_events / stream_attempt (frame kinds,
the uncommitted attempt) + stream_relay (one stream for relay.py): wire and
failure policy, consumed by the adapters below
  ^
  |
subscription_recovery -> subscription_discovery / subscription_catalogue + catalogue / models /
live_refresh / apply_catalogue (client projections and native discovery)
  |
tool_runs (the pairing model, on history_items alone) + agent_handoffs /
compaction / tool_adapter / tool_history / tool_aliases / discovered (request
normalization); external_history reads compaction's codec, never the reverse
decisions (typed-decision wire client, imports only provider_defs)
  |
jev_compaction (opt-in evidence selection, consumes decisions/compaction/tool_runs)
  |
outbound (pure Responses stages and Messages projections over the stages above)
+ rejected_repair (the Responses adapters' pure rejected-request repair proposals)
  |
providers (Responses adapters) + claude (Messages adapters)
  |
protocols (explicit method/path dispatch table; imports the adapters because
it selects one, and holds no policy of its own)
  |
ingress (auth/rebinding, body limits, GET routes, error shaping) + relay (upstream loop)
  |
router (HTTP control: drain/inflight and POST orchestration) + runtime (boot
composition: state, credentials, policy) + __main__ (process entry)
```

`events.py` owns the event log; only `router.py`, `ingress.py` and
`__main__.py` still import `runtime` (for the boot constants and the
handler's injected `log_event`), and nothing else under `ai_router/` does.
`tests/test_import_graph.py` is the enforcement, not this page.

## Detailed pages

- [Installation, setup and update ownership](architecture/installation.md)
- [Streams and request evidence](architecture/streams-and-evidence.md)
- [Handoffs and history](architecture/handoffs-and-history.md)
- [Client contract](architecture/clients.md)
- [Claude desktop attachment](architecture/claude-desktop-attachment.md)
- [Claude profiles and task sharing](architecture/claude-profiles.md)
- [Distribution](architecture/distribution.md)
- [Compaction](architecture/compaction.md)
- [Rules](RULES.md) for placing new code

## Transitional owners (do not entrench)

- `packaging/service.py` keeps the feed/state/cross-platform helpers
  (`health`, `wait_version`, `ensure_serving`, `install_lock`, `rotate_log`) and
  thin delegations for the installer's launchd bindings; the launchd
  rendering/reload half lives in `packaging/launchd.py` with the darwin backend
  (`packaging/platforms/darwin.py`), landed by Plan 103.
- `ai_router/providers.py` holds the Responses adapters and dispatch;
  `compaction_summary.py` owns bounded summary-model selection and requests;
  a key/region-matched availability snapshot gates summary disclosure before
  any history-bearing request; Jev is global-only and is skipped on regional
  routes, which use the region-bound summary path;
  the outgoing projection lives in `outbound.py`, failure policy in
  `upstream.py`, page markup in `setup_page.py`, shared transport in
  `transport.py`, and dispatch in `protocols/`.
- `ai_router/subscription_discovery.py` fetches Codex's native subscription
  catalogue; `subscription_catalogue.py` validates it and composes the
  effective roster without turning local configuration into entitlement data.
  `subscription_recovery.py` refreshes missing native membership before a
  resumed request is rejected, using the same account and client version.
  Concurrent requests share the refresh; external routes never use it.
  `ai_router/catalogue.py` + `models.py` + `live_refresh.py` share client
  projection duties through `model_metadata.py` (pure normalization) and
  `clients/` (capability projection, picker visibility); the served
  instruction text and its capped delegation roster live in the
  `model_instructions.py` leaf (Plan 154). Codex lists at most five
  `spawn_agent` model overrides, in catalogue order. The subscription
  roster comes first, so router models do not appear there. The served roster
  line tells routed sessions which ids they can still pass explicitly; an
  explicit router id routes normally unless company policy rejects it.
- Client activation lives in `packaging/codex_config.py`: the Codex block
  (its Switch Codex variants in `codex_switch_config.py`), picker
  preservation, the seeded startup model, the managed `[desktop]`
  preferences, guidance, and receipts. `--client none` runs the router
  service only and removes every client attachment when it installs a
  release; setup never disconnects an assistant otherwise. Absence of a client
  selection in legacy state means Codex. Subscription policy is per client:
  Responses follows `openai_mode`, Messages follows `anthropic_mode` when
  set, else the legacy `openai_mode` fallback.

## Acceptance gates are distinct

Source, packaged imports, native lifecycle, real-client tools, billing, and
release acceptance are different gates. Record client and OS evidence by
version; a global model tier never asserts every combination works.
