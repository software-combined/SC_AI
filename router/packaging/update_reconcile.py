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
                or any(status.components(state).get(name) != 'ready' for name in status.COMPONENTS)
                or not load('native_resources').ready(home)):
            return False
        cohort, _, _ = load('windows_installation').parts(home)
        if (cohort['version'] != version or cohort['bundle_sha256'] != latest['sha256']
                or load('install_delivery').assistant_status(home, state) != 'ready'):
            return False
        health = service.health(state, timeout=5)
        return bool(health and health.get('status') == 'ok' and health.get('version') == version)
    except (Exception, SystemExit):
        return False  # Unavailable proof must preserve the original timeout failure.


def run(home, service):
    outcomes = {'attachment': 'deferred'}
    try:
        platforms = service.load('router_platforms', Path(__file__).parent / 'platforms' / '__init__.py')
        outcomes['installation'] = platforms.host(service).reconcile_after_update(home, service)
        recovery, runtime = load('codex_recovery'), load('runtime_rebind')
        outcomes['attachment'] = _attachment(recovery, home, service, apply=False)
        outcomes['runtime'] = runtime.reconcile(home, apply=False)
        state = service._state.read(service._state.path(home))
        components = state.get('component_repairs', {}) if isinstance(state, dict) else {}
        components = components if isinstance(components, dict) else {}
        runtime_pending = outcomes['runtime'] in ('ready', 'failed') and components.get('scheduler') != outcomes['runtime']
        attention = _attention(home, service, outcomes['attachment'], apply=False)
        if 'repairable' in outcomes.values() or runtime_pending or attention:
            with service.install_lock(home) as held:
                if held:
                    outcomes['attachment'] = _attachment(recovery, home, service, apply=True)
                    _attention(home, service, outcomes['attachment'])
                    if outcomes['runtime'] == 'repairable' or runtime_pending:
                        outcomes['runtime'] = runtime.reconcile(home)
                else:
                    outcomes['attachment'] = 'deferred'
                    if outcomes['runtime'] == 'repairable':
                        outcomes['runtime'] = 'deferred'
        if outcomes['attachment'] in ('repaired', 'unchanged'):
            recovery.offer(home, service)
        log(home, 'reconcile', 'completed', **outcomes)
    except (Exception, SystemExit) as exc:
        outcomes['attachment'] = 'failed'
        log(home, 'reconcile', 'failed', error=type(exc).__name__)
    return outcomes


def _attachment(recovery, home, service, *, apply):
    try:
        return recovery.reconcile(home, service, apply=apply)
    except (SystemExit, ValueError, KeyError, TypeError):
        return 'conflict'
    except OSError as exc:
        return 'conflict' if isinstance(exc, load('atomic_write').ConcurrentChange) else 'failed'


def _attention(home, service, outcome, *, apply=True):
    if outcome not in ('repaired', 'unchanged', 'conflict', 'unhealthy', 'failed'):
        return
    state = service._state.read(service._state.path(home))
    if not isinstance(state, dict):
        return
    if service._state.saved_clients(state) not in ('codex', 'both'):
        return
    verified = outcome in ('repaired', 'unchanged')
    status = load('install_delivery').assistant_status(home, state) if verified else 'failed'
    if load('update_status').components(state).get('assistants') != status:
        if apply:
            service._state.update(home, lambda doc: load('update_status').set_components(doc, assistants=status),
                                  service._atomic_write)
        return True
