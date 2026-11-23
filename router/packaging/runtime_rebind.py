"""Bind owned scheduled tasks to verified, retained native resources after delivery."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_payload import load


def reconcile(home, *, apply=True):
    """Read-only checks run unlocked; applying repeats checks under install.lock."""
    home, service, status = Path(home), load('service'), load('update_status')
    platforms = service.load('router_platforms', Path(__file__).parent / 'platforms' / '__init__.py')
    backend = platforms.host(service)
    if not hasattr(backend, 'rebind_runtime'):
        return status.INACTIVE  # Only a backend whose tasks run a retained runtime rebinds them.
    outcome = status.FAILED
    try:
        resources = load('native_resources').current(home)
        doc = load('native_payload').metadata(resources)
        if doc['version'] != service.current_version(home) or not doc.get('menu_sha256'):
            return status.DEFERRED
        python = str(resources / 'runtime' / doc['runtime_exec'])
        if not apply:
            return status.READY if backend.runtime_matches(python, home) else status.REPAIRABLE
        backend.rebind_runtime(python, home)
        outcome = status.READY
    except (Exception, SystemExit):
        pass  # Old definitions and runtimes are retained; the next check retries.
    if not apply:
        return outcome
    try:
        service._state.update(home, lambda state: status.set_components(state, scheduler=outcome),
                              service._atomic_write)
    except (OSError, ValueError, TypeError):
        pass
    return outcome
