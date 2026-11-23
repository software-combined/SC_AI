# Native installer delivery

The native packages are unsigned at the owner's request. Existing signed feeds,
manifest checks, SHA-256 checksums and feed replay protection remain required.
This implementation does not establish staff acceptance or authorise closing
the existing public update path.

## Build and publish

`Release` builds one canonical bundle, then creates five packages on native
macOS, Windows and Ubuntu runners. Each build verifies its pinned Python archive.
Linux bundles Zenity and GTK dependencies from Ubuntu 24.04, plus a pinned
AppImage runtime with automatic extraction when FUSE is unavailable.
See [builder details](../../router/packaging/native/README.md).

Each build also exports its existing staged `Resources` directory for installed hosts.
The signed update document includes an optional `native_resources` map.
Each target records its archive URL, checksum, size, version and matching core checksum.
Updates download only the matching target. They retain resources immutably and
change the setup pointer after validation. Failed menu delivery preserves the previous menu.
Same-version installs and cached feed checks repair missing resources.
Runtime rollback preserves a newer working menu and its independent update controller.
These update resources do not change the first-install publication gates below.

Each artifact receipt names its target, exact router bundle, runtime and package
checksum. Publication requires all five targets from one exact bundle.
The publisher uploads immutable packages and signed `SHA256SUMS` first.
It changes the channel's download list last. It refuses a distribution without
public access for both installer files and download lists.

The permanent download page is `https://hub.softwarecombined.com/install`.
Public release metadata and installer files stay on `https://dist.softwarecombined.com`.
Hub reads `/install/stable.json` and `/stable/latest.json` without credentials.
Those metadata files allow browser reads from the production and staging Hub origins only.
Each platform shows its published processor alternatives, or says no installer is ready.
Setup scripts appear only in the page's advanced section for IT.
The page offers stable downloads only. Installer lists,
packages, update feeds, bundles, runtimes and model catalogues are public.
Microsoft download sign-in is not required. Model-provider credentials remain
separate and are never published with software.

## Publication and recovery

The publisher checks that the download origin has no signed-cookie requirement.
The S3 origin remains private behind CloudFront origin access control, and the
`native-builds/` prefix remains unavailable through CloudFront. Package checksums,
signed feeds, runtime pins and replay protection remain enforced.

Release builds take no download sign-in configuration, and the sign-in release
options fail explicitly. Building a release removes any stale generated
`dist/download-auth.json`. Public transport ignores an existing
`download-auth.json` in a user's home; while that file exists, the router leaves
its hourly model refresh to the updater.

With the repository variable `NATIVE_INSTALLERS_ACCEPTED` set to `true`, every stable
release publishes all five installers and switches the download page to them, so
the page always offers the current release. The variable is set to `true`; the
device checks in the native acceptance matrix still apply to each release.
Without it, the page says the installers are not ready and keeps the setup
scripts in its IT section.
After Mac verification, `NATIVE_INSTALLERS_MACOS_ARM64_ONLY=true` can publish
the Mac arm64 stable package while the other native packages remain private.
This platform-specific publication does not assert acceptance of the other
platforms or the complete matrix. Beta update feeds remain separate from the
stable-only download page. Full native publication requires the
existing five-platform checks. The Windows runtime's Visual C++ files follow
the basis recorded in [runtime licences](../legal/runtime-licenses.md).
Use a new release version when adding native platforms to a published version.
Its signed checksum inventory is immutable.

The download page follows Softcom Hub's light canvas, SC Pink, near-black text
and Space Grotesk/Inter font stacks. The corporate icon is the existing bundled
asset. Device-policy help sits below the main download area.

Every stable release publishes the public page and `bootstrap.sh` / `bootstrap.ps1`
under `/install/`, even when native packages have not passed their acceptance gates.
Publication switches the stable feed first, so its installer supports the setup
scripts it receives. Beta-only releases update the beta feed without replacing
shared setup assets. An installation whose old updater cannot
get past Microsoft sign-in must run the current public setup script once. It uses
new installer code, so legacy download settings do not block it; successful delivery
also replaces the independent update controller. The existing channel is preserved
unless the operator explicitly requests another. Model keys and client settings are
preserved. Users with working scheduled updates receive the release normally.

