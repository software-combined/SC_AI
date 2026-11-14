"""Exact owner approvals cannot suppress changed, new or foreign findings."""
from __future__ import annotations

import hashlib
import json
import os
import runpy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_gitleaks_pin_portability import load_helper_module


@unittest.skipUnless(os.name == "posix", "owner-only policy storage qualified on POSIX")
class ScanAdjudicationsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self.git("init", "-b", "main")
        self.git("remote", "add", "origin", "https://example.invalid/team/project.git")
        (self.repo / "fixture.txt").write_text("example object reference\n")
        self.git("add", "fixture.txt")
        self.tree = self.git("write-tree")
        self.owner = self.base / "owner"
        self.owner.mkdir(mode=0o700)
        self.policy = self.owner / "scan-adjudications.json"
        self.report = self.base / "report.json"
        self.entry = {
            "file": "fixture.txt", "rule": "generic-api-key", "line": 1,
            "stagedFileSha256": hashlib.sha256((self.repo / "fixture.txt").read_bytes()).hexdigest(),
            "reason": "Synthetic object reference, not authentication material",
        }
        self.scope = {
            "gitCommonDir": str((self.repo / ".git").resolve()),
            "origin": "https://example.invalid/team/project.git",
            "approvedBy": "Repository owner", "approvedAt": "2026-01-01",
            "reason": "Exact non-secret fixture findings only", "findings": [self.entry],
        }
        self.data = {"schemaVersion": 1, "repositories": [self.scope]}
        self.finding = {
            "File": "fixture.txt", "RuleID": "generic-api-key", "StartLine": 1,
            "Fingerprint": "fixture.txt:generic-api-key:1",
        }
        self.write_policy()
        self.write_report([self.finding])
        helper = Path(load_helper_module().__file__)
        self.adjudicate = runpy.run_path(str(helper.with_name("scg_scan_adjudications.py")))["adjudicate"]

    def git(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        return subprocess.check_output(["git", *args], cwd=self.repo, env=env, text=True).strip()

    def write_policy(self):
        self.policy.write_text(json.dumps(self.data))
        self.policy.chmod(0o600)

    def write_report(self, value):
        self.report.write_text(json.dumps(value))

    def run_adjudication(self):
        return self.adjudicate(self.report, self.policy, self.repo, self.tree)

    def test_exact_approval_reads_staged_blob_not_dirty_working_copy(self):
        (self.repo / "fixture.txt").write_text("unrelated unstaged edit\n")
        self.assertEqual(self.run_adjudication(), 1)

    def test_changed_staged_source_fails(self):
        (self.repo / "fixture.txt").write_text("changed fixture\n")
        self.git("add", "fixture.txt")
        with self.assertRaisesRegex(ValueError, "hash changed"):
            self.run_adjudication()

    def test_changed_path_rule_line_and_new_finding_fail(self):
        for patch in [{"File": "another.txt"}, {"RuleID": "new-rule"}, {"StartLine": 2}]:
            with self.subTest(patch=patch):
                finding = {**self.finding, **patch}
                finding["Fingerprint"] = f"{finding['File']}:{finding['RuleID']}:{finding['StartLine']}"
                self.write_report([finding])
                with self.assertRaisesRegex(ValueError, "unapproved"):
                    self.run_adjudication()
        other = {**self.finding, "StartLine": 2, "Fingerprint": "fixture.txt:generic-api-key:2"}
        self.write_report([self.finding, other])
        with self.assertRaisesRegex(ValueError, "unapproved"):
            self.run_adjudication()

    def test_origin_and_git_common_directory_each_bind_repository(self):
        self.git("remote", "set-url", "origin", "https://example.invalid/other/project.git")
        with self.assertRaisesRegex(ValueError, "scope"):
            self.run_adjudication()
        self.git("remote", "set-url", "origin", self.scope["origin"])
        self.scope["gitCommonDir"] = str(self.base / "another.git")
        self.write_policy()
        with self.assertRaisesRegex(ValueError, "scope"):
            self.run_adjudication()

    def test_owner_storage_rejects_public_file_symlink_and_repository_policy(self):
        self.policy.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "owner-only"):
            self.run_adjudication()
        self.policy.chmod(0o600)
        linked = self.owner / "linked.json"
        linked.symlink_to(self.policy)
        with self.assertRaisesRegex(ValueError, "owner-managed"):
            self.adjudicate(self.report, linked, self.repo, self.tree)
        inside = self.repo / "policy.json"
        inside.write_text(self.policy.read_text())
        inside.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "outside"):
            self.adjudicate(self.report, inside, self.repo, self.tree)

    def test_staged_symlink_cannot_reuse_approved_blob(self):
        (self.repo / "fixture.txt").unlink()
        (self.repo / "fixture.txt").symlink_to("target")
        self.git("add", "fixture.txt")
        with self.assertRaisesRegex(ValueError, "regular staged blob"):
            self.run_adjudication()

    def test_report_missing_empty_malformed_or_duplicate_fails(self):
        for report in [[], {}, [self.finding, self.finding], [None]]:
            with self.subTest(report=report):
                self.write_report(report)
                with self.assertRaises(ValueError):
                    self.run_adjudication()
        self.report.write_text("{")
        with self.assertRaises(ValueError):
            self.run_adjudication()
        self.report.unlink()
        with self.assertRaises(OSError):
            self.run_adjudication()

    def test_missing_malformed_and_duplicate_owner_authorization_fails(self):
        self.scope["approvedBy"] = ""
        self.write_policy()
        with self.assertRaisesRegex(ValueError, "authorization"):
            self.run_adjudication()
        self.scope["approvedBy"] = "Owner"
        self.scope["findings"].append(self.entry)
        self.write_policy()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.run_adjudication()
        self.policy.write_text("{")
        with self.assertRaises(ValueError):
            self.run_adjudication()
        self.policy.unlink()
        with self.assertRaises(OSError):
            self.run_adjudication()

    def test_changed_tree_and_forged_fingerprint_fail(self):
        (self.repo / "unrelated.txt").write_text("new staged source\n")
        self.git("add", "unrelated.txt")
        with self.assertRaisesRegex(ValueError, "tree changed"):
            self.run_adjudication()
        self.finding["Fingerprint"] = "different"
        self.write_report([self.finding])
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            self.run_adjudication()

    def scan_cli(self, exit_code=1, scanner_pin=None):
        home = self.base / "home"
        config_dir = home / ".config/scg-agent-git-hooks"
        config_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
        policy = config_dir / "scan-adjudications.json"
        policy.write_text(self.policy.read_text())
        policy.chmod(0o600)
        scanner = self.base / "scanner"
        scanner.write_text(
            f"#!{sys.executable}\nimport json, pathlib, sys\n"
            "if sys.argv[1] == 'version':\n print('9.9.9'); sys.exit(0)\n"
            f"pathlib.Path(sys.argv[sys.argv.index('--report-path')+1]).write_text({json.dumps([self.finding])!r})\n"
            f"sys.exit({exit_code})\n"
        )
        scanner.chmod(0o755)
        pin = scanner_pin or {
            "binary": str(scanner), "version": "9.9.9",
            "sha256": hashlib.sha256(scanner.read_bytes()).hexdigest(),
        }
        (config_dir / "config.json").write_text(json.dumps({"gitleaks": pin}))
        helper = Path(load_helper_module().__file__)
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("GIT_", "GITLEAKS_"))}
        env.update(HOME=str(home), USERPROFILE=str(home))
        return subprocess.run([sys.executable, str(helper), "scan"], cwd=self.repo,
                              env=env, capture_output=True, text=True)

    def test_full_pinned_scan_visibly_reports_exact_adjudication(self):
        result = self.scan_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("1 exact owner-adjudicated non-secret findings", result.stdout)
        self.assertNotIn("no leaks found", result.stdout)

    def test_scanner_execution_failure_cannot_use_matching_report(self):
        result = self.scan_cli(exit_code=2)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("scan passed", result.stdout)

    def test_boolean_schema_and_malformed_extra_repository_fail(self):
        self.data["schemaVersion"] = True
        self.write_policy()
        with self.assertRaisesRegex(ValueError, "schema"):
            self.run_adjudication()
        self.data["schemaVersion"] = 1
        self.data["repositories"].append(None)
        self.write_policy()
        with self.assertRaisesRegex(ValueError, "repository authorization"):
            self.run_adjudication()

    @unittest.skipUnless(os.environ.get("SCG_RUN_PINNED_SCANNER_TESTS") == "1",
                         "explicit local pinned-scanner qualification")
    def test_real_pinned_scanner_report_is_accepted_and_changed_source_is_rejected(self):
        helper = load_helper_module()
        pin = helper.load_config()["gitleaks"]
        # Construct only a synthetic value in a disposable repository. No
        # credential-shaped literal enters this test source or its output.
        synthetic = hashlib.sha256(b"non-secret scanner contract fixture").hexdigest()
        (self.repo / "fixture.txt").write_text(f'api_key = "{synthetic}"\n')
        self.git("add", "fixture.txt")
        self.tree = self.git("write-tree")
        self.entry["stagedFileSha256"] = hashlib.sha256((self.repo / "fixture.txt").read_bytes()).hexdigest()
        self.write_policy()
        accepted = self.scan_cli(scanner_pin=pin)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertIn("1 exact owner-adjudicated non-secret findings", accepted.stdout)
        self.assertNotIn(synthetic, accepted.stdout + accepted.stderr)
        with (self.repo / "fixture.txt").open("a") as stream:
            stream.write("# changed source requires a new owner decision\n")
        self.git("add", "fixture.txt")
        rejected = self.scan_cli(scanner_pin=pin)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("staged file hash changed", rejected.stderr)
        for expected in ("fixture.txt", "generic-api-key", "Line:"):
            self.assertIn(expected, rejected.stderr)
        self.assertNotIn(synthetic, rejected.stdout + rejected.stderr)


if __name__ == "__main__":
    unittest.main()
