# Troubleshooting

Symptom-first remedies for a machine that runs the router. Every command here
is safe to run and prints no secrets. Replace the home path if you installed
elsewhere; the default is `~/.codex/mixed-model-router`.

```sh
python3.14 packaging/install.py --preflight --home ~/.codex/mixed-model-router
python3.14 packaging/install.py --status --home ~/.codex/mixed-model-router
python3.14 packaging/install.py --doctor --home ~/.codex/mixed-model-router
```

Start with `--doctor`: it reports one row per component (runtime, install,
service, each provider's key, the picker catalogue, the scheduled command and
update recency) and prints a `Fix:` line for every WARN or FAIL.

The catalogue check uses your company policy and the models available to your
key. Models hidden by either filter do not require a repair. A catalogue warning
means the saved rows differ from that installed projection.
Setup and repair record Claude's current served model list, including those
filters, for the separate listing check.

## Pages

- [Codex](codex.md): chats, tool schemas, the Send button, Switch Codex and missing models
- [Claude](claude.md): desktop switching, subscription access and Claude Code routing
- [Install and service](install-and-service.md): Windows setup tools, installer and update failures, serving, request failures, keys and what to send IT

## Automatic checks and logs

Scheduled checks can reconnect Codex when its complete Router block is missing.
This requires an active attachment receipt and a healthy Router.
Partial blocks, conflicting connection settings and damaged receipts require manual review.
Use the supported detach or removal action to disable automatic reconnection.
After attachment or repair, **Restart Codex to load SCG Router** offers **Quit and reopen** and **Later**.
If no dialog is available, the notice stays pending.
The content-free `logs/maintenance.jsonl` records regular and Express check outcomes.
It also records tray helper exits, retry decisions and controller exception types.
An unexpected tray exit gets one retry. Quit keeps the current controller closed.
New resource updates launch the menu quietly, including when sign-in startup is Off.
On Windows, missing or invalid preferences default to On. A valid saved Off stays Off.
Installs and updates reconcile the startup shortcut without saving a preference.
Use the menu's **Start at sign-in** action to save a choice.
Windows menu locks use the native session ID, so scheduled updates share the existing menu.
The menu starts before a startup repair warning; duplicate launches do not show another warning.

Windows task logs record launch, completion and safe failure facts, including missing launch scripts.
If no Python launch event exists, check Task Scheduler History and the task's last-result number.
The launcher cannot record attempts Windows refuses before Python starts.
Task-operation refusals include a numeric Windows error and a safe exception class when available.
They exclude the error message, task paths and raw command output.
`logs/update.log` records `installed <version>; health verified` after each verified installation.
Windows records success after the required runtime, controls and task bindings verify.
Verified restoration retries quietly. Incomplete restoration retains both runtimes and its recovery record for repair.
Menu and graphical setup also record when an install starts, exits or fails.
These events contain safe status fields; they do not copy installer output or settings.
Attachment failures have separate maintenance events. Unchanged checks and rollbacks do not claim an installation.

Windows updates verify the executable paths of all three owned scheduled tasks.
All three Windows tasks catch missed timed checks and use the installing user's sign-in.
Disabled schedules stay disabled. Windows normally delays catch-up runs by ten minutes;
see [Microsoft's scheduling behavior](https://learn.microsoft.com/en-us/windows/win32/taskschd/tasksettings-startwhenavailable).
Failed verification restores prior definitions and retries on the next maintenance pass.
Both runtime folders remain available. Do not remove old setup folders during recovery.
Device acceptance on Windows follows the
[native acceptance matrix](../release/native-installers.md#acceptance-matrix) and its Windows checks.

Temporary network, update-signature and download failures retry on the existing schedule.
The current Router keeps running. Rejected updates cannot install.
The menu shows **Updates will retry automatically**; these failures do not open Repair dialogs.
A verified successful feed check clears its earlier feed error, including an unchanged Express check.
If retry status persists, run **Check for updates** and share the safe error code with IT.

A repair warning can appear when the router runs the latest version.
Read versions and the last check time in **Check setup** or the tray **Updates** menu.
It means an installation is incomplete, a saved component failed, or an installer repeatedly failed.
A successful version check does not verify those components or clear a pending installation repair.
Missed checks alone do not require repair; the computer may have been asleep.
A shortcut or startup entry from another installation on macOS or Linux is recorded once,
not as a daily repair.
The warning names failed parts; `logs/maintenance.jsonl` records their names and your choice.
**Later** delays the next displayed warning for 24 hours. It keeps the repair pending.
If it returns sooner, the log distinguishes an unconfirmed dialog from a failed receipt write.
Choose **Repair now** after finishing active work. If the warning returns, run **Check setup**.
Share the reported part names with IT. Do not share keys or authentication files.

If Windows reports that Router could not check its stored key, retry shortly.
This message does not mean the key is invalid. If it persists, open **SCG Router**
and run **Check setup**. Permission-query diagnostics contain operation names,
Windows error numbers and timings, without key contents.
After three days, summarise `permission_query_failed`, `CREDENTIAL_PERMISSION` and
`CREDENTIAL_CHECK_UNAVAILABLE` across `router.jsonl` and rotations `.1`, `.2`, `.3`.
Include time coverage and missing files. Return counts, without raw log records.
This observation does not delay stable after functional Windows acceptance.

The historical configuration removal during account changes remains unverified.
Reproduce sign-in, sign-out or account switching only in an isolated standard Windows profile.
Compare configuration timestamps, size and block presence; do not read authentication files.

If Codex is installed but setup cannot verify it, setup does not connect it.
Choose **Update or repair** to look again. Do not install a separate CLI or
change PATH. Contact IT if Codex still does not connect.
Setup distinguishes an absent app, unclear Windows identity and an invalid
included setup tool. Preflight and plugin registration report fixed diagnostic
reasons without command output, private paths or credentials.
An installed app with an invalid tool never receives another download instruction.

If Switch Codex reports a missing bundled tool, check its redacted diagnostics.
Router discovers the current Store package, then checks the bundled Windows executable
and its version. Do not set `CODEX_BIN` or save a versioned Store path.
Store Codex identity and process checks use native Windows APIs.
Closing Codex's window can leave its tray app and tasks running.
Switch Codex asks to fully close Codex and stop its tasks before changing settings.
Finish active work before choosing Continue. Cancel leaves Codex unchanged.
The switch gives Codex five seconds to close, then ends its verified root before surviving workers.
It waits for confirmed exits before changing settings. Exiting processes need no further identity reads.
Reopening can take up to thirty seconds on a cold start.
A failure restores the previous connection and attempts reopening.
Confirmation and waiting windows use the verified native helper. Older helpers use
a hidden PowerShell dialog with the same icon and safe Cancel action.
If required Router components differ, switching refuses before closing Codex.
Open SCG Router to finish its update or repair. A temporary service check failure
asks you to retry; it does not establish installation damage.
Switching back remains available with coherent files when the Router is offline.
Claude desktop process checks retain a sixty-second limit for busy sessions.
A failed check refuses before changing settings.
If an update owns the installation lock, Switch Codex waits up to sixty seconds.
Its waiting window offers Cancel. Healthy unchanged update checks do not take that lock.
An actual install or repair can still delay switching; retry after it finishes.
The switch log distinguishes identity timeouts, query failures and rejected commands.
It records identity, quit, proof and reopen durations, plus scan count and maximum scan time.
Its command paths are relative to the package. Protected unrelated Windows processes
do not block switching; an unreadable relevant app process still requires attention.
Task timeouts record a closed stage name. Report that name to IT; raw command output
and private paths are excluded. Task Scheduler history covers failures before Python starts.
