"""Store-only Codex must reach setup and tools without an extra CLI install."""
import tempfile
import contextlib
import io
import json
import os
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tests.test_native_setup import module


class StoreOnboardingTests(unittest.TestCase):
    def setUp(self):
        import client_executable
        self.resolver = client_executable
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name).resolve()
        self.root = self.home / 'StoreCodex'
        self.app = self.root / 'app/ChatGPT.exe'
        self.cli = self.app.parent / 'resources/codex.exe'
        self.cli.parent.mkdir(parents=True)
        self.app.write_bytes(b'MZ desktop fixture')
        self.cli.write_bytes(b'MZ CLI fixture')
        (self.root / 'AppxManifest.xml').write_text(
            '<Package><Applications><Application Id="App" '
            'Executable="app/ChatGPT.exe"/></Applications></Package>')
        self.api = mock.Mock()
        self.api.packages.return_value = ['Codex_fixture']
        self.api.package_path.return_value = str(self.root)
        self.api.user.return_value, self.api.session.return_value = 'fixture-user', 1
        for patcher in (mock.patch('sys.platform', 'win32'),
                        mock.patch.object(self.resolver.windows_codex, 'bindings', return_value=self.api),
                        mock.patch('shutil.which', return_value=None),
                        mock.patch.object(Path, 'home', return_value=self.home),
                        mock.patch.dict(os.environ, {'PATH': '', 'CODEX_BIN': '/untrusted/override',
                                                    'OPENAI_API_KEY': 'synthetic'}, clear=True)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.commands = []

    def runner(self, command, **kwargs):
        self.commands.append(command)
        self.assertEqual(command[0], str(self.cli))
        if command[1:] == ['--version']:
            self.assertFalse(any(key.startswith(('OPENAI_', 'CODEX_')) for key in kwargs['env']))
            return SimpleNamespace(returncode=0, stdout='codex-cli 0.164.0\n')
        entries = [dict(pluginId=name + '@scg-agent-plugins', enabled=name != 'scg-review')
                   for name in ('scg-documentation', 'scg-review', 'scg-router-management')]
        return SimpleNamespace(returncode=0, stdout=json.dumps(
            dict(installed=entries, marketplaces=[])), stderr='')

    def test_all_four_consumers_use_store_cli_and_preserve_disabled_plugins(self):
        setup, skills = module('native_setup'), module('agent_skills')
        readiness, diagnostics = module('native_readiness'), module('diagnostics')
        dialog = mock.Mock()
        with mock.patch.object(setup.webbrowser, 'open') as browser:
            self.assertFalse(setup._missing_assistant(['--clients', 'codex'], dialog, self.runner))
        browser.assert_not_called()
        result, refused = skills.register('codex', self.home / 'marketplace',
            ['scg-documentation', 'scg-review', 'scg-router-management'],
            run=self.runner, which=lambda *args, **kwargs: None)
        self.assertEqual(refused, 0, result)
        self.assertIn('1 left disabled', result)
        adds = [command for command in self.commands if command[1:3] == ['plugin', 'add']]
        self.assertEqual({command[3] for command in adds},
                         {'scg-documentation@scg-agent-plugins', 'scg-router-management@scg-agent-plugins'})
        self.assertTrue(readiness.plugins_available('codex',
            ['scg-documentation', 'scg-review', 'scg-router-management'],
            run=self.runner, which=lambda *args, **kwargs: None))
        with mock.patch.object(diagnostics, 'find_python', return_value='/runtime/python'), \
                mock.patch('subprocess.run', side_effect=self.runner), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(diagnostics.do_preflight(SimpleNamespace(
                python=None, clients='codex', client=None)), 0)
        self.assertFalse((self.home / '.codex').exists())
        self.assertEqual(os.environ['CODEX_BIN'], '/untrusted/override')
        self.api.activate.assert_not_called()
        self.api.end.assert_not_called()
        self.assertTrue(all(call.args == (self.resolver.windows_codex.FAMILY,)
                            for call in self.api.packages.call_args_list))

    def test_supported_store_layouts_use_the_existing_executable_validator(self):
        self.cli.unlink()
        for relative in self.resolver.codex_config_proof.WINDOWS_BUNDLED:
            with self.subTest(relative=relative):
                self.cli = self.app.parent / relative
                self.cli.parent.mkdir(parents=True, exist_ok=True)
                self.cli.write_bytes(b'MZ fixture')
                self.assertEqual(self.resolver.resolve('codex', run=self.runner), str(self.cli))
                self.cli.unlink()

    def test_invalid_header_version_failure_timeout_and_escape_never_run_plugins(self):
        for outcome in ('header', 'wrong_version', 'refused', 'timeout'):
            with self.subTest(outcome=outcome):
                self.cli.unlink(missing_ok=True)
                self.cli.write_bytes(b'not PE' if outcome == 'header' else b'MZ fixture')
                def run(command, **kwargs):
                    self.assertEqual(command[1:], ['--version'])
                    if outcome == 'timeout':
                        raise subprocess.TimeoutExpired(command, 5)
                    return SimpleNamespace(returncode=1 if outcome == 'refused' else 0,
                                           stdout='different tool')
                with self.assertRaisesRegex(self.resolver.DiscoveryError, 'bundled_cli_invalid'):
                    self.resolver.resolve('codex', run=run)

    def test_package_escaping_cli_is_rejected_without_execution(self):
        outside = self.home / 'outside.exe'
        outside.write_bytes(b'MZ fixture')
        self.cli.unlink()
        try:
            self.cli.symlink_to(outside)
        except OSError:
            self.skipTest('symlinks unavailable')
        with self.assertRaisesRegex(self.resolver.DiscoveryError, 'bundled_cli_invalid'):
            self.resolver.resolve('codex', run=self.runner)
        self.assertEqual(self.commands, [])

    def test_scheduled_sync_delivers_management_and_preserves_saved_choices(self):
        skills = module('agent_skills')
        plugins = self.home / 'bundle/plugins'
        for name in ('scg-documentation', 'scg-review', 'scg-router-management'):
            manifest = plugins / name / '.codex-plugin/plugin.json'
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps(dict(name=name, version='1.0.0')))
        state = dict(clients='codex', openai_mode='subscription', claude_mode='subscription',
                     custom=dict(preserve=True))
        before = json.dumps(state)
        settings = self.home / 'settings'
        settings.write_bytes(b'owner settings and synthetic key fixture')
        summary = skills.sync(state, plugins, base=self.home / 'shared', run=self.runner,
                              which=lambda *a, **kw: None)
        self.assertIn('1 left disabled', summary)
        self.assertTrue((self.home / 'shared/marketplace/plugins/scg-router-management/'
                         '.codex-plugin/plugin.json').is_file())
        self.assertEqual(json.dumps(state), before)
        self.assertEqual(settings.read_bytes(), b'owner settings and synthetic key fixture')
        self.assertFalse(any(command[1:3] == ['plugin', 'enable'] for command in self.commands))

    def test_missing_ambiguous_denied_and_invalid_identity_remain_distinct(self):
        self.api.packages.return_value = []
        self.assertIsNone(self.resolver.resolve('codex', run=self.runner))
        self.api.packages.return_value = ['one', 'two']
        with self.assertRaisesRegex(self.resolver.DiscoveryError, 'identity_invalid'):
            self.resolver.resolve('codex', run=self.runner)
        self.api.packages.side_effect = PermissionError('private path and credential fixture')
        with self.assertRaisesRegex(self.resolver.DiscoveryError, '^identity_unavailable$'):
            self.resolver.resolve('codex', run=self.runner)
        self.api.packages.side_effect = None
        self.api.packages.return_value = ['one']
        self.app.write_bytes(b'not PE')
        with self.assertRaisesRegex(self.resolver.DiscoveryError, 'identity_invalid'):
            self.resolver.resolve('codex', run=self.runner)

    def test_package_replacement_is_rejected_then_discovered_fresh(self):
        def replace(command, **kwargs):
            result = self.runner(command, **kwargs)
            self.api.packages.return_value = ['Codex_replacement']
            return result
        with self.assertRaisesRegex(self.resolver.DiscoveryError, 'identity_unavailable'):
            self.resolver.resolve('codex', run=replace)
        moved = self.root.with_name('StoreCodexNew')
        self.root.rename(moved)
        self.api.package_path.return_value = str(moved)
        self.cli = moved / self.cli.relative_to(self.root)
        self.assertEqual(self.resolver.resolve('codex', run=self.runner), str(self.cli))

    def test_retry_repeats_identity_lookup_cancel_never_downloads_or_writes(self):
        setup, dialog = module('native_setup'), mock.Mock()
        self.api.packages.side_effect = [PermissionError('private'), ['Codex_fixture'], ['Codex_fixture']]
        dialog.confirm_result.return_value = True
        self.assertFalse(setup._missing_assistant(['--clients', 'codex'], dialog, self.runner))
        self.assertEqual(self.api.packages.call_count, 3)
        self.api.packages.side_effect = PermissionError('private')
        for answer in (False, None):
            dialog.confirm_result.return_value = answer
            with mock.patch.object(setup.webbrowser, 'open') as browser:
                self.assertTrue(setup._missing_assistant(['--clients', 'codex'], dialog, self.runner))
            browser.assert_not_called()
        self.assertEqual(dialog.confirm_result.call_args.kwargs['labels'], ('Try again', 'Cancel'))
        self.assertNotIn('private', dialog.confirm_result.call_args.args[0])
        self.assertFalse((self.home / '.codex').exists())

    def test_existing_path_and_npm_shims_keep_precedence_and_claude_never_queries_store(self):
        for client, executable in (('codex', '/npm/codex.cmd'), ('codex', '/bin/codex.exe'),
                                   ('claude', '/bin/claude.cmd')):
            with self.subTest(client=client, executable=executable):
                self.assertEqual(self.resolver.resolve(client, which=lambda *a, **kw: executable),
                                 executable)
        self.assertIsNone(self.resolver.resolve('claude'))
        self.api.packages.assert_not_called()

    def test_discovery_failures_reach_all_callers_without_private_output(self):
        self.api.packages.side_effect = PermissionError('private output must not escape')
        skills, readiness = module('agent_skills'), module('native_readiness')
        result, refused = skills.register('codex', self.home / 'marketplace', ['scg-review'],
            run=self.runner, which=lambda *a, **kw: None)
        self.assertEqual((result, refused), ('codex: discovery failed (identity_unavailable)', 1))
        reasons = {}
        self.assertFalse(readiness.plugins_available('codex', ['scg-review'], run=self.runner,
            which=lambda *a, **kw: None, reasons=reasons))
        self.assertEqual(reasons, {'codex': 'identity_unavailable'})
        diagnostics, output = module('diagnostics'), io.StringIO()
        with mock.patch.object(diagnostics, 'find_python', return_value='/runtime/python'), \
                contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            diagnostics.do_preflight(SimpleNamespace(python=None, clients='codex', client=None))
        self.assertIn('identity_unavailable', output.getvalue())
        self.assertNotIn('install Codex', output.getvalue())
        self.assertNotIn('private', output.getvalue())
        self.assertEqual(self.commands, [])

    def test_unreadable_saved_plugin_choices_defer_every_registration_write(self):
        skills = module('agent_skills')
        for failure in ('json', 'status', 'timeout', 'unknown_enabled', 'missing_enabled'):
            with self.subTest(failure=failure):
                self.commands.clear()
                def run(command, **kwargs):
                    if command[1:3] == ['plugin', 'list']:
                        self.commands.append(command)
                        if failure == 'timeout':
                            raise subprocess.TimeoutExpired(command, 180)
                        if failure in ('unknown_enabled', 'missing_enabled'):
                            entry = {'pluginId': 'scg-review@scg-agent-plugins'}
                            if failure == 'unknown_enabled':
                                entry['enabled'] = 'false'
                            return SimpleNamespace(returncode=0, stdout=json.dumps({'installed': [entry]}))
                        return SimpleNamespace(returncode=1 if failure == 'status' else 0,
                            stdout='{"installed":[]}' if failure == 'status' else 'not JSON')
                    return self.runner(command, **kwargs)
                result, refused = skills.register('codex', self.home / 'marketplace',
                    ['scg-review'], run=run, which=lambda *a, **kw: None)
                self.assertEqual(refused, 1, result)
                self.assertIn('choices unavailable', result)
                self.assertTrue(all(command[1:] == ['--version'] or
                    command[1:3] == ['plugin', 'list'] for command in self.commands))

    def test_store_only_setup_does_not_offer_another_download(self):
        setup = module('native_setup')
        import windows_codex
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve() / 'StoreCodex'
            app = root / 'app/ChatGPT.exe'
            cli = app.parent / 'resources/codex.exe'
            cli.parent.mkdir(parents=True)
            app.write_bytes(b'MZ desktop fixture')
            cli.write_bytes(b'MZ CLI fixture')
            (root / 'AppxManifest.xml').write_text(
                '<Package><Applications><Application Id="App" '
                'Executable="app/ChatGPT.exe"/></Applications></Package>')
            api = mock.Mock()
            api.packages.return_value = ['Codex_fixture']
            api.package_path.return_value = str(root)
            api.user.return_value, api.session.return_value = 'fixture-user', 1
            dialog = mock.Mock()
            with mock.patch('sys.platform', 'win32'), \
                    mock.patch('shutil.which', return_value=None), \
                    mock.patch.object(windows_codex, 'bindings', return_value=api), \
                    mock.patch('subprocess.run', return_value=mock.Mock(
                        returncode=0, stdout='codex-cli 0.164.0\n')) as run, \
                    mock.patch.object(setup.webbrowser, 'open') as browser:
                self.assertFalse(setup._missing_assistant(['--clients', 'codex'], dialog))
            browser.assert_not_called()
            dialog.confirm.assert_not_called()
            self.assertEqual(run.call_args.args[0], [str(cli), '--version'])
            api.activate.assert_not_called()
            api.end.assert_not_called()


if __name__ == '__main__':
    unittest.main()
