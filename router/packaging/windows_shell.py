"""The one way installer code starts Windows PowerShell. Runs on Python 3.9+.

Launches use one flag set and no console window, and start the system copy
by absolute path unless a dialog caller passes its own tool. A value reaches a script as JSON on stdin or as a literal
from `ps_quote`, never as raw text.
"""
import json
import os
import subprocess
from pathlib import Path

# PowerShell ends a single-quoted string at any of these characters.
_QUOTES = ('\u0027', '\u2018', '\u2019', '\u201a', '\u201b')


def executable():
    """Windows PowerShell from the system directory, never a search of PATH."""
    root = os.environ.get('SystemRoot')
    if not root or not Path(root).is_absolute():
        raise FileNotFoundError('Windows system directory could not be checked')
    return str(Path(root) / 'System32/WindowsPowerShell/v1.0/powershell.exe')


def ps_quote(value):
    """A single-quoted literal that holds `value` exactly.

    A doubled quote character is one literal copy of that character, so each
    variant is doubled rather than replaced with an ASCII apostrophe.
    """
    text = str(value)
    for mark in _QUOTES:
        text = text.replace(mark, mark * 2)
    return "'" + text + "'"


def argv(script, tool=None):
    """One script without profile, logo or prompts; a dialog may pass its found tool."""
    return [tool or executable(), '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', script]


def run_script(script, run=None, **kwargs):
    """Start one script through `run` (default `subprocess.run`) without a console window.

    Hosts other than Windows have no such flag, so the value is 0 there.
    """
    kwargs.setdefault('creationflags', getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return (run or subprocess.run)(argv(script), **kwargs)


def run_json(script, request, run=None, **kwargs):
    """Send `request` as JSON on stdin and decode UTF-8 output.

    ASCII escapes keep the request independent of the console input code page.
    The script reads `[Console]::In` and sets its own UTF-8 output encoding.
    """
    return run_script(script, run, input=json.dumps(request), capture_output=True,
                      text=True, encoding='utf-8', **kwargs)
