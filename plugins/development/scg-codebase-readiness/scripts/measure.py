"""Measure a repository for the codebase AI readiness audit.

Usage:  python3 -I measure.py <repo> [--path <folder>] > measure.json

Reads tracked files only and prints JSON. It never changes a file and never
runs the repository's code: it uses only git commands that do not read file
contents through filters, disables fsmonitor, optional locks, network access
and on-demand fetches, and runs git only from an absolute PATH folder. Python
3.9 or later, standard library only. Values it cannot measure are null, never
zero. The numbers are evidence; the agent still judges.
"""
import collections
import json
import os
import posixpath
import re
import subprocess
import sys
import time
from urllib.parse import unquote

# python3 -I leaves the script's own folder off the import path; add only that folder.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure_ci import ci_stats, signals  # noqa: E402

SOURCE_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".cs", ".java", ".go", ".rb", ".php",
              ".swift", ".kt", ".rs", ".dart", ".vue", ".svelte", ".sql", ".css", ".scss"}
SKIP_DIRS = {"node_modules", "dist", "vendor", "fixtures", "__snapshots__", "coverage", "obj", "target", ".next"}
SKIP_FILE = re.compile(r"(\.generated\.|\.gen\.|\.min\.|\.d\.ts$|\.designer\.cs$|-lock\.|\.lock$)", re.I)
TEST_FILE = re.compile(r"(\.test\.|\.spec\.|_test\.|_spec\.|_integration\.|\.integration\.|(^|/)test_[^/]*$|conftest\.py$|tests?\.(cs|java|kt)$"
                       r"|(^|/)(tests?|__tests__|e2e|spec)/|\.tests?/)", re.I)
CONFIG_FILE = re.compile(r"(^|/)[^/]*\.config\.[cm]?[jt]s$|(^|/)(setup|conftest)\.py$", re.I)
CATCH_ALL = {"utils", "util", "helpers", "common", "misc", "lib", "shared"}
CODE_FENCE = re.compile(r"^[ \t]*(```|~~~).*?^[ \t]*\1", re.S | re.M)
INLINE_CODE = re.compile(r"`[^`\n]*`")
INLINE_LINK = re.compile(r"\]\(\s*(<[^<>\n]*>|[^)\s]+)")
REF_LINK = re.compile(r"^[ \t]*\[(?!\^)[^\]\n]+\]:[ \t]*(<[^>\n]*>|\S+)", re.M)
# No transport at all: a repository setting must never make git fetch or run a remote command.
# GIT_ALLOW_PROTOCOL overrides every protocol.<name>.allow in the repository config.
ENV = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_NO_LAZY_FETCH="1", GIT_ALLOW_PROTOCOL="none")
SAFE = ["-c", "core.fsmonitor=false", "-c", "protocol.allow=never"]


def find_git():
    """Git from an absolute PATH folder only, never a program in the current or audited folder."""
    names = ("git.exe", "git") if os.name == "nt" else ("git",)
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        for name in names if os.path.isabs(folder) else ():
            path = os.path.join(folder, name)
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
    return None


GIT = find_git()


def git(root, *args):
    done = subprocess.run([GIT, *SAFE, "-C", root, *args],
                          capture_output=True, env=ENV)
    return done.stdout.decode("utf-8", "replace").strip() if done.returncode == 0 else None


def tracked(root):
    """Regular tracked files, plus tracked symlinks listed apart (never followed). Submodules are skipped."""
    out = subprocess.run([GIT, *SAFE, "-C", root, "ls-files", "-s", "-z"],
                         capture_output=True, env=ENV, check=True).stdout.decode("utf-8", "replace")
    entries = [(e.split(" ", 1)[0], e.split("\t", 1)[1]) for e in out.split("\0") if e]
    # A hand-built index can list names that leave the folder: keep only plain relative paths.
    # Backslashes and colons are dropped too, because Windows reads them as folder or drive parts.
    entries = [(mode, p) for mode, p in entries if not p.startswith("/") and "\\" not in p
               and ":" not in p and not {"", ".", ".."} & set(p.split("/"))]
    return [p for mode, p in entries if mode in ("100644", "100755")], [p for mode, p in entries if mode == "120000"]


