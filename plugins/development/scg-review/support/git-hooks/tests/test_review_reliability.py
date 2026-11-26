"""Real Git regressions for receipt scope and chained commit/merge hooks."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest import mock

from test_interpreter_selection import setup
import test_review_gate as gate_fixture


HOOKS = Path(__file__).resolve().parents[1]


class ReviewReliabilityTest(unittest.TestCase):
    def setUp(self):
        self.fixture = gate_fixture.ReviewGateTest(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def run_git(self, *args):
        return subprocess.run(["git", *args], cwd=self.fixture.repo,
                              env=self.fixture.env, capture_output=True, text=True)

    def install_hooks(self):
        target = self.fixture.home / ".config/scg-agent-git-hooks"
        for relative in setup.FILES:
            source = HOOKS / relative
            if source.is_file():
                dest = target / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, dest)
                dest.chmod(0o755)
        config = target / "config.json"
        data = json.loads(config.read_text())
        data["interpreter"] = sys.executable
        config.write_text(json.dumps(data))
        self.fixture.git("config", "core.hooksPath", str(target))

    def local_hook(self, name, body):
        hook = self.fixture.repo / ".git/hooks" / name
        hook.write_text(f"#!{Path(sys.executable).as_posix()}\n" + body)
        hook.chmod(0o755)

    def merge_branches(self):
        self.fixture.git("commit", "-m", "test: initial fixture")
        self.fixture.git("checkout", "-b", "other")
        (self.fixture.repo / "other.txt").write_text("other\n")
        self.fixture.git("add", "other.txt")
        self.fixture.git("commit", "-m", "test: other fixture")
        self.fixture.git("checkout", "main")
        (self.fixture.repo / "main.txt").write_text("main\n")
        self.fixture.git("add", "main.txt")
        self.fixture.git("commit", "-m", "test: main fixture")

    def reviewed_commit(self, name, text, runner):
        (self.fixture.repo / name).write_text(text)
        self.fixture.git("add", "--", name)
        tree = self.fixture.tree()
        base = self.fixture.git("rev-parse", "HEAD").stdout.strip()
        approved = self.fixture.helper("approve", "--runner", runner, *gate_fixture.LANE_ARGS)
        self.assertEqual(approved.returncode, 0, approved.stderr)
        self.fixture.git("commit", "-m", "test: reviewed fixture")
        return self.fixture.state_dir() / f"{tree}.{base}.review.json"

    def prepare_reviewed_merge(self, *, linked=False, overlap=False):
        git = self.fixture.git
        self.fixture.git("commit", "-m", "test: initial fixture")
        self.install_hooks()
        base_text = "start\nkeep 1\nkeep 2\nkeep 3\nkeep 4\nkeep 5\nend\n"
        self.reviewed_commit("shared.txt", base_text, "codex")
        topic = self.fixture.repo
        if linked:
            topic = topic.parent / "linked topic"
            git("worktree", "add", "-b", "other", str(topic))
        else:
            git("switch", "-c", "other")
        with mock.patch.object(self.fixture, "repo", topic):
            first = self.reviewed_commit("shared.txt", base_text.replace("start", "topic"), "codex")
            self.reviewed_commit("other.txt", "topic content\n", "claude-code")
        if not linked:
            git("switch", "main")
        self.reviewed_commit("main.txt", "target content\n", "claude-code")
        if overlap:
            self.reviewed_commit("shared.txt", base_text.replace("end", "target"), "claude-code")
        git("merge", "--no-ff", "--no-commit", "other")
        return first

    def test_unborn_receipt_records_explicit_base(self):
        self.assertEqual(self.fixture.approve().returncode, 0)
        receipt, = self.fixture.state_dir().glob("*.review.json")
        data = json.loads(receipt.read_text())
        self.assertEqual(data["version"], 3)
        self.assertIn("base_commit", data)
        self.assertIsNone(data["base_commit"])
        self.assertEqual(self.fixture.helper("pre-commit").returncode, 0)

    def test_changed_head_rejects_same_tree_receipt_and_preserves_history(self):
        self.assertEqual(self.fixture.approve().returncode, 0)
        before = {p: p.read_bytes() for p in self.fixture.state_dir().glob("*.review.json")}
        tree = self.fixture.tree()
        self.fixture.git("commit", "-m", "test: advance fixture head")
        self.assertEqual(self.fixture.tree(), tree)
        self.assertNotEqual(self.fixture.helper("pre-commit").returncode, 0)
        self.assertEqual(self.fixture.approve().returncode, 0)
        self.assertEqual(len(list(self.fixture.state_dir().glob("*.review.json"))), 2)
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)

    def test_legacy_receipt_is_preserved_but_cannot_approve(self):
        self.assertEqual(self.fixture.approve().returncode, 0)
        receipt, = self.fixture.state_dir().glob("*.review.json")
        data = json.loads(receipt.read_text())
        data["version"] = 2
        receipt.write_text(json.dumps(data))
        self.assertNotEqual(self.fixture.helper("pre-commit").returncode, 0)
        self.assertEqual(json.loads(receipt.read_text())["version"], 2)

    def test_chained_hook_cannot_stage_an_unreviewed_tree(self):
        self.local_hook("pre-commit", "import pathlib, subprocess\n"
                        "pathlib.Path('file.txt').write_text('changed by hook\\n')\n"
                        "subprocess.run(['git', 'add', 'file.txt'], check=True)\n")
        self.assertEqual(self.fixture.approve().returncode, 0)
        tree = self.fixture.tree()
        done = self.fixture.helper("pre-commit")
        self.assertNotEqual(self.fixture.tree(), tree)
        self.assertNotEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("scope changed", done.stderr)

    def test_chained_hook_rejection_is_preserved(self):
        self.local_hook("pre-commit", "import sys\nsys.exit(7)\n")
        self.assertEqual(self.fixture.approve().returncode, 0)
        self.assertEqual(self.fixture.helper("pre-commit").returncode, 7)

    def test_automatic_merge_requires_a_receipt(self):
        self.merge_branches()
        self.install_hooks()
        head = self.fixture.git("rev-parse", "HEAD").stdout.strip()
        done = self.run_git("merge", "--no-edit", "other")
        self.assertNotEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.fixture.git("rev-parse", "HEAD").stdout.strip(), head)
        self.assertIn("review", done.stderr.lower())

    def test_reviewed_automatic_merge_chains_original_merge_hook(self):
        self.merge_branches()
        self.fixture.git("merge", "--no-commit", "other")
        self.assertEqual(self.fixture.approve().returncode, 0)
        self.fixture.git("merge", "--abort")
        self.local_hook("pre-merge-commit", "import pathlib\n"
                        "pathlib.Path('merge-hook-ran').write_text('yes')\n")
        self.install_hooks()
        done = self.run_git("merge", "--no-edit", "other")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertTrue((self.fixture.repo / "merge-hook-ran").exists())

    def test_commit_message_hook_cannot_stage_after_review(self):
        self.local_hook("commit-msg", "import pathlib, subprocess\n"
                        "pathlib.Path('file.txt').write_text('late change\\n')\n"
                        "subprocess.run(['git', 'add', 'file.txt'], check=True)\n")
        self.assertEqual(self.fixture.approve().returncode, 0)
        self.install_hooks()
        done = self.run_git("commit", "-m", "test: reviewed fixture")
        self.assertNotEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("scope changed", done.stderr)

    def test_prepared_merge_reuses_both_clients_receipts_from_linked_worktree(self):
        self.prepare_reviewed_merge(linked=True)
        git = self.fixture.git
        before = git("rev-parse", "HEAD", "other").stdout.split()
        tree = self.fixture.tree()
        status = self.fixture.helper("status")
        self.assertIn("Review state: merge carry-over", status.stdout)
        first = self.run_git("commit", "-m", "Merge other")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(git("log", "-1", "--format=%P").stdout.split(), before)
        self.assertEqual(git("rev-parse", "HEAD^{tree}").stdout.strip(), tree)
        merge_receipt = self.fixture.state_dir() / f"{tree}.{before[0]}.review.json"
        self.assertFalse(merge_receipt.exists())

    def test_each_incoming_commit_needs_a_valid_receipt(self):
        receipt = self.prepare_reviewed_merge()
        before = self.fixture.git("rev-parse", "HEAD").stdout
        data = json.loads(receipt.read_text())
        cases = {
            "missing": None,
            "wrong base": {**data, "base_commit": "wrong"},
            "expired": {**data, "created_at_epoch": 1},
            "blocked": {**data, "decision": "BLOCK", "approved": False},
            "wrong repository": {**data, "repo_id": "different"},
            "missing repository identity": {key: value for key, value in data.items() if key != "git_repository_id"},
            "malformed": [],
            "missing security": {**data, "passes": {"correctness": "c", "quality": "q", "adversarial": "a"}},
        }
        for name, invalid in cases.items():
            with self.subTest(name=name):
                if invalid is None:
                    receipt.unlink()
                else:
                    receipt.write_text(json.dumps(invalid))
                done = self.run_git("commit", "-m", "Merge other")
                self.assertNotEqual(done.returncode, 0, done.stdout + done.stderr)
                self.assertIn("blocked this commit", done.stderr)
                self.assertEqual(self.fixture.git("rev-parse", "HEAD").stdout, before)
        receipt.write_text(json.dumps(data))
        self.fixture.git("commit", "-m", "Merge other")

    def test_clean_merge_with_overlapping_paths_requires_full_review(self):
        self.prepare_reviewed_merge(overlap=True)
        done = self.run_git("commit", "-m", "Merge other")
        self.assertIn("blocked this commit", done.stderr)
        self.assertNotEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.fixture.approve().returncode, 0)
        self.fixture.git("commit", "-m", "Merge other")

    def test_explicit_block_for_the_staged_merge_prevents_receipt_reuse(self):
        self.prepare_reviewed_merge()
        blocked = self.fixture.helper("approve", "--decision", "BLOCK", *gate_fixture.LANE_ARGS)
        self.assertEqual(blocked.returncode, 0, blocked.stderr)
        self.assertNotIn("Review state: merge carry-over", self.fixture.helper("status").stdout)
        done = self.run_git("commit", "-m", "Merge other")
        self.assertNotEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("decision 'BLOCK' is not approved", done.stderr)

    def test_prepared_merge_requires_exact_incoming_paths_and_staged_contents(self):
        self.prepare_reviewed_merge()
        tree = self.fixture.tree()
        for name in ("other.txt", "main.txt", "extra.txt"):
            with self.subTest(name=name):
                (self.fixture.repo / name).write_text("unreviewed content\n")
                self.fixture.git("add", "--", name)
                done = self.run_git("commit", "-m", "Merge other")
                self.assertNotEqual(done.returncode, 0, done.stdout + done.stderr)
                self.assertIn("blocked this commit", done.stderr)
                self.fixture.git("read-tree", tree)

    def test_chained_commit_message_hook_cannot_change_reviewed_merge(self):
        self.prepare_reviewed_merge()
        self.local_hook("commit-msg", "import pathlib, subprocess\n"
                        "pathlib.Path('other.txt').write_text('late change\\n')\n"
                        "subprocess.run(['git', 'add', 'other.txt'], check=True)\n")
        done = self.run_git("commit", "-m", "Merge other")
        self.assertNotEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("merge tree, parents or review receipts changed", done.stderr)

    def test_squash_commit_requires_its_own_review(self):
        self.prepare_reviewed_merge()
        self.fixture.git("merge", "--abort")
        self.fixture.git("merge", "--squash", "other")
        done = self.run_git("commit", "-m", "feat: squash other")
        self.assertNotEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("blocked this commit", done.stderr)

    @unittest.skipIf(os.name == "nt", "uses a POSIX scanner fixture")
    def test_corrupt_copy_cannot_activate_fresh_hooks(self):
        self.fixture.pin_scanner(self.fixture.write_fake_scanner())
        config = json.loads((self.fixture.home / ".config/scg-agent-git-hooks/config.json").read_text())
        config["gitleaks"]["provenance"] = "synthetic test fixture"
        home = self.fixture.home / "fresh-install"
        copy = shutil.copy2

        def corrupt(source, dest):
            copy(source, dest)
            if source.name == "pre-commit":
                dest.write_text("corrupt copy\n")

        with mock.patch.dict(os.environ, self.fixture.env), \
                mock.patch.object(setup.shutil, "copy2", side_effect=corrupt):
            with self.assertRaisesRegex(ValueError, "adapter differs"):
                setup.provision(self.fixture.repo, config, install=True, home=home)
        self.assertFalse((home / ".config/scg-agent-git-hooks").exists())
        self.assertEqual(self.run_git("config", "--local", "--get", "core.hooksPath").returncode, 1)


if __name__ == "__main__":
    unittest.main()
