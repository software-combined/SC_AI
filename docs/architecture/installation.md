# Installation, setup and update ownership

Paths are relative to `router/`. See the [architecture map](../ARCHITECTURE.md) for the module overview and dependency direction.

Native packaging lives under `packaging/native/`; it wraps the canonical
installer without adding inference rules. `native_payload` retains disposable
downloads. `native_setup` owns the graphical flow and uses the existing client,
service and key-window owners. Repair uses the canonical `--repair` path;
explicit assistant additions use the existing client-selection path.
`repair_ui` owns explicit maintenance's graceful assistant-close prompt.
A repair that owns every connection asks only when Claude desktop uses
OpenRouter; any other repair asks when a connection needs rewriting.
Scheduled updates never call it. Public bootstrap scripts retain the saved
channel and working runtime; repair never starts key setup.
`client_dialog` is the one dialog owner. It holds the `SCG Router` title, the
bundled icon and each platform's launch: macOS through `osascript`, Windows
through `windows_shell` and Linux through the tool `dialog_tool` finds. Other
dialog modules keep their own wording and answers and ask it to draw. The
runtime key window loads it only when a window opens. `tests/test_popup_style.py`
fails when another module restates the title or icon or starts a dialog tool.
`dialog_tool` is a standard-library leaf shared by installer and runtime dialogs.
It validates retained setup paths before selecting the Linux wrapper.
`native_dialog` distinguishes cancellation from failed presentation so renewal
notices remain pending until a window appears.
`install_delivery` verifies and retains maintenance code before assistant
discovery. Attachment conflicts cannot block its controller, stable launchers
or Linux scheduler repair. Plugin and native controls delivery remain separate
from routing health, on both full and same-version installs.
The health-verified completion also owns installation evidence. Attachment failures
have separate events. `assistant_status` shares attachment classification with outer reconciliation.
`client_choice` resolves explicit flags, receipt-owned attachments and saved
choices. On a manual run without client flags it adds the assistants it
finds through `client_executable` and `claude_desktop_platform.app_identity`.
Scheduled and Express updates, dry runs, a saved `client: none` and mode flags
on an install with an attached client add none. A
saved `clients: none` adds none unless `--connect-found` (the menu's **Connect
another assistant**) asks. It attaches
each client on its own: a client that is neither named by a flag nor already
attached is skipped when it refuses; any other refusal is raised after the rest
have attached. Receipts record what
attached. The saved choice comes from `--clients` or `--client` (a bare
`--desktop` keeps it), receipts or the saved choice; a found assistant joins
it only after it attaches, and finding nothing never saves `none`. A saved
`clients: none` changes only through client flags or `--connect-found`.
`client_choice.saved_clients` is the one reader of the choice for the restart
notice, the scheduled model offer and `assistant_status`: without a saved
value it names the terminal clients the receipts hold, never Codex by default.
It persists Claude choices in `anthropic_mode`; the runtime keeps its existing
policy reader. Same-version mode changes use the service repair
lifecycle before client attachment, with prior state restored on reload failure.
Its pure mode comparison also drives native readiness. `setup_completion` owns
the installer's bounded key-window wait after attachment and applies late answers
through the same current-install lifecycle. It also owns native saved-key completion,
native setup's one client-aware closing notice and the **Check setup** copy.
**Check setup** verifies replies from Codex and Claude Code only: Claude desktop
keeps its own sign-in, so setup never switches it to OpenRouter.
The runtime only saves answers.
Completion and readiness share `state.setup_pending`: an active access window stays
pending, while expired preparation cannot block usable access with matching receipts.

`client_executable` owns discovery for setup prerequisites, plugin registration,
readiness and diagnostic preflight. Existing PATH, npm, local-bin and desktop
locations retain precedence. Windows Store fallback uses current-user Codex
identity and the existing contained executable/header/version checks.
Each lookup is fresh and rechecks package identity after validation.
Discovery never switches, closes or opens an assistant.

