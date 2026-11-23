"""Run a native menu shell; keep actions asynchronous and status checks silent."""
import argparse
import hashlib
import json
import os
import queue
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_payload import load

# Private exit codes from run_menu to main.
HELPER_LOST = 74  # The helper exited unexpectedly; main retries it once.
RELOAD = 75  # Newer resources are current; main relaunches from them.


def _log(home, event, **facts):
    try:
        load('update_reconcile').log(home, 'desktop', event, **facts)
    except (Exception, SystemExit):
        pass


def _offer_warning(home):
    try:
        load('update_warning').offer(home)
    except (Exception, SystemExit) as exc:
        _log(home, 'warning_failed', error=type(exc).__name__)
    return {}


def _control(home, resources, action=None):
    command = [sys.executable, str(Path(__file__).with_name('desktop_control.py')),
               '--home', str(home), '--resources', str(resources)]
    if action:
        command += ['--action', action]
    result = subprocess.run(command, capture_output=True, text=True, timeout=960 if action else 15,
                            **({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}))
    if len(result.stdout) > 65536:
        raise ValueError('Desktop response too large')
    doc = json.loads(result.stdout)
    if not isinstance(doc, dict):
        raise ValueError('Invalid desktop response')
    return doc


def fallback(home, resources):
    """The same action IDs, including profile choices, when no tray host is available."""
    with load('service').install_lock(home, session_lock() + '.window') as held:
        if held:
            return _control_window(home, resources)
    return dict(outcome='done')


def _control_window(home, resources):
    model, control = load('desktop_model'), load('desktop_control')
    removed = Path(home) / load('native_shortcuts').REMOVED
    if not removed.exists():
        try:
            facts = control.snapshot(home)
        except (Exception, SystemExit):
            facts = dict(status='Status unknown', clients=[], version='Unknown')
        details, options = model.chooser(model.menu(facts)['menu'])
        dialog = load('native_dialog')
        action = dialog.choose('\n'.join(details), options, labels=('Run action', 'Close'))
        if action is None:
            return dict(outcome='done')
        result = _control(home, resources, action)
        if result.get('outcome') == 'done' and action in (
                'router.restart', 'startup.toggle', 'codex.subscription', 'codex.openrouter',
                'claude.subscription', 'claude.openrouter', 'codex.open', 'claude.open'):
            dialog.message(dict(options)[action].rstrip('…') + ' completed.')
        return result
    return dict(outcome='done')


def _events(stream, events):
    while True:
        line = stream.readline(1025)
        if not line or len(line) > 1024:
            events.put({'closed': True})
            return
        try:
            event = json.loads(line)
            if isinstance(event, dict):
                events.put(event, timeout=1)
        except (ValueError, queue.Full):
            pass


def session_lock():
    # UI uniqueness is per graphical session; configuration locks span sessions.
    if sys.platform == 'linux':
        session = (os.environ.get('XDG_SESSION_ID') or os.environ.get('WAYLAND_DISPLAY')
                   or os.environ.get('DISPLAY') or os.environ.get('DBUS_SESSION_BUS_ADDRESS') or 'desktop')
    elif sys.platform == 'win32':
        # Explorer and Task Scheduler do not supply the same environment.
        session = 'session-%d' % load('windows_native').Native().session()
    else:
        session = 'aqua'
    return '.desktop-menu-' + hashlib.sha256(session.encode()).hexdigest()[:16] + '.lock'


def mac_reopen_available(resources):
    # A retained controller can be newer than the native helper after a partial update.
    try:
        version = json.loads((resources / 'installer.json').read_text())['version']
        return tuple(map(int, version.split('.'))) >= (1, 3, 7)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False


