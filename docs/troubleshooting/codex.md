# Codex troubleshooting

Start with the checks in [troubleshooting](README.md).

## Existing Codex chats fail after a model switch

A provider can reject an old chat's tools even when a fresh chat works.
Codex can send current tools alongside saved `additional_tools` declarations.
Router merges these before assigning tool names, then removes the promoted
definition blocks from external requests. Conversation messages and paired
tool results remain available; saved chat history is unchanged.

If the error persists after updating Router, share the model name and safe
`upstream_rejected` diagnostics with IT. Do not share raw chat or request bodies.
Current schemas win. A saved schema can fill in a declaration that has none.
The reproducer is `tools/probe_duplicate_tools.py`; it runs offline
unless `--live --max-calls 3` explicitly enables its bounded provider comparison.

## Claude on OpenRouter rejects Codex tool schemas

A fresh chat can fail even on a greeting because Codex sends its tool schemas
with the message. Claude rejects `anyOf`, `oneOf` and `allOf` at the root of a
tool's parameter schema. Its nested provider error can otherwise appear as an
unnamed HTTP 400 rejection.

The Router uses an argument envelope for these schemas on configured Claude
Responses rows. It restores the original arguments before Codex validates and
executes the tool, and applies the same envelope when replaying tool calls.
Plain object schemas and compositions inside properties keep their native form.

Run the offline regression with `python3.14 -m unittest tests.test_tool_compositions`.
The separate synthetic live check is
`python3.14 tools/probe_tool_compositions.py --model anthropic/claude-haiku-5.5 --live --max-calls 3`.
It makes at most three requests, each capped at 2048 output tokens, and checks
the original rejection, adapted tool arguments and final returned marker.
It does not run as a paid CI test or change installed settings.

## OpenRouter rejects every new Codex chat

Codex can request `output.encrypted_content` in the Responses API `include` list.
OpenRouter rejects that option before selecting a model provider. The router can
then show `PROVIDER_REJECTED` and suggest a new chat, which has the same problem.
Service health and a working key do not detect this request compatibility error.

The compatibility fix removes only `output.encrypted_content` on the OpenRouter
route. It preserves other include options and the ChatGPT subscription request.
Verify with a fresh Codex reply and a tool round trip through the affected model.
A minimal HTTP request can pass because it does not request encrypted output.

## Codex Send button is greyed out or ChatGPT subscription access is unavailable

Open **SCG Router → Codex** and check the displayed ChatGPT sign-in status.
If OpenRouter is not checked, choose it and read the confirmation. If that
confirmation keeps sign-in, confirm it, then select the checked OpenRouter
choice again to offer the signed-out connection. If the status already says
sign-in is not used, do not reselect it: that offers the signed-in connection.
During a limit, confirm the signed-out choice. To sign in again,
select the checked OpenRouter choice or choose **ChatGPT + OpenRouter**.
The commands below remain recovery steps for installations without the
[desktop menu](../start/desktop-menu.md) and have their stated history limits.

Normal OpenRouter-only use keeps your ChatGPT sign-in, projects and setup
choices, and it keeps the same chats visible because it does not change
Codex's model provider. The active-limit fallback signs Codex out to keep
Send available. Projects and setup choices stay separate until you switch
back.

Affected Codex desktop versions disable **Send** when the ChatGPT allowance runs out,
including when you select an OpenRouter model. The router cannot fix a disabled
button by changing models alone. Change Codex's connection to OpenRouter.
If you have no ChatGPT subscription access, use the same OpenRouter connection.
Other causes of a disabled button need diagnosis if this does not restore it.

### Microsoft Windows

Use these commands for new chats. Before changing connections, save a short task
handover outside Codex. Existing chats can need their original connection to reopen:
OpenRouter chats need the OpenRouter connection again after you return to your subscription.
These Windows commands do not provide the Mac helper's preservation of both chat connections.

