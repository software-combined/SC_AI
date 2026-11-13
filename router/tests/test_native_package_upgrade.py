"""Windows package intent uses its verified bundle without maintenance repair."""
import contextlib
import hashlib
import io
import json
import os
import re
import shlex
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tests.install_fixtures import _craft_bundle, _ok_run, install_mod
from tests.test_client_choice import _full_install
from tests.test_native_setup import ROOT, module, resources


class NativePackageUpgradeTests(unittest.TestCase):
    def test_windows_exe_upgrade_repeat_and_retained_state_reinstall(self):
        native = module('native_setup')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            home = root / 'router'
            rc, _, user, _ = _full_install(self, root, home, '1.0.0', ['--clients', 'codex'])
            self.assertEqual(rc, 0)
            state = install_mod.ensure_state(home)
            state.pop('setup', None)
            state.update(custom={'keep': True})
            install_mod._write_state(home, state)
            key = home / 'openrouter.key'
            key.write_text('synthetic-saved-key\n')
            (home / 'channel').write_text('stable\n')
            (home / 'feed-serial').write_text('999\n')
            config = user / '.codex/config.toml'
            config.write_text('model = "owner-choice"\n' + config.read_text() +
                              '\n[plugins."synthetic@marketplace"]\nenabled = false\n')
            auth = user / '.codex/auth.json'
            auth.write_text('{"synthetic_saved_signin":true}\n')
            source = resources(root / 'Resources', version='1.0.1', channel='beta')
            blob, latest = _craft_bundle('1.0.1')
            (source / 'payload/bundle.tar.gz').write_bytes(blob)
            (source / 'payload/latest.json').write_text(json.dumps(dict(latest, url='bundle.tar.gz')))
            metadata = json.loads((source / 'installer.json').read_text())
            metadata['sha256'] = hashlib.sha256(blob).hexdigest()
            (source / 'installer.json').write_text(json.dumps(metadata))
            # Read the actual postinstall command, including its package-intent flags.
            script = (ROOT / 'packaging/native/windows.iss').read_text().split('[Run]')[1]
            suffix = re.search(r'--resources ""\{app\}""(.*?)"; Description:', script)[1]
            argv = ['--resources', str(source), '--home', str(home), *shlex.split(suffix)]
            dialog = mock.MagicMock()
            dialog.choose.return_value = 'resume'
            dialog.Progress.return_value.__enter__.return_value.cancelled = False
            restart = mock.Mock()
            # A handled optional offer may choose Later; no repair shutdown is implied.
            restart.offer.return_value = True
            diagnostics = SimpleNamespace(_key_private=None, _provider_defs=lambda:
                SimpleNamespace(unhandled=lambda *_: []))
            owners = dict(native_dialog=dialog, setup_restart=restart,
                diagnostics=diagnostics, desktop_menu=mock.Mock(),
                claude_desktop_platform=SimpleNamespace(is_running=mock.Mock(return_value=True)),
                codex_desktop_switch=SimpleNamespace(CODEX=object()))
            original, invoke, key_flow = native.load, native.run_installer, native._key
            commands = []
            def child(command, **kwargs):
                commands.append(command)
                self.assertEqual(command[command.index('--feed') + 1],
                                 (source / 'payload/latest.json').as_uri())
                self.assertFalse(set(command) & {'--repair', '--setup', '--choose-clients', '--clients'})
                args = install_mod.build_parser().parse_args(command[2:])
                def fetch(url):
                    self.assertTrue(url.startswith('file:'), 'package attempted a remote feed')
                    return install_mod._svc.fetch(url)
                with mock.patch.dict(os.environ, kwargs['env']):
                    return SimpleNamespace(returncode=install_mod.do_install(args, _fetch=fetch, _run=_ok_run),
                                           stdout='', stderr='')
            env = dict(HOME=str(user), USERPROFILE=str(user), ROUTER_NO_KEY_WINDOW='1',
                       CLAUDE_CONFIG_DIR=str(root / 'claude'), OPENROUTER_API_KEY='')
            no_prompt = mock.Mock(side_effect=AssertionError('saved key must not reopen access'))
            with mock.patch.dict(os.environ, env), contextlib.redirect_stdout(io.StringIO()), \
                    mock.patch.object(native, 'sys', SimpleNamespace(platform='win32')), \
                    mock.patch.object(native, 'load', side_effect=lambda name: owners.get(name) or original(name)), \
                    mock.patch.object(native, 'retained', return_value=source), \
                    mock.patch.object(native, 'run_installer', side_effect=lambda *args: invoke(*args, run=child)), \
                    mock.patch.object(native, '_key', side_effect=lambda *args: key_flow(*args, run=no_prompt)), \
                    mock.patch.object(native, '_check'), \
                    mock.patch.object(install_mod, 'platform_backend') as backend, \
                    mock.patch.object(install_mod._diag, '_key_private', return_value=True), \
                    mock.patch.object(install_mod._delivery, 'close_assistants') as close, \
                    mock.patch.object(install_mod._client_choice, 'attach_codex',
                                      wraps=install_mod._client_choice.attach_codex) as attach:
                backend.return_value.pinned_release.return_value = None
                self.assertEqual(native.main(argv), 0)
                self.assertEqual((home / 'current').read_text().strip(), '1.0.1')
                self.assertEqual((home / 'channel').read_text(), 'beta\n')
                self.assertFalse((home / 'feed-serial').exists())
                progress = home / 'setup-progress.json'
                completed = json.loads(progress.read_text())
                completed['confirmed_clients'] = ['codex']
                progress.write_text(json.dumps(completed))
                saved_progress = progress.read_bytes()
                before_repeat = config.read_bytes()
                backups = sorted(home.glob('config-before-*'))
                self.assertEqual(native.main(argv), 0)
                self.assertEqual(config.read_bytes(), before_repeat)
                self.assertEqual(sorted(home.glob('config-before-*')), backups)
                self.assertEqual(progress.read_bytes(), saved_progress)
                self.assertEqual(attach.call_count, 1)
                # Model canonical removal's detached client and missing runtime; retain user state.
                receipt = install_mod._codex_config.codex_attachment(home)
                _, restored = install_mod._codex_config.removal_plan(config, receipt)
                config.write_bytes(restored.encode())
                install_mod._codex_config.drop_client(home, 'codex', expected=receipt)
                (home / 'current').unlink()
                owners['claude_desktop_platform'].is_running.reset_mock()
                self.assertEqual(native.main(argv), 0)
                self.assertEqual((home / 'current').read_text().strip(), '1.0.1')
                self.assertEqual(progress.read_bytes(), saved_progress)
                close.assert_not_called()
                dialog.choose.assert_not_called()
                dialog.dialog.ask.assert_not_called()
                dialog.Progress.assert_called_with(home=home)
                self.assertEqual(restart.offer.call_count, 3)
                restart.offer.assert_called_with(home, restart.target.return_value, True)
                self.assertEqual(restart.target.call_count, 3)
                self.assertEqual(owners['desktop_menu'].start.call_args_list,
                                 [mock.call(home, source, after_update=True)] * 3)
                owners['claude_desktop_platform'].is_running.assert_called_once_with(
                    'win32', app=owners['codex_desktop_switch'].CODEX)
            self.assertEqual(len(commands), 3)
            no_prompt.assert_not_called()
            self.assertEqual(key.read_text(), 'synthetic-saved-key\n')
            self.assertEqual(auth.read_text(), '{"synthetic_saved_signin":true}\n')
            self.assertIn('model = "owner-choice"', config.read_text())
            self.assertEqual(config.read_text().count('[plugins."synthetic@marketplace"]'), 1)
            self.assertIn('enabled = false', config.read_text())
            final = install_mod.ensure_state(home)
            for name in ('token', 'clients', 'openai_mode', 'claude_mode', 'custom'):
                self.assertEqual(final[name], state[name])
            self.assertNotIn('setup', final)

    def test_failure_keeps_channel_and_explicit_maintenance_keeps_repair(self):
        native = module('native_setup')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = resources(root / 'Resources', version='1.0.1', channel='beta')
            home = root / 'home'
            home.mkdir()
            saved = {'current': '1.0.0\n', 'channel': 'stable\n', 'feed-serial': '999\n',
                     'mixed-router-state.json': '{"clients":"none"}'}
            for name, value in saved.items():
                (home / name).write_text(value)
            dialog, original, invoke = mock.MagicMock(), native.load, native.run_installer
            child = mock.Mock(return_value=SimpleNamespace(returncode=1))
            with mock.patch.object(native, 'load', side_effect=lambda name: dialog
                    if name in ('native_dialog', 'setup_restart') else original(name)), \
                    mock.patch.object(native, 'retained', return_value=source), \
                    mock.patch.object(native, 'run_installer', side_effect=lambda *args: invoke(*args, run=child)):
                for action in ('install', 'resume'):
                    self.assertEqual(native.main(['--resources', str(source), '--home', str(home),
                                                  '--action', action]), 1)
                    command = child.call_args.args[0]
                    self.assertEqual('--repair' in command, action == 'resume')
                    expected = ((source / 'payload/latest.json').as_uri() if action == 'install'
                                else 'https://dist.softwarecombined.com/stable/latest.json')
                    self.assertEqual(command[command.index('--feed') + 1], expected)
            self.assertEqual({name: (home / name).read_text() for name in saved}, saved)


if __name__ == '__main__':
    unittest.main()
