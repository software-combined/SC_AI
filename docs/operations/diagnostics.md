# Diagnostics

What the router logs about latency, failed streams, handoffs and request identity.

## Latency phase fields (aggregate-only comparison recipe)

`request_completed` carries per-phase durations in milliseconds plus the
long-standing cumulative fields (`local_prepare_ms`,
`upstream_headers_ms`, `first_chunk_ms`, `total_ms`), whose meanings are
unchanged:

| Field | Meaning |
|---|---|
| `read_ms` | Socket read plus body decode |
| `prepare_ms` | Provider selection plus body preparation |
| `connect_ms` | Upstream connection establishment (`connect()`) |
| `send_ms` | Request upload (`request()`) |
| `headers_ms` | Wait for upstream response headers (`getresponse()`) |
| `first_data_ms` | First upstream read-return inside adaptation (not provider TTFB on buffering paths) |
| `first_write_ms` | First successful downstream write (forwarding delay, not network TTFB) |
| `response_kind` | `sse`, `json`, or `other` (fixed values only) |
| `response_encoding` | `identity`, `gzip`, `deflate`, `br`, `zstd`, or `other` (fixed values only) |

`transport_error` carries the phases that completed before the failure;
absent later phases mean the request never got that far. To compare
builds, group by version/provider/model/stream/encoding over approved
existing logs, include failed/aborted counts with sample size and time
window, and use per-request ratios, never ratios of unrelated
percentiles. Paid direct-versus-router comparisons need separate
explicit authority.

`request_started` and the request's final record carry the same
`request_id`, a random 32-character hex id. Use it to join the two lines
for one request, including a helper turn answered by the fallback twin. It
is not derived from anything the client sent.

## Failed streams (why the provider ended it)

`request_failed` records a terminal event the upstream sent inside a `200`
stream. `code` is `context_length_exceeded` for a context-limit refusal,
`UPSTREAM_INCOMPLETE` when the provider reported an incomplete response,
`UPSTREAM_INVALID_PROMPT` when OpenRouter refused the converted request after
the stream opened, and `UPSTREAM_STREAM_FAILED` for any other terminal error.
Six fields say why:

| Field | Meaning |
|---|---|
| `terminal_event` | `response.failed`, `response.incomplete`, `error`, or `message_error` |
| `upstream_reason` | the `incomplete_details.reason` enum, when reported |
| `upstream_code` | the error envelope's `code` or `error_type`, when present |
| `upstream_error_type` | the canonical top-level `error_type`, when reported |
| `upstream_provider_code` | the `error.metadata.provider_code`, when reported |
| `serving_endpoint` | the OpenRouter endpoint that answered; absent when the router or an edge validation answered |
| `failure_class` | `context`, `final`, `transient` or `unknown`; the stream replay runs only on a recognised `transient` failure |

Every detail must be code-shaped (letters, digits, dot, dash, underscore,
slash for endpoint slugs) and
at most 64 characters; anything else, including message text, is dropped
rather than recorded, because provider prose can quote prompt content. A
missing detail means the provider did not say why, or said it in a form this
rule refuses to record.

Each routed request ends with one `attempt_ledger` record containing ids, route,
send reasons, decisions, commitment, terminal writer and outcome. It contains
fixed codes and counts; terminal request records repeat those outcome fields.

## Agent handoff failures

`handoff_observed` joins a native Responses handoff to `request_id`, the ledger's
`attempt`, and a response-local `call_ordinal`. It records the tool, declaration
location, whether this request declared the tool readable (`schema_mode` is
`readable` or `native`), and `message_shape`: `readable`, `ciphertext`,
`absent` or `other`, a classification that never carries the text. It also
records the namespace category (`native`, `plaintext` for the readable alias,
or `other`), encryption-marker state and argument JSON kind as the upstream sent
them and as the client received them.
`envelope_changed` identifies a namespace or marker change between envelopes;
`identity_consistent` reports whether their identifiers agree. Raw identifiers,
assignments, recipients, ciphertext and results are never logged.

A readable call that reaches the client as `native` with an empty marker
passed every rule; an alias call is restored that way. `marker_rejected=true`
means the upstream marked a readable call encrypted, or sent ciphertext under
the alias, so it was refused rather than relabelled. A canonical `ciphertext`
message, or a call to a tool this request did not declare readable, stays
unmarked; `guard_rejected=true` means the encrypted-handoff guard refused it
because the recipient is external. `message_shape` therefore shows in live logs whether the
backend returned readable messages for the native namespace. These facts locate
the failure without inferring readable text from ciphertext.

