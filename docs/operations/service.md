# Service

Removing the router, the operator commands and the platform service details.

## Uninstall

On Windows, open Settings → Apps → Installed apps, choose **SCG Router**, then
**Uninstall**. The Start menu also has **Uninstall SCG Router**. On every platform,
the SCG Router menu offers **Manage Router → Remove Router…**. Each asks first;
**Cancel** changes nothing.

Removal leaves Codex and terminal sessions open and restores their settings in place.
It asks to close Claude desktop only while Claude uses OpenRouter, because that
connection is switched back while Claude is closed. If an update is running,
removal waits up to five minutes for it, then reports that nothing was removed.
A successful removal closes the SCG Router menu and removes its sign-in entry.
On Windows it also removes the Start menu entries and the Settings → Apps entry.
The final message names any assistant to reopen.

From the source checkout or installed release directory, run
`python3.14 packaging/install.py --uninstall`. This stops and removes the
service and update schedule after restoring all verified client settings.
It exits with an error, and removes nothing, while another router operation
is still running after that wait.
Every assistant is checked before any detach. Changed connection values or
damaged ownership records refuse with a conflict and keep the service running.
If a later write fails, the result names completed and remaining attachments.
Retry removal; it accepts an already completed restore without repeating it.
Unrelated settings and their formatting remain in place. An empty assistant
JSON file is retained when its ownership was not recorded.
For a bootstrap installation,
use the [pinned interpreter](../start/setup.md#what-the-installer-does) if Python 3.14
is not available on the system.

Before repair or removal, the current setup source can produce a redacted
ownership report:

```sh
python3.14 tools/classify_attachments.py --home ~/.codex/mixed-model-router
```

Share only its JSON result. It contains assistant names, ownership classifications
and specific conflict reasons. It reads the same evidence as repair and removal;
it changes no settings and makes no model or download requests.

The state directory, key file and loopback token remain in place for you to
delete separately. Uninstall does not remove them, so setting up again later is
a reinstall that keeps your key and choices. Test a first installation on a fresh
account or computer, not after removal.

## Operator surface

The [desktop menu](../start/desktop-menu.md) exposes the same setup, key, restart, update,
removal and support owners. Closing the menu leaves routing running.
Menu delivery has its own status and retained files, separate from service health.

Every command is read-only unless it says otherwise, and none prints a
token, key or URL:

```sh
python3.14 packaging/install.py --doctor    # helper rows, a Fix line per WARN/FAIL
python3.14 packaging/install.py --status    # version, service, keys, channel, update recency
python3.14 packaging/install.py --check-update   # installed and available versions only
python3.14 packaging/install.py --update    # apply what the channel offers (scheduled action)
python3.14 packaging/install.py --rollback  # list installed releases; --to VERSION restores one
python3.14 packaging/install.py --support   # 0600 redacted bundle for a support request
```

`--doctor` exits 1 when any row fails. Its rows cover the Python runtime, the
installed release, the serving version, each provider key, the picker
catalogue (one `ai_router.catalogue --check` run), the Claude Code attach
snapshot against the live `GET /v1/models` listing, the scheduled command
carrier and update recency; a host whose launcher or systemd unit still runs
the read-only `--check-update` fails that row until the installer re-renders
it. `--status` reports `last_check_at`, `last_applied_version`, `last_error`
(a code from a closed set) and the per-version failure counts from state, so
a parked release is visible without reading the log. `--support` writes only
booleans, enums, versions, counts and timestamps to
`<home>/logs/support-<UTC>.json` and prints the path.

## Check the Linux desktop app identity

From `router/`, run the read-only check for the installed desktop app:

```sh
python3.14 packaging/desktop_linux.py --app codex
python3.14 packaging/desktop_linux.py --app claude
```

Each command reports the selected desktop entry, executable path, app root and
the package version stored in the app's Electron `package.json`. That is the
app's internal package version, not its distribution package-manager release.
The check refuses unrecognised wrappers and wrappers with relative targets.
It does not start or stop the app or change its settings.

On Linux, a successful update check with no newer release proves checking
only, and timer activity alone does not prove an update succeeded. To prove
installation, use a disposable Linux user session or a systemd-enabled VM with
a newer test bundle, then check the health version. Do not uninstall the live
router to test removal; test uninstall in that isolated setup.

## Windows (Task Scheduler)

Windows tasks use `CodexMixedModelRouter`, `CodexMixedModelRouterUpdate` and
`CodexMixedModelRouterUpdateExpress`, each followed by `-<SID>` for the installing
account's security identifier. Before changing a task, the installer verifies
its principal, Python executable and exact home launcher arguments.
Foreign or inaccessible legacy tasks stay untouched. Such a conflict at an
account-scoped name, or any malformed query, stops the operation. All replacement
definitions register before the old router stops. Registration failure retains
the old service for rollback. Existing schedule settings survive migration,
refresh and rollback, including a disabled schedule whose process is still running.
New tasks retain a pending setup marker in their definition.
Router handover records the same intent before stopping the old process and
clears it only after the expected version serves. A plain installer retry
finishes an interrupted handover or setup before enabling updates. An explicit
stop cancels both owned router definitions during migration. The router stays
stopped even while updater setup or legacy cleanup is pending. Restart or run
setup to verify the service before completing pending work.
Deliberately disabled schedules stay disabled.
After replacement health passes, legacy schedules are disabled. Their definitions
remain while queued or running, or while any instance remains. A later installer
retry removes them after exit. The migration never stops its updater parent.
Tasks run `pythonw.exe` through `task_launch.py` in the router home
(rewritten on every install), which appends stdout and stderr to
`logs\launchd.log` and `logs\update.log` (rotated at 1 MB, one backup). Every console child (`icacls`, `powershell`, `python`)
is spawned without a window; on every platform, a file under `logs/` is
deleted 30 days after its last write, at each service start and scheduled
update, apart from the live files, which keep their caps.

Restart and update: the task allows one instance (`IgnoreNew`), so a
handover posts the authenticated `/shutdown` and waits up to 180 seconds.
Structured task states and running instance identifiers prove exit; lost HTTP
health or a failed task query cannot authorize restart. A hung instance receives
a stop request and must exit within another ten seconds, or restart is refused.
Key protection: the router home carries an
inheritable owner-only grant and the key and state files a plain one.
Permission checks use security identifiers (SIDs) and numeric access rules,
so translated account names cannot change the result. Only the current user,
SYSTEM and Administrators can own the file or receive grants; OWNER RIGHTS
can refer only to that verified owner. An unreadable, malformed or widened
access control list (ACL) makes the router refuse the key. Read checks expire
after 30 seconds; protection writes always receive a fresh check.

## Incidents

Check `install.py --doctor` first, then `/health`, then `logs/launchd.log`,
then `launchctl print` for the router agent (`schtasks /query` on Windows).
Roll back by re-running the installer with `--rollback --to` naming the
previous release.
