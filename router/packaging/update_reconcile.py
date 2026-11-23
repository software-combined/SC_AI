"""Best-effort maintenance after an applying update releases nested install locks."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_payload import load


def log(home, task, event, **facts):
    """Callers supply closed-set outcomes, exception types and numeric exit codes."""
    try:
        directory = Path(home) / 'logs'
        directory.mkdir(exist_ok=True)
        with (directory / 'maintenance.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(dict(at=datetime.now(timezone.utc).isoformat(),
                                         task=task, event=event, **facts)) + '\n')
    except OSError:
        pass


def verified_timeout(home, latest, service):
    """Prove the signed candidate completed despite its Windows child timing out."""
    try:
        state = service._state.read(service._state.path(home))
        version = latest['version']
        status = load('update_status')
        if (not isinstance(state, dict) or state.get('last_applied_version') != version
                or service.current_version(home) != version
                or state.get('last_error') not in (None, 'installer_timeout')
                or any(status.components(state).get(name) != status.READY for name in status.COMPONENTS)
                or not load('native_resources').ready(home)):
            return False
        cohort, _, _ = load('windows_installation').parts(home)
        if (cohort['version'] != version or cohort['bundle_sha256'] != latest['sha256']
                or load('install_delivery').assistant_status(home, state) != status.READY):
            return False
        health = service.health(state, timeout=5)
        return bool(health and health.get('status') == 'ok' and health.get('version') == version)
    except (Exception, SystemExit):
        return False  # Unavailable proof must preserve the original timeout failure.


def run(home, service):
    """Post-update repair in one fixed order; each step's own module owns its checks.

    Unlocked preflight checks installation, Codex attachment and runtime. A needed change
    takes install.lock without waiting, then repairs the attachment, its assistant
    attention and the runtime in that order, repeating each check.
    """
    status = load('update_status')
    outcomes = {'attachment': status.DEFERRED}
    try:
        platforms = service.load('router_platforms', Path(__file__).parent / 'platforms' / '__init__.py')
        outcomes['installation'] = platforms.host(service).reconcile_after_update(home, service)
        recovery, runtime = load('codex_recovery'), load('runtime_rebind')
        outcomes['attachment'] = _attachment(recovery, home, service, apply=False)
        outcomes['runtime'] = runtime.reconcile(home, apply=False)
        saved = status.components(service._state.read(service._state.path(home))).get('scheduler')
        rebind = outcomes['runtime'] in (status.READY, status.FAILED) and saved != outcomes['runtime']
        attention = _attention(home, service, outcomes['attachment'], apply=False)
        if status.REPAIRABLE in outcomes.values() or rebind or attention:
            with service.install_lock(home) as held:
                if held:
                    outcomes['attachment'] = _attachment(recovery, home, service, apply=True)
                    _attention(home, service, outcomes['attachment'])
                    if outcomes['runtime'] == status.REPAIRABLE or rebind:
                        outcomes['runtime'] = runtime.reconcile(home)
                else:
                    outcomes['attachment'] = status.DEFERRED
                    if outcomes['runtime'] == status.REPAIRABLE:
                        outcomes['runtime'] = status.DEFERRED
        if outcomes['attachment'] in (status.REPAIRED, status.UNCHANGED):
            recovery.offer(home, service)
        log(home, 'reconcile', 'completed', **outcomes)
    except (Exception, SystemExit) as exc:
        outcomes['attachment'] = status.FAILED
        log(home, 'reconcile', 'failed', error=type(exc).__name__)
    return outcomes


def _attachment(recovery, home, service, *, apply):
    status = load('update_status')
    try:
        return recovery.reconcile(home, service, apply=apply)
    except (SystemExit, ValueError, KeyError, TypeError):
        return status.CONFLICT
    except OSError as exc:
        return status.CONFLICT if isinstance(exc, load('atomic_write').ConcurrentChange) else status.FAILED


def _attention(home, service, outcome, *, apply=True):
    status = load('update_status')
    if outcome not in (status.REPAIRED, status.UNCHANGED, status.CONFLICT, status.UNHEALTHY, status.FAILED):
        return
    state = service._state.read(service._state.path(home))
    if not isinstance(state, dict):
        return
    if service._state.saved_clients(state) not in ('codex', 'both'):
        return
    verified = outcome in (status.REPAIRED, status.UNCHANGED)
    assistants = load('install_delivery').assistant_status(home, state) if verified else status.FAILED
    if status.components(state).get('assistants') != assistants:
        if apply:
            service._state.update(home, lambda doc: status.set_components(doc, assistants=assistants),
                                  service._atomic_write)
        return True
