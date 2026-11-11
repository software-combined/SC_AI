"""Verify native packages for stable publication or local beta staging."""
import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {'darwin/arm64', 'darwin/x86_64', 'windows/x86_64',
           'linux/arm64', 'linux/x86_64'}
ORIGIN = 'https://dist.softwarecombined.com'
SUFFIXES = {'darwin/arm64': 'macOS-arm64.dmg', 'darwin/x86_64': 'macOS-x86_64.dmg',
            'windows/x86_64': 'Windows.exe', 'linux/arm64': 'Linux-aarch64.AppImage',
            'linux/x86_64': 'Linux-x86_64.AppImage'}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


publisher = load('native_feed_publisher', ROOT / 'tools/publish_feed.py')
verify = load('native_feed_signatures', ROOT / 'packaging/feed_verify.py')


def packages(directory, channel, *, expected=None):
    """Require one untampered artifact per target, all from the same bundle."""
    records, versions, bundles = {}, set(), set()
    for receipt in sorted(Path(directory).glob('*.json')):
        if expected is not None and receipt.is_symlink():
            raise ValueError('unsafe native receipt link')
        doc = json.loads(receipt.read_text())
        if not isinstance(doc, dict) or 'artifact_sha256' not in doc:
            continue
        name, target = doc.get('artifact'), doc.get('target')
        if (not isinstance(name, str) or Path(name).name != name or
                not re.fullmatch(r'SCG-Router-Installer-[A-Za-z0-9._-]+', name) or
                target not in TARGETS or target in records or
                not re.fullmatch(r'\d+(?:\.\d+){2,3}', str(doc.get('version', ''))) or
                doc.get('channel') != channel or doc.get('native_signature') != 'unsigned'):
            raise ValueError('invalid or duplicate native package receipt')
        if expected is not None and (
                doc['version'] != expected['version'] or doc.get('sha256') != expected['sha256']
                or name != 'SCG-Router-Installer-' + expected['version'] + '-' + SUFFIXES[target]):
            raise ValueError('native package does not match the selected beta release')
        artifact = Path(directory) / name
        if artifact.is_symlink():
            raise ValueError('unsafe native package link')
        with artifact.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != doc['artifact_sha256']:
            raise ValueError('native package checksum mismatch')
        if not re.fullmatch('[0-9a-f]{64}', str(doc.get('sha256', ''))):
            raise ValueError('native package bundle identity missing')
        versions.add(doc['version'])
        bundles.add(doc['sha256'])
        records[target] = {'target': target, 'name': name, 'sha256': doc['artifact_sha256']}
    if set(records) != TARGETS or len(versions) != 1 or len(bundles) != 1:
        raise ValueError('five packages from one exact release are required')
    version = versions.pop()
    rows = [records[target] for target in sorted(records)]
    for row in rows:
        row['url'] = ORIGIN + '/installers/' + version + '/' + row['name']
    return {'version': version, 'channel': channel, 'packages': rows}


def public_distribution(distribution):
    """Require the approved public software distribution before advertising it."""
    doc = json.loads(publisher._aws(['cloudfront', 'get-distribution-config',
                                   '--id', distribution, '--output', 'json']))['DistributionConfig']
    if ORIGIN.split('//')[1] not in doc.get('Aliases', {}).get('Items', []):
        raise ValueError('distribution does not serve the expected download origin')
    behaviors = {row['PathPattern']: row for row in doc.get('CacheBehaviors', {}).get('Items', [])}
    for path in ('/installers/*', '/install/*.json'):
        if path not in behaviors:
            raise ValueError('public download behavior is missing')
        trust = behaviors.get(path, {}).get('TrustedKeyGroups', {})
        if trust.get('Enabled') or trust.get('Items'):
            raise ValueError('download sign-in requirement is still active')
    if doc.get('DefaultCacheBehavior', {}).get('TrustedKeyGroups', {}).get('Enabled'):
        raise ValueError('update sign-in requirement is still active')


def signed_inventory(rows, sign):
    checksums = ''.join(row['sha256'] + '  ' + row['name'] + '\n' for row in rows).encode()
    signature = verify.sign_hex(Path(sign).read_text().strip(), checksums)
    if not verify.verify_hex(verify.FEED_PUBLIC_KEY, checksums, signature):
        raise ValueError('checksum signer is not the trusted release signer')
    return checksums, (signature + '\n').encode()