`codex_owned` compares the live marked region with the saved attachment using
standard-library TOML. It preserves added single-line root settings and comments
outside the replacement block. Unknown structures and changed connection values
refuse before a write. A bounded managed-Python verifier covers an interpreter
without standard-library TOML. Removal uses the same
proof and atomic writer, preserving dotfile links and detecting concurrent edits.
Preference and reviewer edits use the same lossless line helpers, including
client-written line endings and inline comments.

`client_removal` checks all connected assistants before detaching any. Its
JSON edits use `owned_json` to preserve unrelated bytes and reject duplicate
keys. Receipts retain original values and the written connection values.
Legacy Claude receipts use the saved Router state for those connection values.
Completed restores remain complete after an I/O failure; remaining receipts
keep the service running for a safe retry. Atomic writes compare saved content
again after preparing the temporary file.

`native_controller` retains verified installer code under an independent version
pointer. `update_launch` selects that controller across runtime rollback.
Linux reloads and reads back the effective stable updater command before
pruning. Loaded jobs and a running legacy updater retain their release files.
`runtime_rebind` uses verified retained resource metadata after `setup-current`
advances. The Windows task adapter snapshots all three owned definitions,
updates executable bindings and shared catch-up/sign-in policy, then verifies
the expected path and policy while preserving enabled and pending states.
Its JSON subprocess contract uses explicit UTF-8 output and decoding for Unicode paths and saved XML.
A failed readback restores attempted definitions. Both runtimes remain retained.
The outer maintenance cadence checks owned task paths without the installation lock.
Only a required repair repeats verification and changes tasks under that lock.
`desktop_menu` records helper exit codes and controller exception types.
It retries an unexpected helper exit once after one second within the controller.
Quit and removal stop it. Resource replacement uses the existing reload path.
Resource advancement launches with `--after-update`, bypassing only sign-in preferences.
That path opens no question or warning dialog. A held session lock leaves reload to its owner.
`work_account` owns native Microsoft sign-in and calls the Hub's dedicated
provisioning endpoint. Public sign-in settings ship with the release. It reuses
the PKCE transport in `download_oauth` and the shared single-question dialog;
the Hub owns company entitlement, workspace selection and personal-key budgets.
The shared progress dialog stays open during sign-in and key preparation.
Cancellation stops callback polling, prevents a later provisioning request and
discards a late response before it can reach the local setup writer.
`key_prompt` asks only how to connect and, for an own key, the key itself; it
submits the result to the existing local setup writer. Work keys,
OAuth tokens and management credentials never become release configuration.
The Microsoft callback shows a self-contained Hub-style confirmation with bundled
brand fonts and logo, and clears the consumed code from the browser address.
`feed` downloads public software without credentials. `control_models` checks
model bytes against a signed feed's checksum. The inference process only reads
the resulting model cache. `infra/downloads` owns token verification and short
download grants for legacy consumers. It cannot change model routing or provider credentials.

`state.update` is the shared read-modify-write path for `mixed-router-state.json`.
It rereads the document, applies the caller's change and writes only when the saved
bytes are unchanged. A concurrent save reruns the change on the newer document, a
bounded number of times; a save landing in the short gap between that check and the
rename can still be lost. `install.py` still writes its whole document under the installation lock.
`update_status` owns verified channel facts, cache identity and repair summaries.
It is the only writer of those facts: component results, installation repair,
failure counts and check results. Other modules pass it their results inside `state.update`.
It names the stored component results and the repair-step outcomes once, and holds the
failure threshold that parks a release. It also owns version validation for packaging callers.
Only a verified release for the same channel and source can support a cached
current-version response. Diagnostics and controls read those facts without
changing state. A successful feed check clears only earlier feed-verification or
transport errors. Unchanged Express checks record that recovery without claiming
installation success or consuming a regular update. Rejected data never reaches installation.
Temporary failures and missed checks remain visible as automatic retries.
A successful feed check cannot clear an incomplete installation or failed component.
`update_warning` offers a detached repair dialog after an applying check or when
controls open, only for incomplete installations, failed components or parked installers.
Its separate receipt records presentation time only; it cannot
clear verified facts or interfere with installation. Missing dialogs leave
the warning pending. Controls bind manual-check results to installed version,
channel and source before displaying them.

