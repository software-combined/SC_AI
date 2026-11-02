# Native installer builds

`tools/build_native_installer.py` wraps a canonical release bundle and its
target's pinned Python 3.14 runtime. The builder checks the bundle manifest,
the bundle checksum, and `packaging/runtime.lock` before it stages files.
`--stage-only` writes `<out>/stage/Resources` and needs no platform packaging
tool. It can run with synthetic archives for offline checks.

Normal builds also compile a small menu helper: AppKit on macOS, Windows Forms
on Windows, and `ksni 0.3.6` on Linux. Linux uses Rust 1.90.0 and committed
`Cargo.lock` checksums. Python has no new runtime dependencies.
The helper renders menus and emits action IDs. Shared Python owners perform actions.
The Linux component check uses a private D-Bus session to test host loss and recovery.

Each build exports the staged Resources tree as a separate archive and descriptor.
Its descriptor binds the target, version, size and checksum to the exact core bundle.
The embedded local feed remains core-only, avoiding an archive checksum cycle.
`--stage-only` does not compile helpers or require native build tools.

Local builds, macOS and Linux remain unsigned. Windows release publication
requires timestamped Authenticode signatures from the configured publisher.
The shared Windows action stages and compiles the menu, signs and verifies it,
then refreshes its checksum before Inno Setup packages it. It signs and verifies
the outer installer before exporting Resources or writing final receipts.
Only the owned menu and installer are signed. Pinned third-party runtime files
retain their original bytes and signatures. Inno Setup creates no uninstaller.
The router's signed update feed remains the authority for online updates.

Configure the `AZURE_SIGNING_` repository secrets named in the release workflow:
`CLIENT_ID`, `TENANT_ID`, `SUBSCRIPTION_ID`, `ENDPOINT`, `ACCOUNT`, `PROFILE`,
and `PUBLISHER_SUBJECT`. The subject must match the validated certificate exactly.
Use a dedicated federated identity with the certificate-profile signer role
scoped to that profile. No client password or certificate is used.
Restrict federation to this repository's immutable identity and release tags.
Do not add a GitHub environment without updating the existing publisher trust.

Complete organisation validation and create a Public Trust profile before use.
The manual Windows signing canary uses the same action and publishes nothing.
GitHub requires its workflow on the default branch before manual dispatch.
That source promotion is a separate approval gate, before any release tag.
Run it only on a reviewed branch with a separately authorised exact-branch
federation rule. A successful canary does not establish staff-device acceptance
or SmartScreen reputation. See [Microsoft's action guide](https://github.com/Azure/artifact-signing-action).

Run the normal build on the target operating system. macOS needs `hdiutil`,
`sips`, and `iconutil`. Windows needs Inno Setup's `ISCC.exe`. Linux needs a
Zenity executable, `libgdk-pixbuf2.0-bin`, an AppImage builder, and a matching
uruntime file. Pass
SHA-256 digests for the Linux builder and uruntime. The builder checks both
files before it runs either one. It embeds uruntime with automatic extraction
when FUSE is unavailable, including images larger than its default 350 MiB
limit.

On Linux, the build copies Zenity, its linked GTK libraries, GObject
Introspection typelibs, compiled GLib settings schemas, and image loaders
into `Resources/gui`. The generated `gui/manifest.json` lists the exact files
copied from that build runner. Build on the oldest supported Ubuntu image so
the copied libraries do not require a newer system C library on staff machines.
The Zenity wrapper sets its library and data paths when a dialog starts. The
recipient does not need a system Zenity command or a system Python install.

The stage's `payload/latest.json` names `file://bundle.tar.gz`. The existing
installer resolves that name beside the local feed document, so moving a DMG,
EXE, or AppImage does not leave a stale build-machine path. The feed's SHA-256
must match `payload/bundle.tar.gz` exactly.
