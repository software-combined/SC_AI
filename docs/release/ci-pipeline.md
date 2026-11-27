# Router verification pipeline

Main acceptance runs the full offline unit suite alongside native checks.
The required `Test` job waits for all of them before running static checks.
A failed or cancelled prerequisite fails that gate. Development keeps static
checks, with local verification still required before each commit.

Main acceptance runs only on pull requests into `main`; a stable tag reuses
that run (see [releasing](releasing.md)).
Title and body edits cannot create a successful required `Test` check.
No push to a branch publishes a router release; publication requires a tag.

The installer and desktop menu checks cover both Windows x64 and ARM64.
The ARM64 release package is also built on a native Windows ARM64 runner.

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

Both Windows architectures run the real Task Scheduler checks. Windows x64
runs the full installer selection in one job. Windows ARM64 runs five jobs
in parallel. The general job runs the remaining installer tests and PowerShell
contracts. Four jobs cover ownership, restart, migration recovery and migration
retry. Each uses its own runner, task names and child processes.
The tests release each child through a gate file after checking its process state.
The required `Test` check waits for all five jobs. The selector's test compares
the ARM64 selections with the complete Windows installer inventory.
The Windows notice tests check that a held worker lock prevents a second
dialog. The live process-ID reuse check covers the macOS and Linux path.

## Why overlap these jobs

The offline suite and the native checks consume no shared generated output,
so they run together. This adds one Ubuntu job setup. It targets elapsed
waiting time; it does not claim lower aggregate runner use or faster
individual tests.

## Diagnostic source comparisons

`ci-source-benchmark.yml` compares a baseline source commit with the current
layout through `windows-ci-benchmark.yml`. The benchmark keeps its original
target matrix so it can run against source from before Windows ARM64 support. The repository variable
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

A push to `cyril/windows-arm-ci-proof-*` runs the same job graph against
`origin/main` for timing. The final job is named
`Diagnostic acceptance (Windows ARM64)`. Stable publication still requires a
successful pull-request acceptance run.
