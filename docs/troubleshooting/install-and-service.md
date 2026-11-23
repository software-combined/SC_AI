# Install and service troubleshooting

Start with the checks in [troubleshooting](README.md).

## Windows: use the installed setup tools

On Microsoft Windows 11 x64, open the permanent **SCG Router** Start menu shortcut
and choose **Check setup** first. The commands below are for IT diagnostics after setup.
Use ordinary PowerShell under the same Windows user who ran setup.
If your organization blocks scripts, contact IT; keep its execution policy in place.
You do not need a repository checkout or a separate Python installation.

Paste this block once to find the installed tools. It reads paths and the
installed version, and prints no keys:

```powershell
$RouterRoot = if ($env:ROUTER_HOME) { $env:ROUTER_HOME } else { Join-Path $env:USERPROFILE '.codex\mixed-model-router' }
$RouterVersion = (Get-Content -Raw -LiteralPath (Join-Path $RouterRoot 'current')).Trim()
$RouterResourceName = (Get-Content -Raw -LiteralPath (Join-Path $RouterRoot 'setup-current')).Trim()
if ($RouterVersion -notmatch '^\d+(?:\.\d+){2,3}$' -or
    $RouterResourceName -notmatch '^\d+(?:\.\d+){2,3}-[0-9a-f]{16}(?:-repair-[0-9a-f]{12})?$') {
    throw 'Run SCG Router setup again before continuing.'
}
$RouterResources = Join-Path (Join-Path $RouterRoot 'setup') $RouterResourceName
$RouterPython = Join-Path $RouterResources 'runtime\python\python.exe'
$RouterInstaller = Join-Path $RouterRoot "releases\$RouterVersion\packaging\install.py"
if (!(Test-Path -LiteralPath $RouterPython) -or !(Test-Path -LiteralPath $RouterInstaller)) { throw 'Run SCG Router setup again before continuing.' }
$RouterSavedState = Get-Content -Raw -LiteralPath (Join-Path $RouterRoot 'mixed-router-state.json') | ConvertFrom-Json
$RouterClaudeRoute = if ($null -ne $RouterSavedState.anthropic_mode) { $RouterSavedState.anthropic_mode } elseif ($null -ne $RouterSavedState.openai_mode) { $RouterSavedState.openai_mode } else { 'subscription' }
Remove-Variable RouterSavedState
if (@('subscription', 'none') -notcontains $RouterClaudeRoute) { throw 'SCG Router settings need an IT check before continuing.' }
```

The `setup-current` pointer selects the retained setup runtime; the block does
not search for the newest folder. It also preserves Claude's current subscription
setting, including older installs where it follows the ChatGPT setting.
Keep `$RouterClaudeRoute` in the Codex commands below so a Codex change does not
disable a working Claude connection.

For a diagnostic check, run:

```powershell
& $RouterPython $RouterInstaller --home $RouterRoot --doctor
```

If you open a new PowerShell window or the router updates, paste the path block again.
For a source installation, use its Python 3.14 interpreter and matching installer instead.

## The installer stops before it downloads anything

Check that the machine can reach the feed origin for this channel
(`https://dist.softwarecombined.com/<channel>/latest.json`; `--status` names
the channel and the feed source, not the URL), including any proxy, then run
the same command again. A transient DNS or TLS failure is not sticky.

## An update keeps failing, or stops trying

After three failed attempts at one version the updater parks that version and
prints `parking <version> after 3 failed attempts; run the installer by hand to
retry`; later checks report `skipping <version>`. A parked version does not
affect the running router, which keeps serving the version it already has.

- Failed attempts are counted per version in the router state and the count is
  cleared by a successful install.
- `logs/update.log` records each activated install as one JSON line (`at`,
  `version`, `source`). The output of a failed attempt goes there too on macOS,
  and to the update service's journal on Linux:
  `journalctl --user -u codex-mixed-model-router-update.service`.
- Retry by hand: run `packaging/install.py --home <home>`.
- Move back: `packaging/install.py --home <home> --rollback --to <installed
  version>` (`--version <version>` stays as its older spelling).

## The router is not serving

- Health: `http://127.0.0.1:<port>/<token>/health`, with the port and token
  from `mixed-router-state.json`. Keep that URL private. A healthy answer is
  `status: ok` with the installed version.
- `--status` reports `service: serving`, `not serving` or `unknown`.
- Service state per platform:

```sh
# macOS
launchctl print gui/$(id -u)/com.local.codex-mixed-model-router
# Linux with a systemd user manager
systemctl --user status codex-mixed-model-router.service
# Windows (PowerShell)
schtasks /Query /TN CodexMixedModelRouter /V /FO LIST
```

- Logs live under `logs/` in the router home. A file there is deleted 30 days
  after its last write, at each router start and scheduled update, apart from
  the three the running router writes, which keep their size caps.

## A request fails

| Code | Meaning |
|---|---|
| 400 | Model id, payload or local key configuration is invalid |
| 403 | Missing or wrong path token, or a browser-originated request was refused |
| 409 | The provider cannot serve this request, for example an unsupported reasoning level; the message names the allowed levels |
| 503 with `Retry-After` | Not served: the router is draining for an update (`SERVER_DRAINING`) or mapped an upstream 429 (`UPSTREAM_RATE_LIMITED`); retry after the delay. A refused subscription turn names the model and the subscription: retry shortly, or select a routed model |

`BODY_TOO_LARGE` (`400`) means the request exceeds the router's local 256 MiB
ceiling on sent or decompressed bytes. Native history and images are preserved;
external Responses can shorten old content before sending it. Reduce large
attachments or use the client's compaction command before retrying. The work
on disk is untouched. `logs/router.jsonl` records sizes and carried classes in
`turn_refused`; `turn_trimmed` records any external content reduction.
`OVERSIZE_BUSY` (`503`) means a large turn could not reserve space in the shared
1 GiB request budget after waiting up to 60 seconds. Retry shortly; smaller
requests can still proceed.

## The key is missing or was revoked

A fresh install opens the native key window by itself when the installed
service has no key; the agent must never handle the key. If no window
appears, re-run the installer with `--setup`: it restarts the current release
with a fresh setup link and opens the window, without re-extracting the
release. A key exported in the invoking shell is not passed to the installed
service, so the installer collects a key file instead. Scheduled `--update`
runs and manual `--check-update` runs never pop the window; the next request
opens it instead. `ROUTER_NO_KEY_WINDOW=1` suppresses only the dialog for
unattended installs.

On Codex, a missing or rejected key opens the native key window on the next
request; on a host with no dialog tool the loopback setup page opens instead.
A rejected key is only detected on that path, so a Claude Code (Messages)
request reports the upstream error instead of opening a window. Never paste a
key into chat, a ticket or a logged terminal. The plain `--status` line covers
the default provider and is one of `usable`, `present` or `missing`;
`--status --json` reports every provider. Neither prints the key.

## What to send IT

`--doctor --json` and `--status --json` output. They carry no tokens, keys,
URLs or config bodies. For anything deeper run `--support` and send the
bundle it names: booleans, counts, versions and timestamps only. Never send
`mixed-router-state.json`, `activation.json` or the raw `logs/` files.
