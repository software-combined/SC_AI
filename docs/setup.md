# Router setup

Start with the [README](../README.md#get-started) for the ordinary staff path.
This guide covers prerequisites, the first-run steps and alternatives. Setup
changes this computer's assistant settings and adds a background service and
automatic update jobs.

## Before you start

- Install the assistants you want to use: Codex, Claude Code or the Claude
  desktop app. Sign in to each one with your own ChatGPT or Claude subscription.
- Use **Sign in with my work account** in the key window when your
  organisation enables it. If you choose your own OpenRouter key, enter it
  only in that window; a coding agent must never handle it.
- Optional: an AWS Bedrock API key enables the Bedrock models. Create it in
  the AWS console for one region, enable the models you want in that
  region, and enter the key only in the key window when the router asks
  for AWS Bedrock. Set `bedrock_region` in the router state file to that
  region (default `us-east-1`) and restart the router after changing it.
- Native installers include Python and graphical setup. They need no Git.
  The macOS and Linux install script needs `python3`, `curl`, `tar` and a
  SHA-256 tool.
- Linux needs a running systemd user manager in the signed-in desktop session;
  setup refuses a bare remote SSH session without one.
- Check [compatibility](compatibility.md) for the supported platforms and
  unfinished acceptance checks.

## Set up SCG Router

1. Download SCG Router from `https://hub.softwarecombined.com/install` and
   choose your computer.
2. Open the installer: the DMG on macOS, the EXE on Windows or the AppImage on
   Ubuntu. On Ubuntu, you may need to allow the file to run as a program in
   its Properties window. You do not need to install FUSE, the Linux file system
   tool that AppImage files use. If your device policy blocks the installer,
   contact IT.
3. Wait for setup to finish. It asks no questions about your assistants. It
   looks for Codex, Claude Code and the Claude desktop app on this computer
   and connects each one it finds.
4. If setup needs a key, a key window opens. Choose **Sign in with my work
   account**, or **Use my own key** and enter your key there. If a key is
   already saved, this window does not open.
5. Read the closing notice. It names the assistants that setup connected and
   says how to restart each one. Restart them.
6. Start a new chat, choose a model and check that it replies.

**Check setup** in the SCG Router menu checks the reply and SC tools.
If no assistant was connected, the closing notice says to install Codex or
Claude if needed, then open SCG Router and choose **Update or repair**.

Claude desktop stays on its Claude subscription after setup. To use OpenRouter
models in it, choose **Claude**, then **OpenRouter**, in the SCG Router menu.

## After setup

The SCG Router app saves setup in your user account. You can delete the
download or eject the disk image. Opening a newer installer updates SCG
Router. With the same or an older download, the installer keeps the installed
version and shows **SCG Router is up to date**.

Open SCG Router to check setup, repair it, connect another assistant, replace
your key or remove the router. These keep the existing channel and settings,
and plugins you turned off stay off.
**Update or repair** and **Connect another assistant** both connect any
assistant installed since setup and keep the existing connections. A saved
choice can limit this; see [saved choices and flags](#reference-saved-choices-and-flags).

Windows Store Codex needs no separate CLI install or PATH change. SCG Router
finds its current package for setup, SC tools and scheduled updates. If
Windows cannot confirm the package, setup does not connect it and shows no
download instruction.

The default channel is `stable`. Use `--channel=beta` on macOS/Linux or
`-Channel beta` in PowerShell only when you intend to follow pre-releases.

## Which assistants connect

Each assistant connects on its own: if one cannot connect, the others still
do. If a newly found Claude desktop cannot connect, setup skips it without a
message. An assistant that is already connected and cannot be updated makes
setup report a failure after the others finish; choose **Update or repair**
to try it again.

Only a manual run looks for new assistants: the installer, the install script,
**Update or repair** and **Connect another assistant**. Scheduled and Express
updates keep the connected assistants and add none. Once an assistant is
connected, a run that passes only `--openai-mode`, `--claude-mode` or
`--anthropic-mode` changes the modes of the connected assistants and adds none.
Setup never disconnects an assistant, except that `--client none` (service
only) removes every connection when it installs a release.

## Reference: saved choices and flags

Every install starts on the ChatGPT and Claude subscriptions. A saved choice
decides what a manual run adds:

- `--client none` (service only): no run looks for or connects an assistant
  until a run passes `--clients` or `--client`. **Connect another assistant**
  does not change this.
- `--clients none` (no terminal assistant, also the result of
  `--clients none --desktop`): the installer, the install script and
  **Update or repair** add nothing and keep this choice.
  **Connect another assistant** (installer flag `--connect-found`) connects
  the assistants it finds and then saves the connected terminal assistants as
  the choice. Otherwise only `--clients` or `--client` changes it.
- `--clients codex` or `--clients claude`: a manual run still connects the
  other assistants it finds.

Explicit flags replace detection for scripted installs. `--clients` connects
only the named clients, including after service-only setup. `--client none`
conflicts with a request to connect an assistant.
From a source checkout's `router/` directory, with Python 3.14, use the
command for your intended setup:

| Assistant | Command |
|---|---|
| Codex app or terminal | `python3.14 packaging/install.py --clients codex` |
| Claude Code terminal | `python3.14 packaging/install.py --clients claude` |
| Claude desktop | `python3.14 packaging/install.py --clients none --desktop` |
| Both Claude surfaces | `python3.14 packaging/install.py --clients claude --desktop` |
| Service only | `python3.14 packaging/install.py --client none` |

The install script needs no checkout. Run the current install script again
to connect a newly installed assistant, or use the
[installed interpreter and installer](claude-code.md#setup).
For Claude desktop, choose **Claude**, then **OpenRouter**, in the SCG Router menu.
Claude restarts on OpenRouter. The first switch sets up the OpenRouter profile; switch back and forth once to bring your saved Code tasks.
Then choose Code, a folder and a
model. All gateway rows bill OpenRouter. [Claude setup](claude-code.md) explains
its separate profile and unfinished task-sharing checks.

Claude Code in the terminal keeps its subscription sign-in. Never set
`ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN`; either overrides that sign-in.
The one exception is an install without a Claude subscription
(`--claude-mode none`): there the installer sets `ANTHROPIC_AUTH_TOKEN` to a placeholder, so Claude Code needs no
Claude sign-in and every reply goes to OpenRouter.

## What the installer does

It checks the download's checksum, tests the runtime, installs the background
service and connects the assistants. If no key is saved, it opens the key
window. That window asks one question: sign in with your work account or use
your own key. In native setup, the window shows no confirmation of its own;
the one closing notice names the connected assistants and how to restart them.
Setup assumes you use the ChatGPT and Claude subscriptions you sign in to.
For a computer without one, IT passes `--openai-mode none` or
`--claude-mode none`. Setup writes no instructions file for your assistants.
If the key window does not appear, run setup again with `--setup` to restart
the current release with a fresh setup link. A key exported in the invoking
shell is not passed to the installed service. `ROUTER_NO_KEY_WINDOW=1`
suppresses only the window.

The default router home is `~/.codex/mixed-model-router`, or
`%USERPROFILE%\.codex\mixed-model-router` on Windows. The install script places
the same installer at `<home>/releases/<version>/packaging/install.py`,
where `<version>` is recorded in `<home>/current`. Use its pinned interpreter
at `<home>/runtime/python/bin/python3.14` (`python.exe` on Windows)
when the computer has no Python 3.14. Source installs can run `--preflight`
to check prerequisites or `--dry-run` to see planned changes without writing.
The install script and scheduled updates pass their retained interpreter to the
installer. An explicit eligible `--python` wins; otherwise an eligible running
interpreter comes before Python found through `PATH`.

<p><img src="assets/key-window-macos.png" alt="The first-run key window on macOS" width="400"></p>
The key window checks your key before saving it on this computer.
<p><img src="assets/update-dialog-macos.png" alt="The update notice on macOS" width="400"></p>
Updates install themselves. This notice asks for an assistant restart when new
models need to appear in its picker.

## Install from source

This alternative requires Git and Python 3.14. The install command
changes your local assistant settings and registers the service and update jobs.
Run from the cloned repository:

```sh
git clone https://github.com/software-combined/SC_AI.git
cd SC_AI/router
ROUTER_DIST_URL="$(python3.14 -c 'from pathlib import Path; print((Path.cwd() / "dist").as_uri())')"
python3.14 packaging/release.py --out dist --url-base "$ROUTER_DIST_URL"
python3.14 packaging/install.py --feed "$ROUTER_DIST_URL/latest.json"
```

On Windows, open PowerShell in the checkout's `router/` directory:

```powershell
$RouterDist = Join-Path $PWD 'dist'
$RouterDistUrl = ([uri]$RouterDist).AbsoluteUri
py -3.14 packaging/release.py --out $RouterDist --url-base $RouterDistUrl
py -3.14 packaging/install.py --feed "$RouterDistUrl/latest.json"
```

Use Python 3.14 for these commands; the installer refuses an older Python.
See [contributing](../CONTRIBUTING.md) for development checks and
[operations](operations.md) for update, rollback, uninstall and diagnostic
commands.
