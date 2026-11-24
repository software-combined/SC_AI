# Claude desktop limits

Observed behaviour and limits of the [Claude desktop app](claude-desktop.md).

The desktop app (observed in the 2.9939.2 native probes) keeps first-party and
third-party mode in separate profiles (`.../Claude` and `.../Claude-3p`).
The third-party profile uses `~/Library/Application Support` on macOS,
`LOCALAPPDATA` on Windows, and `XDG_CONFIG_HOME` with a `~/.config` fallback
on Linux. Windows falls back to Electron's roaming AppData location only
when `LOCALAPPDATA` is absent. The subscription profile uses roaming AppData.
Set `CLAUDE_USER_DATA_DIR` to override the third-party profile on all three
systems. The first-party profile remains at the platform's native location.
The override's parent folder must be writable so sharing and account recovery can coordinate safely.
Windows Store installations resolve that subscription profile from the signed-in
user's package registration automatically. Its `Network/Cookies` storage is a
sign-in change detector, with legacy `Cookies` storage still supported; neither
location supplies authentication to a gateway or crosses profiles. On Windows,
the session callback uses the client's documented executable-and-arguments form,
available since Claude Code 2.1.139, so Git Bash is not a prerequisite.
Automatic updates keep using the profile recorded when Claude was attached,
so an attachment made before Windows moved to `LOCALAPPDATA` keeps updating.
Running setup with `--desktop` refuses a different profile while an existing
attachment still owns its restore record; detach that connection before
selecting another profile.
The paths are pinned by simulated platform tests. Real macOS Code-task visibility,
open and resume passed the installed-launcher round trips above. Windows and
Linux still require native app acceptance.
Pointing the third-party profile at the loopback router lists every
approved Messages-compatible registry row. The app filters non-Anthropic
vendor words from IDs even when a valid `anthropic_family_tier` is present.
Non-Claude rows use stable `claude/scg/<hash>` gateway IDs and keep their actual
vendor, model and provider labels. Router resolves only known IDs to their
registered provider before checking access and forwarding the request. It
assigns no Claude family or `behavesAs` metadata to another vendor.
On Windows Desktop 4.4212.0.0, Router beta showed 30 models for the test account.
DeepSeek V4.1 Flash 1017 ran the SC Documentation skill in a local Code session
and returned a reply. The provider reported the selected model on both requests.
The session kept its model and tool result when reopened. Managed configurations
and other Desktop versions still need native acceptance. Attach with
`packaging/install.py --desktop`. Without a Claude subscription
(`claude_mode` `none`), the menu disables **Claude subscription** and the switch
refuses to move there. Service-only install and uninstall use the strict detach
checks above. The first-party profile's credentials are never touched, so native
sign-in survives. A successful detach returns the app to first-party mode.

Coexistence limit: third-party mode replaces the whole picker with
gateway rows. Native subscription models are not in it, and the profile
starts empty of first-party preferences, trusted folders, and
org-served connectors (those resolve against org identity, not local
files, so the installer does not copy them). Local stdio or remote MCP
declarations can be owned the same way when they exist; on a profile
with none, nothing is carried. This is a client limitation, not a router
defect; reaching the app's hybrid selector would need a bootstrap server
and org changes, which remain out of scope.

Effort control: the desktop keys its thinking-effort options off native
model names, so gateway rows show no effort picker on this client
version. Any `thinking` the app sends still travels byte-identical
through the router. Effort choice for gateway models stays a CLI
(`ANTHROPIC_MODEL` plus per-call fields) and Codex picker affair until
the client offers otherwise.

Deferred tool loading: the app's own gateway mode already asks for it. From
an app that bundles Claude Code `2.1.247` or later, the request carries the
`tool-search-tool-2025-10-19` beta value, the deferred tool loading and the
`tool_reference` blocks, while the app suppresses Claude Code's other
experimental betas for that provider. The external-route rewrite above is
what makes that shape work through OpenRouter; the desktop attachment does
not write any env key of its own for it, and the app's suppression stays as
it is. An operator who wants the app to defer even where its own policy says
otherwise can set `ENABLE_TOOL_SEARCH` to `force` in OS-level Claude Code
managed settings with `parentSettingsBehavior: "merge"`; the installer never
writes that policy file.

## Bounded desktop verification

`tools/probe_claude_desktop.py --execute --endpoint-file <private-file>` starts
a temporary loopback connection for a synthetic Code task. It accepts only
DeepSeek V4.1 Flash, with four requests, 2,048 output tokens and 256 KiB of input
per request. It writes the connection URL to a new owner-only file and logs
only counters, status and served model identity. It does not edit app settings.
Temporarily select that connection in an isolated gateway profile, read a
synthetic file once, and restore the normal router connection before stopping
the probe. A startup check for another model is refused by this test guard.
