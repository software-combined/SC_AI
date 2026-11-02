"""Validate all native Resources archives before adding their signed feed map."""
import hashlib
import importlib.util
import json
import re
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('resources_native_stage', ROOT / 'packaging/native/native_stage.py')
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)
spec = importlib.util.spec_from_file_location('resources_native_signing', ROOT / 'packaging/native/native_signing.py')
signing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(signing)
ORIGIN = 'https://dist.softwarecombined.com'


def records(directory, latest):
    directory = Path(directory)
    version, core = latest.get('version'), latest.get('sha256')
    if (not isinstance(version, str) or not re.fullmatch(r'\d+(?:\.\d+){2,3}', version)
            or not re.fullmatch('[0-9a-f]{64}', str(core))):
        raise ValueError('Invalid native Resources release identity')
    result = {}
    for receipt in sorted(directory.glob('*.resources.json')):
        doc = json.loads(receipt.read_text())
        if not isinstance(doc, dict):
            raise ValueError('Invalid native Resources receipt')
        target = doc.get('target')
        if target not in stage.TARGETS or target in result:
            raise ValueError('Invalid or duplicate native Resources target')
        name = 'scg-router-resources-%s-%s.tar.gz' % (version, target.replace('/', '-'))
        if (doc.get('file') != name or doc.get('version') != version
                or doc.get('bundle_sha256') != core
                or not re.fullmatch('[0-9a-f]{64}', str(doc.get('sha256')))
                or type(doc.get('size')) is not int or not 0 < doc['size'] <= 250 * 1024 * 1024):
            raise ValueError('Native Resources receipt does not match the release')
        path = directory / name
        if path.is_symlink() or path.stat().st_size != doc['size']:
            raise ValueError('Native Resources file does not match its receipt')
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != doc['sha256']:
                raise ValueError('Native Resources checksum mismatch')
        if target == 'windows/x86_64':
            with tarfile.open(path) as archive:
                stage._member_names(archive, links=True)
                info = archive.getmember('Resources/installer.json')
                menu = archive.getmember('Resources/control/scg-router-menu.exe')
                if not info.isfile() or info.size > 8192 or not menu.isfile():
                    raise ValueError('Invalid Windows signing members')
                metadata = json.load(archive.extractfile(info))
                sha = hashlib.file_digest(archive.extractfile(menu), 'sha256').hexdigest()
            if (metadata.get('target') != target or metadata.get('version') != version
                    or metadata.get('sha256') != core or metadata.get('menu_sha256') != sha
                    or metadata.get('menu_signature') != doc.get('signing')
                    or not signing.valid(doc.get('signing'), sha)):
                raise ValueError('Windows Resources signing evidence does not match')
        result[target] = {key: doc[key] for key in ('version', 'bundle_sha256', 'sha256', 'size')}
        result[target]['url'] = ORIGIN + '/bundles/' + name
    if set(result) != set(stage.TARGETS):
        raise ValueError('Native Resources require all five matching targets')
    return result
