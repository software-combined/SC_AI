# Changelog

## 1.4.4

- Let Claude Code estimate context usage locally for OpenRouter models by
  skipping a network call to OpenRouter's unavailable token-counting endpoint.

## 1.4.3

- Restore approved Messages-compatible models in Claude's picker under their
  actual vendor, model and provider names. Stable gateway IDs resolve to the
  exact provider model without assigning Claude capabilities to other models.
  Existing direct IDs, model choices, access checks and worker selection remain valid.

## 1.4.2

- Extract each Windows installer build into its own folder so leftover files from an older installer cannot trigger the setup wizard on a healthy repeat.

## 1.4.1

- Let the key window close on its own deadline. An idle window cancels without a repair warning, and Check setup still recognizes a working saved key after cancellation.
- On Windows, **Help → Troubleshooting…** opens the linked guide in your browser.
- Reopening the same Windows installer for a healthy copy of SCG Router shows one up-to-date notice.

## 1.4.0

- The download page and setup guide describe the automatic setup.
- Setup from a source checkout (`install.sh`, `install.ps1` or `packaging/install.py`) needs Python 3.14 and says so clearly on an older Python.
- Remove retired download sign-in code. Downloads were already public, so updates work as before.
- `tools/build_native_installer.py` no longer accepts `--download-config` or the no-op `--allow-unsigned`.
- Setup and update saves retry on the newer settings instead of overwriting a concurrent save. A very short window remains, and an installer run can still replace a save made while it runs.
- Count a deferred Windows update once. The retry counter no longer rises twice, and the deferral message appears once.
- Setup asks one access question: sign in with your work account or use your own key. It no longer asks about ChatGPT or Claude subscriptions and assumes you use them; IT can still pass `--openai-mode none` or `--claude-mode none`. Saved choices are kept.
- Setup no longer offers or writes starter instructions (`AGENTS.md`). An existing file is untouched.
- Setup ends with one notice that names your assistants and how to restart them. During setup it no longer asks for a test message, an SC tool check, a Claude switch to OpenRouter or (on Windows) a Codex restart, and the access window shows no separate confirmation. **Check setup** still offers the reply checks, and the SCG Router menu offers the Claude switch.
- Opening the Mac installer again installs, updates or repairs, as on Windows, instead of showing a list of actions. With the same or an older installer it only says SCG Router is up to date.
- **Update or repair** asks you to close your assistants only when a connection must change, or when Claude desktop uses OpenRouter.
- Setup asks no question about assistants. It connects Codex, Claude Code and Claude desktop when it finds them, and one that cannot connect does not stop the others. If none connects, the closing notice says to install Codex or Claude if needed and choose **Update or repair**. Scheduled updates, and runs that only change modes once an assistant is connected, never connect a new assistant. A saved `--client none` connects nothing. A saved `--clients none` keeps the installer, bootstrap and **Update or repair** from connecting new assistants; **Connect another assistant** still connects them. Without a saved choice, update notices name only the assistants that are connected.
- On Windows, a folder or name that contains a curly apostrophe (’) no longer breaks setup shortcuts, startup or dialogs. Shortcuts, startup, notices and Windows maintenance start the Windows system copy of PowerShell.
- The installer and `bootstrap.sh` option `--choose-clients`, the `bootstrap.ps1` option `-ChooseClients` and the `ROUTER_NO_CLIENT_CHOOSER` setting are removed. Scripts that pass them should drop them.
- On Linux, restart notices appear on computers that have only the dialog tool bundled with setup, as other SCG Router windows already do.
- **Help → Troubleshooting…** opens the troubleshooting overview, which links to separate pages for Codex, Claude, and install and service problems.