def read(path):
    # Never read through a link at any level, even one made after checkout. Root is a real path.
    # Returns None when the file cannot be read, so callers report it instead of counting zero.
    if os.path.realpath(path) != os.path.normpath(path):
        return None
    try:
        with open(path, encoding="utf-8", errors="replace", newline="") as handle:
            return handle.read()
    except OSError:
        return None


def source_lines(text):
    return len(text.rstrip().split("\n")) if text.strip() else 0


def doc_lines(text):
    return len(text.split("\n")) - int(text.endswith("\n"))


def size_stats(root, files):
    texts = [(read(os.path.join(root, f)), f) for f in files]
    rows = [(source_lines(t), f) for t, f in texts if t is not None]
    lines = [n for n, _ in rows]
    count = len(rows)
    over_400 = sum(1 for n in lines if n > 400)
    return {"files": len(rows), "unreadable_files": len(texts) - len(rows),
            "total_lines": sum(lines), "average_lines": round(sum(lines) / count, 1) if count else None,
            "up_to_250": sum(1 for n in lines if n <= 250), "from_251_to_400": sum(1 for n in lines if 250 < n <= 400),
            "over_400": over_400, "over_400_percent": round(100 * over_400 / count, 1) if count else None,
            "over_1000": sum(1 for n in lines if n > 1000),
            "largest": [{"lines": n, "path": f} for n, f in sorted(rows, reverse=True)[:15]]}


def link_targets(text):
    text = INLINE_CODE.sub("", CODE_FENCE.sub("", text))
    for raw in INLINE_LINK.findall(text) + REF_LINK.findall(text):
        target = unquote(raw.strip("<>").split("#")[0].split("?")[0])
        if target and not re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
            yield raw, target


def with_folders(paths):
    return {"."} | set(paths) | {f.rsplit("/", i)[0] for f in paths for i in range(1, f.count("/") + 1)}


def live_links(root, files, symlinks):
    """Tracked links whose index text names a tracked path. A dangling link is not a valid link target."""
    known, live = with_folders(files + symlinks), []
    for link in symlinks:
        target = git(root, "cat-file", "blob", ":" + link)
        if not target or target.startswith("/"):
            continue
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(link), target))
        if resolved in known:
            live.append(link)
    return live


def doc_stats(root, docs, all_files, whole_repo):
    known = with_folders(all_files)
    rows, broken, blocks, unreadable, linked = [], [], collections.defaultdict(set), 0, set()
    for doc in docs:
        text = read(os.path.join(root, doc))
        if text is None:
            unreadable += 1
            continue
        rows.append((doc_lines(text), doc))
        for raw, target in link_targets(text):
            base = "" if target.startswith("/") else os.path.dirname(doc)
            resolved = os.path.normpath(os.path.join(base, target.lstrip("/"))).replace(os.sep, "/")
            if resolved not in known:
                broken.append({"doc": doc, "link": raw})
            # A link to a folder reaches the README a reader sees there. A link to itself does not count.
            if resolved != doc:
                linked.update((resolved, resolved + "/README.md"))
        for block in re.split(r"\n\s*\n", CODE_FENCE.sub("", text)):
            block = " ".join(block.split())
            if len(block) >= 200 and not block.startswith("|"):
                blocks[block].add(doc)
    pairs = collections.Counter(tuple(sorted(found)) for found in blocks.values() if len(found) > 1)
    # A unit's guides may be linked from outside it, so the list is measured for the whole repository only.
    unlinked = sorted(f for _, f in rows if "/" in f and f not in linked) if whole_repo else None
    return {"files": len(rows), "unreadable_files": unreadable, "over_200_count": sum(1 for n, _ in rows if n > 200),
            "over_200_lines": [{"lines": n, "path": f} for n, f in sorted(rows, reverse=True) if n > 200][:25],
            "folders": dict(collections.Counter(os.path.dirname(f) or "." for _, f in rows).most_common(30)),
            "broken_local_links": broken[:40], "broken_local_link_count": len(broken),
            # Root files are entry points; any other guide no document links to is hidden from an agent.
            "unlinked_documents": None if unlinked is None else unlinked[:40],
            "unlinked_document_count": None if unlinked is None else len(unlinked),
            "documents_sharing_paragraphs": [{"docs": list(k), "paragraphs": v} for k, v in pairs.most_common(15)]}


