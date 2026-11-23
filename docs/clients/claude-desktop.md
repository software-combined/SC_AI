# Claude desktop app

With the router already installed, run this once from the router checkout:

```sh
python3.14 packaging/install.py --desktop
```

Attachment leaves Claude on your Claude subscription, the connection it is
already using. Choose **Claude**, then **OpenRouter**, in the
[SCG Router menu](../start/desktop-menu.md), or open **Switch Claude** on Mac. Without
the menu, run `python3.14 packaging/claude_desktop_switch.py --to 3p`. Claude
restarts on OpenRouter. Claude creates that profile's identity on its first
OpenRouter launch, so the first switch only sets it up; switch back and forth
once to bring your saved Code tasks. Then choose **Code**,
select your folder, choose a model and type your task. No key copying or
Developer-menu configuration is needed. Attachment also runs when there is no
newer router release.

Claude may seal the saved gateway placeholder when it starts. Router recognises
the supported sealed format only when the existing attachment receipt and
all routing settings still match. Setup preserves the sealed entry, receipt
and selected connection. This check does not decrypt the value or prove its
original text. Changed routing or an unrecognised value still refuses setup.

The task-sharing candidate detects the signed-in account and workspace when
you open a Code task. On macOS, setup installs that background callback
automatically; you do not enter account IDs or choose profile folders. The
callback exits quietly when the router or its sharing files are gone. It makes no
model call; its cached identity becomes invalid when the account or workspace changes.
The installed macOS launchers passed both subscription-to-OpenRouter-to-subscription
and OpenRouter-to-subscription-to-OpenRouter Code-tab round trips, preserving
original tool results and the newest turns. This acceptance does not cover Cowork
sharing or Windows/Linux switching. See [compatibility](../release/compatibility.md)
for the current client versions and limits.

