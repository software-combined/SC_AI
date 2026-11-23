# Recon: map the repository before scoring

Recon builds one fixed map of the repository. Scoring then reads only the map, `measure.json` and the files the map names. The same repository must give the same map on every run, so every choice below follows a rule, not judgement.

## 1. Choose the unit and the size tier

The main agent does this step itself.

1. Decide the unit of audit. By default it is the whole repository. In a monorepo where the user named one app or package, use `--path` for that folder and score only it. Say which unit you chose in the report.
2. Read `production_source.files` and the number of workspaces (apps and packages folders, or the workspace list in the package or build file) from `measure.json`.
3. Pick the tier:

| Tier | When | Who maps |
|---|---|---|
| Small | Fewer than 300 production files and one app | The main agent runs the three lanes itself, in order |
| Medium | 300 to 3,000 files, or 2 to 4 apps or packages | Three subagents, one per lane |
| Large | More than 3,000 files, or more than 4 workspaces | One subagent each for the documentation and delivery lanes, and the code map split into up to four groups of related workspaces: six subagents at most |

Use a smaller model tier for lanes when the host allows it: mapping is reading and listing, not judging.

## 2. The three lanes

Each lane is defined by paths and rules, so two runs split the work the same way. Every lane reads files from Git and never follows a symbolic link.

**Lane 1: code map.**
- Domains are the folders directly under each workspace's source root (for example `packages/payables/src/*`, `apps/web/src/features/*`). Subdomains are the folders one level below.
- For each domain, record: its subdomains, its entry points (web, API, worker, command line), the number of files, its largest file, any catch-all folder (`utils`, `helpers`, `common`, `misc`) and the imports that cross into another domain.
- Read imports from three files per domain only: the largest, the most recently changed (newest commit date), and the first entry point in path order. Break any tie by path order.
- Sample for pattern consistency: the largest production file, plus the largest file in each of the three biggest domains.

**Lane 2: documentation map.**
- Every `AGENTS.md` and `CLAUDE.md` at any level, the documentation folder tree and its index.
- For each document: the code domain it matches (`match`, `doc-only` or `code-only`), its line count, and its responsibility (`rules`, `design`, `testing`, `operations`, `reference` or `mixed`).
- Claims: the first five checkable claims, taken in the order of the root `AGENTS.md` routes. A checkable claim names a command, a path, a number or a boundary that you can check by reading the repository's files.

**Lane 3: verification and delivery map.**
- CI files, the single check command (if any), hooks, secret-scan and coverage config, deploy triggers, environments and the release and rollback guide.
- The read-only settings from the code host: branch protection for each shared branch, CODEOWNERS, the delete-on-merge setting, deployments, and the median time of recent pull request runs.

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

The main agent merges the lanes into `recon.json` in the output folder.

1. Join the code map and the documentation map on the domain name. List domains that have code but no documents, and the reverse.
2. Remove duplicate paths. Keep the first lane's entry.
3. Check every claim by reading files. Never run a command from the audited repository. Record `holds` or `wrong` with the evidence.
4. If a lane does not return, record its whole scope as `unreadable`. Never fill a gap with a guess.

## 5. Use the map for scoring

Each score cites the map entry IDs it relies on, for example `code:payables/extraction`. The rules for absent and unreadable evidence are in the [scoring rules](../SKILL.md#scoring-rules).
