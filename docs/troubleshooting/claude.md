# Claude troubleshooting

Start with the checks in [troubleshooting](README.md).

## Claude desktop: switch to OpenRouter and back

From 1.3, use **SCG Router → Claude** to choose an explicit connection.
The [desktop menu](../start/desktop-menu.md) uses the same guarded switch owner described below.
Native Windows and Linux desktop acceptance remains pending.

Claude desktop uses separate subscription and OpenRouter profiles. Selecting a
model inside one profile does not change the connection. The OpenRouter profile
lists models billed to your OpenRouter key.

### Microsoft Windows

First setup connects Claude desktop when it finds the app. On an existing
router installation, quit Claude normally, paste the [installed-tool path block](install-and-service.md#windows-use-the-installed-setup-tools), then run:

```powershell
& $RouterPython $RouterInstaller --python $RouterPython --home $RouterRoot --desktop
```

This attaches only Claude desktop and keeps other attached assistants in place.
Claude stays on your Claude subscription until you choose **SCG Router → Claude →
OpenRouter**. Claude then restarts on OpenRouter. The first switch sets up the OpenRouter profile; switch back and forth once to bring your saved Code tasks. Choose **Code**,
a folder and an OpenRouter model. Send a short greeting and check that it replies. Re-running setup preserves an existing connection choice;
it does not toggle between subscription and OpenRouter.

**Windows switching is an IT pilot, not a verified staff rollout.** Setup does
not install **Switch Claude** or **Open Claude** shortcuts on Windows yet.
The release includes a manual helper for an IT-led pilot:

```powershell
$RouterClaudeSwitch = Join-Path $RouterRoot "releases\$RouterVersion\packaging\claude_desktop_switch.py"
& $RouterPython $RouterClaudeSwitch --home $RouterRoot --action switch
```

The helper asks to change to the other connection, closes Claude normally, then reopens it.
Run the same command again to return. It can refuse if settings are managed,
tasks are not ready to share, or Claude cannot close. Keep that refusal and contact IT.
Do not edit profile files or force-close Claude to get past it.

Before staff use this Windows switch, IT must verify both directions on a real
Windows machine, including a reply, saved Code tasks and the original subscription sign-in.
Windows task sharing remains unverified; Cowork tasks and cloud chats are not transferred.
Until that pilot passes, use Codex's Windows OpenRouter steps when you need to
work without ChatGPT subscription access.

### macOS

Open **Switch Claude** from your user's Applications folder. Confirm the change
to OpenRouter and let Claude restart. Choose **Code**, a folder and an OpenRouter
model, then check that it replies. Open **Switch Claude** again to return to your
Claude subscription, confirm the restart and check a subscription reply.
**Open Claude** opens whichever connection is selected; it does not switch it.
Cancel leaves the selection unchanged. If Claude refuses to close or share a task,
follow its message; keep your original tasks in place.

Mac Code-task sharing has passed recorded round trips. Cowork tasks and cloud chats
remain separate. See [Claude desktop setup and limits](../clients/claude-desktop.md#claude-desktop-app).

If your Claude account changed, choosing OpenRouter offers a separate profile.
Confirm the restart to keep the previous profile and tasks in a private archive
and start clean. Nothing from that earlier profile is shared into the new one.
You can also return to your subscription without sharing the earlier tasks.
If Claude asks you to open a Code task first, do that on your subscription so
the current account can be verified. Do not delete account bindings or history.
If recovery was interrupted, choose Claude in SCG Router again. Recovery asks
before restarting and returns to your subscription. A conflict retains the
saved data and leaves Claude closed; contact IT rather than forcing it open.

## I have no Claude subscription access

Ask IT to add `--claude-mode none` to the install command. Then:

- Claude Code in the terminal needs no Claude sign-in. It starts on OpenAI
  GPT-6 Luna at max effort. Its Opus, Sonnet, Haiku and Fable choices use the
  matching Claude models on OpenRouter, or Claude Sonnet when one is missing.
  Restart it after setup.
- Claude desktop opens on OpenRouter. **Claude subscription** is unavailable
  in the SCG Router menu.

Setup stops with a message when your OpenRouter key cannot use Claude Sonnet.
Ask IT to check the key. To add a subscription later, ask IT to run the
installer with `--claude-mode subscription`.

## Claude Code stopped using the router

`ANTHROPIC_BASE_URL` must point at the loopback URL with the path token;
`ANTHROPIC_AUTH_TOKEN` and `ANTHROPIC_API_KEY` must stay unset, because either
one replaces the subscription credential the router forwards. Without a Claude
subscription, the installer sets `ANTHROPIC_AUTH_TOKEN` to its own placeholder;
leave that value as it is.

- Re-attach: `packaging/install.py --home <home> --clients claude` (or `both`).
- Detach everything: `packaging/install.py --home <home> --uninstall`.
- Desktop third-party profile: add `--desktop` when attaching.

If Claude Code routes but loads every MCP tool on every turn, deferred tool
loading is off. `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS`, set anywhere in
reach, forces it off and no value overrides it: the attach refuses while it is
set and `python3.14 packaging/install.py --doctor` names the file carrying it.
Remove the variable, restart Claude Code, and check that `ENABLE_TOOL_SEARCH`
is `true` in the client's `env` block. See [Claude Code setup](../clients/claude-code.md).
