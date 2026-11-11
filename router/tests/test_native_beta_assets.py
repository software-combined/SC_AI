"""Beta assets bind five native bodies to the selected core and trusted signer."""
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tests.test_native_publish import publish

NATIVE_NAMES = {
    'darwin/arm64': 'SCG-Router-Installer-1.2.3.4-macOS-arm64.dmg',
    'darwin/x86_64': 'SCG-Router-Installer-1.2.3.4-macOS-x86_64.dmg',
    'windows/x86_64': 'SCG-Router-Installer-1.2.3.4-Windows.exe',
    'linux/arm64': 'SCG-Router-Installer-1.2.3.4-Linux-aarch64.AppImage',
    'linux/x86_64': 'SCG-Router-Installer-1.2.3.4-Linux-x86_64.AppImage'}


def beta_artifacts(root):
    native, dist = root / 'native', root / 'dist'
    native.mkdir()
    dist.mkdir()
    core = b'synthetic core bundle'
    digest = hashlib.sha256(core).hexdigest()
    (dist / 'ai-router-1.2.3.4.tar.gz').write_bytes(core)
    (dist / 'latest.json').write_text(json.dumps(dict(version='1.2.3.4', channel='beta',
        sha256=digest, serial=1, min_python='3.14',
        url='https://example.invalid/releases/ai-router-1.2.3.4.tar.gz')))
    bodies = {}
    for target, name in NATIVE_NAMES.items():
        bodies[name] = ('synthetic native body ' + target).encode()
        (native / name).write_bytes(bodies[name])
        (native / (name + '.json')).write_text(json.dumps(dict(
            artifact=name, target=target, version='1.2.3.4', channel='beta',
            native_signature='unsigned', sha256=digest,
            artifact_sha256=hashlib.sha256(bodies[name]).hexdigest())))
    seed, public = publish.verify.generate_keypair()
    secret = root / 'synthetic-signing-seed'
    secret.write_text(seed)
    return SimpleNamespace(artifacts=native, dist=dist, stage_beta=root / 'beta-assets',
        sign=secret, channel='beta', macos_arm64_only=False, dry_run=False), public, bodies


