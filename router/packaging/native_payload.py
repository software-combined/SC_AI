"""Validate and retain a native installer's files before using its Python.

The download is disposable. Services and the installed setup shortcut must
only refer to the retained copy, never a disk image or temporary mount.
"""
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import sysconfig
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loader  # noqa: E402


class OwnershipConflict(ValueError):
    """A user-owned entry point belongs to another installation."""
    ownership_conflict = True


class Deferred(Exception):
    """A Windows update stopped safely and will retry; the installer exits 0.

    Importers share this class through the normal `native_payload` import,
    so a file-loaded caller still catches what another file-loaded module raised.
    """


def load(name):
    return loader.load(Path(__file__).with_name(name + '.py'), 'router_native_' + name)


def succeeded(result):
    """A deferred installer exits zero without completing the requested operation."""
    output = getattr(result, 'stdout', '') or ''
    if isinstance(output, bytes):
        output = output.decode(errors='replace')
    return result.returncode == 0 and not any(line.startswith('deferred:') for line in output.splitlines())


def read_json(path):
    try:
        doc = json.loads(Path(path).read_text())
    except FileNotFoundError:
        return {}
    if not isinstance(doc, dict):
        raise ValueError('The saved setup cannot be read. Contact Software Combined IT.')
    return doc


def target():
    system = {'Darwin': 'darwin', 'Windows': 'windows', 'Linux': 'linux'}.get(
        platform.system())
    machine = (sysconfig.get_platform().removeprefix('win-') if system == 'windows'
               else platform.machine()).lower()
    cpu = {'amd64': 'x86_64', 'aarch64': 'arm64'}.get(machine, machine)
    return '%s/%s' % (system, cpu)


def metadata(resources, expected_target=None):
    resources = Path(resources).resolve()
    doc = json.loads((resources / 'installer.json').read_text())
    if (not isinstance(doc, dict) or
            not re.fullmatch(r'\d+(?:\.\d+){2,3}', str(doc.get('version', ''))) or
            doc.get('channel') not in ('stable', 'beta') or
            doc.get('target') != (expected_target or target())):
        raise ValueError('This installer is not for this computer.')
    executable = Path(doc.get('runtime_exec', ''))
    if (not executable.parts or executable.is_absolute() or
            '..' in executable.parts or
            not (resources / 'runtime' / executable).is_file()):
        raise ValueError('The bundled Python is missing.')
    if doc['target'].startswith('windows/') and not (resources / 'runtime' / executable.with_name('pythonw.exe')).is_file():
        raise ValueError('The bundled Python is missing.')
    blob = resources / 'payload' / 'bundle.tar.gz'
    digest = hashlib.sha256(blob.read_bytes()).hexdigest()
    feed = json.loads((resources / 'payload' / 'latest.json').read_text())
    if (digest != doc.get('sha256') or digest != feed.get('sha256') or
            feed.get('version') != doc['version']):
        raise ValueError('The installer files did not pass verification.')
    for name in ('install.py', 'native_setup.py', 'VERSION'):
        if not (resources / 'router' / 'packaging' / name).is_file():
            raise ValueError('The installer is incomplete.')
    if (resources / 'router/packaging/VERSION').read_text().strip() != doc['version']:
        raise ValueError('The installer files did not pass verification.')
    if 'menu_sha256' in doc:
        helper = resources / 'control' / ('scg-router-menu.exe' if doc['target'].startswith('windows/') else 'scg-router-menu')
        if (not re.fullmatch('[0-9a-f]{64}', str(doc['menu_sha256'])) or not helper.is_file()
                or hashlib.sha256(helper.read_bytes()).hexdigest() != doc['menu_sha256']):
            raise ValueError('The menu files did not pass verification.')
    return doc


