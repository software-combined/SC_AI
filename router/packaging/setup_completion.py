"""Installer-owned key and native completion; runtime only records its answers."""
import os
import subprocess
import sys
from pathlib import Path


PENDING = ('Setup is pending. Your installed router and any saved key are kept. '
           'Open SCG Router and choose Check setup to finish.')


class SavedKeyError(ValueError):
    """A known completion failure with fixed, safe user-facing wording."""
    def __init__(self):
        super().__init__('Your saved key is kept, but setup could not finish. '
                         'Try Check setup again. If it still fails, contact Software Combined IT.')


def complete_native(resources, home, run_installer):
    from native_payload import load, read_json, succeeded
    path = Path(home) / 'mixed-router-state.json'
    state, diagnostics = read_json(path), load('diagnostics')
    if diagnostics._provider_defs().unhandled(Path(home), state, diagnostics._key_private):
        raise SavedKeyError()
    flags = load('client_choice').mode_flags(state,
        load('codex_config').read_receipt(home).get('clients', {}))
    if flags and not succeeded(run_installer(resources, home, flags)):
        raise SavedKeyError()
    if load('service')._state.setup_pending(read_json(path)):
        raise SavedKeyError()
    return 0


def confirm_client(home, dialog, client, saved_key):
    label = {'codex': 'Codex', 'claude': 'Claude Code', 'claude-desktop': 'Claude desktop'}[client]
    if saved_key and client != 'claude-desktop':
        return dialog.confirm_result(
            'Your saved key is ready. Keep %s open and keep your current model. '
            'Send a message and use an enabled SC tool, such as SC documentation. '
            'If both already work, choose Confirm.' % label,
            home, labels=('Confirm', 'Later')) is True
    return dialog.confirm(
        'To finish setup for %s:\n\n%s'
        'Choose an OpenRouter model and send a greeting. Use an enabled SC tool, '
        'such as SC documentation.\n\n'
        'Choose Continue only after you receive a reply and the SC tool works.'
        % (label, 'Choose Code and start a new task. ' if client == 'claude-desktop'
           else 'Quit and reopen it, then start a new chat. '), home=home)


def ready_message(clients, saved_key):
    if saved_key and clients and 'claude-desktop' not in clients:
        labels = ['Codex' if client == 'codex' else 'Claude Code' for client in clients]
        return 'Ready. %s %s connected. You can keep working in this chat.' % (
            ' and '.join(labels), 'is' if len(labels) == 1 else 'are')
    return 'Ready. Your assistants are connected and updates are automatic.'


def open_window(python, home, release, url, clients):
    """Wait for the owned popup; never put the setup URL in argv or output."""
    try:
        proc = subprocess.Popen([python, '-m', 'ai_router.key_prompt', '--stdin',
                                 '--clients', clients], cwd=str(release),
                                start_new_session=True, stdin=subprocess.PIPE,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                                env=dict(os.environ, ROUTER_HOME=str(Path(home).resolve())),
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.stdin.write((url + '\n').encode())
        proc.stdin.close()
        return proc.wait(timeout=900)
    except (OSError, subprocess.SubprocessError):
        return None


def finish(args, home, python, url, clients, open_window, complete):
    """Manual installs finish after attachment; unattended installs never prompt."""
    if url is None:
        return
    interactive = (not args.update and os.environ.get('ROUTER_AUTOMATIC_UPDATE') != '1'
        and os.environ.get('ROUTER_NO_KEY_WINDOW') != '1'
        and (sys.platform != 'linux' or os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')))
    if interactive and open_window(python, home, url, clients) == 0:
        try:
            complete(home, python)
            return
        except (OSError, ValueError, subprocess.SubprocessError, SystemExit):
            pass
    print(PENDING)


def reconcile(home, python, choice, receipts, state, parser, attach):
    """Read answers without mutation; attach only when saved modes differ."""
    attached = receipts.read_receipt(home).get('clients', {})
    flags = choice.mode_flags(state.read_strict(state.path(home)), attached)
    if flags:
        args = parser().parse_args(['--home', str(home), *flags])
        args.desktop = 'claude-desktop' in attached
        return attach(args, home, python)
    return 0