The [SCG Router menu](../start/desktop-menu.md) offers explicit Claude connections on Mac,
Windows and Linux. Native desktop acceptance remains separate from source and
filesystem checks; see the [native acceptance matrix](../release/native-installers.md#acceptance-matrix)
for the required platform checks.
Mac setup retains **Open Claude** and **Switch Claude** recovery launchers.
**Open Claude** opens the app with the selected connection.
**Switch Claude** asks for confirmation,
lets Claude exit normally, shares local tasks using the old selection as the
conflict winner, rechecks settings and that Claude is still closed, changes only
`deploymentMode` for an unchanged account pair, and reopens Claude. A changed
account uses the recovery flow below instead. A second launcher request is refused until
the first finishes, so it cannot copy from an outdated selection.
**Cancel** leaves everything alone. If Claude does not finish closing within
about a minute, or you cancel its quit prompt, nothing changes. Claude reopens
only when the selected profile still matches the current account. Task sharing runs only when switching; ordinary
app launches and router startup leave histories alone. Setup and updates preserve the selected mode.
A standalone Claude Code terminal installation is not required for the
desktop app. If the installed router predates these launchers, setup keeps
Claude connected and asks for a router update before installing them.
After `install.py --rollback --to` a 0.6 release, **Switch Claude** makes that
release's plain switch without sharing tasks, **Open Claude** just opens Claude,
and the session callback stays silent. Reinstall 1.0.0 to restore task sharing.

Every model labelled **OpenRouter** uses the OpenRouter key. In synthetic tests,
the candidate launchers copy local Claude Code tasks (`claude-code-sessions`)
between the `Claude` and `Claude-3p` profiles, with their JSON records and task
files. Cowork tasks (`local-agent-mode-sessions`) stay in their own profile in
this beta. Cloud conversations are not local session files and
are outside this transfer. The desktop adapter's `detach` operation restores
the original profile settings when the receipt proves each current value.
A sealed gateway value cannot prove its original plaintext. When the route,
selected profile and receipt still match, removal first retains an exact private
copy of that entry. It then restores only the owned settings. A changed proof or
failed retention keeps the receipt and service available for retry. When
restoration is proven, full removal also detaches Codex and the terminal client.

Task sharing preserves `sessionId` and `cliSessionId`, keeps workspace paths
outside the profiles unchanged, and retains tasks that exist in only one
profile. Only the resolved current account in each profile participates, and
in the subscription profile only its current organization. Previous accounts'
tasks and other organizations' tasks remain separate, including any unreadable
old records.
Before the first OpenRouter launch with a Claude subscription, open a Code task
on that subscription so Router can verify and retain the current account choice.
Without a subscription, the separate OpenRouter profile does not share tasks.
After the first copy, sharing is tied to that pair of accounts. Signing into a
different account stops sharing so it cannot inherit the earlier account's
gateway copies. Choosing OpenRouter offers a separate profile for the current
account. After confirmation and shutdown, the router retains the complete old
gateway profile, its sharing binding and ledger in a private sibling archive.
It prepares a clean profile at Claude's original supported location. Claude
creates the new gateway identity; the router never copies or invents it.
Choosing the subscription can return without sharing the old gateway tasks.
Cancel changes nothing. The Open Claude launcher checks the same boundary when
OpenRouter is selected; direct app launches do not run the router's account check.

Recovery archives use `.Claude-3p.rotation-<id>.archive` beside `Claude-3p`.
They retain the old profile under `profile`, along with its activation receipt,
router-state before-image, account binding and ledger when present. They are
not imported into the new profile or removed by an update. An interrupted
transition leaves a private pending marker. Choose Claude in SCG Router again
to recover the old attachment and return to the subscription. A recovery
conflict keeps the saved data and leaves Claude closed; contact IT.
Recovery finishes the subscription selection before clearing its pending marker.
Scheduled update status does not block it, but changed connection settings do.
Recover before setup, repair or rolling back Router. Then choose OpenRouter again to switch;
recovery does not count as that switch.
Scheduled updates wait for recovery without counting the hold as a failed release.
Finished archives are retained evidence, not an automatic restore option. IT
must verify the original account before reactivating one. Do not copy an older
profile into the current account or delete its saved receipt and sharing data.

A newly separated pair shares only the verified current account's tasks.
Each task authorizes its exact CLI session transcript from `.claude/projects`
or its existing bundle; unrelated shared histories are not imported. This is
task separation, not isolation between people sharing one operating-system
login. Claude's explicit terminal-history import remains outside the router's
transfer boundary. Use separate operating-system accounts when separate
people need confidentiality.
When both profiles contain the same session, the profile selected
before a switch wins conflicting record fields and files. Unique files from
both bundles remain, and task files keep their exact bytes. If the two
profiles hold different continuations of the same conversation, or a task's
conversation file no longer exists anywhere, that task is not shared and every
copy stays as it is. The switch still goes ahead, and Claude then shows how
many tasks were not shared. A second successful run makes no content or
permission changes.

A task you delete stays deleted. After each successful share, the router notes
which tasks both profiles hold, in a private file in its own folder that keeps
task IDs and fingerprints but no titles or conversation text. When one of those
tasks is later missing from one profile, it was deleted there, so the next
switch moves the other profile's copy to a trash folder instead of copying it
back. Nothing is erased. The copy goes to the hidden
`.claude-profile-control-trash` folder inside that profile's
`claude-code-sessions` folder, for example
`~/Library/Application Support/Claude-3p/claude-code-sessions/.claude-profile-control-trash`
on macOS. Each entry there keeps the task's record, its files and a
`retire.json` note of where they came from, so a task can be moved back by
hand while Claude is closed. A copy that changed since the last switch is kept
and shared again, so an edit wins over a delete. If a profile loses all of
its shared tasks at once, and it had more than one, for example after signing
out or resetting Claude, the router treats it as a reset rather than
deletions: nothing goes to the trash, and the tasks are shared back as before. A trash
entry that cannot be finished or undone safely stays where it is and prevents
switching.

Separate sign-in and credential files, account identity, profile settings, trust state, connector
settings and caches never cross profiles. A rejected or malformed source
record fails by itself and leaves the source data in place. Existing full and
shortened native bundle folders keep their layout; new copies use full folders.
Two sessions claiming one shortened folder are refused without overwriting it.
Duplicate records
are consolidated only after their unique bundle files have been preserved.
The next run recovers interrupted transactions that have a valid journal,
including a committed cleanup that stopped partway. A copied or restored home
folder, a shared transcript that Claude Code later deleted, or a writer that
changed a transcript during its repair does not block later switches.
Ambiguous recovery files remain in place for inspection, and prevent switching.

The target account and organization must be positively identified. When they
cannot be resolved, no tasks are shared. Switching from OpenRouter to your
subscription still works and changes only the connection, so you can sign in
there. Switching away from an unidentified subscription while tasks are saved
asks you, before Claude closes, to open a Code task in Claude first; that
establishes the automatic binding. A first switch to an OpenRouter profile that
Claude has never opened changes only the connection; switch back and forth once
to share tasks. Existing hooks are preserved, and removing the desktop
attachment removes only the callback installed by the router. If any other
required history cannot be copied safely, switching stops, the original profile
remains selected and Claude reopens on it. No transcript is silently discarded
or redacted.
Every transcript row keeps all of its fields and text, including checkpoint
file lists, code examples and keys pasted into a conversation; only paths
inside the profile folders are relocated. That text can
reach the selected provider when the task resumes. Separate credential files
remain excluded, and other copied artifacts still undergo content screening.
The launcher checks that Claude still uses
this router's saved configuration; run setup again if that configuration has
changed. An organization policy that prevents subscription sign-in also
prevents a mode switch. The launcher checks the selected local configuration
and the platform's managed source before and after Claude quits. Managed
connection overrides and unreadable policy refuse switching. Update, lifecycle
and proxy policy alone can coexist with the locally controlled connection.
