"""One backend per OS behind a single interface (Plan 056).

`select()` returns a backend or None; None means unsupported, never macOS.
Backends own service lifecycle (plists/units, reload, restart, stop, updater
job, uninstall) and answer the installation repair hooks below, so shared
modules ask `host()` instead of naming a platform. Shared feed/verify/config
logic stays in install.py.
Loaded via the installer's file-based import pattern, never
`import packaging.platforms`, so installed bundles keep working without a
`packaging` distribution.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import loader  # noqa: E402

_status = loader.load(Path(__file__).resolve().parents[1] / 'update_status.py')


def _load(name, filename):
    return loader.load(Path(__file__).resolve().parent / filename, name)


_darwin = None
_linux = None
_windows = None


def _darwin_mod():
    global _darwin
    if _darwin is None:
        _darwin = _load('router_platform_darwin', 'darwin.py')
    return _darwin


def _linux_mod():
    global _linux
    if _linux is None:
        _linux = _load('router_platform_linux', 'linux.py')
    return _linux


def _windows_mod():
    global _windows
    if _windows is None:
        _windows = _load('router_platform_windows', 'windows.py')
    return _windows


def select(platform, svc, run):
    """Backend for this platform, or None when unsupported.

    `svc` is the shared service helper module; `run` is the patchable
    subprocess seam. Bound per call so test seams keep working.
    """
    if platform == 'darwin':
        return _darwin_mod().Backend(svc, run)
    if platform == 'linux':
        return _linux_mod().Backend(svc, run)
    if platform == 'win32':
        return _windows_mod().Backend(svc, run)
    return None


def host(svc):
    """Backend for the running machine; no-op repair hooks when unsupported."""
    return select(sys.platform, svc, svc.run) or NoRepair()


class NoRepair:
    """Repair hooks for a backend without an installation journal (macOS, Linux).

    Windows answers the same hooks from `windows_installation.Repair`. Each
    default reports nothing to recover and leaves the shared path in charge.
    """

    def recover_interrupted(self, home):
        """Restore an interrupted installation; the caller holds install.lock."""
        return _status.INACTIVE

    def reconcile_after_update(self, home, service):
        """Retry an interrupted installation after an update, without waiting."""
        return _status.INACTIVE

    def recover_pending(self, python, home, release_dir, version):
        """Finish a legacy install whose scheduled tasks are still pending."""
        return None

    def prepare_maintenance(self, home, source, latest, delivery):
        """Stage maintenance inside the installation; None runs the shared pass."""
        return None

    def finish_maintenance(self, home, native, fetch):
        """Deliver required controls first: False stops, True marks maintenance done, None runs the shared finish."""
        return None

    def verified_after_timeout(self, home, latest, service):
        """Whether a timed-out installer child provably completed this release."""
        return False

    def controls_ready(self, home):
        """Whether an applied update also has the controls this platform requires."""
        return True

    def installation_ready(self, home):
        """Whether the installation is one coherent release."""
        return True

    def repair_controls(self, home, latest, feed_url, fetch):
        """Repair required controls through the installation; None runs shared delivery."""
        return None
