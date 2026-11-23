# Releasing

How a change reaches a tagged release, and what to test before the tag.

## How to ship

Work lands on `development` via `fix/*`/`feat/*` branches, then `development`
merges to `main` via PR. Release tags use the full `v<VERSION>` label
matching `packaging/VERSION`: `0.6.117` becomes `v0.6.117`.
Add `-beta` for a pre-release, `-express` for an urgent stable release, or
`-beta-express` for an urgent beta. The release workflow runs on `v*` tags
only. A beta tag needs a commit that `development` or `main` moved to, such as a
PR merge commit, not a commit inside a merged branch. A
stable tag needs the `main` merge commit of a pull request whose main
acceptance `Check` run passed, with the merge keeping that pull request's
exact tree, and `main` must not move after that run began. Before merging,
check that `main` has not moved since the run started; if it has, push to the
pull request or reopen it for a fresh run (a re-run keeps the old start time).
After such a merge, only a new release merge can be tagged. Tag that merge
commit as soon as the pull request merges. The
workflow then validates the exact version, builds the bundle, publishes the
release to the public feed and creates the GitHub Release with
`latest.json` as a public mirror for humans. The semantic version remains in
the public tag, bundle and feed, where the updater uses it for ordering.
Healthy current updaters check their saved channel every four hours. Old installs
blocked by download sign-in need the [current public setup once](../start/repair.md); publication alone
does not recover them. Never push to `main` directly for a release; only a pull
request merge carries the acceptance run the stable gate needs.

Develop PRs and branch pushes run fast static checks. The full offline suite,
scoped native installer checks, plugin scheduler checks and hook-adapter
portability checks run for pull requests into `main`. A beta tag does not
wait for them: `development` accepts commits only through pull requests that pass
the required `Test` check, and local tests and review run before every commit.
A stable tag reuses its pull request's `main` acceptance when the merge commit
keeps the tested tree, instead of repeating it on `main`.
Both channels then run packaging, runtime-pin verification, signing and
publication. A tag runs the copy of the release workflow saved in the tagged
commit, so a tag on a commit made before this acceptance check existed can
still publish without it. Stopping those older copies from publishing is a
separate step.

Beta GitHub prereleases also carry the five native installers from the selected
core bundle, plus SHA256SUMS and SHA256SUMS.sig. The workflow checks every
receipt, filename and body hash before it publishes the beta feed. The full
native publication gate must pass. The checksum signature uses the existing
release trust. The native installers remain unsigned.

An existing beta release must contain the required assets with exactly the
verified local bytes. Local feed preparation uses the same publisher and signing
path as publication. A missing or different asset stops the rerun before any
feed write. Recovery
requires an operator decision; the workflow never uploads replacements or
deletes existing assets automatically.

The stable download page and installer list continue to follow the stable
release. Promote a beta only after its native desktop journey and normal stable
release gates pass. Record the version actually installed during the pilot:
existing installations preserve their saved channel.

## How to test first

If the release changes anything under `packaging/`, run the installer tests
locally before you tag the beta:

```sh
SCG_RUN_INSTALLER_TESTS=1 python3.14 -m unittest discover -s tests -t .
```

The default discovery run skips them, and a beta does not wait for the `main`
checks that run them. The release workflow's native packaging step runs them
and stops the release when one fails. On 21 October 2026 AEDT this stopped
`v1.3.12-beta` before it published anything.

Merge the release candidate into `development` through its PR, then tag the
resulting `development` commit `v<VERSION>-beta`. A beta waits only for that PR's
checks, not the long `main` checks. The workflow publishes a pre-release to the
public beta document (`beta/latest.json`). Cyril's machine follows the
`beta` channel (`beta`
in the `channel` file beside the state directory), so it updates first;
watch its `/health` version and `logs/update.log` before promoting `development`
to `main` through its PR. Promote only what the beta ran: before merging the
release PR, confirm its head is still the beta commit; if `development` has moved,
tag and watch a new beta on the new `development` commit first. Once the
release PR merges after its checks pass, tag the merge commit `v<VERSION>` for
stable.

The stable publisher refreshes the legacy public install page independently
of native-installer acceptance. It publishes the stable feed before shared setup
scripts. Beta releases leave those shared files in place. Keep native acceptance
flags unchanged until their desktop evidence is complete. After publication,
verify anonymous downloads through [the install page](https://hub.softwarecombined.com/install)
and both channel feeds. Distribute the notice in [recovery](../start/repair.md) only
after those checks. Older blocked updaters still need that one external action.