1. Let any running task finish. Quit Codex and close its terminal sessions normally.
2. Open PowerShell and paste the [installed-tool path block](install-and-service.md#windows-use-the-installed-setup-tools).
3. Run this command to use OpenRouter without a ChatGPT subscription:

```powershell
& $RouterPython $RouterInstaller --python $RouterPython --home $RouterRoot --clients codex --openai-mode none --anthropic-mode $RouterClaudeRoute
if ($LASTEXITCODE -ne 0) { throw 'The connection change failed. Stop and contact IT.' }
& $RouterPython $RouterInstaller --python $RouterPython --home $RouterRoot --setup
if ($LASTEXITCODE -ne 0) { throw 'SCG Router did not restart. Stop and contact IT.' }
```

4. The second command restarts SCG Router and opens its key window. If your key
   already works, choose **Cancel**; the connection change and restart still apply.
5. Reopen Codex and start a new chat. Select a model labelled `· OpenRouter`, then send a short greeting.
6. Check that Send works and that you receive a reply. OpenRouter charges your key.

When ChatGPT subscription access returns, quit Codex normally and run this command
from the same PowerShell window. Recreate the paths first if needed:

```powershell
& $RouterPython $RouterInstaller --python $RouterPython --home $RouterRoot --clients codex --openai-mode subscription --anthropic-mode $RouterClaudeRoute
if ($LASTEXITCODE -ne 0) { throw 'The connection change failed. Stop and contact IT.' }
& $RouterPython $RouterInstaller --python $RouterPython --home $RouterRoot --setup
if ($LASTEXITCODE -ne 0) { throw 'SCG Router did not restart. Stop and contact IT.' }
```

In the key window, choose **Cancel** if your key already works.
Reopen Codex, start a new chat and choose a subscription model without the `· OpenRouter` suffix.
Check that it replies. Switching back cannot restore an expired plan or exhausted allowance.
These commands keep your sign-in and other attached assistants in place.
Use `--clients codex` with the mode flag so an already-current install applies the change.
Run `--setup` separately afterwards to restart the router; combining the flags
can take the key-window repair path without applying the client connection.

### macOS

If the menu is unavailable, run [setup and repair](../start/repair.md) to restore
the current controls and shortcut first. Then follow the sign-in status and
OpenRouter steps above. Do not rely on an outdated shortcut.
You can also choose **Open Switch Codex** in the Router usage-limit notice.
Confirm the restart. Select an OpenRouter model and check that it replies.
When subscription access returns, open **Switch Codex** again, confirm, and
choose a subscription model after Codex reopens.

For a first setup without a ChatGPT subscription, ask IT to install with
`--openai-mode none`. The Switch Codex helper is unnecessary in that mode.
The helper verifies the loaded settings and restores the previous connection if switching fails.
See [Switch Codex](../clients/codex.md#switch-codex) for the affected versions and recovery details.

While Codex uses its OpenRouter connection, automatic chat titles and archiving
are unavailable. On Mac, switch back with **Switch Codex** when you need to archive a chat.
On Windows, keep the chat-resume limit above in mind when changing connections.

## Codex does not show a model

Subscription installs use the router's `/models` response, which combines the
ChatGPT subscription catalogue with the approved OpenRouter registry. Codex
requests it immediately and on its own refresh cadence. Desktop picker repaint
timing is not yet proven, so quit and reopen Codex when a known addition is
not visible.

If only the built-in models appear while router health is good, check discovery
with `python3.14 tools/probe_model_discovery.py --codex <client-executable> --installed`.
This reads the model list through that client without making an inference call.
Release 0.6.117 rejected valid native visibility and upgrade metadata, causing
this fallback; update to the corrected release instead of disabling discovery.

- `--static-catalogue` uses `mixed-models.json` instead and requires a Codex
  restart after an install or catalogue change.
- A model outside this machine's policy is not listed; `--status` shows the
  router state, and the request log records a refusal rather than serving it.
- A ChatGPT subscription row is always listed, exhausted or not, and its
  OpenRouter twin (`openai/<slug>`, labelled `· OpenRouter`) is listed beside
  it: picking the twin bills OpenRouter deliberately when the subscription
  cannot run. An exhausted subscription row answers the refusal message that
  names the model and points at a routed row.
