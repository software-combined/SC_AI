# Router verification pipeline

Main acceptance runs the full offline unit suite alongside native checks.
The required `Test` job waits for all of them before running static checks.
A failed or cancelled prerequisite fails that gate. Development keeps static
checks, with local verification still required before each commit.

Main acceptance runs only on pull requests into `main`; a stable tag reuses
that run (see [operations](operations.md)).
Title and body edits cannot create a successful required `Test` check.
No push to a branch publishes a router release; publication requires a tag.

## Windows standard-user acceptance

Windows acceptance uses four selections: `core-first`, `core-second`,
`native-runtime` and `native-shortcuts`. Each has a separate disposable runner
and standard account, keeping profile and process state isolated.
All four matrix entries reach the required `Test` gate. One failure does not
cancel the others; failed and cancelled results cannot satisfy acceptance.

`tools/run_windows_standard.ps1 -Python <interpreter> -Suite core-first` runs
the first core partition; `core-second` runs the rest. Partitions preserve
module fixtures, discovery order and duplicate occurrences. `native-runtime`
runs the lifecycle, access-control and task-cohort modules; `native-shortcuts`
runs shortcut recovery. `-Suite core` and `-Suite native` run complete selections.
Omitting `-Suite` runs core followed by native. Every selected suite must
report positive test counts and success; native contracts permit no skips.
The launcher keeps its standard-user identity checks and account cleanup.
Its default child timeout is 20 minutes; tests can request a shorter timeout.

Diagnostic runs cannot produce the required `Test` check. The production
matrix needs no diagnostic native aggregate: the matrix dependency makes `Test`
wait for all four selections.

## Why overlap these jobs

The offline suite and the native checks consume no shared generated output,
so they run together. This adds one Ubuntu job setup. It targets elapsed
waiting time; it does not claim lower aggregate runner use or faster
individual tests.

## Diagnostic source comparisons

`ci-source-benchmark.yml` compares a baseline source commit with the current
layout through `windows-ci-benchmark.yml`. The repository variable
`HISTORICAL_SOURCE_REPOSITORY` must name the archive that holds the baseline
commit; the job fails before checkout if it is missing. A private archive also
needs authorised cross-repository read access, which the repository token does
not provide. These diagnostic jobs do not replace normal acceptance checks.

## Verification

`tests/test_ci_pipeline.py` checks that the full suite has no native dependency,
runs once with installer coverage enabled, and reaches the required gate.
`tests/test_workflows.py` keeps the main/development, text-edit and release guards.

Use the actual main pull-request workflow to measure the result.
Compare completed runs with equivalent source, coverage and runner classes.
Record queue time, individual steps, aggregate runner time and failures separately.
Timing from runs that are not equivalent does not prove a controlled improvement.
