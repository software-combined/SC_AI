# Data

The files the router keeps in its home directory, and the records it writes there.

## Layout of the state directory

`~/.codex/mixed-model-router/` holds `current` (pointer to the live
release), `releases/` (current plus two priors for rollback depth), `logs/`,
`mixed-router-state.json` (port, token and feature flags, mode 600),
`activation.json` (config receipt), and one owner-only key file per
external provider (`openrouter.key` by default, mode 600).
The code may live anywhere; only this directory matters at runtime.

## Codex usage-limit record

The router writes `codex-usage-limit.json` in its home when ChatGPT refuses a
Codex desktop request because the allowance has run out. It is machine state
like the catalogues: never bundled, never copied, and it holds nothing from
the request. It is the contract for the Switch Codex offer, so a reader may
parse the JSON directly, including packaging code.

```json
{
  "seen_at": "2026-09-29T05:12:33+00:00",
  "resets_at": "2026-09-29T10:12:33+00:00",
  "client_version": "26.924.22138"
}
```

`seen_at` is when the episode started, in UTC with a `+00:00` offset.
`resets_at` is when ChatGPT said the allowance returns, in the same form, or `null` when it named no reset or
named one in the past or more than 31 days out. `client_version` is the Codex
desktop version from the request's User-Agent, digits and dots only, or
`null`.

Only one refusal counts: a ChatGPT subscription 429 whose body names
`error.type` `usage_limit_reached`, which is how Codex itself recognises a
spent allowance, from a request whose User-Agent carries the desktop's
`(Codex Desktop; <version>)` suffix. Other 429s are plain rate limits to
Codex; they and requests from the Codex CLI (`codex-tui`) never write the
file.

One episode is one limit period. It ends at `resets_at`, or five hours after
`seen_at` when `resets_at` is `null`. A refusal before then keeps `seen_at` and
`client_version` and can only change `resets_at`; a refusal after it starts a
new episode. The file is replaced atomically and is owner-only (0600). Nothing
deletes it when an episode ends, so a reader compares the times itself. A
missing, unreadable or malformed file means no episode, which is what
`usage_episodes.current(home)` returns as None. A failed write is logged as
`usage_episode_failed` and never changes the answer the client gets.

The updater remembers which Switch Codex offers it has made in
`codex-switch-offers.json` beside it, for the latest episode only:

```json
{
  "seen_at": "2026-09-29T05:12:33+00:00",
  "offered": ["switch", "back"]
}
```

`seen_at` names the episode, and a new episode starts with no offers made.
All platforms start a worker without claiming that a dialog appeared.
`switch` offers the signed-out OpenRouter fallback. `back` offers the prior
combined or signed-in OpenRouter connection. The recorded reset only triggers
the offer; another limit can still apply. Before showing a dialog, the worker
writes a temporary `claim` in this record. It recovers an abandoned claim on
the next pass, and an unwritable record prevents the dialog. A declined offer
stays recorded. A failed switch or an unshown dialog leaves the offer pending.
The worker rechecks the connection and episode after the offer. Its dialog
never holds the update-check lock.
Missing or invalid return-choice evidence defaults to the combined connection.
An unreadable receipt leaves the offer pending instead of changing settings.
The Codex entry in `activation.json` stores a `fallback_return` choice while
the signed-out fallback is active. Updates and interrupted-switch recovery
preserve it; leaving that fallback removes it.

`installation-pending.json` retains the fixed Windows recovery inputs while an
installation changes required components. It contains owned launchers, pointers,
task definitions and Windows entry points. Independently refreshed catalogues stay outside rollback. It contains no
credentials, client configuration or full Router state. A failed restoration keeps
this record and both runtimes for the next maintenance attempt.
`installed-cohort.json` records verified component versions and hashes after
completion. Startup preferences remain independently controlled by the user.

## Switch Codex run log

Applying update checks append content-free records to `logs/maintenance.jsonl`.
The regular and Express tasks record launch, completion or failure.
Reconciliation records `repaired`, `unchanged`, `inactive`, `deferred`, `unhealthy`,
`conflict` or `failed` for the Codex attachment. Records contain no settings or keys.
A repaired attachment retains its original uninstall evidence in `activation.json`.
Verified normal attachments and repairs retain a `repair_notice` event to deduplicate the restart offer in
`update-notice.json`. A missing dialog leaves that offer pending.
An unsafe active recovery marks the existing assistant component as needing attention.

`desktop-preferences.json` records only an explicit startup choice.
Windows treats missing, unreadable or malformed preferences as On without rewriting them.
Verified resource advancement uses a quiet `--after-update` launch, independent of that choice.
The session lock prevents duplicates. A retained controller reloads the advanced resources.

Each Switch Codex run appends one JSON line to `logs/codex-switch.log`, so a
switch that refused can be diagnosed afterwards:

```json
{"at": "2026-09-30T12:31:05+10:00", "to": "switched", "open": ["ChatGPT", "browser_crashpad_handler"], "result": "The ChatGPT app (Codex) did not close. Quit it from the ChatGPT menu, close any Codex sessions in Terminal, then open Switch Codex again."}
```

`at` is the local time with its offset. `to` is the variant the run aimed
for: `switched` for the signed-out limit fallback, `openrouter` for normal
OpenRouter-only use on the ChatGPT provider, `switched_signed_in` for the
earlier signed-in routed provider, or `switched_back` for the subscription. It is
`null` when the run refused before choosing one. `result` is `done`,
`cancelled` or the message the person saw, which
never holds paths, settings, addresses or keys. `open` appears only when the
app did not close: the sorted file names of the executables still running
from the app bundle, never their paths or arguments, or `null` when the
process list could not be read. A line that cannot be
written never stops a switch, and the file ages out a month after its last
write, like the other logs.