def windows_helper_env(home, resources, doc=None):
    """Use an owner-only extraction directory for the verified ARM helper."""
    if (doc['target'] if doc else target()) != 'windows/arm64':
        return None
    try:
        doc = doc or metadata(resources)
        if not doc.get('menu_sha256'):
            raise ValueError('Missing verified menu')
        home = Path(home)
        directory = home / 'dotnet-bundle'
        if any(path.is_symlink() or path.is_junction() for path in (home, directory)):
            raise ValueError('Unsafe menu folder')
        service = load('service')
        platforms = loader.load(Path(__file__).parent / 'platforms' / '__init__.py')
        backend = platforms.select(os.sys.platform, service, service.run)
        backend.protect_secret(home)
        directory.mkdir(mode=0o700, exist_ok=True)
        backend.protect_secret(directory)
        return {**os.environ, 'DOTNET_BUNDLE_EXTRACT_BASE_DIR': str(directory.resolve())}
    except (OSError, ValueError, SystemExit) as exc:
        raise OSError('The menu is unavailable.') from exc


def retained(resources, home, expected_target=None, *, repair=False):
    """Stage and atomically retain one immutable package; returns its path."""
    resources, home = Path(resources).resolve(), Path(home).expanduser()
    doc = metadata(resources, expected_target)
    for entry in resources.rglob('*'):
        if entry.is_symlink() and resources not in entry.resolve().parents:
            raise ValueError('The installer contains an unsafe file link.')
    if home.is_symlink() or (home / 'setup').is_symlink():
        raise ValueError('The setup folder is not safe to use.')
    home.mkdir(parents=True, mode=0o700, exist_ok=True)
    service = load('service')
    # The backend protects Windows ACLs as well as POSIX permissions.
    platforms = loader.load(Path(__file__).parent / 'platforms' / '__init__.py')
    backend = platforms.select(os.sys.platform, service, service.run)
    if backend is None:
        raise ValueError('This computer is not supported.')
    backend.protect_secret(home)
    base = home / 'setup'
    base.mkdir(mode=0o700, exist_ok=True)
    destination = base / (doc['version'] + '-' + doc['sha256'][:16])
    if destination.is_symlink():
        raise ValueError('The setup folder is not safe to use.')
    if destination.exists():
        try:
            matches = metadata(destination, expected_target) == doc
        except (OSError, ValueError):
            matches = False
        if matches:
            return destination
        if not repair:
            raise ValueError('The installed setup files have changed.')
        destination = base / (destination.name + '-repair-' + uuid.uuid4().hex[:12])
    with tempfile.TemporaryDirectory(dir=base) as temporary:
        staged = Path(temporary) / 'Resources'
        shutil.copytree(resources, staged)
        metadata(staged, expected_target)
        staged.rename(destination)
    return destination


def install_arguments(resources, home, *, key=False, repair=False):
    """Use permanent Python and a local bundle; the installer picks the clients."""
    resources, home = Path(resources), Path(home)
    doc = metadata(resources)
    python = resources / 'runtime' / doc['runtime_exec']
    source = load('native_controller').launcher_source(home, resources / 'router')
    feed = ((resources / 'payload/latest.json').absolute().as_uri() if not repair else
            load('feed').FEED_URL.replace('/stable/', '/' + load('update_status').channel(home) + '/'))
    args = [str(python), str(source / 'packaging' / 'install.py'),
            '--python', str(python), '--home', str(home),
            '--feed', feed]
    if key:
        args.append('--setup')
    elif repair:
        args.append('--repair')
    return args


def record_channel(resources, home, *, existing=False, package=False):
    """An explicit package adopts its channel only after its core has landed."""
    home = Path(home)
    doc = metadata(resources)
    if package:
        if load('service').current_version(home) != doc['version']:
            raise ValueError('The packaged router version was not installed.')
        if load('update_status').channel(home) != doc['channel']:
            (home / 'feed-serial').unlink(missing_ok=True)
    elif (home / 'channel').exists():
        return
    load('atomic_write').replace_text(home / 'channel',
        (doc['channel'] if package or not existing else 'stable') + '\n')
