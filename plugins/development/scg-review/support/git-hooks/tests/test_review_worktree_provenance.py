"""A reusable approval must belong to the repository receiving the merge."""
from __future__ import annotations

import json
import unittest
from unittest import mock

import test_review_reliability as reliability


class ReviewWorktreeProvenanceTest(unittest.TestCase):
    def setUp(self):
        self.hooks = reliability.ReviewReliabilityTest(methodName="runTest")
        self.hooks.setUp()
        self.addCleanup(self.hooks.doCleanups)

    def test_path_only_receipt_still_approves_its_exact_staged_commit(self):
        fixture = self.hooks.fixture
        self.hooks.install_hooks()
        approved = fixture.approve()
        self.assertEqual(approved.returncode, 0, approved.stderr)
        receipt, = fixture.state_dir().glob("*.review.json")
        state = json.loads(receipt.read_text())
        del state["git_repository_id"]
        receipt.write_text(json.dumps(state))
        fixture.git("commit", "-m", "test: legacy direct review")

    def test_reusing_checkout_path_does_not_reuse_foreign_repository_receipts(self):
        fixture = self.hooks.fixture
        git = fixture.git
        git("commit", "-m", "test: initial fixture")
        self.hooks.install_hooks()
        fork = fixture.repo.parent / "other checkout"
        git("clone", str(fixture.repo), str(fork))
        with mock.patch.object(fixture, "repo", fork):
            git("config", "user.name", "Test User")
            git("config", "user.email", "test@example.invalid")
            self.hooks.install_hooks()
            receipt = self.hooks.reviewed_commit("other.txt", "reviewed elsewhere\n", "codex")
        git("fetch", str(fork), "main:refs/heads/other")
        fork.rename(fork.with_name("original checkout"))
        git("worktree", "add", "-b", "linked", str(fork))
        git("merge", "--no-ff", "--no-commit", "other")

        state = json.loads(receipt.read_text())
        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                if legacy:
                    del state["git_repository_id"]
                    receipt.write_text(json.dumps(state))
                done = self.hooks.run_git("commit", "-m", "Merge other")
                self.assertNotEqual(done.returncode, 0, done.stdout + done.stderr)
                self.assertIn("blocked this commit", done.stderr)