def _settle(home, resources, worker, state):
    """Fold a finished job into the menu, then start a due refresh or control window."""
    job = state['job']
    if job and job.done():
        try:
            answer = job.result()
            if state['busy']:
                state['checked_update'] = answer.get('checked_update', state['checked_update'])
            elif answer.get('outcome') == 'failed':
                # Keep the last known rows so connections stay reachable.
                state['facts']['status'] = 'Needs attention'
            else:
                state['facts'] = answer
        except (Exception, SystemExit) as exc:
            _log(home, 'controller_failed', error=type(exc).__name__)
            state['facts']['status'] = 'Needs attention'
        state['next_check'] = 0 if state['busy'] else time.monotonic() + 30
        state['job'] = state['busy'] = None
    if state['job'] is None and time.monotonic() >= state['next_check']:
        state['job'] = worker.submit(_control, home, resources)
    if state['needs_fallback'] and not state['busy']:
        state['needs_fallback'], state['fallback_allowed'] = False, False
        state['job'] = worker.submit(fallback, home, resources)
        state['busy'] = 'Control window open…'


def _push(shell, model, state, request, mac_reopen):
    """Send the menu document when it changed or when macOS asked to open the menu."""
    document = model.menu(state['facts'], busy=state['busy'], checked_update=state['checked_update'])
    if mac_reopen:
        try:
            request.unlink()
        except FileNotFoundError:
            pass
        else:
            state['open_menu'] = True
        if state['open_menu']:
            document['open_menu'] = True
            state['open_menu'] = False
            state['last_doc'] = None  # A second reopen request must be delivered too.
    doc = json.dumps(document)
    if doc != state['last_doc']:
        shell.stdin.write(doc + '\n')
        shell.stdin.flush()
        state['last_doc'] = doc


def _handoff(home, resources, helper, idle):
    """True when an idle menu should reload from newer current resources."""
    try:
        name = (home / 'setup-current').read_text().strip()
        replacement = home / 'setup' / name
        if (name and Path(name).name == name and replacement != resources
                and idle and (replacement / 'control' / helper.name).is_file()):
            load('native_payload').metadata(replacement)
            _log(home, 'resource_handoff', reason='resources_advanced')
            return True
    except (OSError, ValueError):
        pass
    return False


def _on_event(event, home, resources, worker, state, actions):
    """Apply one helper event; True ends the menu loop."""
    if event.get('closed'):
        return True
    if event.get('host') is False and state['fallback_allowed']:
        state['needs_fallback'] = True
    action = event.get('action')
    if action == 'refresh':
        state['next_check'] = 0
    elif action == 'menu.quit' and not state['busy']:
        state['quit'] = True
        return True
    elif action in actions and not state['busy']:
        state['busy'] = ('Opening…' if action.endswith('.open') else
                         'Switching…' if action.startswith(('codex.', 'claude.')) else
                         'Connecting…' if action == 'setup.key' else
                         'Updating…' if action == 'updates.install' else 'Working…')
        state['job'] = worker.submit(_control, home, resources, action)
    return False


