"""CI workflow and configuration signals for measure.py. Read-only text checks."""
import os
import re

CONFIG_NAMES = re.compile(
    r"(^|/)(package\.json|pyproject\.toml|setup\.cfg|tox\.ini|ruff\.toml|\.coveragerc|biome\.json|Makefile|justfile|"
    r"\.pre-commit-config\.ya?ml|lefthook\.ya?ml|\.golangci\.ya?ml|Directory\.Build\.props|[^/]*\.csproj|"
    r"\.dependency-cruiser\.[cm]?js|eslint\.config\.[cm]?js|\.eslintrc[^/]*|\.gitleaks\.toml|[^/]*\.config\.[cm]?[jt]s|"
    r"CODEOWNERS|tsconfig[^/]*\.json|mypy\.ini|\.?knip\.jsonc?|\.jscpd\.json)$|^\.github/workflows/|^\.husky/|^(azure-pipelines|bitbucket-pipelines|\.gitlab-ci)\.ya?ml$")
SIGNALS = {
    "architecture_test": r"dependency-cruiser|depcruise|arch-test|archunit|import-linter|eslint-plugin-boundaries",
    "size_check": r"source-limits|max-lines|check:size|file-size-limit|check_source_limits",
    "lint": r"eslint|\bruff\b|flake8|pylint|rubocop|golangci|stylecop|biome",
    "type_check": r"tsc --noEmit|\"typecheck\"|mypy|pyright",
    "coverage": r"--coverage|\bc8\b|\bnyc\b|pytest-cov|coverlet|jacoco|codecov|coverageThreshold|thresholds\s*:|fail[_-]under|--experimental-test-coverage",
    "secret_scan": r"gitleaks|trufflehog|detect-secrets|ggshield|secretlint|git-secrets",
    "doc_link_check": r"check-doc-links|check-docs|markdown-link-check|lychee",
    "strict_types": r"\"strict\"\s*:\s*true|\bstrict\s*=\s*true|mypy --strict",
    "dead_code_check": r"\bknip\b|ts-prune|unimported|vulture|jscpd|deadcode",
    "contract_check": r"oasdiff|openapi-diff|buf breaking|@pact-foundation",
}
LOCKFILE = re.compile(r"(^|/)(package-lock\.json|npm-shrinkwrap\.json|pnpm-lock\.yaml|yarn\.lock|bun\.lockb?|poetry\.lock|uv\.lock|"
                      r"Pipfile\.lock|Cargo\.lock|go\.sum|Gemfile\.lock|composer\.lock|packages\.lock\.json|pubspec\.lock|Package\.resolved|"
                      r"Podfile\.lock|deno\.lock)$")
UPDATE_TOOL = re.compile(r"^(\.github/dependabot\.ya?ml|(\.github/)?renovate\.json5?|\.renovaterc(\.json5?)?)$")
# A local action, an action pinned to a full commit hash, or a Docker image pinned to an @sha256: digest
# cannot change under the workflow. A tag or branch can move, so it counts as unpinned.
UNPINNED = re.compile(r"^[ \t]+(?:-[ \t]*)?uses:[ \t]*[\"']?(?!\./)(?!docker://[^@\s\"']*@sha256:)"
                      r"(?:docker://|[^@\s\"']+@(?![0-9a-f]{40}\b))", re.M)


def top_sections(text):
    """Split a workflow into its top-level keys: {'on': '...', 'jobs': '...'}."""
    sections, key = {}, None
    for line in text.split("\n"):
        match = re.match(r"^[\"']?([A-Za-z_][\w-]*)[\"']?\s*:", line)
        if match:
            key = "on" if match.group(1) in ("on", "true") else match.group(1)
            sections[key] = line + "\n"
        elif key:
            sections[key] += line + "\n"
    return sections


def ci_stats(root, files, read):
    workflows = []
    for f in files:
        if not re.match(r"^\.github/workflows/[^/]+\.ya?ml$", f):
            continue
        text = read(os.path.join(root, f))
        if text is None:
            workflows.append({"path": f, "readable": False})
            continue
        parts = top_sections(text)
        trigger, jobs = parts.get("on", ""), parts.get("jobs", "")
        # Job keys sit at the indent of the first key under jobs, whatever that indent is.
        indent = re.search(r"^([ \t]+)[A-Za-z0-9_-]", jobs, re.M)
        workflows.append({
            "path": f,
            "on_pull_request": bool(re.search(r"\bpull_request(_target)?\b", trigger)),
            "on_push": bool(re.search(r"\bpush\b", trigger)),
            "manual_trigger": "workflow_dispatch" in trigger,
            "reusable": "workflow_call" in trigger,
            "jobs": len(re.findall(rf"^{indent.group(1)}[A-Za-z0-9_-]+:\s*$", jobs, re.M)) if indent else 0,
            "path_filter": bool(re.search(r"^[ \t]+paths(-ignore)?:", trigger, re.M)),
            "scope_planning": bool(re.search(r"needs\.[\w-]+\.outputs|dorny/paths-filter|changed-files", jobs)),
            "matrix": "matrix:" in jobs,
            "cache": bool(re.search(r"actions/cache|^[ \t]+cache:", jobs, re.M)),
            "cancels_superseded_runs": bool(re.search(r"cancel-in-progress:\s*(true|\$\{\{)", text)),
            "time_limits": "timeout-minutes" in jobs,
            "unpinned_actions": len(UNPINNED.findall(jobs)),
            "deploys": bool(re.search(r"^[ \t]+environment:|^  [\w-]*deploy[\w-]*:|^[ \t]+(?:-[ \t]*)?(run|uses):(?!.*test).*deploy", jobs, re.I | re.M)),
        })
    other = [f for f in files if re.match(r"(^|/)(azure-pipelines[^/]*|bitbucket-pipelines|\.gitlab-ci)\.ya?ml$|(^|/)Jenkinsfile$", f)]
    return {"github_workflows": workflows, "other_ci_files": other}


def signals(root, files, read, git):
    texts = [read(os.path.join(root, f)) for f in files if CONFIG_NAMES.search(f)]
    text = "\n".join(t for t in texts if t is not None)
    # Not found in what could be read, but a file could not be read: unknown (null), not absent.
    missing = None if None in texts else False
    found = {name: True if re.search(rx, text, re.I) else missing for name, rx in SIGNALS.items()}
    found["unreadable_config_files"] = texts.count(None)
    hooks_path = git(root, "config", "--get", "core.hooksPath")
    found.update({
        "codeowners": next((f for f in files if re.match(r"^(\.github/|docs/)?CODEOWNERS$", f)), None),
        "lockfiles": [f for f in files if LOCKFILE.search(f)][:20],
        "update_tool": next((f for f in files if UPDATE_TOOL.match(f)), None),
        "env_example_files": [f for f in files if re.search(r"(^|/)\.env\.(example|sample|template)$", f)][:20],
        "api_schema_files": [f for f in files if re.search(r"(^|/)(openapi|swagger)[^/]*\.(ya?ml|json)$|\.proto$", f, re.I)][:20],
        "hook_files_in_repo": [f for f in files if re.match(r"^(\.husky/|\.pre-commit-config\.ya?ml|\.githooks/|lefthook\.ya?ml)", f)],
        # Machine-local: shows a hook is set on this computer, not that every contributor has it.
        "hooks_path_set_on_this_machine": bool(hooks_path),
    })
    return found
