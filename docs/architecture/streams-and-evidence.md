# Streams and request evidence

Paths are relative to `router/ai_router/`. See the [architecture map](../ARCHITECTURE.md) for the module overview and dependency direction.

`request_evidence.py` observes each ledger-owned send. Protocol parsers retain
bounded model, effort and endpoint reports with their source; the transport
observer measures actual reads while preserving bytes. A prior attempt's
identity never attests a later one. These records cannot authorize replay.
`inspect_requests.py` reads the existing rotated log without contacting a model
or loading credentials. Request outcomes and each attempt's observed ending
remain separate when recovery preserves an earlier terminal for the client.
Canonical Codex child and parent UUID headers bind the ledger to a child;
`inspect_requests` owns exact assignment-window lookup and retained-only
summaries. No agent names, turn metadata blobs or tool results are persisted.

`wire_shape.py` reads measured extra item types from the request's captured row.
The registry owns that profile; absence means unverified and never changes
what is forwarded. A model-family prefix cannot grant another row's evidence.
The route conformance suite enumerates all registry rows and provider-supported
protocols, including hidden rows. It exercises the real handler and common
request owners with simulated upstreams, plus discovered and future native
IDs. Native bytes and auth remain the native provider's contract.
The policy scan rejects literal model-name comparisons and prefix decisions in
runtime Python. Only the existing, exact discovery, picker and tracking-alias
predicates are exempt; preparation and recovery use capability data instead.

`candidate_evidence.py` owns content-free onboarding proof beside `candidate.py`.
It reads normalized registry capabilities, provider protocols and client IDs;
request handling never imports it. Git revision metadata is optional; source and
capability fingerprints remain required on machines without Git.
`models.py` promotes a new row only after
every advertised route passes offline conformance and a real-client probe
against unchanged source and capabilities. The ledger checker shares this
validator. `tools/probe_candidate.py` owns one isolated send budget across the
common transport and compaction summary boundaries. Repairs, replays and
summary retries all consume that cap.
This guard belongs to the probe process and never changes production limits.

