# Patterns

Recurring patterns in the router code, with the page that owns each one.
Reuse the pattern before adding a new one.

| Pattern | Where it is described |
|---|---|
| One upstream is one entry in `ai_router/provider_defs.py`; adapter classes take that definition. A different wire format is a new adapter class, never a new branch in the request path. | AGENTS.md section 3, [rules](RULES.md) |
| Dependencies point inward: leaves import nothing local and know nothing about their consumers. | [Architecture](ARCHITECTURE.md#domains-and-direction) |
| Model rows are data; new behaviour is always code. | [Design rules](DESIGN.md) |
| `state.update` is the shared read-modify-write path for `mixed-router-state.json`. | [Installation ownership](architecture/installation.md) |
| Client configuration edits change only the owned region, keep a receipt of original values, and refuse before writing when the file has an unknown structure. | [Installation ownership](architecture/installation.md), [client contract](architecture/clients.md) |
| One dialog owner draws every popup in one style. | AGENTS.md section 4a, [installation ownership](architecture/installation.md) |
| Logs and evidence are content-free: no request or tool content, keys or private paths. | AGENTS.md section 4, [diagnostics](operations/diagnostics.md), [data](DATA.md), [troubleshooting](troubleshooting/README.md) |
| Outgoing requests pass through named stages in a fixed, tested order. | [Handoffs and history](architecture/handoffs-and-history.md) |
| `attempt_policy` decides every send from the terminal vocabulary and commitment facts; only an uncommitted attempt can be replaced by a safe replay. | [Streams and request evidence](architecture/streams-and-evidence.md) |
| Live probes carry hard caps on calls and spend. | [Testing](TESTING.md#live-probes) |
