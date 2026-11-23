"""Installs, updates and removal leave global instructions alone."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests._platform import unix_only
from ai_router.catalogue import merge
from tests.test_install_config import _install
from tools import global_instructions


@unix_only
class GlobalInstructionsTests(unittest.TestCase):
    def test_legacy_shim_is_a_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            path = home / 'AGENTS.md'
            path.write_text('mine\n')
            got_path, before, after, receipt = global_instructions.prepare(home, {'path': 'x', 'block': 'y'})
            self.assertEqual(before, 'mine\n')
            self.assertEqual(after, 'mine\n')
            global_instructions.write(got_path, before, after + 'changed')
            self.assertEqual(path.read_text(), 'mine\n')
            global_instructions.restore(receipt)
            self.assertEqual(path.read_text(), 'mine\n')

    def test_installer_never_writes_global_instructions(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / 'router'
            config, _, _, _ = _install(self, tmp, home, '1.0.0')
            self.assertFalse((config.parent / 'AGENTS.md').exists())
            (config.parent / 'AGENTS.md').write_text('owner\n')
            _install(self, tmp, home, '1.0.1')
            self.assertEqual((config.parent / 'AGENTS.md').read_text(), 'owner\n')
            receipt = json.loads((home / 'activation.json').read_text())
            self.assertNotIn('global_instructions', receipt['clients']['codex'])
            for model in merge({'models': []})['models']:
                self.assertNotIn('## Subagents and tool discovery',
                                 model['model_messages']['instructions_template'])

    def test_disable_leaves_global_instructions_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / 'router'
            config, _, _, _ = _install(self, tmp, home, '1.0.0')
            config.write_text(config.read_text() + '\n# user setting\n')
            rules = config.parent / 'AGENTS.md'
            rules.write_text('User instructions.\n')
            disable = Path(__file__).resolve().parents[1] / 'tools' / 'disable.py'
            # Run it the way the installer does: subprocess with
            # ROUTER_RESTORE_ONLY=1. Never in-process (2026-09-13 incident).
            result = subprocess.run(
                [sys.executable, str(disable)], capture_output=True, text=True,
                env=dict(os.environ, ROUTER_HOME=str(home),
                         ROUTER_RESTORE_ONLY='1'))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(config.read_text(), '\n\n# user setting\n')
            self.assertEqual(rules.read_text(), 'User instructions.\n')
