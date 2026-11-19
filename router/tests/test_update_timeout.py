"""A timed-out Windows child cannot invalidate independently verified completion."""
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tests.install_fixtures import _craft_bundle, install_mod_factory
from tests.test_native_setup import module


class VerifiedTimeoutTests(unittest.TestCase):
    def setUp(self):
        self.home = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (self.home / 'current').write_text('1.0.0')
        (self.home / 'releases/1.0.0').mkdir(parents=True)
        self.install = install_mod_factory()
        self.updater = self.install._updater
        self.blob, self.latest = _craft_bundle('1.0.1')
        self.latest['express'] = True
        self.verifier = module('feed_verify')
        self.seed, public = self.verifier.generate_keypair()
        self.enterContext(mock.patch.object(self.updater, '_FEED_VERIFY_KEY', public))
        self.candidate = dict(port=1, token='synthetic', clients='none',
            last_applied_version='1.0.1', component_repairs={
                name: 'ready' for name in self.updater._status.COMPONENTS})
        self.save({})
        self.platform = SimpleNamespace(platform='win32', executable=sys.executable, exc_info=sys.exc_info)
        self.enterContext(mock.patch.object(self.updater, 'sys', self.platform))
        self.enterContext(mock.patch.object(self.updater._models, 'refresh'))
        self.enterContext(mock.patch.object(self.updater._models, 'accept'))
        self.enterContext(mock.patch.object(self.updater._reconcile, 'run'))
        self.enterContext(mock.patch.object(self.updater, '_offer_notices'))
        self.ready = mock.Mock(return_value=True)
        self.parts = mock.Mock(return_value=(dict(version='1.0.1',
            bundle_sha256=self.latest['sha256']), None, None))
        self.assistants = mock.Mock(return_value='ready')
        owners = dict(native_resources=SimpleNamespace(ready=self.ready),
            windows_installation=SimpleNamespace(parts=self.parts),
            install_delivery=SimpleNamespace(assistant_status=self.assistants), update_status=self.updater._status)
        self.enterContext(mock.patch.object(self.updater._reconcile, 'load', side_effect=owners.__getitem__))
        self.enterContext(mock.patch.object(self.updater._resources, 'ready', self.ready))
        self.health = self.enterContext(mock.patch.object(self.updater._svc, 'health',
            return_value=dict(status='ok', version='1.0.1')))
        self.enterContext(mock.patch.object(self.updater._svc, 'run', side_effect=self.timeout))
        self.error = subprocess.TimeoutExpired('private command', 900, output='private output', stderr='private error')
        self.current = '1.0.1'

    def save(self, state):
        (self.home / 'mixed-router-state.json').write_text(json.dumps(state))

    def state(self):
        return json.loads((self.home / 'mixed-router-state.json').read_text())

    def timeout(self, *_, **__):
        (self.home / 'current').write_text(self.current)
        (self.home / 'releases/1.0.1').mkdir(exist_ok=True)
        self.save(self.candidate)
        raise self.error

    def update(self, express=True):
        args = self.install.build_parser().parse_args(['--home', str(self.home),
            '--update', '--feed', 'file:///latest.json'] + (['--express-only'] if express else []))
        body = json.dumps(self.latest).encode()
        signature = self.verifier.sign_hex(self.seed, body).encode()
        with contextlib.redirect_stdout(io.StringIO()):
            return self.install.do_update(args, _fetch=lambda url: signature if url.endswith('.sig') else self.blob,
                _read_feed=lambda *_: (200, body, 'candidate'),
                _sleep=lambda _: None, _announce=lambda *_: None)

    def test_verified_timeout_finishes_regular_and_express_without_repair(self):
        for express in (True, False):
            with self.subTest(express=express):
                (self.home / 'current').write_text('1.0.0')
                self.save({})
                self.candidate.update(last_error='installer_timeout', installation_repair_required=True,
                                      update_failures={'1.0.1': 2})
                self.assertEqual(self.update(express), 0)
                state = self.state()
                self.assertNotIn('last_error', state)
                self.assertNotIn('installation_repair_required', state)
                self.assertEqual(state['update_failures'], {})
                self.assertEqual(state['last_applied_version'], '1.0.1')
                self.assertFalse(self.updater._status.summary(state, '1.0.1')['offer_repair'])
        rows = [json.loads(row) for row in (self.home / 'logs/maintenance.jsonl').read_text().splitlines()]
        recovered = [row for row in rows if row['event'] == 'timeout_verified']
        self.assertEqual(len(recovered), 2)
        self.assertTrue(all(row['error'] == 'TimeoutExpired' and row['version'] == '1.0.1' for row in recovered))
        self.assertNotIn('private', json.dumps(rows))

    def assert_failed(self, code='installer_timeout'):
        with self.assertRaises(self.updater.UpdateError) as caught:
            self.update()
        self.assertEqual(caught.exception.error_code, code)
        state = self.state()
        self.assertEqual(state['last_error'], code)
        self.assertTrue(state['installation_repair_required'])
        self.assertGreater(state['update_failures']['1.0.1'], 0)
        self.assertFalse((self.home / 'update-etag').exists())

    def test_incomplete_wrong_unhealthy_and_conflicting_candidates_still_fail(self):
        changes = (
            lambda: setattr(self, 'current', '1.0.0'),
            lambda: self.candidate.pop('last_applied_version'),
            lambda: self.candidate.update(last_applied_version='1.0.0'),
            lambda: self.candidate['component_repairs'].pop('assistants'),
            lambda: self.candidate['component_repairs'].update(assistants='failed'),
            lambda: self.candidate['component_repairs'].update(controls='unknown'),
            lambda: self.candidate.update(last_error='installer_failed'),
            lambda: setattr(self.ready, 'return_value', False),
            lambda: setattr(self.parts, 'return_value', (dict(version='1.0.1', bundle_sha256='0' * 64), None, None)),
            lambda: setattr(self.parts, 'return_value', (dict(version='1.0.0', bundle_sha256=self.latest['sha256']), None, None)),
            lambda: setattr(self.assistants, 'return_value', 'failed'),
            lambda: setattr(self.assistants, 'return_value', 'unknown'),
            lambda: setattr(self.health, 'return_value', None),
            lambda: setattr(self.health, 'return_value', dict(status='ok', version='1.0.0')),
            lambda: setattr(self.health, 'side_effect', OSError('private health error')),
        )
        baseline = json.dumps(self.candidate)
        for index, change in enumerate(changes):
            with self.subTest(case=index):
                self.candidate = json.loads(baseline)
                self.current = '1.0.1'
                self.ready.return_value = True
                self.parts.return_value = (dict(version='1.0.1', bundle_sha256=self.latest['sha256']), None, None)
                self.assistants.return_value = 'ready'
                self.health.return_value = dict(status='ok', version='1.0.1')
                self.health.side_effect = None
                (self.home / 'current').write_text('1.0.0')
                self.save({})
                change()
                self.assert_failed()

    def test_other_platforms_and_non_timeout_errors_keep_the_failure_path(self):
        for platform, error, code in (
                ('darwin', self.error, 'installer_timeout'),
                ('linux', self.error, 'installer_timeout'),
                ('win32', subprocess.SubprocessError('private error'), 'installer_failed')):
            with self.subTest(platform=platform, code=code):
                self.platform.platform, self.error = platform, error
                (self.home / 'current').write_text('1.0.0')
                self.save({})
                self.assert_failed(code)
                self.health.assert_not_called()


if __name__ == '__main__':
    unittest.main()
