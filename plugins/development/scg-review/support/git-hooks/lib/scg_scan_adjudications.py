"""Owner-managed adjudication of exact non-secret findings; no scanner overrides."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess


def git(root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", *args], cwd=root, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False,
    )
    if result.returncode:
        raise ValueError("cannot verify staged source or repository identity")
    return result.stdout


def read_policy(policy: Path, root: Path) -> dict:
    # This is an owner change, never a repository-controlled suppression file.
    if os.name != "posix":
        raise ValueError("owner-only adjudication storage is not qualified on this platform")
    if policy.resolve().is_relative_to(root.resolve()):
        raise ValueError("adjudication policy must remain outside the repository")
    for item in (policy.parent, policy):
        meta = item.lstat()
        if stat.S_ISLNK(meta.st_mode) or meta.st_uid != os.getuid() or meta.st_mode & 0o022:
            raise ValueError("adjudication policy must be owner-managed and not writable by others")
    descriptor = os.open(policy, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
        meta = os.fstat(stream.fileno())
        if not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.getuid() or meta.st_mode & 0o077:
            raise ValueError("adjudication policy must be an owner-only regular file")
        data = json.load(stream)
    if not isinstance(data, dict) or type(data.get("schemaVersion")) is not int or data["schemaVersion"] != 1:
        raise ValueError("invalid adjudication policy schema")
    return data


def key(entry: dict) -> tuple[str, str, int]:
    if not isinstance(entry, dict):
        raise ValueError("invalid finding entry")
    file, rule, line = entry.get("file"), entry.get("rule"), entry.get("line")
    if not isinstance(file, str) or not file or "\\" in file or "\0" in file:
        raise ValueError("invalid finding path")
    path = PurePosixPath(file)
    if path.is_absolute() or any(p in ("", ".", "..", ".git") for p in file.split("/")):
        raise ValueError("invalid finding path")
    if not isinstance(rule, str) or not rule or type(line) is not int or line < 1:
        raise ValueError("invalid finding rule or line")
    return file, rule, line


def approved_findings(scope: dict) -> dict:
    entries = scope.get("findings")
    if not isinstance(entries, list) or not entries:
        raise ValueError("empty or invalid adjudication inventory")
    approved = {}
    for entry in entries:
        identity = key(entry)
        digest = entry.get("stagedFileSha256")
        if identity in approved or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("duplicate or invalid adjudication fingerprint/hash")
        if not isinstance(entry.get("reason"), str) or not entry["reason"].strip():
            raise ValueError("adjudication finding lacks a reason")
        approved[identity] = digest
    return approved


def adjudicate(report: Path, policy: Path, root: Path, tree: str) -> int:
    """Return the visible approved count only when every reported match is bound."""
    data = read_policy(policy, root)
    scopes = data.get("repositories")
    if not isinstance(scopes, list):
        raise ValueError("invalid adjudication repository list")
    for scope in scopes:
        if not isinstance(scope, dict) or not all(
            isinstance(scope.get(k), str) and scope[k].strip()
            for k in ("gitCommonDir", "origin", "approvedBy", "approvedAt", "reason")
        ) or not Path(scope["gitCommonDir"]).is_absolute():
            raise ValueError("invalid adjudication repository authorization")
        approved_findings(scope)
    common = str(Path(git(root, "rev-parse", "--path-format=absolute", "--git-common-dir").decode().strip()).resolve())
    origin = git(root, "remote", "get-url", "origin").decode().strip()
    matches = [s for s in scopes if isinstance(s, dict)
               and s.get("gitCommonDir") == common and s.get("origin") == origin]
    if len(matches) != 1:
        raise ValueError("repository has no unique owner-approved adjudication scope")
    scope = matches[0]
    approved = approved_findings(scope)
    findings = json.loads(report.read_text(encoding="utf-8"))
    if not isinstance(findings, list) or not findings:
        raise ValueError("scanner failure has no valid nonempty JSON report")
    seen = set()
    for finding in findings:
        if not isinstance(finding, dict):
            raise ValueError("invalid scanner finding")
        identity = key({"file": finding.get("File"), "rule": finding.get("RuleID"), "line": finding.get("StartLine")})
        file, rule, line = identity
        if finding.get("Fingerprint") != f"{file}:{rule}:{line}" or identity in seen:
            raise ValueError("invalid or duplicate scanner fingerprint")
        seen.add(identity)
        if identity not in approved:
            raise ValueError("unapproved scanner finding remains")
        mode = git(root, "ls-files", "--stage", "-z", "--", file).decode()
        if not re.fullmatch(r"100(?:644|755) [0-9a-f]{40,64} 0\t" + re.escape(file) + "\0", mode):
            raise ValueError("adjudicated source must be one regular staged blob")
        digest = hashlib.sha256(git(root, "cat-file", "blob", ":" + file)).hexdigest()
        if digest != approved[identity]:
            raise ValueError("adjudicated staged file hash changed")
    if git(root, "write-tree").decode().strip() != tree:
        raise ValueError("staged tree changed during adjudication")
    return len(seen)
