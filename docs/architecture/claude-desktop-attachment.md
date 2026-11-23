# Claude desktop attachment

Paths are relative to `router/`. See the [architecture map](../ARCHITECTURE.md) for the module overview and dependency direction.

`packaging/claude_desktop_config.py` owns desktop attachment and its original
restore snapshot. A matching owned attachment keeps the user's selected
subscription or gateway mode on subsequent setup and update runs.
Its shared `operational_snapshot` validator accepts a supported opaque sealed
API field only for an existing receipt-bound route. It requires a complete
typed restore snapshot, the exact written map, applied entry, provider,
credential kind and full loopback URL. Duplicate JSON keys, changed routes,
bootstrap settings and invalid modes refuse. Repeated opaque attachment keeps
the entry and restore evidence unchanged. A late subscription answer updates only
the receipt's saved mode. An unchanged answer keeps the receipt bytes unchanged.
Classification and every switch recheck
use this proof; it proves routing ownership, never decrypted plaintext.
`client_removal.json_plan` restores an opaque field only after this route proof
passes and an exact private entry copy is retained under Router home. The
opaque plaintext is never inferred. Saved state and selected-entry metadata
remain comparison guards until publication finishes. Changed proof inputs keep
the receipt and service available for a safe retry. A failed current-version
pointer cleanup reports incomplete removal, while retained releases stay.
Linux retry does not disable units already removed by the earlier attempt.
`desktop_windows.py` resolves the current user's registered Claude Store
package and its virtualized roaming profile; the gateway profile stays separate.
`windows_native.py` binds package, process, token and window APIs with explicit
pointer types. It owns native handles and returns identity facts to desktop policy.
It performs no discovery, shutdown or activation on import.
`windows_codex.py` owns fresh Store package discovery, process selection and
verified Windows Codex lifecycle policy. It reuses the desktop writer tracker.
Termination requires explicit consent from its caller. Each process is verified
once for creation time, account, session, package and executable, then its handle
stays open through shutdown. Subsequent scans check that handle's signal state;
they do not read identity from an exiting process. A second snapshot checks
parent metadata before selection. The verified root exits first, allowing its
job to close workers before remaining verified survivors are ended.
`windows_dialog.py` verifies the retained compiled helper for switch confirmation
and progress. The helper owns presentation; Python owns consent and configuration.
Without the helper, the dialog owner's styled form takes its place.
`windows_shell.py` is the PowerShell launcher for shipped installer code (the shared single-select question's dialog tool and
the checkout build tools still find PowerShell themselves). It starts the
system copy by absolute path with one flag set and no console window. Values reach a
script as JSON on stdin or through `ps_quote`, which doubles every single-quote variant.
`claude_desktop_switch.py` owns the switch lifecycle. After Claude exits normally,
it shares the current account's local tasks and changes the mode only when all
required copies succeed. `claude_profile_accounts.py` checks the current native
account before restart consent and again after shutdown. A changed account
retains the complete old gateway profile through `claude_profile_rotation.py`
instead of reassigning its task-sharing binding. Open and Switch share one
transition lock, held before reading the mode through reopening, so overlapping
requests cannot use a stale source profile. The switch rechecks the attachment,
managed policy and stopped app before changing the mode. The mode write compares the exact settings
bytes to preserve concurrent edits. When setup recorded no Claude subscription,
it refuses a move to the subscription before asking or closing Claude, and the
menu disables that choice. Open Claude does not share tasks, but checks account
ownership before opening an existing OpenRouter profile. The stable
`claude_profile_launch.py` follows the installed release pointer so both actions
survive updates and release pruning. After a rollback to a release without task
sharing it runs that release's plain switch, opens Claude for Open Claude and
keeps the callback silent. Setup rebuilds 0.6 shortcuts and deletes only the
router's own copy of their home shim. Setup owns the callback installation and
removal. Existing recovery launchers remain Mac applications; the identity
callback also supports account-bound task sharing from Windows and Linux tray controls.
