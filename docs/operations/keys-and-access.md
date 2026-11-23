# Keys and access

How keys are issued, rotated and limited, and which client uses which subscription.

## Per-user OpenRouter keys (IT issue and revoke)

Work-account provisioning uses Microsoft sign-in and the Hub's dedicated
`Router.Provision` permission. The backend selects the approved company workspace
from the verified home tenant and issues one personal key with a US$50 monthly
limit. A tenant is a company's Microsoft account directory. Reinstalls and additional
computers receive that same key and allowance. Unknown or ambiguous company
tenants are refused. Existing manual keys require
IT migration before a new allowance can be issued.

The public release contains only public sign-in settings. Management credentials
and encrypted personal keys stay in the Hub backend. OAuth tokens remain in memory;
the local setup route writes only the personal inference key through its existing
protected writer. Downloads and updates remain public.

Sign-in uses the dedicated Router API and does not require directory read access.
Each company can connect a separate read-only directory app for automatic key
revocation after an account is disabled or deleted. That connection requires one
company administrator approval. Until connected, IT must revoke keys manually.
Offboarding must disable the OpenRouter key as well as Entra access. Replacement
keys need an explicit remaining-budget decision; automatic rotation is not enabled.
The legacy `tools/provision_key.py` does not implement this managed contract and
must not be used for work-account issuance.

For a separately issued unmanaged key, the existing IT flow remains available:

One key file per external provider (Plan 139): the installer and the setup
window name the provider whose key they are collecting, and a second
provider's key never overwrites the first. `--status` reports each
provider's key under `providers`, with the legacy `key_present` /
`key_usable` pair still describing the default provider (OpenRouter).

AWS Bedrock is an optional second provider. Its key lives in
`bedrock.key` beside `openrouter.key` (or `BEDROCK_API_KEY` for a manual
run), and requests go to `bedrock-mantle.<region>.api.aws` for the
`bedrock_region` in the state file. Bedrock keeps its own availability
file, `models-availability-bedrock.json`; `/health` reports
`bedrock_region`, `bedrock_host` and `bedrock_availability` beside the
OpenRouter fields. A missing or rejected Bedrock key hides only Bedrock
rows: it never blocks an OpenRouter install, and the router never falls
back to another region or provider.

1. IT creates the key in the OpenRouter dashboard with a monthly allowance
   and hands it to the user over an existing trusted channel (never commit
   it, never paste it into chat or email threads beyond that handoff).
2. The user installs and a native window opens by itself. It asks one
   question: sign in with a work account or use their own key. Subscription
   modes come from the installer defaults, saved choices or IT flags. The
   window validates the key against OpenRouter before storing anything and shows
   remaining credit; the key lands in `openrouter.key` (mode 600), which the
   router reads per request. A host with no dialog tool (headless Linux, SSH)
   opens the loopback page instead, and an interactive terminal prints the
   link so the operator can paste it into a browser. The installed
   service does not receive the invoking shell's environment, so an exported
   `OPENROUTER_API_KEY` does not count as configured and still opens the
   window. Re-run with `--setup` only if no window appears; it restarts the
   current release with a fresh link, without re-extracting it. Scheduled
   `--update` runs and manual `--check-update` runs never pop the window; the
   next request opens it instead.
3. Rotation: delete `openrouter.key` first (the setup window refuses to
   overwrite a file holding a real key with 409), then re-run the installer
   with `--setup` and paste the replacement. File-level alternative is under
   `Key rotation` below.
4. Revocation is at the OpenRouter dashboard: delete or pause the user's key,
   then confirm fail-closed by asking the user to run any OpenRouter request
   and checking the router log for a `request_completed` entry carrying the
   upstream 401 rather than a completion. Offboarding also removes the seat
   per the portco process; there is no local grant to unwind as long as no
   `OPENROUTER_API_KEY` env or OpenCode-auth fallback is set on that machine,
   because entitlement otherwise lives entirely in the dashboard key state.

## Client activation and subscription policy

`--client codex` (the default) manages the Codex config block, picker
preservation, global guidance, and the activation receipt.
`--client none` installs, updates, rolls back, and uninstalls the router
lifecycle without touching any client file; uninstall needs no receipt.
Switching an active Codex install to `none` restores the exact owned block
first, or refuses when the block was edited. The choice persists in router
state and survives scheduled updates.