`notice_windows` owns Windows restart presentation and calls the existing
desktop identity, shutdown and visible-reopen checks. Retained setup resources
keep it available after the updater's extraction is removed. Its dialog lock
prevents stacked notices. Presentation and pending restart are separate facts:
a failed restart stays pending with manual steps, without automatic repeat
prompts. A notice that older setup already offered stays quiet in the background.
Compared atomic writes preserve a newer notice that arrives meanwhile.
Graphical setup suppresses detached notices while it owns completion guidance.

`update_reconcile` runs after applying-update installation locks close, including
unchanged regular and Express checks. It runs post-update repair in one fixed order:
installation, Codex attachment, assistant attention, then scheduled-task runtime.
Each step's module owns its checks. Read-only preflight does not take the installation lock.
An attachment repair, runtime repair or changed attention result takes the lock without waiting
and repeats verification. Healthy unchanged checks do not acquire it.
Restart-notice presentation runs after the lock closes.
`windows_installation` owns required Windows completion and interrupted recovery under
that existing lock. Shared modules reach its recovery, maintenance and readiness steps
through the Windows backend's repair hooks. Activating and finalising a staged cohort
(`install_delivery.activate` and `_finalize`) call it directly, because only a Windows
delivery stages one. It stages matching core, controller and native resources before activation.
Its private journal captures only fixed owned files, task definitions and entry points.
It never captures client configuration, credentials or full state.
Completion verifies health and component bindings before writing the cohort receipt.
After a runtime rollback, this transaction may select a verified matching older controller.
Newer controller files stay retained; independent callers keep their non-downgrade rule.
Verified restoration defers the update quietly: it raises `native_payload.Deferred`,
which the installer entry point turns into exit code 0. Incomplete restoration keeps both
runtimes and exposes repair attention. Attachment and plugin outcomes remain separate.
`codex_recovery` repairs only an absent block under a valid, active receipt and
healthy Router. `codex_owned` validates absence, connection conflicts and TOML.
Configuration and receipt writes compare their prior contents and verify readback.
Original uninstall evidence remains intact. The receipt retains a repair event
until `notice` can offer its configuration-only restart reason.
Normal attachment uses the same receipt event after configuration and receipt readback.
Unsafe active recovery marks assistant attention without replacing configuration or other component results.
The Windows task launcher records task kind, time, numeric status and safe failure classes.

`winsecurity` reads Windows security descriptors through the operating system.
`winacl` owns the permitted identities and rejects unsupported rules. Checks
have no verdict cache, so permission changes apply on the next key read.
Temporary operating-system failures cannot grant access or open key setup.

Desktop connection commands accept explicit destinations. The switch owner
rechecks the current selection while holding the installation lock, followed
by the client transition and profile locks. Repeated explicit destination
selections do nothing; reselecting the single OpenRouter menu choice offers
the other sign-in mode. Existing shortcuts retain their toggle behaviour. Platform identity
and lifecycle helpers serve both clients; the configuration proof uses the
CLI bundled with the verified desktop app.
Windows switching checks the required-component receipt under the installation lock
before identity discovery or pending-switch recovery. Forward preflight and proof
also check the serving version; reverse recovery can proceed offline without a CLI.
Legacy tray resources use the existing quiet Windows dialog rather than unsupported helper modes.
The updater marks an automatic installer child once. Installation consumes that marker
and respects removal under its lock. Explicit setup can reinstall. Runtime-only legacy
installs retain their pending-task protocol; native installations never use that bypass.