def stage_beta(args):
    """Stage a complete beta cohort locally; never publish software or metadata."""
    if args.channel != 'beta' or args.macos_arm64_only or args.dry_run:
        raise ValueError('beta staging requires a complete beta release')
    dist, output = Path(args.dist), Path(args.stage_beta)
    document = dist / 'latest.json'
    if document.is_symlink():
        raise ValueError('unsafe beta document link')
    latest = json.loads(document.read_text())
    if (not isinstance(latest, dict) or latest.get('channel') != 'beta'
            or not re.fullmatch(r'\d+(?:\.\d+){2,3}', str(latest.get('version', '')))
            or not re.fullmatch('[0-9a-f]{64}', str(latest.get('sha256', '')))):
        raise ValueError('selected release is not a valid beta')
    bundle = publisher.bundle_name(latest)
    if (dist / bundle).is_symlink():
        raise ValueError('unsafe beta bundle link')
    publisher._check_bundle(dist, bundle, latest['sha256'])
    manifest = packages(args.artifacts, 'beta', expected=latest)
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ValueError('beta assets need a fresh output directory')
    checksums, signature = signed_inventory(manifest['packages'], args.sign)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        stage = Path(temporary) / 'assets'
        stage.mkdir()
        for row in manifest['packages']:
            copied = stage / row['name']
            shutil.copyfile(Path(args.artifacts) / row['name'], copied)
            with copied.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != row['sha256']:
                    raise ValueError('native package changed during staging')
        (stage / 'SHA256SUMS').write_bytes(checksums)
        (stage / 'SHA256SUMS.sig').write_bytes(signature)
        stage.rename(output)
    print('Staged five beta native installers ' + latest['version'])
    return 0


def publish(args):
    if args.channel != 'stable':
        raise ValueError('public native downloads use the stable channel only')
    directory = Path(args.artifacts)
    manifest = packages(directory, args.channel)
    # ponytail: published scope needs a new version; checksum inventories are immutable.
    if args.macos_arm64_only:
        manifest['scope'] = 'macos-arm64'
        manifest['packages'] = [row for row in manifest['packages'] if row['target'] == 'darwin/arm64']
    with tempfile.TemporaryDirectory() as temporary:
        stage = Path(temporary)
        version = manifest['version']
        prefix = 'installers/' + version + '/'
        if args.dry_run:
            print(json.dumps({'version': version, 'channel': args.channel,
                              'packages': len(manifest['packages']), 'public_downloads': True}))
            return 0
        public_distribution(args.distribution_id)
        checksums, signature = signed_inventory(manifest['packages'], args.sign)
        (stage / 'SHA256SUMS').write_bytes(checksums)
        (stage / 'SHA256SUMS.sig').write_bytes(signature)
        for row in manifest['packages']:
            publisher.publish_bundle(args.bucket, prefix + row['name'], directory / row['name'],
                                     row['sha256'], 'application/octet-stream')
        for name in ('SHA256SUMS', 'SHA256SUMS.sig'):
            body = stage / name
            publisher.publish_bundle(args.bucket, prefix + name, body,
                                     hashlib.sha256(body.read_bytes()).hexdigest(), 'text/plain')
        publisher.publish_setup_page(args.bucket)
        target = stage / 'downloads.json'
        target.write_text(json.dumps(manifest, indent=2) + '\n')
        publisher.publish_document(args.bucket, 'install/' + args.channel + '.json', target, 'no-store')
        publisher.invalidate(args.distribution_id, '/install/*')
        print('Published ' + args.channel + ' native installers ' + version)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', required=True)
    parser.add_argument('--channel', choices=('stable', 'beta'), required=True)
    parser.add_argument('--bucket')
    parser.add_argument('--distribution-id')
    parser.add_argument('--stage-beta', metavar='DIRECTORY')
    parser.add_argument('--dist', default='dist')
    parser.add_argument('--sign', required=True)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--macos-arm64-only', action='store_true')
    args = parser.parse_args(argv)
    if args.stage_beta:
        return stage_beta(args)
    if not args.bucket or not args.distribution_id:
        parser.error('publication requires --bucket and --distribution-id')
    return publish(args)


if __name__ == '__main__':
    raise SystemExit(main())