`frame_end_offset` is the end of the adapted frame in that attempt's outgoing
body. Compare it with `forwarded_delta_bytes` for the same request and attempt:
the router confirmed the complete write only when that counter reaches the
offset. A failed or partial write remains unconfirmed; a successful socket write
does not prove the child ran. `handoff_observation_finished` lists missing
envelopes. Each response retains at most 32 call identities and emits at most 96
observations, 32 summaries and one limit record. A limit or logging failure
marks observation incomplete while forwarding continues unchanged.

## Tool alias repair (why a called name changed)

`tool_call_repaired` and `tool_call_unresolved` carry a `cause`: `native`
(the plain tool name), `dotted` (`namespace.tool`), `digest` (a damaged
fallback digest), `near` (a readable alias within two edits; an ambiguous
near miss is never guessed), or `delivered` (a delivered-message name such
as `delivered_message`, which is not a tool). `unknown` means the name
matched nothing repairable.

## Request identity and failure evidence

Resolve the installed release from its `current` pointer, then run the command
(macOS/Linux shown; use the corresponding router home on Windows):

```sh
router_home="$HOME/.codex/mixed-model-router"
cd "$router_home/releases/$(basename "$(cat "$router_home/current")")"
python3.14 -m ai_router.inspect_requests --minutes 60
python3.14 -m ai_router.inspect_requests --request-id <request-id> --json
python3.14 -m ai_router.inspect_requests --model <model-id> --identity mismatch
```

The command reads completed request chains from the existing four rotated
logs. It makes no model call and loads no credentials. `--minutes 0` includes
all retained records; `--limit` accepts 1–100. Identity filters also accept
`unverified` and `contradictory`. Logs from earlier versions may lack evidence.

Each send records the requested, resolved and upstream IDs separately from
provider reports, including their header or response-field source. Reports
survive later read errors, and a retry starts fresh. Missing or unreadable
identity stays unverified. A mismatch means the reported ID differs literally;
native aliases or snapshot names may explain it. A provider report is not
independent proof of the weights executed. `/health served_models` remains a
last-observed cache and never attests the selected request.

For a Codex V1 child, keep the `agent_id` returned by spawn, the actual parent
thread ID and the assignment start/completion times. Router 1.0.11 records only
canonical UUID values from `thread-id` and `x-codex-parent-thread-id`; malformed
values, agent names and the rest of the turn metadata are not retained.
The real-client, zero-paid `tools/probe_agent_identity.py` checks two overlapping
same-model children and proves the returned IDs match these headers. Run it
again after a client upgrade before relying on that mapping.

From the installed release directory, look up a pass without filtering away
other models or mismatching attempts:

```sh
python3.14 -m ai_router.inspect_requests --agent-summary --json --limit 100 \
  --thread-id <agent-id> --parent-thread-id <parent-id> \
  --since <assignment-start-with-offset> --until <completion-with-offset> \
  --model <requested-model> --expected-effort <requested-effort>
```

In summary mode `--model` is the expected model, not a filter. Model and effort
statuses are separate. A matching retry cannot erase an earlier mismatch or
contradiction; missing or limited reports and failed request chains stay
unverified. `records` retain the source and request/attempt IDs.
`limit_reached: true` marks a full page conservatively: matching fields stay
unverified because older records may have been omitted; retained mismatches
and contradictions still take precedence. Compaction and
non-turn operations are counted separately. The coverage label is always
`retained_records_only`: the bounded log may have rotated or hit the record
limit, and an abrupt exit may leave no ledger. Never call this complete serving
attestation, or treat an echoed effort as measured reasoning compute. The
client-facing `openai-model` header remains the configured compatibility slug,
not identity proof. An older router or unavailable parent ID leaves the pass
unverified rather than guessed from the latest health cache or reviewer text.

Attempt outcomes describe the observed upstream or transport ending. The
request outcome also reflects delivery and recovery, which can preserve the
first terminal after a later attempt fails. Timings name connect, send, headers
and actual read calls; read wait includes response consumption and must not be
presented as provider compute time. Age, time since the last upstream data,
socket timeout, commitment and retry decisions help distinguish failures.
Write failures are identified separately; a broken client connection is a
cancellation, while an upstream read failure remains a transport failure.
Service restart remains separately recorded by `draining`, `exit` and
`router_started`; an abruptly terminated request may have no final chain.
Prompts, tool data, credentials and raw error bodies are excluded.