`outcome.py` owns the terminal vocabulary. `attempt_policy.py` owns every send
and the one helper-fallback transition, deciding from `Outcome` and commitment
facts rather than metrics. Responses routes allow three, two and one sends;
the fallback gets one fresh route and cannot fall back again. `attempt_ledger`
reports bounded request, attempt and terminal facts.
The ledger captures routing facts before the first send. Each response attempt
also captures its protocol, operation, stream intent, body kind and encoding in
an immutable `transport.ResponseFormat`, held by `StreamRecord` and replaced on
replay. Parsing and terminal emission use these facts, so clearing or replacing
the diagnostic dictionary cannot change repair, replay or finalization.
`stream_errors.py` owns shared HTTP/SSE context-error classification and applies
it to external Responses terminal events after tool adaptation. It preserves
successful frames and records semantic failure separately from the HTTP status.
An unrecognised terminal error stays `unknown` and is never replayable.
The external Responses stream lifecycle (Plan 187) is shared by every model
on that protocol, and nothing in it reads a model name. `stream_errors.events`
parses each frame once and `stream_events.py` names its kind (setup,
reasoning, plumbing, answer, failure, completion, or opaque for anything it
cannot place), keeping the frame's original bytes. `stream_attempt.py` owns
the uncommitted attempt: one slot each for `response.created` and
`response.in_progress` in that order, one for a failure terminal without
output, and a shared 64 KiB budget for reasoning and data-less frames, so one
attempt retains at most three parser-capped frames plus that budget. Any frame
it refuses commits the attempt: the held frames go out in order, then that
frame. It also owns `replay_safe`, the request-level rule that a replay may
only follow a prepared body offering no tools or only client-run ones
(`function`, `custom`; preparation already turns client tool search and
namespaced tools into functions); a hosted tool such as `web_search`, or an
unknown type, may already have run upstream, so that request keeps the
provider's verdict. `stream_relay.py` owns one upstream stream for `relay.py`:
offering frames to the hold and recording what the client received by kind.
For a stream outside that normalized lifecycle, every upstream chunk is
forwarded unchanged. Only complete frames are observed as a sidecar, so an
encoded body or incomplete final frame cannot be delayed, rewritten or turned
into a router parsing failure.
The same Responses observer reads identity-encoded streaming turns whose
content type is absent or unrecognised, as current native Codex traffic can
use that representation. It preserves partial frames immediately and requires
a readable terminal to name the outcome. Unrecognised nonstream data and all
encoded data stay opaque and unknown. Responses and token-count JSON retain
their existing EOF rule; Messages JSON needs a readable message and stop reason.
`messages_events.py` owns both Messages routes' lifecycle observation. A valid
empty start followed by a final delta and stop distinguishes success, client
tool use, truncation, server-tool pause, refusal and context exhaustion.
Unknown endings remain unknown; documented overload errors are transient.
Signatures, redacted thinking and future events remain opaque. Native chunks
are forwarded immediately and the subscription route keeps one send.
External Messages generation may hold one validated empty start and one
failure terminal. The same ledger permits one transient stream replay, only
with client-owned `input_schema` tools or no tools. Tool, thinking, unknown
and signature frames commit; the compatibility repair emits an explicit
replay fence before holding a potentially removable thinking block. That
fence remains effective even when no wire bytes exist to flush. Setup slots
are protocol facts on the common event, not names interpreted by the hold.
Non-stream requests, token counting and HTTP errors gain no retry. `messages_errors.py` renders
the shared outcome as a native Claude error, including a truthful 5xx status
for temporary failures. A broken external stream ends with one Messages
error; native and encoded streams remain untouched.
`attempt_policy` decides and opens a safe replay. It replaces the uncommitted
attempt; a failed replay leaves its verdict to reach the client. These leaves
never dispatch or own credentials.
`wire_shape.py` owns the learnt upstream acceptance rules as data plus checks:
the tool call/output pairing rules the test fake also enforces, and every
other rule an incident taught, each with the route it binds, its level and its
evidence. It observes and never changes a request. Each body prepared for a
Responses turn is checked (not the helper-turn fallback twin, which is off
by default), a broken rule becomes one `wire_contract` log line, and a
refusal line carries the same facts beside the body's names and counts.
Enforcing a rule is a separate, evidence-backed change. Its call and output
families stay local rather than coming from `history_items`: they map only
the client-run calls that expect an output, including `computer_call_output`,
while the vocabulary's call set also holds server-side calls that never get
one, and the import would widen this layer.
`request_context.py` owns the request's one registry read (Plan 188).
A model refresh (`model_refresh.apply`) can swap the registry while a request
is in flight. So the protocol policy's `resolve` captures one read-only
slug-to-row snapshot before provider selection. It returns a frozen
`Resolved`: the request id, the resolved slug, its row and that snapshot.
Every later decision takes its row from `Resolved`, never from
`registry.by_slug`. That covers the owner, the upstream id, the protocol pair,
the tool and history quirks (`outbound`'s tool stages), effort
(`capabilities.check_row_effort`), images, the output cap, compaction budgets,
the Claude alias and the helper-fallback twin. The next request captures the
new registry. `Prepared.context` carries it to the relay, and the pending
fallback plan retargets it in place, so the twin keeps the same request id. A
native id with no registry row resolves with `row=None` and goes out as the
client spelled it. `request_started` and the final record share the
`request_id`. It is a random id, not derived from request content.
The readable-handoff metadata retains that same catalogue through response
adaptation. The encrypted spawn, send and follow-up guard resolves child models
from it, so a refresh cannot change an in-flight request's decision. Direct
helper callers without a request context capture once when creating it.
`codex_route.py` owns the switched Codex route. Switch Codex gives Codex a
provider entry that needs no OpenAI sign-in and sends `x-scg-codex-route`, so
that header marks the route; a missing credential cannot, because the normal
route may carry no Authorization header either. `subscription_fallback.prepare`
asks it about each request the ChatGPT subscription adapter would serve, before
anything is prepared or sent. Native service paths get the no-subscription
answers; every other request gets one final `invalid_prompt` refusal, which
`ingress.error` sends as a `response.failed` frame when the turn streams. The
refusal names the twin row only when the portco allowlist, the key's
availability snapshot and the Codex picker all admit it. `codex_helpers.py`
owns the bounded helper-source parser and bare Luna aliases. Before Responses
adapter selection, known metadata helpers on the switched route or an install
without a subscription resolve to the external Luna row. Normal model policy,
availability and credential checks still apply; a denied Luna never falls back
to Fable or the subscription. The normal subscription helper fallback stays opt-in.
`routed_models.py` owns `routed-models.json`, the picker Switch Codex points
Codex at: the rows no-subscription mode shows, under the mixed list's key and
portco filters, plus hidden bare Luna aliases only when Luna is admitted.
Those aliases prevent the client from selecting its first chat model when its
requested helper ID is missing. Readiness checks bind them to the real Luna row.
`availability.sync_catalogue` rewrites it after the mixed list,
never empty and never without a live snapshot, since Codex rejects an empty
list and a stale one offers models the key cannot use. `codex_route.ready`
answers whether Switch Codex may use it, reading "current" through
`availability.effective_ids`; it sits in `codex_route` because `availability`
imports the writer, so a check beside it would import `availability` back.
`usage_episodes.py` owns `codex-usage-limit.json`, the record of ChatGPT
usage-limit episodes the Switch Codex offer reads. `subscription_fallback.refused`
answers every ChatGPT 429, so it hands each one over with the drained error
body. Only the refusal Codex itself reads as a spent allowance counts
(`error.type` `usage_limit_reached`, per `codex-rs/codex-api/src/api_bridge.rs`),
and only from Codex desktop, recognised by the `(Codex Desktop; <version>)`
User-Agent suffix its app-server adds. The module imports leaves plus
`upstream.parse_payload`, keeps three fields and nothing from the request, and
swallows its own failures, so the client's answer never changes. The format
is in [data](../DATA.md#codex-usage-limit-record).
