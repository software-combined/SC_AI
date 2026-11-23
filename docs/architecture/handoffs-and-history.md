# Handoffs and history

Paths are relative to `router/ai_router/`. See the [architecture map](../ARCHITECTURE.md) for the module overview and dependency direction.

`agent_handoffs.py` owns readable handoff schemas and the per-call plaintext
marker. Codex delivers a brief as plaintext only when its call carries
`encrypted_function_args: []`. The ChatGPT subscription adapter asks the
install's credentials whether any external provider's key resolves; only then
can an external child exist, so only then are native briefs made readable.
Without such a key the request keeps Codex's stock encryption contract and
gains only lane hints. The native backend refuses a canonical
`collaboration.spawn_agent`, `send_message` or `followup_task` whose message is
not `encrypted: true`, so a keyed native request moves those three out of each
`collaboration` namespace into a `collaboration_plaintext` namespace placed
after it, as readable copies. This happens in Classic, Lite and discovered
declarations; the other collaboration tools stay, and an emptied namespace is
dropped. The model therefore sees one handoff surface, with nothing to choose.
A changed Lite prefix receives a stable content-based identity.
Each alias call returns to its canonical name with the marker, so Codex
executes the normal tool and saves canonical history. `handoff_history.py` owns
the handoff vocabulary, history parsing and model-visible replay projection.
On the next native Responses request, an explicitly readable historical call
uses the same alias as its current declaration. Arguments, call and item IDs,
encryption markers and outputs stay unchanged. The client's saved history is
never mutated. Encrypted, malformed or undeclared calls keep their original
namespace; compaction and installs without an external key keep their contract.
The host's developer `multi_agent_role` block can contain a direct-call example
using the canonical name. Its backtick-quoted `to=functions.collaboration` handoff
examples use the declared readable aliases too, so instructions and schemas agree.
Only that complete developer block is projected. User text, tool output, opaque
content and unrelated instructions retain their original bytes.
Captured spawn models still protect later follow-ups, including repeated
preparation of an already-projected request. Offered descriptions explain
this name conversion and direct native dispatch outside the exec-only `ALL_TOOLS`
catalogue. A returned child handle establishes acceptance, not review completion.
Ciphertext under an alias,
or an upstream encryption marker, is refused, never relabelled. A canonical
call to a readable declaration gets the marker unless its message matches the
backend ciphertext fingerprint; that call stays unmarked for the guard.
`handoff_response.py` applies those decisions to native Responses envelopes and
records bounded structural provenance through the shared event logger. Its
per-response call ordinals retain upstream ids only until that response closes.
Observation never grants plaintext authority or changes a handoff decision.
An encrypted handoff to an external recipient raises a typed response refusal
before an executable completed item is released. `relay.py` returns HTTP 400
before JSON headers or one terminal `invalid_prompt` event on an open stream.
It never replays the parent request or invents a tool result. Earlier valid
calls remain released. `tool_adapter.py` promotes developer Lite declarations
through its existing tool map. External upstreams accept readable canonical
schemas, so external projection rewrites them in place, including recalled
schemas, and its effective tool map after paging controls which calls receive
the marker.
`sse.py` owns shared event framing without provider-specific argument rewriting.
`standalone_outputs.py` owns app-injected output projection. External requests
project readable peer messages and standalone outputs into matched tool results.
A child-to-parent reply with readable text plus an encrypted sidecar is
projected with the readable text and an incompleteness warning; the sidecar is
withheld. Other opaque messages fail closed. Subscription replay changes only a
thread that switched model: it applies the switch boundary, then projects fully
readable agent messages, the shape external peers send. The backend reads
native encrypted replies and app-delivered outputs itself, so those stay
unchanged. Client history is never edited.
`history_portability.py` owns the model-switch boundary: a `developer` or
`system` message whose string content, or any of its text blocks, starts with
`<model_switch>` after leading whitespace marks a switch, and items before the
last marker were produced under another model. The marker names no model, so a
switch between two subscription models gets the same treatment as a switch off
OpenRouter.
`history_items.py` owns the history vocabulary more than one outbound stage
reads: the tool call and output families, the readable-text readers, the two
encrypted predicates and the readable agent-message predicates. The two
custom and discovery paths share its narrow `fc_` to `ctc_` or `tsc_` item ID repair:
response adaptation creates valid native items, and subscription projection heals saved
items without changing client history or the `call_id` linking each result.
The two predicates disagree on an empty marker: `has_encryption_marked_agent_item`
counts an `encrypted_content` marker whatever its value, while
`holds_encrypted_payload` needs a non-empty payload, and each call site keeps
its own. `tool_runs.py` owns the pairing model (`pairs`, `open_calls`) and the
fragment scrub, on `history_items` alone. Plan 183 moved these out of
`history_portability.py`, `compaction.py` and `agent_handoffs.py`; every
importer reads them from these two owners, and the old names are gone.
`compaction.py` owns compaction only: the prompt, the `ocx1:` codec, the V1
output and the summary transcript, including bounded native `apply_patch` and
tool-search call/result evidence. `external_history.py` owns the two external
stages that read that codec: compaction items replay as readable text
(`rewrite_input`), and OpenAI-owned reasoning blobs go (`strip_reasoning_blobs`,
which the subscription retry repair reuses). External Responses also drop
the contiguous reasoning suffix after blob stripping: Codex saves interrupted
reasoning before retrying, and an external upstream can reject that suffix as
assistant prefill. Subscription retry repair keeps its existing blob-only rule.
The
switch boundary's run check, the custom-pair call map and Jev's candidate
pairing keep their own id rules (any truthy id and any later output; the last
custom call; ambiguous ids pinned), so moving them onto `pairs` would be a
behaviour change with its own review, not part of the move.
`outbound.py` owns outgoing Responses and Messages projections (Plans 183/188).
Messages adapters call named external and subscription entrypoints. External
alias, billing-header and deferred-tool repairs copy only changed containers;
native Messages history returns unchanged, preserving the original wire body.
`EXTERNAL_STAGES` and `SUBSCRIPTION_STAGES` are tuples of named stages that
run in order over one `Projection`: the path, the client's model id, the
request's captured row, and what a later stage or the adapter reads back.
`tests/test_outbound.py` pins both orders, so a reorder is a visible edit. A
subscription compaction request runs only the two replay stages. The adapters
resolve the row, then keep destination, credentials, headers, body encoding
and the external turn-size fit. `outbound.contain` is the one opaque-brief
rule: the first external stage and `router.py`'s compaction guard (through the
`providers.reject_opaque_agent_items` name) both apply it.
`tool_adapter.prepare_tools(payload, row)` shapes the declarations only and
returns the tool list to send with the kind and wire-name maps.
The registry's `json_text_composition` profile envelopes root schema compositions
for upstreams that reject them. Plain object schemas and nested compositions stay native.
The model-cache overlay preserves the shipped profile for the same upstream target.
`tool_history.py` then rewrites the external tool history against them:
custom pairs, discovery listings, tool-search items, call renames and
`json_text` arguments, output annotations, then the model-switch boundary.
Neither looks a row up. Preparation never edits the client's payload (Plan 183
phase 3). Every stage and helper returns its result: the value it was given
when nothing changed, otherwise new lists with copies of only the items and
containers it changed. `agent_handoffs.native_handoffs` returns the payload
with the readable-handoff metadata, `hint_full_lanes` and `rewrite_tool_history`
return the payload, and `rewrite_custom_pairs` returns the items. The external
turn-size fit follows the same rule: `turn_budget.fit` returns
`(payload, stats)`, and its image and tool-output trims copy only the path to
each trimmed block, never the whole body. The original body stays whole, so
the helper fallback's twin or a second route prepares again from it
with the same bytes. `tests/test_outbound_purity.py` pins this against every
replay fixture on both routes, the native-then-twin sequence and both trims.
Native passthrough still forwards the client's own bytes when nothing
changed.
`subscription_history.py` owns the pure outgoing projection of replayed
reasoning and the router's own non-empty, structurally valid `ocx1:` compaction
summary (sent as readable text) for subscription Responses requests; it never
edits persisted client history. Opaque, malformed, or mixed encrypted native
compaction data is preserved and never becomes a repair target.
`rejected_repair.py` owns the Responses adapters' rejected-request repair
(Plan 183 step 2.5). Each adapter's `repair_rejected(prepared, described, raw)`
proposes at most one repaired `Prepared` for the one rejection it can justify:
the external annotation strip for an OpenRouter 400 that names no cause, and
the subscription `invalid_encrypted_content` repair of reasoning blobs and the
router's non-empty, structurally valid compaction summary. Opaque, malformed,
or mixed encrypted native compaction data makes the proposal ineligible. None
means ineligible and a proposal without a body means unchanged. A proposal
opens no connection, reads no response, logs
nothing and never retries. `strip_retry.py` keeps the `annotation_retry`
lines and asks `attempt_policy.Ledger` for the one repair send. The Messages
adapters propose no repair.
Codex desktop can send the ChatGPT-specific `access_programs` field with a
fresh task. `ExternalResponsesProvider.prepare` removes it before dispatch, and
`SubscriptionProvider.prepare` keeps it; the model, reasoning effort, tool
declarations and tool-result history stay unchanged. The annotation retry is
bounded to one additional dispatch. Its `annotation_retry` event records
`eligible`, `attempted` and `outcome` (`ineligible`, `unchanged`, `started`,
`accepted`, `rejected` or `transport_error`). Rejections include status and
bounded classification metadata. `accepted` means HTTP acceptance only; the
normal stream outcome and client acceptance probe establish completion. A
rejected retry follows the ordinary failure policy, including credit,
authentication and context handling. Deterministic refusals are cached
against the original request.
`context_recovery.py` adds fixed recovery guidance for client-declared context
resets on either Responses route, finding the `<context_window>` message by the
same rule. Codex owns saved history and executes its
retrieval tools; the router stores no assignment or transcript cache.
It also owns the exact legacy paragraph migration used by catalogue upgrades.
