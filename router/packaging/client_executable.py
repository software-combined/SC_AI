"""Shared client discovery for setup, plugin delivery and read-only checks."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import codex_config_proof
import windows_codex


def _windows_codex_dirs(environ=None):
    """Windows desktop's bundled CLI directories, newest build first."""
    local = (os.environ if environ is None else environ).get('LOCALAPPDATA')
    if not local:
        return ()
    base = Path(local) / 'OpenAI' / 'Codex' / 'bin'
    try:
        builds = sorted((p for p in base.iterdir() if p.is_dir()),
                        key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return ()
    return tuple(str(p) for p in builds)


def _macos_codex_dirs():
    """Desktop installs can supply Codex without a separate terminal install."""
    dirs = []
    for root in (Path.home() / 'Applications', Path('/Applications')):
        for app in ('ChatGPT.app', 'Codex.app'):
            for relative in ('Contents/Resources/codex-cli/bin', 'Contents/Resources'):
                folder = root / app / relative
                if (folder / 'codex').is_file():
                    dirs.append(str(folder))
    return tuple(dirs)


def client_path(environ=None, os_name=None):
    """Find client CLIs and their helpers in scheduled jobs and desktop setup."""
    # ponytail: fixed common dirs; a client under a version manager (nvm, fnm)
    # still needs its bin dir on the scheduled job's PATH.
    env = os.environ if environ is None else environ
    dirs = [d for d in env.get('PATH', '').split(os.pathsep) if d]
    extra = (str(Path.home() / '.local' / 'bin'),)
    if (os.name if os_name is None else os_name) == 'nt':
        extra += _windows_codex_dirs(env)
    else:
        # Admin-owned on macOS and Linux. On Windows they would be drive-root
        # folders any local account can create, so a planted client could run.
        extra += ('/opt/homebrew/bin', '/usr/local/bin')
        if sys.platform == 'darwin':
            extra += _macos_codex_dirs()
    return os.pathsep.join(dirs + [d for d in extra if d not in dirs])

class DiscoveryError(OSError):
    """Only fixed, content-free reasons cross the discovery boundary."""
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def resolve(client, *, path=None, run=None, which=None):
    """Prefer existing CLI paths; otherwise verify the current user's Store Codex."""
    executable = (which or shutil.which)(client, path=client_path() if path is None else path)
    if executable or client != 'codex' or sys.platform != 'win32':
        return executable
    try:
        identity = windows_codex.identity()
    except (OSError, ValueError) as error:
        reason = getattr(error, 'facts', {}).get('reason')
        if reason == 'app_unavailable':
            return None
        raise DiscoveryError('identity_invalid' if reason == 'invalid_identity'
                             else 'identity_unavailable') from None
    try:
        executable = codex_config_proof.codex_bin(
            os.environ, identity['root'], app_exe=identity['exe'],
            platform_name='win32', run=run or subprocess.run)
        windows_codex.validate(identity)
    except (OSError, ValueError, subprocess.SubprocessError):
        raise DiscoveryError('identity_unavailable') from None
    if executable is None:
        raise DiscoveryError('bundled_cli_invalid')
    return executable
