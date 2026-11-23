# Router documentation

Run source-checkout Router commands from `router/`. Installed releases retain
their existing flat layout; use the installed release directory for those commands.

Start with the repository [README](../README.md) for the ordinary user path,
models and billing. These pages go deeper.

## Entry pages

| Page | Use it for |
|---|---|
| [Architecture](ARCHITECTURE.md) | Module ownership and the allowed dependency direction |
| [Rules](RULES.md) | Where new code goes and which way imports point |
| [Design rules](DESIGN.md) | Standing product decisions the code keeps |
| [Data](DATA.md) | Files the router keeps in its home and the records it writes |
| [Patterns](PATTERNS.md) | Recurring code patterns and where each is described |
| [Testing](TESTING.md) | Which checks to run and where each test layer is described |
| [Glossary](GLOSSARY.md) | Terms these pages use |

## Start

| Page | Use it for |
|---|---|
| [Setup](start/setup.md) | Staff setup, assistant choices, prerequisites and installation from source |
| [Repair an installation](start/repair.md) | Public repair without uninstalling, saved choices and the maintainer notice |
| [Desktop menu and tray](start/desktop-menu.md) | Connection switching, management, sign-in startup and Linux fallback controls |
| [Agent install prompt](start/agent-install-prompt.md) | The prompt to hand a coding agent |

## Clients

| Page | Use it for |
|---|---|
| [Codex](clients/codex.md) | Switch Codex, subscription chats after a restart, global instructions and new model notices |
| [Claude Code setup](clients/claude-code.md) | Pointing the Claude Code terminal client at the router |
| [Claude Code reference](clients/claude-code-reference.md) | Discovery, model choice, the attachment contract, limits and verification |
| [Claude desktop app](clients/claude-desktop.md) | Attaching and switching the desktop app, and task sharing |
| [Claude desktop limits](clients/claude-desktop-limits.md) | Observed desktop behaviour, limits and bounded verification |
| [Context recovery](clients/context-recovery.md) | What to do when a long turn or a compaction goes wrong |

## Models

| Page | Use it for |
|---|---|
| [Adding a model](models/adding-a-model.md) | Adding, probing and promoting a registry row |
| [Media generation](models/media-generation.md) | Preview image and video routes, client prerequisites and bounded verification |

## Operations

| Page | Use it for |
|---|---|
| [Updates](operations/updates.md) | The update feed, Express updates, rollback and safe restarts |
| [Service](operations/service.md) | Uninstall, the operator commands, the Linux app check and Windows tasks |
| [Keys and access](operations/keys-and-access.md) | Per-user keys, client activation, key rotation and model policy |
| [Diagnostics](operations/diagnostics.md) | Latency fields, failed streams, handoff failures and request evidence |
| [Router answer codes](operations/answer-codes.md) | The codes the router answers with on the Responses protocol |

## Troubleshooting

| Page | Use it for |
|---|---|
| [Troubleshooting](troubleshooting/README.md) | Symptom-first checks, automatic repair and logs |
| [Codex](troubleshooting/codex.md) | Codex chats, tool schemas, the Send button and missing models |
| [Claude](troubleshooting/claude.md) | Claude desktop switching, subscription access and Claude Code routing |
| [Install and service](troubleshooting/install-and-service.md) | Windows setup tools, installer and update failures, serving, keys and what to send IT |

## Release

| Page | Use it for |
|---|---|
| [Releasing](release/releasing.md) | Branches, tags, the release workflow and tests before a tag |
| [Feed publishing](release/feed-publishing.md) | Feed infrastructure, publication reporting and bad-release recovery |
| [Native installers](release/native-installers.md) | DMG, EXE and AppImage builds, staff downloads, migration and acceptance |
| [Verification pipeline](release/ci-pipeline.md) | Parallel main acceptance, required checks and diagnostic comparisons |
| [Compatibility](release/compatibility.md) | Current client versions, latest release checks, their limits and the Codex upgrade check |
| [Installed runtime files](release/runtime-files.md) | What the release bundle contains |

## Architecture detail

| Page | Use it for |
|---|---|
| [Installation, setup and update ownership](architecture/installation.md) | Installer, delivery, client choice, state and update modules |
| [Streams and request evidence](architecture/streams-and-evidence.md) | Request evidence, stream outcomes, sends and the switched Codex route |
| [Handoffs and history](architecture/handoffs-and-history.md) | Agent handoffs, history projection and outgoing stages |
| [Client contract](architecture/clients.md) | Adding a client and the Codex connection switch |
| [Claude desktop attachment](architecture/claude-desktop-attachment.md) | Desktop attachment and the switch lifecycle |
| [Claude profiles and task sharing](architecture/claude-profiles.md) | Profile rules, records, identity and sync |
| [Distribution](architecture/distribution.md) | Desktop controls, native resources, the feed and agent plugins |
| [Compaction](architecture/compaction.md) | Experimental compaction and the Jev compaction consumer |

## Plugins and legal

| Page | Use it for |
|---|---|
| [Agent plugins](plugins/agent-plugins.md) | The bundled tools, standalone setup and their release rules |
| [Provenance](legal/provenance.md) | Where the code came from |
| [Publication](legal/publication.md) | Integration scope, safeguards and owner decisions |
| [Runtime licences](legal/runtime-licenses.md) | Pinned archive and notice verification |