def run_menu(home, resources, *, autostart=False, after_update=False, offer_warning=False):
    quiet = autostart or after_update
    control, model = load('desktop_control'), load('desktop_model')
    removed = Path(home) / load('native_shortcuts').REMOVED
    if removed.exists():
        return 0
    helper = resources / 'control' / ('scg-router-menu.exe' if os.name == 'nt' else 'scg-router-menu')
    if not helper.is_file():
        if not quiet:
            fallback(home, resources)
        return 1
    mac_reopen = sys.platform == 'darwin' and mac_reopen_available(resources)
    if sys.platform == 'darwin' and not mac_reopen and not quiet:
        fallback(home, resources)
        return 0
    service = load('service')
    request = home / (session_lock() + '.open')
    with service.install_lock(home, session_lock()) as held:
        if not held:
            _log(home, 'launch_skipped', reason='existing_controller')
            if not quiet:
                if sys.platform == 'darwin':
                    request.touch(mode=0o600)
                    deadline = time.monotonic() + 2
                    while request.exists() and time.monotonic() < deadline:
                        time.sleep(0.1)
                    try:
                        request.unlink()  # An older resident controller did not consume the request.
                    except FileNotFoundError:
                        pass
                    else:
                        fallback(home, resources)
                else:
                    fallback(home, resources)
            return 0
        try:
            if time.time() - request.stat().st_mtime > 3:
                request.unlink(missing_ok=True)
        except FileNotFoundError:
            pass
        events = queue.Queue(maxsize=32)
        icon = resources / 'router/packaging/assets/router-icon.png'
        try:
            shell = subprocess.Popen([str(helper), str(icon)], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     text=True, bufsize=1,
                                     **({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}))
        except OSError as exc:
            _log(home, 'helper_launch_failed', error=type(exc).__name__)
            if not quiet:
                fallback(home, resources)
            return 1
        _log(home, 'helper_launched')
        threading.Thread(target=_events, args=(shell.stdout, events), daemon=True).start()
        state = dict(facts=dict(status='Checking setup…', version='Unknown', clients=[]),
                     checked_update=None, busy=None, job=None, next_check=0, last_doc=None,
                     open_menu=mac_reopen and not quiet, fallback_allowed=not quiet,
                     needs_fallback=False, reload=False, quit=False)
        with ThreadPoolExecutor(max_workers=1) as worker:
            try:
                # A successful removal closes the menu, even mid-action or with a submenu open.
                while shell.poll() is None and not removed.exists():
                    _settle(home, resources, worker, state)
                    _push(shell, model, state, request, mac_reopen)
                    if _handoff(home, resources, helper, state['job'] is None):
                        state['reload'] = True
                        break
                    if offer_warning and state['job'] is None and not state['busy']:
                        offer_warning, state['busy'] = False, 'Checking setup…'
                        state['job'] = worker.submit(_offer_warning, home)
                    try:
                        event = events.get(timeout=0.5)
                    except queue.Empty:
                        continue
                    if _on_event(event, home, resources, worker, state, control.ACTIONS):
                        break
            except (BrokenPipeError, ConnectionResetError):
                pass  # The helper exited between poll and pipe write.
            finally:
                try:
                    shell.stdin.close()
                except OSError:
                    pass
                try:
                    exit_code = shell.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    shell.terminate()
                    exit_code = shell.wait(timeout=5)
                shell.stdout.close()
                reason = ('reload' if state['reload'] else 'removed' if removed.exists()
                          else 'quit' if state['quit'] else 'unexpected')
                _log(home, 'helper_exited', exit_code=exit_code, reason=reason)
    return RELOAD if state['reload'] else 0 if state['quit'] or removed.exists() else HELPER_LOST


def start(home, resources, *, autostart=False, after_update=False):
    if (Path(home) / load('native_shortcuts').REMOVED).exists():
        _log(home, 'launch_skipped', reason='removed')
        return
    if autostart and not after_update and not load('desktop_startup').enabled(home):
        return
    helper = Path(resources) / 'control' / ('scg-router-menu.exe' if os.name == 'nt' else 'scg-router-menu')
    launcher = Path(home) / 'desktop_launch.py'
    if helper.is_file() and launcher.is_file():
        reason = ['--after-update'] if after_update else ['--autostart'] if autostart else []
        try:
            subprocess.Popen([sys.executable, str(launcher)] + reason,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             **({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt'
                                else {'start_new_session': True}))
        except OSError as exc:
            _log(home, 'launch_failed', reason='launch_failed', error=type(exc).__name__, errno=exc.errno)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, required=True)
    parser.add_argument('--resources', type=Path, required=True)
    parser.add_argument('--autostart', action='store_true')
    parser.add_argument('--after-update', action='store_true')
    args = parser.parse_args(argv)
    if args.autostart and not args.after_update and not load('desktop_startup').enabled(args.home):
        return 0
    os.environ.update(load('native_setup').environment(args.resources))
    try:
        for attempt in range(2):
            rc = run_menu(args.home, args.resources, autostart=args.autostart,
                          after_update=args.after_update,
                          offer_warning=not args.after_update and attempt == 0)
            if rc != HELPER_LOST or attempt:
                break
            time.sleep(1)
            if (args.home / load('native_shortcuts').REMOVED).exists():
                return 0
            try:
                replacement = load('native_resources').current(args.home)
            except (OSError, ValueError):
                replacement = args.resources
            if replacement != args.resources:
                rc = RELOAD
                break
            _log(args.home, 'helper_retry')
    except (Exception, SystemExit) as exc:
        _log(args.home, 'controller_failed', error=type(exc).__name__)
        return 1
    if rc == RELOAD:
        command = [sys.executable, str(args.home / 'desktop_launch.py'), '--after-update']
        os.execv(sys.executable, command)
    return rc


if __name__ == '__main__':
    sys.exit(main())