class BetaAssetTests(unittest.TestCase):
    def test_cli_stages_only_five_bodies_and_trusted_signed_inventory_without_aws(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args, public, bodies = beta_artifacts(root)
            (args.artifacts / 'stray.exe').write_bytes(b'not a release asset')
            before = set(root.iterdir())
            with mock.patch.object(publish.verify, 'FEED_PUBLIC_KEY', public), \
                    mock.patch.object(publish.publisher, '_aws', side_effect=AssertionError('no AWS')) as aws:
                self.assertEqual(publish.main(['--artifacts', str(args.artifacts), '--channel', 'beta',
                    '--dist', str(args.dist), '--stage-beta', str(args.stage_beta),
                    '--sign', str(args.sign)]), 0)
            aws.assert_not_called()
            self.assertEqual(set(root.iterdir()) - before, {args.stage_beta})
            self.assertEqual({p.name for p in args.stage_beta.iterdir()},
                             set(bodies) | {'SHA256SUMS', 'SHA256SUMS.sig'})
            checksums = (args.stage_beta / 'SHA256SUMS').read_bytes()
            rows = checksums.decode().splitlines()
            self.assertEqual(len(rows), 5)
            order = ('darwin/arm64', 'darwin/x86_64', 'linux/arm64',
                     'linux/x86_64', 'windows/x86_64')
            self.assertEqual([row.split('  ', 1)[1] for row in rows],
                             [NATIVE_NAMES[target] for target in order])
            self.assertEqual(dict(row.split('  ', 1)[::-1] for row in rows),
                             {name: hashlib.sha256(body).hexdigest() for name, body in bodies.items()})
            self.assertTrue(publish.verify.verify_hex(public, checksums,
                (args.stage_beta / 'SHA256SUMS.sig').read_text().strip()))
            for name, body in bodies.items():
                self.assertEqual((args.stage_beta / name).read_bytes(), body)
                self.assertEqual((args.artifacts / name).read_bytes(), body)

    def test_incomplete_tampered_foreign_or_misnamed_cohorts_never_create_assets(self):
        for case in ('missing', 'duplicate', 'tampered', 'channel', 'mixed_version',
                     'foreign_version', 'foreign_core', 'filename', 'selected_channel',
                     'selected_core', 'partial_platforms', 'requested_channel', 'dry_run'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                args, public, _ = beta_artifacts(Path(temporary))
                receipts = sorted(args.artifacts.glob('*.json'))
                first = receipts[0]
                doc = json.loads(first.read_text())
                if case == 'missing':
                    first.unlink()
                elif case == 'duplicate':
                    (args.artifacts / 'duplicate.json').write_text(first.read_text())
                elif case == 'tampered':
                    (args.artifacts / doc['artifact']).write_bytes(b'changed')
                elif case == 'channel':
                    doc['channel'] = 'stable'
                    first.write_text(json.dumps(doc))
                elif case in ('mixed_version', 'foreign_version', 'foreign_core'):
                    for receipt in (receipts[:1] if case == 'mixed_version' else receipts):
                        value = json.loads(receipt.read_text())
                        value['sha256' if case == 'foreign_core' else 'version'] = (
                            'b' * 64 if case == 'foreign_core' else '1.2.9.4')
                        receipt.write_text(json.dumps(value))
                elif case == 'filename':
                    old = args.artifacts / doc['artifact']
                    doc['artifact'] = doc['artifact'].replace('1.2.3.4', '1.2.3.5')
                    old.rename(args.artifacts / doc['artifact'])
                    first.write_text(json.dumps(doc))
                elif case in ('selected_channel', 'selected_core'):
                    latest = args.dist / 'latest.json'
                    value = json.loads(latest.read_text())
                    value['channel' if case == 'selected_channel' else 'sha256'] = (
                        'stable' if case == 'selected_channel' else 'b' * 64)
                    latest.write_text(json.dumps(value))
                elif case == 'requested_channel':
                    args.channel = 'stable'
                elif case == 'dry_run':
                    args.dry_run = True
                else:
                    args.macos_arm64_only = True
                with mock.patch.object(publish.verify, 'FEED_PUBLIC_KEY', public):
                    with self.assertRaises((ValueError, SystemExit)):
                        publish.stage_beta(args)
                self.assertFalse(args.stage_beta.exists())

    def test_untrusted_signer_and_existing_output_are_refused_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            args, _, _ = beta_artifacts(Path(temporary))
            with self.assertRaisesRegex(ValueError, 'trusted release signer'):
                publish.stage_beta(args)
            self.assertFalse(args.stage_beta.exists())
            args.stage_beta.mkdir()
            sentinel = args.stage_beta / 'keep'
            sentinel.write_bytes(b'incumbent')
            args.sign.unlink()
            with self.assertRaisesRegex(ValueError, 'fresh output'):
                publish.stage_beta(args)
            self.assertEqual(sentinel.read_bytes(), b'incumbent')

    @unittest.skipIf(os.name == 'nt', 'publication symlink fixtures run on POSIX')
    def test_symlink_inputs_are_refused_even_with_matching_bytes(self):
        for case in ('artifact', 'receipt', 'document', 'bundle'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                args, public, _ = beta_artifacts(root)
                receipt = sorted(args.artifacts.glob('*.json'))[0]
                path = {'artifact': args.artifacts / json.loads(receipt.read_text())['artifact'],
                        'receipt': receipt, 'document': args.dist / 'latest.json',
                        'bundle': args.dist / 'ai-router-1.2.3.4.tar.gz'}[case]
                saved = root / 'linked-input'
                path.rename(saved)
                path.symlink_to(saved)
                with mock.patch.object(publish.verify, 'FEED_PUBLIC_KEY', public):
                    with self.assertRaisesRegex(ValueError, 'link'):
                        publish.stage_beta(args)
                self.assertFalse(args.stage_beta.exists())

    def test_copy_drift_cannot_leave_a_publishable_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            args, public, _ = beta_artifacts(Path(temporary))
            copy = publish.shutil.copyfile
            def changed(source, target):
                copy(source, target)
                Path(target).write_bytes(b'changed after initial verification')
            with mock.patch.object(publish.verify, 'FEED_PUBLIC_KEY', public), \
                    mock.patch.object(publish.shutil, 'copyfile', side_effect=changed):
                with self.assertRaisesRegex(ValueError, 'changed during staging'):
                    publish.stage_beta(args)
            self.assertFalse(args.stage_beta.exists())


if __name__ == '__main__':
    unittest.main()