The page advertises native packages only when their version matches the current
stable feed. A stale list after deferred or interrupted publication keeps the
current setup scripts visible instead.

Normal update jobs run independently from the serving Router process. An offline
computer or disabled update job cannot fetch a release until it runs again.
Publishing a new feed alone cannot repair an old controller that rejects downloads
before making its first network request. Do not claim automatic recovery on such
hosts without proving their update path works.

Linux dialogs use the retained setup wrapper after the download is deleted,
with system Zenity as a fallback. The wrapper scopes GTK dependencies to its
dialog child, so service processes do not inherit bundled library overrides.

**Update or repair** uses the newest verified maintenance controller and the
public release for the saved channel. The explicit `--repair` path preserves
keys, subscription sign-ins, connected assistants and disabled tools. It asks
to close assistants only when a connection needs rewriting, or when Claude desktop
uses OpenRouter, because that connection changes while Claude is closed. Automatic
updates never force an assistant closed. A one-shot public repair does not
replace a saved custom feed. Controller and stable-launcher delivery can finish
even when an assistant receipt needs attention. Connection conflicts retain
their own warning. Choose **Sign in with work account** when model access is missing.
The secure window also offers **Use my own key**. **Manage Router > Replace model key**
remains available for recovery. A saved key is kept unless the provider confirms
that it no longer works; an outage or an unknown result does not permit replacement.
Fresh subscription installs retain the assistant's native model default.
Explicit model choices and the default for users without a subscription are preserved.
Setup applies subscription answers to the connected assistants before its closing notice.
That one notice names each connected assistant and how to restart it. It does not
claim that a reply works; **Check setup** in the menu checks that.

Claude desktop can connect without a terminal client. Automatic SC tool delivery
also needs the Claude Code setup tools from the desktop app's Install page.
The graphical setup checks this prerequisite before making a desktop attachment.
It guides existing desktop users there instead of repeating a repair request.
This does not attach the terminal client or restart an assistant.
Manual CLI setup waits for the access window after attaching the selected assistants.
It then applies saved subscription answers. Cancelled or unavailable windows leave
setup pending. Keep the saved key and choose **Check setup** in SCG Router to finish.

## Acceptance matrix

Complete this matrix for Windows x64, macOS arm64 and Intel, and Ubuntu
24.04/26.04 GNOME on x64 and arm64. Existing client compatibility records remain
separate from native-package acceptance.

| Gate | Required evidence |
| --- | --- |
| Fresh computer | Install with no Python or Git; use an installed, signed-in supported assistant. |
| Retained files | Delete the download or eject the DMG, then restart the router and the SCG Router app. |
| Existing user | Upgrade and same-version repair preserve key, channel, custom feed, instructions, policy and disabled plugins. |
| Assistant attachment | Verify desktop-only setup and attaching another assistant without detaching the first. |
| Ready state | See one closing notice naming the attached assistants. After their restart, **Check setup** observes a routed reply and enabled SC tools. Reopening the same installer shows only the up-to-date notice. |
| Cancellation | Cancel before attachment, during setup; reopening must resume safely. |
| Recovery | Interrupt setup, run scheduled updates, restore an older runtime and verify public update recovery. |
| Removal | Restore the prior assistant configuration and stop the owned services. |
| Linux | Run with FUSE and without FUSE on both supported Ubuntu releases and processors. |
| Access | Allow downloads without an account; reject tampered metadata, bundles and off-origin redirects. |

On Windows, also run native Windows CI and real desktop checks for one tray
icon after updating, sign-in startup, missed-check recovery, both switch
directions, title routing, guarded attachment recovery and coherent task runtime
paths. Check that a startup warning follows the menu rather than delaying it. Windows
Server CI does not replace Windows 11 desktop acceptance.

Build and dependency checks do not complete this matrix. They also do not prove
that a nontechnical staff member can finish the shared-link flow.
