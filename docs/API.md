# API

The interfaces the router offers to other programs, and the rules for
changing them. Paths are relative to `router/`.

The router is a local web service. Codex and the Claude apps send their
requests to it instead of to OpenAI or Anthropic, and it forwards each request
to the right provider. It does not invent its own wire format: it speaks the
OpenAI Responses and Anthropic Messages formats that the clients already use.

## Who can call it

The router listens on a loopback address only, so only programs on the same
machine can reach it. Every request must carry the installation's path token,
either as the first path segment (`/<token>/responses`) or as
`Authorization: Bearer <token>`. A request without the token, from a
non-loopback host, or with an `Origin` header (except on the setup and model
access pages) gets 403 `FORBIDDEN`. `ingress.authorized_path` owns this check.
A `POST` to a subscription route accepts the token only in the path: a
Bearer-only call gets 401 `BEARER_NO_SUBSCRIPTION_ONLY`.
The token is unique to each installation and lives in the state file that
[Data](DATA.md) describes.

## Routes

| Method and path | Caller | Format |
|---|---|---|
| `POST /responses`, `POST /responses/compact` | Codex turns and compaction | OpenAI Responses |
| `POST /images/generations`, `POST /images/edits` | Codex image tools | OpenAI Images |
| `POST /v1/messages`, `POST /v1/messages/count_tokens` | Claude Code and the Claude desktop app | Anthropic Messages |
| `POST` Codex service paths (`providers.NATIVE_SERVICE_PATHS`) | Codex search, notes and safety checks | Passed to OpenAI or answered locally |
| `GET /models` | Codex model list | Codex catalogue |
| `GET /v1/models` | Claude model list | Anthropic listing |
| `GET /health` | Installer, updater, desktop menu | Router JSON: version, in-flight count, draining, served models, regions |
| `POST /shutdown` | Installer and updater | Drains, then exits so the service manager restarts it |
| `/setup/...`, `/model-prompt...` | Local setup and model access pages | HTML pages with their own token and same-origin check |

`protocols/__init__.py` (`TABLE`) lists the `POST` routes that reach a
provider, the two model listings, and the policy each uses. `ingress.do_get`
dispatches every `GET` route by hand; only `/v1/models` takes its listing from
the table. `router.py` handles `POST /shutdown` first, then the table, then
the setup and model access pages when no row matches.
A path the router does not serve gets 404
`UNSUPPORTED_ROUTE`. A WebSocket upgrade gets 426 `WEBSOCKET_REJECTED`, which
makes Codex fall back to ordinary HTTP streaming. A `POST` body must be
`application/json`. The `/backend-api/codex` prefix that Codex adds is removed
before routing.

## Errors

Every router error uses one body shape, built by `errors.RouterError`:

```json
{"error": {"message": "Plain words for the person", "type": "router_error", "code": "UNKNOWN_MODEL"}}
```

The status says what the client should do. On the Responses protocol, Codex
ends a turn at once only on 400 and retries other failures, so pick the status
by meaning:

| Status | Used for |
|---|---|
| 400 | A request that cannot succeed as sent; the client shows the message |
| 401, 403 | Sign-in or token refused |
| 404, 415, 426 | Route, body type or connection type not served |
| 409 | A provider refusal that a repeat may cure: the compaction summary, and the Messages path |
| 429, 503 | Too busy, draining or a passing upstream failure, with `Retry-After` |
| 500 | An unexpected fault inside the router |
| 502 | The upstream stopped responding or compaction is unavailable |

A refusal for a request that asked for a stream is sent as HTTP 200 with a
`response.failed` event instead. The message is for a person who is not
technical. The `code` is stable, for logs and tests, and usually upper case.
`context_length_exceeded` stays lower case because Codex matches that exact
string. `errors.py` is the source of truth for every status and code.

[Router answer codes](operations/answer-codes.md) explains the main Responses
codes, the size ceiling (256 MiB per request) and the in-flight limit
(32 requests).

## Changing the API

- **Formats belong to upstream.** Keep request and response shapes as the
  verified client versions expect them ([Compatibility](release/compatibility.md)).
  Never add a field of our own to a provider format.
- **A new route** joins `protocols.TABLE` with its policy when it is a `POST`
  that reaches a provider; a `GET` route also needs a branch in
  `ingress.do_get`. A new wire format
  needs a verified client contract first ([Client contract](architecture/clients.md))
  and a new adapter class, never a branch in the request path ([Rules](RULES.md), rule 3).
- **A new error** is a function in `errors.py` with a new code and the status
  that fits its meaning, as above. Add Responses codes to
  [Router answer codes](operations/answer-codes.md).
- **Retries never repeat an action.** Only an attempt that has sent nothing to
  the client can be replayed ([Streams and request evidence](architecture/streams-and-evidence.md)).
- **No paging.** Model listings return the whole set.
- **No URL versions.** `/health` reports the Router version. After a client
  upgrade, the compatibility check decides whether the API still fits.

## Command line

| Command | Use it for | Described in |
|---|---|---|
| `packaging/install.py` (`--status`, `--doctor`, `--rollback`, `--uninstall`) | Install, check, roll back and remove | [Service](operations/service.md), [Updates](operations/updates.md) |
| `python3.14 -m ai_router.models` and `ai_router.candidate` | Model rows and probes | [Adding a model](models/adding-a-model.md) |
| `python3.14 -m ai_router.media_cli` | Image and video fallback | [Media generation](models/media-generation.md) |

The files the router reads and writes are in [Data](DATA.md).
