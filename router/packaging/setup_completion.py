"""Installer-owned key window lifecycle; runtime only records its answers."""
import os
import subprocess
import sys
from pathlib import Path


PENDING = ('Setup is pending. Your installed router and any saved key are kept. '
           'Open SCG Router and choose Check setup to finish.')


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
