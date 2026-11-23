# Updates

How installed routers receive, apply and roll back releases.

## Update feed: public and automatic

Every install polls the public feed at
`https://dist.softwarecombined.com/<channel>/latest.json` with no token,
no enrolment, no GitHub account and no repository access. The `channel`
file in the router home (`~/.codex/mixed-model-router`) selects the
document: `beta` follows the pre-release document, anything else (or a
missing file) follows `stable`. Checks run every 4 hours (macOS
`StartInterval` 14400, systemd `OnUnitInactiveSec=4h`, Windows `PT4H`);
Linux also runs a first check 5 minutes after the timer activates, and
macOS runs one when the job loads. Every channel document carries a
detached Ed25519 signature (`latest.json.sig`); the updater verifies the
exact served bytes before parsing and refuses unsigned or bad-signature
feeds with the `feed_signature` code (Plan 145). `file://` manual installs
stay operator-trusted when no sidecar is present. SHA-256 verification of
every bundle, version and identity checks, and the feed serial replay guard
still apply on top. Feeds and bundles off the trusted origins are
refused. Feeds and bundles never follow a redirect off that
origin, and a feed document without a bundle checksum is refused. A manual install passes `--feed` with a downloaded release
document; `--status` reports the feed source (`cloudfront`) and the
channel. A leftover `feed-token` file on an older host is inert and can
be ignored or deleted. The signing seed lives in Secrets Manager
(`FEED_SIGNING_SEED_ARN` in the release workflow) by name only; the seed
value never appears in logs or docs. `update.log` records each install with its source
(`cloudfront` or `local`).

A host still on a pre-cutover build reaches the public-feed version with
one bootstrap or one manual `--feed` install; after that it updates
itself.

First install uses the two bootstrap wrappers
(`packaging/bootstrap.sh` for macOS/Linux, `packaging/bootstrap.ps1` for
Windows). Each bootstrap downloads the pinned runtime and the release
bundle from the public feed, verifies both checksums, and runs the bundle
installer; `--channel=beta` follows pre-releases. The recipient never
touches GitHub and supplies no token.

The first-install assets are published by
`tools/publish_first_install.py`: it reads `packaging/runtime.lock`,
downloads each pinned CPython build (macOS arm64/x86_64, Linux x86_64 and
arm64 on glibc, Windows x64), verifies its sha256 before anything is
uploaded, and publishes the wrappers only after the runtimes and the
`runtimes.json` table they read. Re-run it after a runtime-lock change;
identical runtime artifacts are skipped and different bytes under a
runtime key are refused. The two `bootstrap/*` wrappers are the one
mutable entry point: they are replaced when they change and cached for
five minutes, so a wrapper fix can still reach new installers.

```sh
python3.14 tools/publish_first_install.py --bucket "$FEED_BUCKET" --dry-run  # plan only
python3.14 tools/publish_first_install.py --bucket "$FEED_BUCKET"  # download, verify, upload
```

Hand a recipient the `install/` URL for their OS. Every release refreshes
the `install/*` copies, while the `bootstrap/*` copies change only when this
tool runs:

```sh
curl -fsSL https://dist.softwarecombined.com/install/bootstrap.sh -o bootstrap.sh
sh bootstrap.sh
```

A machine that cannot use the bootstrap's download path still gets its
first install from a handed-off release directory with
`python3.14 packaging/install.py --feed file:///path/to/latest.json`, a
one-shot pin that is never persisted.

`docs/start/agent-install-prompt.md` guides staff through the native installer
and permanent SCG Router app. It selects assistants before setup, uses the
secure work-account route and diagnoses failures through retained tools.
Credentials, licence/security decisions and assistant restarts stay with the user.

Never run the installer against a scratch `--home` on a live machine:
service names are machine-wide, so even a /tmp home bootstraps, bootouts,
or TERMs the production jobs. `main()` refuses mutating actions on a
non-production home unless `ROUTER_LIVE_RUN=1` is set; local feed
experiments belong in a disposable session or VM with its own service
manager. Direct `do_install` calls in tests must use the fake `run` seam.

## Express updates

Maintainers can publish an urgent stable release with `v<VERSION>-express`,
or an urgent beta with `v<VERSION>-beta-express`. The tag includes the exact
semantic version from `packaging/VERSION`: `0.6.117` is `v0.6.117`. Use a new
tag for each release. These tags use the same tests, publisher permissions
and integrity checks as ordinary releases.

