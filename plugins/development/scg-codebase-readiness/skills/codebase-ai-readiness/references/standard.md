# The standard: an AI-optimised codebase

The goal: a person who is not an engineer can open the repository, ask an agent for a change, and ship it without worry. An engineer is comfortable to let them, because the repository itself stops a bad change.

That needs two things. The agent must find the right files fast, read little, and get a clear pass or fail on its change. And the path to production must be protected and automatic, so nobody needs special knowledge to release safely. This standard describes a repository built for that. It is abstracted from Software Combined repositories that work this way today.

The numbers are defaults. A repository may set different limits, but it must write them down and check them automatically.

**Proportionate, not strict.** The standard rewards structure where it earns its keep. Put an abstraction at a real boundary, such as an external service, storage or a framework, not around every function. A wrapper, factory or interface with one use and no test need is a cost, not a benefit. Level 5 means good practice that a team keeps up without effort, not perfection.

## 1. Structure

**Split by domain, then subdomain, then file.** Code lives under the business area that owns it, for example `packages/payables/src/extraction/`. A task in one area opens those files, not the whole repository.

**Clear service and layer boundaries.** Entry points (web, API, worker) do not import each other. Shared packages do not import apps. Pure domain rules do not import the database, HTTP or cloud code. An automatic architecture test (for example dependency-cruiser) runs as a required check, so a change that breaks a boundary cannot merge.

**Small files, one job each.**

| Lines in a handwritten source file | Meaning |
|---|---|
| Up to 250 | Fine |
| 251 to 400 | Review: can a part move out? |
| Over 400 | Split it. The check fails |

An old large file may stay on a baseline, but it cannot grow. A script in the repository checks the limits on every change.

## 2. Consistency

**Written rules.** One short rules document covers ownership, dependencies, naming, branches, tests and review. Each rule is one or two sentences.

**The code follows the rules.** Files in different domains have the same shape and naming. A new file can copy the pattern of its nearest neighbour.

**The machine enforces the rules.** One command (for example `pnpm check`) runs lint, type checks, the architecture test, the size check and the build. CI runs the same command, and it is a required check, so a failing change cannot merge.

## 3. Documentation

**One entry file routes each task.** `AGENTS.md` at the repository root is short (about 40 lines or fewer). It holds a table: "if the task touches X, read Y". `CLAUDE.md` contains one line that loads `AGENTS.md`. The agent reads only what the task needs.

**Documents are structured like the code.** Guides sit in one documentation folder, grouped by domain and then subdomain, for example `Doc/payables/extraction/`. The folders use the same domain names as the code. Each document has one responsibility: rules, design, testing and operations are separate documents, not sections of one long guide. A short index lists every guide. Each Markdown document is 200 lines or fewer, and a longer guide is split by responsibility.

**Documents are accurate and say each thing once.** Every local link resolves. Commands, paths and limits in the documents match the repository. Each decision has one owning guide; other guides link to it and do not repeat it. Stale text is revised or deleted, not left beside the new text.

## 4. Verification

**CI is fast and scoped.** CI works out what a change touched and runs only the checks that change needs. Independent jobs run in parallel. A newer push cancels the older run. Dependencies are cached. One final job decides pass or fail.

**Tests cover the behaviour and coverage is measured.** Tests sit next to the code or in a clear test folder. Coverage is measured, has a written target, and CI fails below it. Every bug fix adds a test.

**Checks run before the change leaves the laptop.** A pre-commit review and a secret scan run on every commit. The same check command runs locally and in CI.

**Anyone can run and see a change.** One documented command starts the app locally with sample data and no real credentials. Each pull request gets a preview or staging link, so the person who asked for the change can see it working before it merges.

## 5. Safe delivery

**The main branch is protected.** Nobody pushes to the production branch directly. A change arrives through a pull request, the CI gate must pass, and at least one approval is required. Force pushes and deletion are off, and the rules apply to administrators too. If work merges into a shared integration branch first (for example `development`), that branch is protected in the same way. High-risk areas, such as access, money, data migrations and infrastructure, need a named owner's review, for example through a CODEOWNERS file.

**Branches are clean and named the same way.** A written rule gives the naming convention, for example `feat/…`, `fix/…`, `docs/…`. A branch is short-lived and is deleted when it merges. Few branches are open at one time and none is stale.

**Deployment is automatic.** A merge deploys to a staging environment with no manual step. Production is one approved action, not a set of commands that one person knows. Each deployment is recorded and checked after release, and the way to roll back is written down.

## 6. Contracts and API

**One shared source for contracts.** Request and response shapes live in one shared place, for example a contracts package with Zod or OpenAPI schemas. Screens, the API and tools import them instead of copying them. The API checks all input against them where it enters.

**Written API conventions, checked automatically.** One guide covers naming, error shape, paging, retries that do not repeat an action (idempotency) and versioning. The API reference is generated from the code or checked against it. A check catches a change that would break existing callers.

**Abstraction where it is needed.** Each external service and store sits behind one adapter at a clear boundary. Business rules do not import framework or vendor code. Nothing is wrapped without a reason.

## 7. Hygiene

This dimension checks that the code stays tidy and current. Security is not scored here; use the dedicated security review for that.

**Clean code and configuration.** Strict typing and lint run with zero warnings. Dead code and copied blocks are found by a tool and removed. Settings live in one config module with an example file, not hard-coded across the code.

**Dependency hygiene.** A lockfile is committed. An update tool such as Dependabot or Renovate opens updates, and the team merges them regularly. Third-party CI actions are pinned to exact versions.
