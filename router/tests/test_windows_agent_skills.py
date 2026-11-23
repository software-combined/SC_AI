"""App-installed Codex stays discoverable from a scheduled Windows updater."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.loading import load

ROOT = Path(__file__).resolve().parents[1]
skills = load(ROOT / 'packaging' / 'agent_skills.py', 'router_windows_agent_skills')


class WindowsClientPathTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.local = self.tmp / 'Local'
        self.base = self.local / 'OpenAI' / 'Codex' / 'bin'
        self.path = str(self.tmp / 'System32')
        self.env = {'PATH': self.path, 'LOCALAPPDATA': str(self.local)}
        self.home = self.tmp / 'home'
        self.home.mkdir()
        home = patch.object(Path, 'home', return_value=self.home)
        home.start()
        self.addCleanup(home.stop)

    def test_search_prefers_the_newest_codex_build(self):
        old, new = self.base / 'aaa', self.base / 'zzz'
        for index, build in enumerate((old, new)):
            build.mkdir(parents=True)
            os.utime(build, (1_000 + index, 1_000 + index))
        found = skills.client_path(self.env, os_name='nt')
        self.assertEqual(found.split(os.pathsep),
                         [self.path, str(self.home / '.local' / 'bin'), str(new), str(old)])

    def test_search_without_a_codex_tree_adds_nothing(self):
        found = skills.client_path(self.env, os_name='nt')
        self.assertEqual(found, os.pathsep.join(
            [self.path, str(self.home / '.local' / 'bin')]))

    @unittest.skipUnless(os.name == 'nt', 'native Windows executable resolution')
    def test_scheduled_path_resolves_the_app_cli(self):
        executable = self.base / 'build' / 'codex.exe'
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b'')
        self.assertIsNone(shutil.which('codex', path=self.path))
        found = shutil.which('codex', path=skills.client_path(self.env))
        self.assertIsNotNone(found)
        self.assertEqual(Path(found), executable)


if __name__ == '__main__':
    unittest.main()