After installing an Express-capable version, macOS, Windows and Linux run
a separate lightweight Express check about every minute. Online machines
can begin an urgent update within a few minutes of feed publication;
downloads, request draining and health checks take additional time.
Each machine follows its existing stable or beta channel. Normal releases
continue on the four-hour schedule. A failed Express attempt waits for the
regular retry schedule, retaining the existing three-failure limit.

The jobs are `com.local.codex-mixed-model-router.update.express` on macOS,
`CodexMixedModelRouterUpdateExpress-<SID>` on Windows (the account's security identifier), and
`codex-mixed-model-router-express.timer` on Linux. The installer registers
and removes these with the regular jobs. They use the same home launcher
under the name `express_launch.py`, which skips older restored releases
that do not support Express.

Existing machines first need this version through their current update
schedule or a manual update. Sleeping/offline machines check when available.
A missing interpreter or broken updater still needs local recovery.

## How to roll back

Revert through `development` to `main` and tag (the next release supersedes
the bad one), or pin one machine with
`python3.14 packaging/install.py --rollback --to X`. The installer itself
restores the old pointer automatically when the new release fails its
health check. Scheduled updates keep running after a rollback, so the
channel offers the newer release again at the next pass; stop the scheduled
update job if the rollback has to persist until a fix ships.

A rollback does not rewrite the picker catalogue. Rows the newer release
added stay listed in the picker even though the restored release cannot
route them, and selecting one ends the turn with "That model is not
available on this machine". Re-run the installer, or refresh the picker
with `python3.14 -m ai_router.catalogue --merge <home>/mixed-models.json`
from the restored release, after rolling back across a release that added
or renamed a row.

A release before 0.6.9 recorded a `--feed` install's own build number in
`<home>/feed-serial`, so a local build could leave a number the published
feed has not reached. Every scheduled check then refuses the real feed with
`stale feed serial N is older than M`. Delete `<home>/feed-serial` to clear
it; the next unpinned update records the channel's own serial. Installs from
0.6.9 on leave that file alone.

## Safe update, restart, reinstall

Updates do not wait for idle traffic. Activation swaps the `current`
pointer, then sends one `TERM`: launchd `KeepAlive` restarts the router on
the held socket into the new release, so new connections queue in the
kernel while the outgoing process finishes the requests it already
accepted. An in-flight chat completes on the old release, and on macOS
nothing is refused. Linux has no socket activation (see below): the
outgoing process owns the port and stops accepting for the length of its
drain, so a connection attempted mid-handover fails until the new process
binds. One writer at a time, enforced by an advisory lock on
`install.lock` in the router home, so a scheduled pass and a manual run
cannot interleave.

Prefer `TERM` over `bootout` for a live service: `bootout` unloads the
definition, and if the following `bootstrap` does not take, the machine is
left with no router and no `KeepAlive` to recover it. A reload is only for
a plist launchd has actually loaded differently (a changed interpreter or
port), and it must wait for the label to leave the domain before
bootstrapping: `bootout` returns success while the job is still draining,
and a `bootstrap` issued in that window fails with `Bootstrap failed: 5`.
The installer never boots out the scheduled updater from inside it, since
that job is what runs the installer.

On failed health the installer restores the old pointer, TERMs again, and
then verifies a loaded job is serving the restored version, bootstrapping
it if launchd has none; it says the router is not serving rather than
reporting a clean rollback over a dead machine. A version that fails three
times is parked, so a bad release stops costing a service restart every
four hours; run the installer by hand to retry. The count lives in the
state file, which is what parks it on the production feed -- that feed is
read from the public feed. Linux uses
systemd user service restart with a 150-second stop timeout; the launcher
opens the same loopback port after the old process drains. It does not use
launchd socket activation. Failed upgrades restore the prior catalogue too.

Releases are installed only when feed version, manifest version and the
bundled `packaging/VERSION` marker all agree; any mismatch aborts
before any file, pointer or launchd change. `--feed` selects one run's
source and is never pinned, so a local test feed cannot freeze future
updates. Run local feed experiments in a disposable OS user session or VM,
with its own service manager and Codex configuration. A different `--home`
alone does not isolate the fixed user service names or client configuration.
