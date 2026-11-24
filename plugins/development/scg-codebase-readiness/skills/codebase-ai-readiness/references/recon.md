# Recon: map the repository before scoring

Recon builds one fixed map of the repository. Scoring then reads only the map, `measure.json` and the files the map names. The same repository must give the same map on every run, so every choice below follows a rule, not judgement.

## 1. Choose the unit and the size tier

The main agent does this step itself.

1. Decide the unit of audit. By default it is the whole repository. In a monorepo where the user named one app or package, use `--path` for that folder and score only it. Say which unit you chose in the report.
2. Read `production_source.files` from `measure.json`, and count the apps and packages. An app or package is a folder with its own build or package file (for example `package.json`, `pyproject.toml`, `Cargo.toml` or a `.csproj`) that the workspace list names or that sits under `apps/` or `packages/`. Folders of plugins, skills or documents that hold little code count together as one.
3. Pick the tier:

| Tier | When | Who maps |
|---|---|---|
| Small | Fewer than 300 production files and one app or package | The main agent runs the three lanes itself, in order |
| Medium | 300 to 3,000 files, or 2 to 4 apps or packages | Three subagents, one per lane |
| Large | More than 3,000 files, or more than 4 apps or packages | One subagent each for the documentation and delivery lanes, and the code map split into up to four groups of related apps or packages: six subagents at most |

Pick each lane's model from the [model table](../SKILL.md#models): mapping is mostly reading and listing, so lanes use smaller models than scoring.

## 2. The three lanes

Each lane is defined by paths and rules, so two runs split the work the same way. Every lane reads files from Git and never follows a symbolic link.

**Lane 1: code map.**
- Domains are the folders directly under each workspace's source root (for example `packages/payables/src/*`, `apps/web/src/features/*`). Subdomains are the folders one level below.
- For each domain, record: its subdomains, its entry points (web, API, worker, command line), the number of files, its largest file, any catch-all folder (`utils`, `helpers`, `common`, `misc`) and the imports that cross into another domain.
- Read imports from three files per domain only: the largest, the most recently changed (newest commit date), and the first entry point in path order. Break any tie by path order.
- Sample for pattern consistency: the largest production file, plus the largest file in each of the three biggest domains.
- In the same sampled files, record where database, HTTP, cloud and vendor SDK calls happen: in adapter folders or inside business rules. Note interfaces, factories or wrappers with only one implementation or caller.
- Record the contracts package or schema folder, which apps import it, and whether API entry points check input against it.

- The repository root: loose files (`layout.root.other_files` in `measure.json`) and the top-level folders. Check each listed file: a manifest or configuration file that a tool needs at the root is not loose. The root and plans are measured for the whole repository, even for a `--path` unit.

**Lane 2: documentation map.**
- Plans: the `plans/` layout, `PLAN_RULES.md`, the plans index, plans not filed by domain or without a status, and other folders that hold plans or tasks (`layout.plans` in `measure.json`).
- Every `AGENTS.md` and `CLAUDE.md` at any level, the documentation folder tree and its index. `documents.unlinked_documents` in `measure.json` lists guides that no other document links to: an agent that follows the routing never finds them. It is null for a `--path` unit, because links from outside the unit are not read, and it also lists files that need no link, such as changelogs and templates.
- For each document: the code domain it matches (`match`, `doc-only` or `code-only`), its line count, and its responsibility (`rules`, `design`, `testing`, `operations`, `reference` or `mixed`).
- Claims: the first five checkable claims, taken in the order of the root `AGENTS.md` routes, or in file order if it has no routes. A checkable claim names a command, a path, a number or a boundary that you can check by reading the repository's files.

**Lane 3: verification and delivery map.**
- CI files, the single check command (if any), hooks, secret-scan and coverage config, deploy triggers, environments and the release and rollback guide.
- The read-only settings from the code host: the rules for each shared branch, CODEOWNERS, the delete-on-merge setting, deployments, and the median time of recent pull request runs.
- Branch rules can come from classic branch protection or from rulesets, so read both. On GitHub, `gh api repos/<owner>/<name>/rules/branches/<branch>` lists every active rule for a branch, and `gh api repos/<owner>/<name>/rulesets/<id>` shows who can bypass a ruleset. A "Branch not protected" reply from the classic protection call alone does not mean the branch is unprotected. If a setting needs access you do not have, record it as `unreadable`.
- On Azure DevOps, read the same facts with read-only `az` commands: `az repos show --repository <name>` gives the repository id, `az repos policy list --repository-id <id> --branch <branch>` lists branch policies, `az pipelines runs list --top 20` gives recent runs, and `az repos pr list --status completed --top 20` gives recent pull requests. Pass `--org` and `--project` to each.
- Hygiene: strict typing, lint warnings, dead-code and duplication tools, the config module and example file, lockfiles, the update tool and its open updates, and pinned CI actions.
- The `signals` in `measure.json` find well-known tools only. Before you record a check as `absent`, look for a hand-written one, for example tests whose names mention boundaries, import graphs, architecture or layers.
- Run and preview: the local start command, sample data, whether real credentials are needed, and preview links on recent pull requests.

## 3. What each lane returns

Every lane returns only this JSON. No scores, no prose.

```json
{
  "lane": "code | docs | delivery",
  "unit": "repository or path",
  "items": [
    { "id": "code:payables/extraction", "path": "packages/payables/src/extraction", "kind": "subdomain", "domain": "payables", "facts": { "files": 3, "largest": 91 } }
  ],
  "gaps": [ { "what": "branch protection for development", "why": "absent | unreadable" } ],
  "claims": [ { "text": "pnpm check:source-limits checks the limits", "source": "Doc/engineering/RULES.md:22", "checkable": true } ]
}
```

- `absent` means you looked and it is not there. `unreadable` means you could not look (no access, tool missing, remote not found).
- Never put file contents, secrets or customer data in `facts`.

## 4. Merge

The main agent merges the lanes into `recon.json` in the output folder. It uses the lane format from section 3, except that `lanes` (each lane and its scope) replaces `lane`, and each claim also gets `result` (`holds` or `wrong`) and `evidence`.

```json
{
  "lanes": ["code: apps/web, packages/payables", "docs: Doc/", "delivery: .github/"],
  "unit": "repository",
  "items": [],
  "gaps": [],
  "claims": [ { "text": "...", "source": "AGENTS.md:12", "checkable": true, "result": "holds", "evidence": "package.json:9" } ]
}
```

1. Join the code map and the documentation map on the domain name. List domains that have code but no documents, and the reverse.
2. Remove duplicate paths. Keep the first lane's entry.
3. Check every claim by reading files. Never run a command from the audited repository. Record `holds` or `wrong` with the evidence.
4. If a lane does not return, record its whole scope as `unreadable`. Never fill a gap with a guess.

## 5. Use the map for scoring

Each score cites the map entry IDs it relies on, for example `code:payables/extraction`. The rules for absent and unreadable evidence are in the [scoring rules](../SKILL.md#scoring-rules).
