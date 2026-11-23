# Codex

Router features specific to Codex. Codex fixes are in [Codex troubleshooting](../troubleshooting/codex.md).

## Switch Codex

Open the [SCG Router menu](../start/desktop-menu.md) and choose an explicit Codex connection.
The existing Mac Switch Codex shortcut remains available for recovery.

Choose **OpenRouter** to use OpenRouter models. The usual connection keeps
your ChatGPT sign-in. Select the checked **OpenRouter** choice again to change
the sign-in setting, even when Router has not recorded a usage limit.

From version 26.917.51856, the ChatGPT app (Codex) stops sending messages once
your ChatGPT subscription reaches its usage limit, even for OpenRouter models.
Switch Codex keeps your ChatGPT sign-in during normal OpenRouter use, so
projects, chats and setup choices stay with your account; only the model list
changes. During an active limit,
the fallback signs Codex out to keep Send available. Projects and setup
choices stay separate until you switch back. On Mac, SCG Router adds Switch Codex to your
Applications folder when Codex uses your ChatGPT subscription and your ChatGPT
app is affected.

When a limit is recorded, SCG Router offers to switch once. Choose **Open
Switch Codex** in that notice, or select **OpenRouter** in the SCG Router menu.
If OpenRouter is checked and its status says sign-in is required, select it
again to offer the signed-out connection. If sign-in is already not used,
leave it selected. Switch Codex asks before it changes anything, then quits and reopens
the ChatGPT app. It keeps the switch only after Codex loads the new settings.

On Windows, closing the window can leave Codex running in the tray.
The confirmation explains that Codex will fully close and running tasks will stop.
Finish active work before choosing Continue. Cancel leaves the app unchanged.
The switch verifies exit before writing settings and reopening before keeping them.
If reopening fails, it restores the previous connection and tries to reopen that connection.

After the recorded reset time, SCG Router offers the previous connection once.
The offer is not proof that every usage limit has reset. Confirm before Codex
restarts. If the earlier connection is unknown, the offer returns to **ChatGPT
+ OpenRouter**. That return needs no bundled command or proof. Windows still
requires a verified app identity and exit before it changes settings. On Mac
and Linux, an unavailable app can use the manual quit and reopen path.

While Codex is switched:

- only OpenRouter models are listed, and they are billed to OpenRouter;
- image generation uses GPT Image 2 and bills the OpenRouter key; the
  active-limit fallback needs no ChatGPT sign-in; see [media generation](../models/media-generation.md);
- a model that needs your ChatGPT subscription answers with a short message
  that says what to pick instead;
- Codex still asks you before it runs a command that needs approval;
- chats you start in the signed-out limit fallback stay in that profile and
  are not listed after you switch back; normal OpenRouter chats stay with
  your ChatGPT provider.

Conversation titles and other chat metadata use Luna through the OpenRouter
key while switched. Your chosen chat model stays unchanged. If Luna is absent
from the key's model list or company policy excludes it, these helpers cannot run.
Archiving a conversation still fails with "Failed to archive conversation",
a ChatGPT app (Codex) issue, so switch back to archive it.

### Subscription chats after a router restart

An ongoing Codex chat can request a subscription model before Codex asks the
restarted router for `/models`. The saved model preferences are not a complete
entitlement list: a model discovered before the restart can be
missing from them. Rejecting that first request would turn a routine update
into Codex's "model is not available on this machine" error.

For a missing native model, the router asks the native catalogue using the
request's subscription authentication and client version. It routes the
original request only if the returned roster allows it. The same recovery
applies when compaction is the first request. Concurrent resumptions reuse one
result. Account, workspace and version boundaries stay in force, and recovery
never switches a subscription request to OpenRouter.

An unavailable catalogue returns a retryable service error. Rejected
authentication clears that account's discovery scope. A model absent from a
successful catalogue response stays unavailable. The router does not repeat
discovery for every request.

`tests/test_subscription_restart.py` covers this offline. Run its wrapper from
`router/`; it uses synthetic credentials and mocked upstreams:

```bash
python3.14 tools/probe_subscription_restart.py
```

## Global instructions

Setup, updates and uninstall never write, change or remove the global
`AGENTS.md` or `AGENTS.override.md` beside `config.toml`. The owner's file is
always authoritative.

## New model notifications

When a scheduled update lands a version that adds models for the machine's
policy scope, the updater asks the running router over loopback (the
updater never imports the runtime) and shows one native restart dialog. The
dialog names up to three new models the way the picker does
(`<Vendor>: <Model>`, without the `· OpenRouter` route suffix). No browser
page or separate desktop notification opens. The dialog appears only when the
router names at least one model that no earlier dialog has listed. An update
or check with no new model stays silent, and so does one that cannot reach
the running router, so a stopped service never delays an update. Once a
dialog is on screen, the router is told to mark every model it covers as
seen (the dialog names three and counts the rest as `+2 more`), through the
same Later action the old approval page used, so no later update lists them
again. Dialogs never stack: a model that arrives while an earlier dialog is
still open waits, and a later pass names it once that dialog has closed.
`Later` leaves the client running; `Quit and reopen` quits
and reopens Codex on macOS. The offer is skipped on installs whose state
records no Codex attachment (`--clients claude`, `--client none`; a `clients`
value recorded by an earlier run can lag the current attachment) and whenever
`ROUTER_NO_NOTICE=1` silences the update notice. If no native dialog tool is
available, the notice stays pending for a later GUI run, and its models stay
waiting until a dialog actually shows them. The first run seeds
the snapshot without announcing the catalogue, so the first landing after
this feature ships only seeds it and later landings announce; removals and
version-only updates stay silent, and an unverified or out-of-policy row is
never announced.
