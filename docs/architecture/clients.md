# Client contract

`ai_router/clients/registry.py` is the one owner of who sees what: one row per
client, carrying its primary picker protocol and supported wire protocols, the picker
predicate and the discovery predicate. Both Claude projections read it, and
`packaging/install.py` derives its `--client`/`--clients` choices from the
`ai_router/clients/roster.py` leaf, which is import-free so the installer can
spec-load it (`packaging/service.py::load`). Adding a client means:

1. a row in `ai_router/clients/registry.py` (and its id in the roster leaf);
2. protocols the router already dispatches on, per `protocols/TABLE`:
   Responses and native Images for Codex, Messages for Claude Code. A new
   wire protocol requires a verified client contract before it joins this table;
3. a capability projection under `ai_router/clients/` only if the client's
   catalogue shape differs from Codex's;
4. an activation adapter under `packaging/` owning that client's config file,
   the keys it owns, its conflict refusal and its detach path, following
   `claude_config.py` as the smaller of the two examples;
5. a receipt entry through the shared receipt writer, so `--status` and
   `--uninstall` know what was touched;
6. an entry in `docs/release/compatibility.md` naming the client version verified.

The genuinely hard case is a client that speaks neither protocol: it needs a
new adapter class behind the definition table, never a branch in the request
path ([rules](../RULES.md), rule 3).

## Codex connection switching

`packaging/codex_switch_config.py` owns the four managed Codex blocks. The
default is `codex_config.build_block` unchanged, so a never-switched install
and older Codex builds see nothing new. `switched` is root keys only: Codex's
active provider becomes `scg_router`, which needs no OpenAI sign-in, sends
`x-scg-codex-route` and reads `routed-models.json`, and
`approvals_reviewer = "user"` stays, as in every managed block, because
attach moves the owner's own line into the receipt and this route refuses
ChatGPT's reviewer. `switched_signed_in` keeps the same routed-only connection
with ChatGPT sign-in for normal use, preserving account projects and setup
state. `switched_back` is the default plus `scg_router` with
sign-in on, so threads started while switched still resume. The Codex receipt
entry records the variant (`variant`, absent until the first switch), and
`client_choice.attach_codex` rebuilds it on every install and update.
Entering the signed-out fallback also records whether the prior choice was
signed-in OpenRouter or the combined connection. Update and pending-switch
recovery preserve that return choice. Older receipts default to the combined
connection and are not changed merely by updating the router.
`switch` and `restore` are the only writers that change it. `switch` writes the config first, then the receipt, with the config
put back if the receipt write fails; `restore` undoes a switch, putting both
back. While Codex is switched, `tools/disable.py` (and so a
service-only install), `--uninstall` and `--rollback` refuse and leave its
settings as they are.

`packaging/codex_desktop_switch.py` owns the native desktop connection transition. It
moves an attached install to the other variant, holding the installer lock
throughout, and a hand-edited block refuses before anything is asked. Each
run appends one line to `logs/codex-switch.log` ([data](../DATA.md#switch-codex-run-log)).
`codex_switch_transaction.py` owns pending markers, proof and restoration of the owned settings.
Its Windows rollback guard verifies exit again if reopening may have launched the app.
An unavailable rollback shutdown keeps the pending marker and preserves the current configuration.
Windows Codex discovers the current Store package through native APIs and checks
registration before lifecycle actions. Process snapshots use Toolhelp metadata
and native token reads; they do not start PowerShell. A busy installation offers a Cancel window while
Switch Codex waits up to sixty seconds, before discovering the current app and settings.
Its process snapshot queries owners only for package processes, named writers,
descendants and previously tracked PIDs. Vanished processes do not invalidate a scan;
an unreadable relevant process still refuses. Windows CLI selection checks the package
boundary, executable header and `codex-cli` version before preflight and proof share it.
Only package-relative selection diagnostics enter the log; no Codex install path is persisted.
Windows confirmation names the full close and stopped tasks. Shutdown allows five seconds
for window closure, then ends verified surviving processes within a fifteen-second deadline.
Settings remain pending until proof and a visible reopened package window succeed.
Cold reopening has a separate thirty-second bound.
Failure restores the previous owned settings and attempts fresh-package reopening.

Both OpenRouter variants are strict. They need `codex_route.ready`, a subscription install
(no-subscription mode already runs without sign-in), exactly one ChatGPT app
(Codex) with its bundled CLI at the verified platform installation, and a verified
exit. It then writes a pending marker, calls `codex_switch_config.switch` and
proves the result with `codex_config_proof`: that CLI, started as an app
server on `~/.codex`, must load the config and report no managed
`model_provider` and the variant's account state. Normal use requires the
ChatGPT account; the active-limit fallback requires no account. Any doubt
refuses before the dialog; a failed
proof puts back the previous receipt entry and the block exactly as
config.toml held it, the owner's latest model pick included, through
`codex_switch_config.restore`, and reopens the app.

Switching back is the only way out of `switched`, since detach, uninstall and
rollback refuse while switched, so it depends on nothing it can lose. It runs
no proof: it only returns to the install's own block plus the provider entry.
Windows requires a current package identity and verified exit in both directions.
Mac and Linux retain their manual quit and reopen path when the app cannot be identified.

A switch that refused before writing needs no undo, and any refusal after the
quit reopens the app unchanged. A marker left by a run that stopped halfway is
kept when its switch was written and needs no proof or proves; anything else
is rolled back. Windows first obtains consent and verifies exit, then settles the
pending configuration and verifies reopening. Cancellation leaves the marker pending.

`packaging/codex_switch_offer.py` owns the automatic offers. The updater
calls it after every pass that holds the update lock, the minute Express job
included, and swallows anything it raises. It reads the router's
`codex-usage-limit.json` itself, because the router's reader needs Python
3.14, so its parsing and five-hour rule are copies that a test pins to
`ai_router/usage_episodes.py`. For a Codex install in subscription mode, it
offers the signed-out fallback once per episode from an affected desktop build.
It offers the recorded previous connection after the recorded reset, or when the
installed app is at or above `FIXED_IN`. A recorded reset is a trigger for an
offer, not proof that every limit has ended. On all platforms a retained
controller opens a detached dialog worker.
Its `offer_and_switch` owns the offer dialog and claim for that worker and the
menu's `codex.limit_offer` action. It rechecks the episode and receipt after the
dialog; the switch owner repeats the episode check under the installation lock
and asks before changing anything.
Missing dialogs leave the offer pending.

`packaging/codex_switch_app.py` owns that app. Every Codex attach and update
builds or refreshes it on a Mac when Codex is attached in subscription mode
and either the installed ChatGPT app is at or above `AFFECTED_FROM` or Codex
is switched right now, so older Codex builds see nothing new. Otherwise it
removes an app it owns, but never while Codex is switched, because the app is
the way back. Detach and uninstall remove it through `tools/disable.py`,
which refuses while switched. The app is ours when its bundle id matches and
its Info.plist names this router home, so a run for another home (a test's)
never removes it. It runs `codex_switch_launch.py`, a copy in the router
home, under the router's own Python, which follows `current` to that
release's `codex_desktop_switch.py` and names an older release in one plain
message. `claude_desktop_platform.install_mac_app` builds it and both Claude
launchers, staged and then swapped in, and refuses an app it does not own. A
failed build prints one line and never fails an install.
