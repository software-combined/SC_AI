# Distribution (outside the request path)

`desktop_control.py` owns the redacted desktop status and fixed action IDs.
It reads status through `diagnostics` without loading the installer.
It calls the existing client switchers, offer, setup, support and update owners.
Menu and graphical setup use `install_delivery.run_logged` for content-free
launch and child-exit records in `update.log`. `native_payload.succeeded` rejects
deferred zero exits consistently; child exit is separate from verified installation.
`desktop_service.py` uses the platform service lifecycle for bounded restart.
`desktop_model.py` gives native shells and the fallback window identical actions.
`desktop_menu.py` runs one shell per installation and graphical session.
Windows uses the native session ID rather than launcher environment variables.
Only the lock-owning controller offers a startup warning, through its worker
after the helper starts and the first menu document is sent.
On Mac, a session-scoped reopen request tells that shell to open its menu.
Fallback windows run one selected action and then close.
It serializes actions in a worker, while native menus stay responsive.
`desktop_startup.py` owns per-user startup entries and the persistent preference.
Only explicit choices write that preference. Windows defaults missing or invalid choices to On.
`native_shortcuts.py` snapshots and restores only its three fixed Windows shortcuts
and named per-user Apps values. It checks ownership before recovery and reads back
the result. Binary shortcut writes use the shared compare-before-write helper.
Recovery keeps a concurrent explicit startup choice and reconciles its shortcut.
These owner APIs support installation recovery; they never capture client settings.
When all three shortcut paths are absent, the snapshot records empty entries without
starting PowerShell. Any existing entry still requires native ownership inspection.
Symbolic links and filesystem inspection errors stop the operation. This avoids an
unnecessary process; it does not resolve failures when PowerShell is required.
`desktop_launch.py` follows retained setup resources, independently of inference rollback.
Closing the shell never stops routing. Polling is silent and makes no model calls.
`native_resources.py` consumes only this target's signed Resources descriptor.
It verifies archive size, checksum and matching core identity before retention.
Installation owns its lock. Windows repairs missing controls through required cohort
completion, including unchanged checks. Mac and Linux retain independent controls delivery.
`native_resources_publish.py` validates all five archives before `publish_feed.py`
uploads immutable resources and signs the channel document containing their map.

`infra/` owns the update feed as code (repository-only templates, deployed from a checkout): the certificate stack, the private
bucket, the CloudFront distribution, the DNS alias, and the tag-only
publisher role. `tools/publish_feed.py` owns
release publication: it turns a built `dist/` into the feed's
`<channel>/latest.json` and the GitHub Release document.
`tools/publish_first_install.py` owns the first-install assets: the pinned
`runtimes.json` and `runtimes/*`, plus the `bootstrap/*` wrappers. The
router imports neither: hosts read the feed through `packaging/feed.py`, which
stays the client-side owner of origin and channel resolution.

`packaging/release.py` parses normal and Express tags; Express is feed
urgency on stable or beta, never a third channel or a package-version suffix.
The platform backends own a separate minute Express job alongside the regular
four-hour job. Both use `update_launch.py` (also installed as
`express_launch.py`) and `updater.py`; an update-parent lock serializes
them while the child installer retains its own installation lock.
All three Windows tasks run for their installing user's sign-in and catch
missed timed runs. Runtime reconciliation migrates these settings transactionally
with task actions, while preserving enabled state, pending state and other settings.
Registered-task inspection uses its own running instances, refreshed before ID reads.
Only the documented not-running result is omitted; unknown errors still refuse.
The adapter returns numeric HRESULT and identifier-only exception type without messages.

## Agent plugins

`plugins/` and `.agents/plugins/marketplace.json` host the SCG agent-plugin
marketplace outside the router dependency map: no `ai_router/`, `tools/` or
`packaging/` module imports from `plugins/`, and plugin scripts never import
router code.

Plugin source is grouped under `plugins/<domain>/<plugin-name>/`; the
[domain index](../../plugins/README.md) also routes to shared department briefs.
`packaging/release.py` discovers package roots by their Codex manifest, so
updater exclusions apply to each plugin. `packaging/agent_skills.py` reads both
domain folders and older flat bundles, then preserves flat installed paths.
Duplicate plugin folder names fail before marketplace files are written.
