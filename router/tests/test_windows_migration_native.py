"""Migration and recovery against the real Windows Task Scheduler."""
import json
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from tests.test_windows_backend import _state_file, backend, service
from tests.windows_native_fixture import FIXTURE_LIFETIME, NativeChild, cleanup, write_launcher

RELEASE_DIR = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == 'win32', 'requires the real Windows Task Scheduler')
class NativeMigrationTests(unittest.TestCase):
    @contextmanager
    def scheduler(self):
        self.obj = backend.Backend(service, subprocess.run)
        self.sid = self.obj._identity()
        prefix = 'SCG-CI-' + uuid.uuid4().hex
        self.names = [prefix + suffix for suffix in ('', '-Update', '-Express')]
        router, update, express = self.names
        with tempfile.TemporaryDirectory(prefix='router migration ') as tmp, \
                mock.patch.multiple(backend, ROUTER_TASK=router, UPDATE_TASK=update,
                                    EXPRESS_TASK=express, DRAIN_TIMEOUT_S=0), \
                mock.patch.object(backend, '_post_shutdown', return_value=False), \
                mock.patch.object(service, 'wait_version', side_effect=self.healthy), \
                mock.patch.object(service, 'health', return_value={'version': '1.0.0'}):
            self.home = Path(tmp)
            _state_file(self.home)
            children = []
            for script in ('router_launch.py', 'update_launch.py', 'express_launch.py'):
                write_launcher(self.home, script, FIXTURE_LIFETIME)
            service.install_task_launcher(self.home, RELEASE_DIR)
            try:
                self.register_legacy(router, backend.render_router_xml, start=True)
                self.register_legacy(update, backend.render_update_xml, start=True)
                self.register_legacy(express, backend.render_express_xml, start=False)
                self.parent = self.task(update, 'disable', legacy=True)['instances']
                self.parent_child = NativeChild.capture(self.home / 'update_launch.alive')
                children.append(self.parent_child)
                self.parent_child.assert_alive('before-migration')
                yield
            finally:
                for gate in self.home.glob('*.gate'):
                    gate.unlink(missing_ok=True)
                cleanup(self.obj._call, self.names + [name + '-' + self.sid for name in self.names],
                        children)

    def task(self, name, operation='query', **kwargs):
        return self.obj._task_state(name, self.home, operation, **kwargs)

    def running(self, name, *, legacy=False):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            result = self.task(name, legacy=legacy)
            if result and result['instances']:
                return result
            time.sleep(0.2)
        self.fail('disposable migration task did not start')

    def register_legacy(self, name, render, *, start):
        self.task(name, 'register', legacy=True, xml=render(sys.executable, self.home, self.sid))
        if start:
            self.task(name, 'run', legacy=True)
            self.running(name, legacy=True)
            self.task(name, 'complete', legacy=True)

    def healthy(self, state, version):
        self.assertEqual(version, '1.0.0')
        self.running(self.names[0])
        return True  # HTTP health is simulated. Task state is real.

    def migrate_and_check_live_parent(self):
        _, update, express = self.names
        self.obj.install(sys.executable, self.home, {}, RELEASE_DIR, None, expected_version='1.0.0')
        updater = self.task(update)
        self.assertFalse(updater['enabled'])
        self.assertFalse(updater['pending'])
        expedited = self.task(express)
        self.assertTrue(expedited['enabled'])
        self.assertFalse(expedited['pending'])
        self.parent_child.assert_alive('after-migration')
        legacy = self.task(update, legacy=True)
        self.assertFalse(legacy['enabled'])
        self.assertEqual(legacy['instances'], self.parent)

    def test_failed_registration_preserves_running_tasks_and_allows_retry(self):
        with self.scheduler():
            router, update, express = self.names
            original_router = self.task(router, legacy=True)['instances']
            run = self.obj._run

            def failed_registration(cmd, **kwargs):
                request = json.loads(kwargs.get('input', '{}'))
                if request.get('name') == express + '-' + self.sid and request['operation'] == 'register':
                    request['xml'] = '<Task>'  # The real Scheduler API must reject this definition.
                    kwargs['input'] = json.dumps(request)
                return run(cmd, **kwargs)

            with mock.patch.object(self.obj, '_run', side_effect=failed_registration):
                with self.assertRaisesRegex(SystemExit, f'Windows task {express}-{self.sid} during register'):
                    self.obj.install(sys.executable, self.home, {}, RELEASE_DIR, None)
            self.assertEqual(self.task(router, legacy=True)['instances'], original_router)
            self.assertEqual(self.task(update, legacy=True)['instances'], self.parent)
            self.migrate_and_check_live_parent()

    def test_migration_recovers_after_the_disabled_parent_exits(self):
        with self.scheduler():
            update = self.names[1]
            self.migrate_and_check_live_parent()
            heartbeat = self.home / 'update_launch.alive'
            before = heartbeat.read_text()
            time.sleep(0.3)
            self.assertNotEqual(heartbeat.read_text(), before)
            self.assertTrue(self.obj.ensure_serving(self.home, {}, '1.0.0'))
            (self.home / 'update_launch.gate').unlink()
            self.assertTrue(self.obj._wait_stopped(update, 15, self.home, legacy=True))
            self.obj.recover_pending(sys.executable, self.home, RELEASE_DIR, '1.0.0')
            self.assertIsNone(self.task(update, legacy=True))
            self.assertFalse(self.task(update)['enabled'])
