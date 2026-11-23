# Claude profiles and task sharing

Paths are relative to `router/packaging/`. See the [architecture map](../ARCHITECTURE.md) for the module overview and dependency direction.

`claude_profile_rules.py` owns the local-data transfer policy being integrated
by Plan 169. It keeps conversation payloads intact, excludes separate sign-in
and credential files, and relocates only recognized metadata paths. The folder
Claude Code names after a task's workspace is exempt from the sensitive-word
name screen and the dashed -before/-after suffix rule, because its words are
the user's; router markers, credential file names and the content screen still
apply there. It imports
only the standard library. Callers must supply validated source and destination
paths and publish through their own transaction; the helper does not select an
account, change profiles or start synchronization.

`claude_desktop_policy.py` owns the read-only policy check for Plan 169's
switch path. Organization-managed connection settings take priority over a
local attachment; unreadable or ambiguous settings refuse the switch. Platform
readers follow the published [managed-policy precedence](https://claude.com/docs/third-party/claude-desktop/mdm).
The switch check returns a decision; it never writes or logs settings.

`claude_profile_records.py` discovers records within the resolved account and
store layout. It owns namespace selection, native abbreviated bundle paths and
source snapshots. Its `STORES` list is the only switch for which stores are
shared; the 1.0.0 beta shares the Code store and leaves Cowork untouched.
It does not guess identity from saved history or write tasks.
Profile paths follow the saved attachment, so an installer default change cannot
silently reassign an existing attachment or its restore record.

`claude_profile_identity.py` owns the account boundary for Plan 169. A native
session callback must match one exact host and CLI task pair. Cached account
state and the hashed workspace preference detect changes; they cannot select
an organization. Authentication values are neither read nor copied. Static
gateway identity comes from the existing device and local configuration.
A private router-local hash binds the account pair so a later sign-in cannot
inherit the previous account's copied tasks; the same hash keys the shared-task
ledger. The coordinator must hold both profile locks before creating that
binding; this helper does not start a copy.

`claude_profile_rotation.py` is a closed-app retention primitive. The caller owns
consent, account decisions and both profile locks. It retains the complete old
profile and control before-images before preparing a clean same-root profile.
A private pending marker requires explicit recovery before either profile opens.
Receipt publication stays with `codex_config.replace_receipt`, which compares
the exact generation. Unknown account pairs stop sync before any task effects.
The native permission leaf rejects macOS extended allow rules on the archive
parent; Windows uses the existing owner-only ACL check. Shared parents refuse
before creating recovery state. Control copies and final markers use local
publication and removal, so separate home mounts do not require a rename.
Rotation and recovery also validate Router home's access before publishing private
files. Recovery preserves live update-status fields while requiring all connection
and unknown settings to match the saved configuration. It publishes the subscription
selection before clearing pending work; rollback refuses until recovery finishes.
Setup and repair refuse before shared receipts or client choices can change while
Claude recovery is pending.

`claude_profile_publish.py` and `claude_profile_transaction.py` share the record
and bundle publication contract. They validate file generations before exclusive
renames and retain originals and journals when competing writes make recovery
ambiguous. Committed cleanup accepts a partly deleted before-image, so an
interrupted cleanup finishes on the next run. Private control directories
protect backups without changing the permissions of hard-linked attachments
outside the profile. Callers must stop Claude, hold both profile locks and
provide a private, fully prepared bundle.

The path rules convert Windows filesystem arguments to absolute extended Unicode
paths, including network shares, so long session and transaction paths work with
the default Windows path policy. Enumeration results return to ordinary paths
before record projection or journal construction. Ancestor, reparse-point,
ownership and generation checks cover the same paths through this boundary.
The transaction layout and recovery phases stay unchanged. See Microsoft's
[Windows path limits](https://learn.microsoft.com/windows/win32/fileio/maximum-file-path-limitation).

`claude_profile_bundle.py` assembles the complete admitted bundle union before
publication. It uses the shared transfer rules and retains unique duplicate
content before retirement. Task files keep their exact bytes; transcript rows
keep every field and only relocate profile paths. A losing transcript copy that
holds rows the kept copy lacks leaves the task unshared, because publication
would delete it.
`claude_profile_history.py` separates foreign request
metadata from native response diagnostics while preserving messages and IDs.
Repairs to shared CLI transcripts retain a private original and recover through
a separate journal because those files sit outside the desktop bundle. A
completed repair's original is checked by content, not file identity, so a
copied home still validates; a writer that races the rename gets its file back
and the next run repairs the new content.
Canonical CLI files, their sibling journals and private originals use the same
Windows filesystem boundary. The version-1 repair journal keeps ordinary file
names and retains the open-handle identity and no-replace recovery checks.

`claude_profile_sync.py` coordinates both directions under the two profile locks.
Only the current account pair participates, and on the subscription side only
its resolved organization; the gateway's organization is synthetic, so it spans
the account. The outgoing profile wins conflicts; unique bundle artifacts join
the union before duplicates are retired. Shared CLI history takes precedence
over an older bundle snapshot. A task with no transcript anywhere, or with
diverged transcripts, is left unshared and counted. Invalid tasks are reported
to the switch caller, which must keep the current mode until every in-scope
task is safe. Before either pass, the ledger retires copies of tasks deleted
since the last clean sync, and only a clean sync updates what it remembers. The
coordinator has no app-lifecycle authority.

`claude_profile_ledger.py` keeps a deleted task deleted. After a clean sync it
records, in a private router-home file, a digest of each copy of every task both
profiles hold once: record bytes, bundle tree and paths, never titles or
content. Tasks the sync left unshared or refused are not recorded. Presence
counts across the whole account, so an organization change never looks like a
delete. A remembered task missing from exactly one profile has its other copy
retired to that store's `.claude-profile-control-trash` folder while the copy
still matches; a changed copy stays and is shared again. Retirement reuses the
publication pattern: a journal, then exclusive renames of the record and then
the bundle. The next run undoes an interrupted retirement before deciding again.
Interrupted transfers are recovered first; an unreadable record or a second
copy keeps every copy, and a profile that lost every shared task at once, when
there was more than one, is treated as a reset. Nothing is hard-deleted, and a
trash entry that cannot be put back safely stays for inspection and fails the
switch.

`claude_desktop_platform.py` owns native app identity, graceful shutdown,
dialogs and owned shortcuts. It waits for known writers and their children. A
Linux identity check delegates to `desktop_linux.py`, which selects one XDG
desktop entry, resolves its supported command shape, and validates the matching
Electron `resources/app.asar` package metadata. It reads only `package.json`
from the archive and never launches the desktop command or wrapper. Linux
tray switching uses this verified entry and waits for bundled writers.
Native desktop acceptance remains separate from these source and filesystem checks. A
process that execs another program keeps its start time and stays tracked; an
exited process still waiting for its parent (a zombie) can no longer write, so
it counts as gone. Before the quit request, an unknown writer or unreadable
process list refuses the operation, and a refused request ends it at once.
After a request that was sent, the wait decides the outcome, even when the
request timed out, because Claude may still close once its own confirmation is
answered. Processes that are quitting can briefly fail a check,
so a failed check, including a reused process ID, is retried until the deadline
and only a clean check ends the wait. Its macOS lifecycle helpers take an
`app` (bundle id, plus the executable names only that app may run) that
defaults to Claude; Switch Codex passes the ChatGPT app's, which lists no such
names, so unrelated standalone clients do not seed its writer set.
On macOS, bundle discovery uses Spotlight metadata because AppleScript app
lookup launches a closed app. Browser-owned native messaging hosts do not seed
the writer set, and crash reporters (any `crashpad_handler`) never join it:
they write only crash reports and can outlive an app update by days. Actual
app descendants remain tracked after reparenting.
Descendant discovery precedes rejection of an otherwise unknown Claude process,
because Desktop's Code executable can live outside its application bundle.
`claude_profile_launch.py` resolves the current installed release and dispatches
the requested action. `claude_profile_hook.py` owns only its exact SessionStart
callback entry and captures the focused native account identity asynchronously.
It never copies history, and uninstall preserves unrelated user hooks. The
callback runs Python with `-P`, so a file in the session's project folder can
never stand in for a module it imports.
