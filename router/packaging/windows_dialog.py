"""Verified native Windows dialogs; the dialog owner's styled form is the fallback."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loader  # noqa: E402


def _load(name):
    return loader.load(Path(__file__).with_name(name + '.py'))


_dialog = _load('client_dialog')


def command(home, mode, text, labels):
    resources = _load('native_resources').current(home)
    metadata = _load('native_payload').metadata(resources)
    helper = resources / 'control/scg-router-menu.exe'
    icon = resources / 'router/packaging/assets/router-icon.png'
    if not metadata.get('menu_sha256') or not icon.is_file():
        raise OSError('The switch window is unavailable')
    if tuple(map(int, metadata['version'].split('.')[:3])) < (1, 3, 17):
        return _powershell(text, len(labels) > 1, labels), '', resources, metadata
    request = json.dumps(dict(text=text, labels=list(labels)), ensure_ascii=False) + '\n'
    return [str(helper), mode, str(icon)], request, resources, metadata


def show(text, home, confirm, run=subprocess.run, *, labels=('Continue', 'Cancel')):
    args, request, resources, doc = command(home, '--dialog', text, labels if confirm else labels[-1:])
    try:
        env = _load('native_payload').windows_helper_env(home, resources, doc)
        result = run(args, input=request, capture_output=True, text=True, encoding='utf-8',
                     timeout=120, creationflags=0x08000000, env=env)
    except OSError:
        # Endpoint protection can refuse the helper; the styled script keeps the action available.
        result = run(_powershell(text, confirm, labels), capture_output=True, text=True,
                     encoding='utf-8', timeout=120, creationflags=0x08000000)
    markers = [line for line in (result.stdout or '').splitlines()
               if line.startswith('SCG_ROUTER_DIALOG_RESULT=')]
    if result.returncode == 0 and markers == ['SCG_ROUTER_DIALOG_RESULT=accept']:
        return True
    if result.returncode == 1 and markers == ['SCG_ROUTER_DIALOG_RESULT=cancel']:
        return False
    raise _load('windows_native').NativeError('confirmation', 'invalid_response', result.returncode)


def progress(home, text, button):
    args, request, resources, doc = command(home, '--progress', text, (button,))
    try:
        env = _load('native_payload').windows_helper_env(home, resources, doc)
        child = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, text=True, encoding='utf-8', creationflags=0x08000000, env=env)
    except OSError:
        return subprocess.Popen(_powershell(text, False, (button,)), stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True, encoding='utf-8',
            creationflags=0x08000000)
    try:
        child.stdin.write(request)
        child.stdin.flush()
    except OSError:
        child.terminate()
        child.communicate(timeout=5)
        raise
    return child


def _powershell(text, confirm, labels):
    """The owner's styled form, for old packages or a helper that cannot start."""
    return _dialog.powershell(_dialog.windows_form(text, confirm, labels))
