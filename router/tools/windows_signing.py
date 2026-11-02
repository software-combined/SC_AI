"""Package and finalize Windows artifacts only after Authenticode verification."""
import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packaging/native'))
import native_build as build  # noqa: E402
import native_signing as signing  # noqa: E402
import native_resources_archive as archives  # noqa: E402

spec = importlib.util.spec_from_file_location('signing_native_payload', ROOT / 'packaging/native_payload.py')
payload = importlib.util.module_from_spec(spec)
spec.loader.exec_module(payload)
MENU = 'control/scg-router-menu.exe'


def identity(resources, latest):
    doc = json.loads((resources / 'installer.json').read_text())
    if (doc.get('target') != 'windows/x86_64' or doc.get('version') != latest.get('version')
            or doc.get('channel') != latest.get('channel') or doc.get('sha256') != latest.get('sha256')):
        raise ValueError('Windows signing inputs do not match the release')
    return doc


def package(resources, out, latest, publisher):
    resources, out = Path(resources), Path(out)
    signing.unchanged(resources, json.loads((resources.parent / 'signing-inputs.json').read_text()), (MENU,))
    doc = identity(resources, latest)
    doc['menu_signature'] = signing.verify(resources / MENU, publisher)
    doc['menu_sha256'] = doc['menu_signature']['sha256']
    (resources / 'installer.json').write_text(json.dumps(doc, indent=2) + '\n')
    payload.metadata(resources, 'windows/x86_64')
    compiler = Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')) / 'Inno Setup 6/ISCC.exe'
    artifact = build.windows(resources, out, doc['version'], iscc=str(compiler))
    signing.capture(resources, resources.parent / 'packaged-inputs.json')
    return artifact


def finalize(resources, out, latest, publisher):
    resources, out = Path(resources), Path(out)
    signing.unchanged(resources, json.loads((resources.parent / 'packaged-inputs.json').read_text()))
    doc = identity(resources, latest)
    payload.metadata(resources, 'windows/x86_64')
    menu = signing.verify(resources / MENU, publisher)
    if menu != doc.get('menu_signature'):
        raise ValueError('Packaged Windows menu signature changed')
    artifact = out / ('SCG-Router-Installer-' + doc['version'] + '-Windows.exe')
    outer = signing.verify(artifact, publisher)
    if menu['publisher_sha256'] != outer['publisher_sha256']:
        raise ValueError('Windows signing publishers do not match')
    archives.export(resources, out, doc)
    receipt = build.receipt(artifact, dict(doc, native_signature='authenticode', signing=outer))
    print(json.dumps(dict(artifact=artifact.name, receipt=receipt.name, sha256=outer['sha256'])))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('package', 'finalize'))
    parser.add_argument('--resources', type=Path, required=True)
    parser.add_argument('--dist', type=Path, default=Path('dist'))
    parser.add_argument('--out', type=Path, default=Path('native-artifacts'))
    args = parser.parse_args(argv)
    latest = json.loads((args.dist / 'latest.json').read_text())
    operation = package if args.phase == 'package' else finalize
    return operation(args.resources, args.out, latest, os.environ.get('SCG_EXPECTED_PUBLISHER', ''))


if __name__ == '__main__':
    main()