def agent_files(root, files, symlinks):
    # Link text comes from the index copy, so a folder link on disk cannot redirect the read.
    result = [{"path": f, "symlink_to": git(root, "cat-file", "blob", ":" + f)} for f in symlinks
              if os.path.basename(f) in ("AGENTS.md", "CLAUDE.md")]
    for f in files:
        if os.path.basename(f) in ("AGENTS.md", "CLAUDE.md"):
            text = read(os.path.join(root, f))
            if text is None:
                result.append({"path": f, "readable": False})
                continue
            result.append({"path": f, "lines": doc_lines(text), "links": sum(1 for _ in link_targets(text)),
                           "table_rows": sum(1 for line in text.split("\n") if line.startswith("|"))})
    return result


def repo_state(root):
    remotes = (git(root, "remote") or "").split()
    remote = "origin" if "origin" in remotes else (remotes[0] if remotes else None)
    url = git(root, "remote", "get-url", remote) if remote else None
    # Only hosted URLs give a name; userinfo (tokens, user names) and local paths never reach the output.
    hosted = re.match(r"^(?:[a-z][a-z0-9+.-]*://(?:[^/@]*@)?[^/]+/|[\w.-]+@[\w.-]+:)(.+?)(?:\.git)?/?$", url or "", re.I)
    # Accept only an owner/name pair: a longer path can hold a server folder or a user name.
    match = hosted if hosted and re.fullmatch(r"[\w.-]+/[\w.-]+", hosted.group(1)) else None
    upstream = git(root, "rev-list", "--count", "HEAD..@{upstream}")
    shallow = git(root, "rev-parse", "--is-shallow-repository")
    return remote, {"name": match.group(1) if match else os.path.basename(root), "remote": remote,
                    "commit": git(root, "rev-parse", "--short", "HEAD"), "branch": git(root, "branch", "--show-current"),
                    # git status can run repository-configured filters, so it is never called.
                    "uncommitted_changes": None,
                    "commits_behind_upstream": int(upstream) if upstream else None,
                    "shallow_clone": None if shallow is None else shallow == "true"}


def branch_stats(root, remote, shallow):
    """Remote branches as this clone last fetched them. Null when they cannot be measured."""
    head = git(root, "symbolic-ref", "--short", f"refs/remotes/{remote}/HEAD") if remote else None
    if not head or shallow:
        reason = "no remote" if not remote else "shallow clone" if shallow else f"{remote}/HEAD not set"
        return {"measured": False, "reason": reason}
    merged_out = git(root, "branch", "-r", "--merged", head)
    refs = git(root, "for-each-ref", f"refs/remotes/{remote}", "--format=%(refname:short)\t%(committerdate:unix)")
    if merged_out is None or refs is None:  # for example, HEAD names a branch this clone no longer has
        return {"measured": False, "reason": f"{head} could not be read"}
    merged = {b.strip() for b in merged_out.split("\n")}
    now, rows = time.time(), []
    for line in refs.split("\n"):
        name, _, stamp = line.partition("\t")
        if stamp and name not in (remote, f"{remote}/HEAD", head):
            rows.append({"name": name[len(remote) + 1:], "days_since_last_commit": int(now - int(stamp)) // 86400,
                         "merged_into_default": name in merged})
    return {"measured": True, "default_branch": head[len(remote) + 1:], "other_branches": len(rows),
            "name_prefixes": dict(collections.Counter(r["name"].split("/")[0] if "/" in r["name"] else "(none)" for r in rows).most_common(15)),
            "no_commit_for_30_days": sum(1 for r in rows if r["days_since_last_commit"] > 30),
            "merged_but_not_deleted": sum(1 for r in rows if r["merged_into_default"]),
            "branches": sorted(rows, key=lambda r: -r["days_since_last_commit"])[:40]}


