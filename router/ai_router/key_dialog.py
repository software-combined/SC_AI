"""Platform dialogs behind the first-run key window (Plan 139).

One place owns how each OS asks for the key and how it reports a plain
message. `ai_router.key_prompt` owns the flow on
top of it. The key is written by the dialog tool to stdout; it is never
passed in argv, the environment, a file or a log.

The installer's dialog owner, `packaging/client_dialog.py`, supplies the
title, icon and platform launch (AGENTS.md section 4a). It loads only when a
dialog is drawn, so the runtime never imports installer code at startup.
"""
import functools
import importlib.util
import subprocess
import sys
from pathlib import Path

from . import dialog_tool, provider_defs

TIMEOUT_S = 900  # matches ai_router.setup.SETUP_TTL_S

def key_prompt(provider_id=None):
    """Key prompt for one provider; checked wording only when it checks."""
    defn = provider_defs.get(provider_id) or provider_defs.OPENROUTER
    checked = ('checked before it is saved' if defn.key_info_shape != 'none'
               else 'saved as you paste it; the first request checks it')
    return f'Paste the {defn.label} key you were given. It is {checked}, and kept only on this computer.'


KEY_PROMPT = key_prompt()


@functools.cache
def owner():
    """The installer's dialog owner, loaded on first use."""
    path = Path(__file__).resolve().parents[1] / 'packaging' / 'client_dialog.py'
    spec = importlib.util.spec_from_file_location('router_key_dialog_owner', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tool(platform_name=None, which=None):
    """Path to this platform's dialog tool, or None when there is no GUI."""
    return dialog_tool.tool(platform_name, which)


def _macos_script(provider_id=None):
    """One AppleScript run that returns the hidden key answer."""
    return 'text returned of (%s)' % owner().display_dialog(
        key_prompt(provider_id), ('Cancel', 'Continue'), 'Continue',
        extra=' default answer "" with hidden answer')


def _windows_script(provider_id=None):
    """One WinForms form: product icon and masked key.

    Every control goes into an explicit top-down FlowLayoutPanel. WinForms
    gives a control added straight to a Form the default Location (0, 0), so
    without a layout container the whole dialog stacks in the top-left
    corner: the key box and both buttons end up hidden behind the label and
    the operator cannot type or submit. macOS and Linux are unaffected,
    because osascript and zenity lay their own dialogs out.
    """
    picture, icon = '', owner().icon()
    if icon:
        picture = ("$i = $null; try { $i = [System.Drawing.Image]::FromFile(%s) } "
                   "catch { }; if ($i) { $pic = New-Object "
                   "System.Windows.Forms.PictureBox; $pic.Image = $i; "
                   "$pic.Size = New-Object System.Drawing.Size(48, 48); "
                   "$pic.SizeMode = 'Zoom'; "
                   "$pic.Margin = New-Object System.Windows.Forms.Padding(0, 0, 0, 8); "
                   "$p.Controls.Add($pic) }; "
                   % owner().ps_quote(icon))
    return (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "Add-Type -AssemblyName System.Drawing; "
        "[System.Windows.Forms.Application]::EnableVisualStyles(); "
        "$f = New-Object System.Windows.Forms.Form; $f.Text = %s; "
        "$f.TopMost = $true; $f.StartPosition = 'CenterScreen'; $f.Tag = 'cancel'; "
        "$f.FormBorderStyle = 'FixedDialog'; $f.MaximizeBox = $false; "
        "$f.MinimizeBox = $false; $f.AutoSize = $true; "
        "$f.AutoSizeMode = 'GrowAndShrink'; "
        "$f.Padding = New-Object System.Windows.Forms.Padding(14); "
        "$p = New-Object System.Windows.Forms.FlowLayoutPanel; "
        "$p.FlowDirection = 'TopDown'; $p.WrapContents = $false; "
        "$p.AutoSize = $true; $p.AutoSizeMode = 'GrowAndShrink'; $p.Dock = 'Fill'; "
        "%s"
        "$t = New-Object System.Windows.Forms.Label; $t.AutoSize = $true; "
        "$t.MaximumSize = New-Object System.Drawing.Size(420, 0); "
        "$t.Margin = New-Object System.Windows.Forms.Padding(0, 0, 0, 6); "
        "$t.Text = %s; $p.Controls.Add($t); "
        "$k = New-Object System.Windows.Forms.TextBox; $k.Width = 420; "
        "$k.UseSystemPasswordChar = $true; $p.Controls.Add($k); "
        "$r = New-Object System.Windows.Forms.FlowLayoutPanel; "
        "$r.FlowDirection = 'LeftToRight'; $r.WrapContents = $false; "
        "$r.AutoSize = $true; $r.AutoSizeMode = 'GrowAndShrink'; "
        "$r.Margin = New-Object System.Windows.Forms.Padding(0, 12, 0, 0); "
        "$b = New-Object System.Windows.Forms.Button; $b.Text = 'Save and connect'; "
        "$b.AutoSize = $true; "
        "$b.Add_Click({ $f.Tag = 'save'; $f.Close() }); $r.Controls.Add($b); "
        "$c = New-Object System.Windows.Forms.Button; $c.Text = 'Cancel'; "
        "$c.AutoSize = $true; "
        "$c.Add_Click({ $f.Tag = 'cancel'; $f.Close() }); $r.Controls.Add($c); "
        "$p.Controls.Add($r); $f.Controls.Add($p); "
        "$f.AcceptButton = $b; $f.CancelButton = $c; "
        "$f.Add_Shown({ $f.Activate(); $k.Focus() }); "
        "[void]$f.ShowDialog(); if ($f.Tag -ne 'save') { exit 2 }; "
        "[Console]::Out.Write($k.Text)"
        % (owner().ps_quote(owner().TITLE), picture, owner().ps_quote(key_prompt(provider_id))))


def _zenity_argv(tool_path, provider_id=None):
    defn = provider_defs.get(provider_id) or provider_defs.OPENROUTER
    return owner().zenity(tool_path, 'forms', key_prompt(provider_id), '--add-password=%s key' % defn.label)


def argv(tool_path, platform_name, provider_id=None):
    """The command that shows the key dialog on this platform."""
    if platform_name == 'darwin':
        return [tool_path, '-e', _macos_script(provider_id)]
    if platform_name == 'win32':
        return owner().powershell(_windows_script(provider_id))  # System copy, never a PATH lookup.
    return _zenity_argv(tool_path, provider_id)


def collect(tool_path, platform_name=None, run=None, provider_id=None):
    """{'key': ...} from the platform dialog, or None when the operator cancels.

    OSError means the dialog itself could not be used, so the caller falls
    back to the loopback page.
    """
    if platform_name is None:
        platform_name = sys.platform
    if run is None:
        run = subprocess.run
    result = run(argv(tool_path, platform_name, provider_id),
                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=TIMEOUT_S,
                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if (platform_name.startswith('linux') and result.returncode == 1) \
            or (platform_name == 'win32' and result.returncode == 2):
        # zenity without a display (SSH, headless) also exits 1; that is not
        # a cancel, so the caller can fall back to the loopback page.
        if 'cannot open display' in (result.stderr or '').lower():
            raise OSError('the key dialog has no display')
        return None
    if result.returncode:
        stderr = result.stderr or ''
        # AppleScript reports cancel as error -128, and macOS spells it
        # "cancelled" in some versions; match either, since a missed cancel
        # is treated as a dialog failure and opens the browser fallback.
        if 'User cancel' in stderr or '(-128)' in stderr:
            return None
        raise OSError('the key dialog did not complete')
    # The tool may add a trailing newline; strip it. A blank key stays blank,
    # so the caller asks again.
    return {'key': (result.stdout or '').strip()}


def message_argv(tool_path, message, platform_name):
    """The command that shows a plain native message."""
    dialog = owner()
    if platform_name == 'darwin':
        return [tool_path, '-e', dialog.display_dialog(message, ('OK',), 'OK')]
    if platform_name == 'win32':
        return dialog.powershell(dialog.windows_form(message, False, ('OK',)))
    return dialog.zenity(tool_path, 'info', message)


def message(tool_path, text, platform_name=None, run=None):
    """Best-effort native message; a missing dialog tool is not an error."""
    if platform_name is None:
        platform_name = sys.platform
    if run is None:
        run = subprocess.run
    try:
        run(message_argv(tool_path, text, platform_name), stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=60, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except (OSError, subprocess.SubprocessError):
        pass
