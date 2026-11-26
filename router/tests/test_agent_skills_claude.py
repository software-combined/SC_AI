"""Claude plugin updates bind to the Router marketplace and user scope."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tests.test_agent_skills_delivery import _Client, _found, skills


class ClaudePluginRefreshTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.entry = {'id': 'scg-review@scg-agent-plugins', 'enabled': True, 'scope': 'project'}

    def test_a_project_only_install_does_not_trigger_an_update(self):
        run = _Client(installed=[self.entry])
        skills.register('claude', self.root, ['scg-review'], run=run, which=_found)
        self.assertIn(['claude', 'plugin', 'install', self.entry['id']], run.calls)
        self.assertFalse(any(c[2] == 'update' for c in run.calls))

    def test_a_refused_marketplace_stops_delivery(self):
        self.entry['scope'] = 'user'
        client = _Client(installed=[self.entry])

        def refuse_marketplace(command, **kwargs):
            if command[2:4] == ['marketplace', 'add']:
                client.calls.append(command)
                return SimpleNamespace(returncode=1, stdout='', stderr='source mismatch')
            return client(command, **kwargs)

        line, refusals = skills.register('claude', self.root, ['scg-review'],
                                        run=refuse_marketplace, which=_found)
        self.assertEqual(refusals, 1)
        self.assertIn('source mismatch', line)
        self.assertEqual([c[2] for c in client.calls], ['list', 'marketplace'])
