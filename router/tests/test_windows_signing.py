"""Signing changes bytes before hashes, packaging and publication acceptance."""
import importlib.util
import json
import tempfile
import subprocess
import unittest
from pathlib import Path
from unittest import mock
from types import SimpleNamespace

from tests.test_native_stage import _bundle, _runtime, _lock, stage

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('windows_signing_tool', ROOT / 'tools/windows_signing.py')
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class WindowsSigningTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.resources = self.root / 'stage/Resources'
        bundle, runtime = _bundle(), _runtime('windows/x86_64')
        paths = self.root / 'bundle.tar.gz', self.root / 'runtime.tar.gz', self.root / 'runtime.lock'
        paths[0].write_bytes(bundle)
        paths[1].write_bytes(runtime)
        paths[2].write_text(json.dumps(_lock('windows/x86_64', runtime)))
        stage.stage(*paths[:2], 'windows/x86_64', 'stable', self.resources, lock_path=paths[2])
        self.menu = self.resources / 'control/scg-router-menu.exe'
        self.menu.parent.mkdir()
        self.menu.write_bytes(b'compiled menu')
        self.latest = json.loads((self.resources / 'installer.json').read_text())
        self.latest['menu_sha256'] = stage.sha256_file(self.menu)
        (self.resources / 'installer.json').write_text(json.dumps(self.latest))
        tool.signing.capture(self.resources, self.resources.parent / 'signing-inputs.json')
        self.out = self.root / 'out'
        self.out.mkdir()
        self.events = []

    def verify(self, path, expected):
        self.assertEqual(expected, 'Synthetic Publisher')
        self.assertTrue(path.read_bytes().endswith(b' SIGNED'), path)
        self.events.append('verify:' + path.name)
        return dict(sha256=stage.sha256_file(path), publisher_sha256='a' * 64, timestamped=True)

    def package(self, resources, out, version, **kwargs):
        self.events.append('package')
        metadata = tool.payload.metadata(resources, 'windows/x86_64')
        self.assertEqual(metadata['menu_sha256'], stage.sha256_file(self.menu))
        self.assertEqual(self.menu.read_bytes(), b'compiled menu SIGNED')
        artifact = out / ('SCG-Router-Installer-' + version + '-Windows.exe')
        artifact.write_bytes(b'installer contains ' + self.menu.read_bytes() + b' END-INSTALLER')
        return artifact

    def test_sign_verify_package_sign_finalize_uses_final_bytes(self):
        runtime_before = (self.resources / 'runtime/python/python.exe').read_bytes()
        self.menu.write_bytes(self.menu.read_bytes() + b' SIGNED')
        with self.assertRaisesRegex(ValueError, 'menu files'):
            tool.payload.metadata(self.resources, 'windows/x86_64')
        with mock.patch.object(tool.signing, 'verify', self.verify), \
                mock.patch.object(tool.build, 'windows', self.package):
            artifact = tool.package(self.resources, self.out, self.latest, 'Synthetic Publisher')
            self.assertFalse(list(self.out.glob('*.json')), 'unsigned outer file has no receipt')
            artifact.write_bytes(artifact.read_bytes() + b' SIGNED')
            tool.finalize(self.resources, self.out, self.latest, 'Synthetic Publisher')
        receipt = json.loads(artifact.with_suffix('.exe.json').read_text())
        self.assertEqual(receipt['native_signature'], 'authenticode')
        self.assertEqual(receipt['artifact_sha256'], stage.sha256_file(artifact))
        self.assertEqual(receipt['signing']['sha256'], receipt['artifact_sha256'])
        self.assertEqual((self.resources / 'runtime/python/python.exe').read_bytes(), runtime_before)
        self.assertEqual(self.events[0:2], ['verify:scg-router-menu.exe', 'package'])
        self.assertTrue(list(self.out.glob('*.resources.json')))

    def test_unsigned_menu_and_changed_runtime_cannot_reach_packaging(self):
        for defect in ('unsigned', 'runtime'):
            with self.subTest(defect=defect), mock.patch.object(tool.signing, 'verify', self.verify), \
                    mock.patch.object(tool.build, 'windows') as build:
                if defect == 'runtime':
                    (self.resources / 'runtime/python/python.exe').write_bytes(b'changed')
                with self.assertRaises((ValueError, AssertionError)):
                    tool.package(self.resources, self.out, self.latest, 'Synthetic Publisher')
                build.assert_not_called()

    def test_verification_failure_emits_no_publishable_outputs(self):
        self.menu.write_bytes(self.menu.read_bytes() + b' SIGNED')
        with mock.patch.object(tool.signing, 'verify', self.verify), \
                mock.patch.object(tool.build, 'windows', self.package):
            artifact = tool.package(self.resources, self.out, self.latest, 'Synthetic Publisher')
        with mock.patch.object(tool.signing, 'verify', side_effect=ValueError('untrusted signer')):
            with self.assertRaises(ValueError):
                tool.finalize(self.resources, self.out, self.latest, 'Synthetic Publisher')
        self.assertTrue(artifact.exists())
        self.assertFalse(list(self.out.glob('*.json')))

    def test_unsigned_outer_installer_cannot_produce_resources_or_receipts(self):
        self.menu.write_bytes(self.menu.read_bytes() + b' SIGNED')
        with mock.patch.object(tool.signing, 'verify', self.verify), \
                mock.patch.object(tool.build, 'windows', self.package):
            artifact = tool.package(self.resources, self.out, self.latest, 'Synthetic Publisher')
            with self.assertRaises(AssertionError):
                tool.finalize(self.resources, self.out, self.latest, 'Synthetic Publisher')
        self.assertEqual(self.events, ['verify:scg-router-menu.exe', 'package', 'verify:scg-router-menu.exe'])
        self.assertTrue(artifact.exists())
        self.assertFalse(list(self.out.glob('*.json')))
        self.assertFalse(list(self.out.glob('*.tar.gz')))

    def test_real_verifier_contract_rejects_missing_timestamp_wrong_publisher_and_warning(self):
        for status, subject, timestamp in [('Valid', 'Wrong', True), ('Valid', 'Synthetic Publisher', False),
                                           ('HashMismatch', 'Synthetic Publisher', True)]:
            run = mock.Mock(return_value=SimpleNamespace(stdout=json.dumps(
                dict(status=status, subject=subject, timestamped=timestamp))))
            with mock.patch.object(tool.signing.shutil, 'which', return_value='signtool.exe'), self.assertRaises(ValueError):
                tool.signing.verify(self.menu, 'Synthetic Publisher', run=run)
            self.assertEqual(run.call_args_list[0].args[0][1:6], ['verify', '/pa', '/all', '/v', '/tw'])
            self.assertTrue(run.call_args_list[0].kwargs['check'])
        with mock.patch.object(tool.signing.shutil, 'which', return_value='signtool.exe'), \
                self.assertRaises(subprocess.CalledProcessError):
            tool.signing.verify(self.menu, 'Synthetic Publisher',
                run=mock.Mock(side_effect=subprocess.CalledProcessError(2, ['signtool'])))


if __name__ == '__main__':
    unittest.main()
