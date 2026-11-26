"""Read review receipts and prove when a prepared merge can reuse them."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any


REVIEW_ROOT = Path.home() / ".cache" / "scg-agent-git-hooks" / "reviews"
ALLOW_DECISIONS = {"ALL_CLEAR", "PROCEED_WITH_NOTES"}
STATE_VERSION = 3


def repo_identity(root: str) -> str:
    return hashlib.sha256(root.encode("utf-8")).hexdigest()


def state_path(repo_id: str, tree: str, base_commit: str | None) -> Path:
    return REVIEW_ROOT / repo_id / f"{tree}.{base_commit or 'unborn'}.review.json"


def load_candidate_states(info: dict[str, Any]) -> list[tuple[Path, dict[str, Any], str]]:
    path = state_path(info["repo_id"], info["tree"], info["base_commit"])
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [(path, {}, f"cannot read receipt: {exc}")]
    if not isinstance(state, dict):
        return [(path, {}, "receipt is not a JSON object")]
    return [(path, state, "loaded")]


def state_is_valid(
    state: dict[str, Any],
    info: dict[str, Any],
    lanes: list[str],
    ttl_seconds: int,
    *,
    match_branch: bool = True,
) -> tuple[bool, str]:
    if state.get("version") != STATE_VERSION:
        return False, f"state version {state.get('version')!r} is not supported"
    if state.get("repo_root") != info["repo_root"]:
        return False, "repo root mismatch"
    if state.get("repo_id") != info["repo_id"]:
        return False, "repo id mismatch"
    branch = state.get("branch")
    if not isinstance(branch, str) or not branch or (match_branch and branch != info["branch"]):
        return False, "branch mismatch"
    if state.get("tree") != info["tree"]:
        return False, "tree mismatch"
    if "base_commit" not in state or state["base_commit"] != info["base_commit"]:
        return False, "base commit mismatch"
    decision = state.get("decision")
    if not isinstance(decision, str) or decision not in ALLOW_DECISIONS or state.get("approved") is not True:
        return False, f"decision {decision!r} is not approved"
    try:
        created_at = int(state.get("created_at_epoch"))
    except (TypeError, ValueError, OverflowError):
        return False, "created_at_epoch missing or invalid"
    if int(time.time()) - created_at > ttl_seconds:
        return False, "review state expired"
    passes = state.get("passes")
    if not isinstance(passes, dict):
        return False, "passes missing or invalid"
    if set(passes) != set(lanes):
        return False, "recorded review lanes do not match required lanes"
    if any(not isinstance(model, str) or not model.strip() for model in passes.values()):
        return False, "one or more recorded review models are empty or invalid"
    return True, "ok"


def _git_bytes(*args: str, env: dict[str, str] | None = None) -> bytes:
    return subprocess.check_output(
        ["git", "--no-replace-objects", *args], env=env, stderr=subprocess.PIPE,
    )


def _git_path(*args: str) -> Path:
    return Path(os.fsdecode(_git_bytes("rev-parse", *args).rstrip(b"\r\n")))


def git_repository_id(common_dir: Path | None = None) -> str:
    path = common_dir if common_dir is not None else _git_path("--git-common-dir").resolve()
    identity = path.stat()
    return repo_identity(f"{path}\0{identity.st_dev}\0{identity.st_ino}")


def _changed_paths(left: str, right: str) -> set[bytes]:
    output = _git_bytes(
        "diff-tree", "-r", "--name-only", "-z", "--no-renames", "--no-relative",
        "--no-ext-diff", "--no-textconv", "--ignore-submodules=none", left, right, "--",
    )
    return set(output.split(b"\0")) - {b""}


def _receipt_scopes(info: dict[str, Any], common_dir: Path) -> list[dict[str, str]]:
    scopes = [{"repo_root": info["repo_root"], "repo_id": info["repo_id"]}]
    git_env_vars = set(_git_bytes("rev-parse", "--local-env-vars").decode("ascii").split())
    env = {key: value for key, value in os.environ.items() if key not in git_env_vars}
    for record in _git_bytes("worktree", "list", "--porcelain", "-z").split(b"\0\0"):
        name, _, attributes = record.partition(b"\0")
        if not name.startswith(b"worktree ") or b"bare" in attributes.split(b"\0"):
            continue
        root = os.fsdecode(name.removeprefix(b"worktree "))
        if root == info["repo_root"]:
            continue
        try:
            path = _git_bytes("-C", root, "rev-parse", "--path-format=absolute", "--git-common-dir", env=env)
        except subprocess.CalledProcessError:
            continue
        if Path(os.fsdecode(path.rstrip(b"\r\n"))).resolve() == common_dir:
            scopes.append({"repo_root": root, "repo_id": repo_identity(root)})
    return scopes


def reusable_merge(info: dict[str, Any], lanes: list[str], ttl_seconds: int) -> str | None:
    """Return the reviewed incoming parent of a merge with an exact staged result."""
    head = info["base_commit"]
    if not head:
        return None
    try:
        incoming_raw = _git_path("--git-path", "MERGE_HEAD").read_bytes().strip()
        if len(incoming_raw) != len(head) or not re.fullmatch(rb"[a-f0-9]+", incoming_raw):
            return None
        incoming = incoming_raw.decode("ascii")
        if any(status == "loaded" and state.get("branch") == info["branch"] and state.get("decision") == "BLOCK"
               for _, state, status in load_candidate_states(info)):
            return None
        if (_git_bytes("rev-parse", "--is-shallow-repository").strip() != b"false"
                or os.environ.get("GIT_GRAFT_FILE")
                or _git_path("--git-path", "info/grafts").exists()):
            return None
        bases = _git_bytes("merge-base", "--all", head, incoming).decode("ascii").split()
        if len(bases) != 1:
            return None
        base = bases[0]
        branch_paths = _changed_paths(base, incoming)
        if not branch_paths.isdisjoint(_changed_paths(base, head)):
            return None

        staged_tree = info["tree"]
        if not _changed_paths(head, staged_tree).issubset(branch_paths):
            return None
        if not branch_paths.isdisjoint(_changed_paths(incoming, staged_tree)):
            return None

        # Include every incoming commit, including the side of any nested merge.
        # A receipt for a merge commit records its first parent as its base.
        history = _git_bytes("log", "--no-show-signature", "--no-decorate", "--format=%T %P",
                             f"{head}..{incoming}", "--").decode("ascii").splitlines()
        if not history:
            return None
        common_dir = _git_path("--git-common-dir").resolve()
        repository_id = git_repository_id(common_dir)
        scopes = _receipt_scopes(info, common_dir)
        for entry in history:
            tree, parent, *_ = entry.split()
            if not any(
                _approved_in_scope({**scope, "tree": tree, "base_commit": parent},
                                   lanes, ttl_seconds, repository_id)
                for scope in scopes
            ):
                return None
        return incoming
    except (OSError, ValueError, subprocess.CalledProcessError):
        return None


def _approved_in_scope(
    info: dict[str, Any], lanes: list[str], ttl_seconds: int,
    repository_id: str,
) -> bool:
    return any(
        status == "loaded"
        and state.get("git_repository_id") == repository_id
        and state_is_valid(state, info, lanes, ttl_seconds, match_branch=False)[0]
        for _, state, status in load_candidate_states(info)
    )
