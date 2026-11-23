# Router answer codes (Responses protocol)

The router answers deterministic refusals with HTTP 400 (the client treats
400 as final and shows the message at once) and transient upstream failures
with HTTP 503 plus `Retry-After: 2` (the client retries on its own backoff;
Codex paces itself and does not read the header). The only retryable 409
left on Responses is the compaction summariser's, where a repeat can cure
the failure; an oversized turn answers 400 with guidance instead of 413. The
Anthropic Messages path keeps its existing answers except at that shared
size boundary, where it answers 400 like Responses.

Every request has a local 256 MiB ceiling on its wire, decoded and prepared
bytes, on all four routes and for identity and zstd bodies alike. A turn past
it answers 400 `BODY_TOO_LARGE` with no upstream call, and the transport checks
the same ceiling again on every send. The ceiling bounds what one turn makes
this machine hold; it does not mean a provider or subscription accepts a body
that size. Native history, images, signatures and headers are forwarded whole.

16 MiB is the ordinary request threshold, not a limit. A turn past it on the
wire, on decode or once prepared reserves bytes in a shared 1 GiB budget, before
the rest of a compressed body is expanded. Several large turns can run together.
If the budget is full, a new reservation waits up to 60 seconds for space.
After preparation returns, the
router releases it if the remaining request is at most 16 MiB and retains
neither a fallback plan nor a response adapter. This lets another large turn
prepare while the reduced request streams. Large retained requests keep the
reservation through relay, retries, fallback and final cleanup. An exhausted
wait answers 503 `OVERSIZE_BUSY` with `Retry-After: 2` before the blocked send.
Smaller turns proceed within the 32-request in-flight limit, which also counts
waiting requests. Restarting wakes waiters with `SERVER_DRAINING`.
A repair or fallback body is sized together with the body still held.
After an early release, a retry reserves bytes again before an additional send.
An existing holder may grow beyond the budget without waiting, so two holders
cannot deadlock while each keeps its earlier body. A request above the budget
may start alone. The budget counts body sizes, not Python's actual memory use;
the 256 MiB per-request ceiling and 32-request limit still bound each request
and the total number of active requests.

The router generates a request ID before reading each POST body. Request,
rejection and attempt-ledger records share that ID. Large-slot records add
validated chat and parent IDs, the router version and the acquisition stage
(`wire`, `decode`, `prepared` or `retry`). Known sizes are `wire_bytes`,
`decoded_bytes`, `prepared_wire_bytes`, `prepared_decoded_bytes` and
`retained_accounted_bytes` (the combined size used for admission). If decoding
stops early, `decoded_lower_bound_bytes` names the observed lower bound;
it is never reported as an exact decoded size. Unavailable facts are omitted.

Acquisition and release events retain their names `oversize_slot_acquired` and
`oversize_slot_released`. Both record `waited_ms`, `reserved_bytes`,
`budget_used_bytes` and `holders`. An `OVERSIZE_BUSY` rejection snapshots the
holder count and bytes in use at timeout; `owner_held_ms` is the oldest holder's
age. These facts remain valid even if the budget changes before logging.
Reservation release records use
`release_reason=prepared_small` or `request_end`, `acquisition_stage` and `held_ms`.
All these fields are scalar metadata; no payload, raw header, credential or
token-bearing URL is recorded. The server lock protects ownership and snapshots;
reading, streaming and logging run outside it.

An external Responses turn still over the 16 MiB prepared budget is reduced
with visible notes before it is sent: repeated released-tool listings collapse
to the newest copy per tool, the oldest images past the newest four (or 4 MiB)
become a note, and long old tool outputs are truncated head and tail. Tool
call/output pairing and the newest items are never touched, and a turn with
nothing reducible left is sent as it is, within the ceiling. Native routes are
never trimmed. Upstream answers keep their own caps: 16 MiB for a response
body or one SSE frame, 1 MiB for an error body.

A refused subscription turn (an upstream 429 on a login the client owns)
answers 503 `UPSTREAM_RATE_LIMITED` whose message names the model and the
subscription that refused it and says the turn was not served, to retry
shortly or to select a routed model. An external route's transient 429
keeps the neutral text, and neither answer carries upstream prose.

Every refusal, retryable or final, leaves one `request_rejected` line with
`status`, `code` and `path`, plus `retry_after` when a retry hint went out and
a bounded, path-redacted `detail` when the plain message left a technical
reason behind (a credential problem's OS text). An upstream rejection keeps
its own line (`upstream_rejected`: `status`, `code`, `parameter`,
`serving_endpoint`, and the bounded `tool`), so the status, codes, field and
tool names a person no longer reads stay searchable in the log.

| Event | Meaning |
|---|---|
| `request_rejected` | one per refusal, retryable or final: `status`, `code`, `path`, `retry_after`, bounded `detail` |
| `oversize_slot_acquired` | a request took the large-request slot; correlated IDs, version, stage and known sizes |
| `oversize_slot_released` | the owner released the slot; reason, acquisition stage, hold time and known sizes |
| `upstream_unavailable` | an upstream 5xx or 408 on a Responses turn, answered 503 |
| `client_disconnected` | the client hung up mid-stream; previously counted as `transport_error` |
| `upstream_rate_limited` | an upstream 429, with `category` `quota`, `auth` or `transient`; on Responses a quota 429 answers 400 `PROVIDER_REJECTED` and an auth 429 opens the key window; a subscription turn's `transient` 429 answers 503 naming the model and the subscription |
| `turn_refused` | a turn refused before any upstream call for its size (`BODY_TOO_LARGE`, `INVALID_REQUEST_SIZE`), with compressed, decoded, limit and prepared bytes plus counts and byte weight per carried class and images; no content |
| `turn_trimmed` | an oversized routed turn was reduced with visible notes; names the bytes dropped and how many images and tool outputs were replaced |
| `usage_reported` | a routed Codex turn carrying tools had its reported input tokens raised to what the thread carries (never lowered); names the provider's figure and the reported one |
| `wire_contract` | observe only: a prepared Responses body broke a rule learnt from an earlier upstream refusal (the check never changes or blocks the request); names each rule under `violations` or `warnings` with a count, plus up to eight unknown top-level field names (`error_type` instead when the check itself failed); refusal lines carry the same rules, pairing under `pair_problems` and the rest as `contract_violations` and `contract_warnings`; no content |
