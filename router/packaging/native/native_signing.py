"""Windows Authenticode verification and final-byte signing evidence."""
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def valid(record, sha256):
    return (re.fullmatch('[0-9a-f]{64}', str(sha256)) is not None
            and isinstance(record, dict) and record.get('sha256') == sha256
            and record.get('timestamped') is True
            and re.fullmatch('[0-9a-f]{64}', str(record.get('publisher_sha256', ''))) is not None)


def capture(resources, destination=None):
    resources = Path(resources)
    files = {}
    for path in resources.rglob('*'):
        if path.is_symlink():
            raise ValueError('Windows signing inputs must not contain links')
        if path.is_file():
            files[path.relative_to(resources).as_posix()] = digest(path)
    if destination:
        Path(destination).write_text(json.dumps(files, sort_keys=True) + '\n')
    return files


def unchanged(resources, inventory, skip=()):
    actual = capture(resources)
    if set(actual) != set(inventory) or any(actual[p] != sha for p, sha in inventory.items() if p not in skip):
        raise ValueError('Prepared Windows inputs changed')


def verify(path, expected_publisher, run=subprocess.run):
    if not expected_publisher:
        raise ValueError('The expected signing publisher is required')
    tool = shutil.which('signtool.exe')
    if not tool:
        base = Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')) / 'Windows Kits/10/bin'
        candidates = [p for p in base.glob('*/x64/signtool.exe') if re.fullmatch(r'\d+(?:\.\d+)+', p.parent.parent.name)]
        tool = str(max(candidates, key=lambda p: tuple(map(int, p.parent.parent.name.split('.'))))) if candidates else None
    if not tool:
        raise ValueError('Windows SDK SignTool is required')
    run([tool, 'verify', '/pa', '/all', '/v', '/tw', str(path)], check=True)
    script = ("$ErrorActionPreference='Stop';$s=Get-AuthenticodeSignature -LiteralPath $env:SCG_SIGNATURE_FILE;"
              "@{status=$s.Status.ToString();subject=$s.SignerCertificate.Subject;"
              "timestamped=($null -ne $s.TimeStamperCertificate)}|ConvertTo-Json -Compress")
    result = run(['pwsh', '-NoProfile', '-NonInteractive', '-Command', script],
                 env=dict(os.environ, SCG_SIGNATURE_FILE=str(Path(path).resolve())),
                 check=True, capture_output=True, text=True)
    record = json.loads(result.stdout)
    if (record.get('status') != 'Valid' or record.get('timestamped') is not True
            or record.get('subject') != expected_publisher):
        raise ValueError('Windows signature, timestamp or publisher did not verify')
    return dict(sha256=digest(path), timestamped=True,
                publisher_sha256=hashlib.sha256(expected_publisher.encode()).hexdigest())