The attachment also manages Codex settings beyond the connection lines. A
fresh install seeds `model = "deepseek/deepseek-v4.1-flash-1017"` and
`model_reasoning_effort = "max"` inside the managed block; Codex writes the
owner's later pick into those same lines, and an update carries it forward
instead of resetting it. In the config's `[desktop]` table it sets
`followUpQueueMode = "steer"`, so a message sent while a turn runs steers it
instead of queueing, and `enabled-reasoning-efforts`, the client's own list
with `max` added and `ultra` removed. Ultra is Codex's automatic-delegation
level and the served catalogue never offers it, so the picker cannot show it
even if a client default reintroduces it. The managed block also carries
`approvals_reviewer = "user"` in both modes, so installs never fall back to
the background reviewer. An owner root line that sets any key the block
sets (`approvals_reviewer`, or `model_provider` in no-subscription mode) is
set aside on attach, recorded in the activation receipt's `reviewer`
record, and restored on detach, one line per key; a key inside an owner
table, such as a profile's own `model_provider`, is never touched. Detach,
`--client none` and uninstall put the desktop values back as the attach
found them, and a value the owner changed afterwards is left alone. A `[desktop]` table or value the
installer cannot rewrite safely skips that edit with one line of output
rather than risk a second definition or a mangled value.

Native service calls (`/alpha/*`, `/guardian*`) pass through to the
ChatGPT backend with the client's own login in subscription mode and answer
404 in `none` mode; the list is a prefix rule on the OpenAI definition, so a
new backend path needs no router change. A dot segment, percent-encoded dot
or backslash in the path is refused before the prefix test.

Subscription routing is independent per client: `openai_mode` governs
Responses, `anthropic_mode` governs Messages when explicitly set, otherwise
Messages follows the legacy `openai_mode` fallback. Neither mode widens
access on migration; unsets keep prior behavior.

Thread titles, descriptions, summaries and title reconsiderations are the
model calls behind the client's thread metadata. They run as their own
helper threads and are the only turns whose `x-codex-turn-metadata` carries
a `thread_source` of `thread_title`, `thread_description`, `thread_summary`
or `thread_title_reconsideration`. Client 0.154 also puts the read-only app
tool allowlist it derives from the installed apps and MCP servers on those
turns, so a helper turn carries tools; they do not make it ineligible.
When the ChatGPT allowance is exhausted upstream refuses those turns, and
the client stores a slice of the prompt as the title instead. The fallback
requires explicit `openai_helper_fallback: true` in
`mixed-router-state.json` (restart the service to load a change): a 429 on
such a turn is answered from the OpenRouter twin row `openai/<slug>`, or
from the Luna twin `openai/gpt-6-luna` when the requesting slug has no
twin of its own, and logged as `subscription_fallback`, or as
`subscription_fallback_unavailable` when the twin cannot be prepared (no
OpenRouter key, for example), which keeps the existing 503. An exhausted
subscription also answers helper turns 401; those take the same twin path,
while ordinary turns keep the raw upstream answer so a sign-in problem
stays visible. Every other
turn keeps that 503 unchanged. A provisioned portco list still gates the
twin: an excluded twin row is never used, so the helper path stays inside
the same allowlist as a directly requested OpenRouter row.
The twin answers the client's own payload, tools included, so the helper
thread keeps the tools its client granted it. The fallback means the
helper prompt reaches OpenRouter and bills that key, and the helper marker
is a client header: any local process holding the loopback path token can
present a helper-shaped turn and have its prompt answered - and billed - by
an allowed twin. It grants no other rerouting.

## Key rotation

Replace the `openrouter.key` file contents. No restart is needed; the
router reads the key per request.

## Per-portco model policy

Onboarding: add the user to the portco subgroup, resolve the slug subset
centrally against the current `models.json` (a department list must stay
within its portco list), and deliver `<home>/model-policy.json` (`0600`,
atomic write) with `portco`, `department`, `allowed_models`, `version`,
and `updated_at`. The router loads it at startup into
`state['allowed_models']`; both protocol policies gate OpenRouter slugs
on it, subscription rows unaffected. Offboarding: remove the user from
the subgroup and delete their OpenRouter key by id; the policy file goes
with the machine's decommissioning, never as a revocation control.

Managed installs: the state file may carry `policy_enforced: true`, set
only by the trusted provisioning path (the installer flag, MDM, or the central
grant tool) and never by a user or a routine update. With the flag set, a
missing policy denies external routing instead of granting it, and the router
logs one token-free `model_policy_rejected` event with reason
`enforced_without_policy` (Plan 176). An unreadable or invalid policy denies on
any install, each with its own reason. A personal install never sets the flag,
so an absent policy keeps today's behaviour. A value that is not true or false
stops the boot with `policy_enforced must be true or false`.