def main(argv):
    args = argv[1:]
    if GIT is None:
        print("measure.py: git was not found in an absolute PATH folder.", file=sys.stderr)
        return 2
    if any(a.startswith("--") and a != "--path" for a in args):
        print(__doc__, file=sys.stderr)
        return 2
    flag = args.index("--path") if "--path" in args else None
    raw = args[flag + 1] if flag is not None and flag + 1 < len(args) else None
    unit = posixpath.normpath(raw.replace("\\", "/")).strip("/") if raw else ""
    unit = "" if unit == "." else unit
    root = git(os.path.abspath(args[0]), "rev-parse", "--show-toplevel") if args and flag != 0 else None
    if root is None or (flag is not None and raw is None) or (raw and (raw.startswith(("/", "\\")) or unit.startswith(".."))):
        print(__doc__, file=sys.stderr)
        return 2
    root = os.path.realpath(root)
    files, symlinks = tracked(root)
    in_unit = [f for f in files if not unit or f == unit or f.startswith(unit + "/")]
    if unit and not in_unit:
        print(f"measure.py: no tracked files under '{unit}'.", file=sys.stderr)
        return 2
    in_scope = [f for f in in_unit if not ({p.lower() for p in f.split("/")[:-1]} & SKIP_DIRS)]
    kept = [f for f in in_scope if not SKIP_FILE.search(f)]
    # Checks count only inside the unit, plus root files and CI or hook folders that serve every unit.
    shared = {f for f in files if "/" not in f or f.startswith((".github/", ".husky/", ".githooks/", ".azure/", ".azuredevops/")) or f == "docs/CODEOWNERS"}
    source = [f for f in kept if os.path.splitext(f)[1].lower() in SOURCE_EXT]
    tests = [f for f in source if TEST_FILE.search(f)]
    config = [f for f in source if not TEST_FILE.search(f) and CONFIG_FILE.search(f)]
    excluded = set(tests) | set(config)
    production = [f for f in source if f not in excluded]
    folders = collections.Counter("/".join(f.split("/")[:4]) if f.count("/") >= 4 else os.path.dirname(f) or "." for f in production)
    remote, state = repo_state(root)
    print(json.dumps({
        "repository": state, "unit": unit or "repository", "tracked_files": len(in_unit),
        "excluded_as_generated_or_vendored": len(in_unit) - len(kept), "config_source_files": len(config),
        "production_source": size_stats(root, production),
        "test_source": {"files": len(tests), "ratio_to_production": round(len(tests) / len(production), 2) if production else None,
                        "top_folders": dict(collections.Counter(f.split("/")[0] for f in tests).most_common(10))},
        "structure": {"production_files_by_folder": dict(folders.most_common(60)),
                      "catch_all_folder_names": dict(collections.Counter(p for f in production for p in f.split("/")[:-1] if p.lower() in CATCH_ALL))},
        "documents": doc_stats(root, [f for f in kept if f.lower().endswith(".md")], files + live_links(root, files, symlinks), not unit),
        "agent_files": agent_files(root, kept, symlinks),
        "ci": ci_stats(root, files, read),
        "signals": signals(root, sorted(set(in_scope) | shared), read, git),
        "branches": branch_stats(root, remote, state["shallow_clone"]),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
