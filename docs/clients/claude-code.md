# Claude Code via the local router (Preview)

Claude Code can talk to the local router instead of Anthropic directly. It
keeps your Claude subscription sign-in. Claude-family OpenRouter models can
appear next to subscription models and charge the OpenRouter key. The router
also offers other vendors' models under their real IDs. Claude desktop's
OpenRouter mode can use them, but Anthropic does not support Claude Code
routing to other vendors, and the stock terminal client and some desktop
versions may hide them.
Native requests use your existing Claude sign-in.

## Setup

The desktop app and the terminal client are separate connections and are set
up separately. This section covers the terminal (`claude`); for the app, use
[Claude desktop app](claude-desktop.md#claude-desktop-app) below.

### Set it up

Run the installer. It connects every assistant it finds on this computer,
Claude Code and the Claude app included:

```sh
python3.14 packaging/install.py
```

To connect only named clients instead:

```sh
python3.14 packaging/install.py --clients claude            # terminal only
python3.14 packaging/install.py --clients none --desktop    # Claude app only
python3.14 packaging/install.py --clients claude --desktop  # terminal and app
```

Then quit and restart Claude Code. That is the whole setup: the installer
writes the three public settings it owns in `~/.claude/settings.json`, keeps your
existing subscription sign-in, and records what it changed so the same
installer can undo it. Attaching is additive, so nothing is removed. The one thing it will
not do is overwrite a setting you edited by hand: it refuses and tells you to
fix that value first.

When `CLAUDE_CONFIG_DIR` is set, setup uses that folder's `settings.json`.
Keep the same folder for updates and `--setup` repair. To change folders,
detach the existing Claude attachment first, then attach the new folder.
The installer keeps the original restore record until detach completes.

Claude's subscription choice is independent of Codex's `--openai-mode`.
`--claude-mode` and `--anthropic-mode` name the same Claude choice; conflicting
values are refused. A changed mode reloads the current router and checks its
health before confirming connection. Updates preserve `none` for already
connected Claude clients.

### Without a Claude subscription

Pass `--claude-mode none` to the installer. The key window does not ask about
subscriptions: setup assumes a Claude subscription unless this flag or a saved
choice says otherwise.

Claude Code then needs no Claude sign-in, and every request goes to OpenRouter.
The installer also owns these settings:

| Setting | Value |
|---|---|
| `ANTHROPIC_AUTH_TOKEN` | `scg-router`, a placeholder that outranks a stored Claude login. The router sends its own OpenRouter key upstream, never this value. |
| `ANTHROPIC_MODEL` | `openai/gpt-6-luna`, or the Sonnet row when Luna is not listed |
| `CLAUDE_CODE_EFFORT_LEVEL` | `max` |
| `ANTHROPIC_DEFAULT_OPUS_MODEL`, `_SONNET_`, `_HAIKU_`, `_FABLE_` | the matching Claude row on OpenRouter, or the Sonnet row when a tier is missing |

Model ids come from the router's listing at attach time, so an update replaces
an id this installer wrote. Without a Sonnet row, attach refuses. The effort is
an environment setting because Claude Code 2.1.283 saves `effortLevel` only up
to `xhigh` and keeps `max` for one session. It applies to every request,
including Haiku background calls; every Claude row and Luna accept `max`.
Choosing a subscription again removes these settings and restores any value
you had before the first attach.

### Deferred tool loading

Claude Code can hold MCP tool definitions back and load them only when they
are needed: the client keeps the catalogue, searches it locally through its
own `ToolSearch` tool, and sends the model only the tools a search released.
That is what keeps a session attached to a dozen connector servers inside a
model's context window instead of sending every schema on every turn.

The installer sets the public `ENABLE_TOOL_SEARCH=true` setting alongside
the base URL and discovery flag. It does not set the private first-party
base-URL override. Deferred loading without that override needs renewed
client verification; the earlier measurements below describe older builds.

Two things defeat it, and neither is something the installer can fix quietly:

- `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS`, set to anything truthy, turns the
  feature off and no value overrides it. The attach refuses while it is set in
  the settings `env` block or in the environment, and `--doctor` reports it
  with the file that carries it.
- A client that cannot search at all still loads every MCP tool. Exclude the
  connector servers for that session with
  `--strict-mcp-config --mcp-config '{"mcpServers": {}}'`.

On a machine installed from the bootstrap there is no checkout to run from.
Choose **Update or repair** in the SCG Router menu, re-run the current bootstrap,
or run the installer already in the router home:

```sh
# beta hosts: download the current bootstrap, then run it to connect what it finds
curl -fsSL https://dist.softwarecombined.com/install/bootstrap.sh -o bootstrap.sh
sh bootstrap.sh --channel=beta
# a stable host omits --channel=beta

# or run the installer already in the router home with its pinned interpreter
# (use $ROUTER_HOME instead of $HOME if the router was installed elsewhere)
"$HOME/.codex/mixed-model-router/runtime/python/bin/python3.14" "$HOME/.codex/mixed-model-router/releases/$(cat "$HOME/.codex/mixed-model-router/current")/packaging/install.py" --clients claude
```

### Check it worked

- `claude` starts normally, and `/status` still shows your Claude
  subscription rather than an API key.
- `/model` lists the router's rows alongside your subscription models. A row
  named with its vendor and `· OpenRouter` is billed to the OpenRouter key;
  the plain Claude models use your subscription.
- `python3.14 packaging/install.py --doctor` reports the `claude` row as
  `match` (`absent` when nothing is attached).

Start a fresh session when you switch between a subscription model and a
routed one.

### Set it up by hand

If you would rather not use the installer, point the client at the router
yourself, using the `port` and `token` from `mixed-router-state.json` in the
router home (do not share that URL):

```sh
export ANTHROPIC_BASE_URL="http://127.0.0.1:<port>/<token>/"
export CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=true
```

Set only those two. Never set `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN`:
either one overrides the subscription bearer and breaks subscription
passthrough. Without a Claude subscription, use the settings in
[the table above](#without-a-claude-subscription) instead. Unset `ANTHROPIC_BASE_URL` to return to direct routing, and
restart Claude Code after changing it.
