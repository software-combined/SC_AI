"""The router's one dialog owner, in the popup style of AGENTS.md 4a.

Runs on the installer's Python 3.9 with no router imports. It holds the
title, the bundled icon and how each platform draws a window: macOS through
osascript, Windows through `windows_shell` and Linux through the dialog tool
that `ai_router/dialog_tool.py` finds. Callers keep their own wording, flow
and answers; they never restate the title or icon or start a dialog tool
themselves. It also asks the shared single-select question.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loader  # noqa: E402
_tool = loader.load(Path(__file__).resolve().parents[1] / 'ai_router/dialog_tool.py')
_shell = loader.load(Path(__file__).resolve().with_name('windows_shell.py'))
ps_quote = _shell.ps_quote  # One PowerShell literal rule for every Windows dialog.

TITLE = 'SCG Router'
ICON = Path(__file__).resolve().parent / 'assets' / 'router-icon.png'


def tool(platform_name=None, which=None, home=None):
    """This platform's dialog tool, or None when the machine has no GUI."""
    return _tool.tool(platform_name, which, home)


def quote(text):
    """An AppleScript or JavaScript string; raw UTF-8, since AppleScript has no unicode escape."""
    return json.dumps(text, ensure_ascii=False)


def icon():
    """The bundled icon, or None when the asset is not installed."""
    return str(ICON) if ICON.is_file() else None


def display_dialog(message, buttons, default, cancel=None, shown=None, extra=''):
    """One macOS `display dialog` expression; `shown` replaces the bundled icon, and no icon draws the note."""
    shown = icon() if shown is None else shown
    cancel_clause = ' cancel button %s' % quote(cancel) if cancel else ''
    icon_spec = '(POSIX file %s)' % quote(str(shown)) if shown else 'note'
    return ('display dialog %s with title %s buttons {%s} default button %s%s%s with icon %s'
            % (quote(str(message)), quote(TITLE), ', '.join(map(quote, buttons)), quote(default),
               cancel_clause, extra, icon_spec))


def dialog_script(message, confirm=False, labels=('Continue', 'Cancel')):
    """A notice or confirmation: the last label is the safe action, a confirmation's action the default."""
    safe = labels[-1]
    if not confirm:
        return display_dialog(message, (safe,), safe, safe)
    return display_dialog(message, (safe, labels[0]), labels[0], safe)


def zenity(tool_path, kind, text, *options, shown=None):
    """argv for one Linux window of `kind`; `tool_path` comes from `tool()`."""
    shown = icon() if shown is None else shown
    argv = [tool_path, '--' + kind, '--title=' + TITLE]
    if shown:
        argv.append('--window-icon=' + shown)
    return argv + ['--text=' + text, *options]


def powershell(script, tool_path=None):
    """argv for one Windows script through the shared PowerShell launcher."""
    return _shell.argv(script, tool_path)


def windows_form(message, confirm, labels=('Continue', 'Cancel')):
    """The styled notice or confirmation form; prints its answer marker.

    Bitmap icon and layout containers match the question; text width is constrained.
    """
    ps = _shell.ps_quote
    action = ("$b=New-Object System.Windows.Forms.Button;$b.Text=%s;"
              "$b.AutoSize=$true;$b.DialogResult='OK';$r.Controls.Add($b);$f.AcceptButton=$b;"
              % ps(labels[0])) if confirm else ''
    return (
        "$ErrorActionPreference='Stop';Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
        "$f=New-Object System.Windows.Forms.Form;$f.Text=%s;"
        "$f.Icon=[System.Drawing.Icon]::FromHandle((New-Object System.Drawing.Bitmap %s).GetHicon());"
        "$f.AutoSize=$true;$f.AutoSizeMode='GrowAndShrink';"
        "$p=New-Object System.Windows.Forms.FlowLayoutPanel;"
        "$p.FlowDirection='TopDown';$p.WrapContents=$false;$p.AutoSize=$true;"
        "$p.Padding=New-Object System.Windows.Forms.Padding(12);"
        "$l=New-Object System.Windows.Forms.Label;$l.Text=%s;"
        "$l.MaximumSize=New-Object System.Drawing.Size(440,0);$l.AutoSize=$true;"
        "$r=New-Object System.Windows.Forms.FlowLayoutPanel;$r.AutoSize=$true;"
        "$r.FlowDirection='LeftToRight';$r.WrapContents=$false;"
        "%s$c=New-Object System.Windows.Forms.Button;$c.Text=%s;"
        "$c.AutoSize=$true;$c.DialogResult='Cancel';$r.Controls.Add($c);"
        "$f.CancelButton=$c;$p.Controls.Add($l);$p.Controls.Add($r);$f.Controls.Add($p);"
        "if($f.ShowDialog() -eq 'OK'){'SCG_ROUTER_DIALOG_RESULT=accept';exit 0}"
        "else{'SCG_ROUTER_DIALOG_RESULT=cancel';exit 1}"
        % (ps(TITLE), ps(ICON), ps(message), action, ps(labels[-1])))


def notice_argv(message, platform_name, confirm, labels=('Continue', 'Cancel'), tool_path=None):
    """argv for one notice (one safe button) or confirmation (action, then safe)."""
    if platform_name == 'darwin':
        return [tool_path or '/usr/bin/osascript', '-e', dialog_script(message, confirm, labels)]
    if platform_name == 'win32':
        return powershell(windows_form(message, confirm, labels), tool_path)
    tool_path = tool_path or tool(platform_name)
    if not tool_path:
        raise FileNotFoundError('no dialog tool')
    options = ['--width=460', '--ok-label=' + (labels[0] if confirm else labels[-1])]
    if confirm:
        options.append('--cancel-label=' + labels[1])
    return zenity(tool_path, 'question' if confirm else 'info', str(message), *options)


def _labels(items):
    return [label for _key, label in items]


def _macos_script(question, items, labels):
    """A native popup menu keeps the question to two action buttons."""
    return ('ObjC.import("AppKit");\n'
            'function run() {\n'
            '    var app = $.NSApplication.sharedApplication;\n'
            '    app.setActivationPolicy($.NSApplicationActivationPolicyAccessory);\n'
            '    var alert = $.NSAlert.alloc.init;\n'
            '    alert.messageText = %s;\n'
            '    alert.window.title = %s;\n'
            '    alert.informativeText = %s;\n'
            '    alert.icon = $.NSImage.alloc.initWithContentsOfFile(%s);\n'
            '    var picker = $.NSPopUpButton.alloc.initWithFramePullsDown('
            '$.NSMakeRect(0, 0, 260, 26), false);\n'
            '    picker.addItemsWithTitles(%s);\n'
            '    picker.sizeToFit;\n'
            '    picker.selectItemAtIndex(0);\n'
            '    alert.accessoryView = picker;\n'
            '    alert.addButtonWithTitle(%s);\n'
            '    alert.addButtonWithTitle(%s).keyEquivalent = "\\u001b";\n'
            '    app.activateIgnoringOtherApps(true);\n'
            '    if (alert.runModal !== $.NSAlertFirstButtonReturn) return "";\n'
            '    return ObjC.unwrap(picker.titleOfSelectedItem);\n'
            '}\n' % (quote(TITLE), quote(TITLE), quote(question),
                     quote(str(ICON)), quote(_labels(items)), *map(quote, labels)))


def _windows_script(question, items, labels):
    """One PowerShell question: a small list with Continue and Cancel.

    Every control sits in a layout panel: WinForms gives a control added
    straight to a form the location (0, 0), so a flat script stacks the
    list and both buttons in the corner (found live on Windows).
    """
    shown, ps = icon(), _shell.ps_quote
    icon_line = ("$f.Icon = [System.Drawing.Icon]::FromHandle("
                 "(New-Object System.Drawing.Bitmap %s).GetHicon()); " % ps(shown)) if shown else ''
    choices = ','.join(ps(label) for label in _labels(items))
    return ("Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
            "$f = New-Object System.Windows.Forms.Form; $f.TopMost = $true; "
            "$f.AutoSize = $true; $f.AutoSizeMode = 'GrowAndShrink'; $f.StartPosition = 'CenterScreen'; "
            "$f.Text = %s; %s"
            "$p = New-Object System.Windows.Forms.FlowLayoutPanel; "
            "$p.FlowDirection = 'TopDown'; $p.WrapContents = $false; "
            "$p.AutoSize = $true; $p.Dock = 'Fill'; "
            "$p.Padding = New-Object System.Windows.Forms.Padding(12); "
            "$l = New-Object System.Windows.Forms.Label; "
            "$l.Text = %s; $l.AutoSize = $true; $l.MaximumSize = '640,0'; "
            "$b = New-Object System.Windows.Forms.ListBox; "
            "@(%s) | ForEach-Object { [void]$b.Items.Add($_) }; "
            "$b.Width = [Math]::Min(640, [Math]::Max(260, (($b.Items | ForEach-Object { "
            "[System.Windows.Forms.TextRenderer]::MeasureText([string]$_, $b.Font).Width "
            "} | Measure-Object -Maximum).Maximum + 32))); "
            "$b.Height = [Math]::Min(8, $b.Items.Count) * $b.ItemHeight + 6; $b.HorizontalScrollbar = $true; "
            "$b.SelectionMode = 'One'; $b.SelectedIndex = 0; "
            "$r = New-Object System.Windows.Forms.FlowLayoutPanel; "
            "$r.FlowDirection = 'LeftToRight'; $r.WrapContents = $false; "
            "$r.AutoSize = $true; "
            "$ok = New-Object System.Windows.Forms.Button; $ok.Text = %s; "
            "$ok.AutoSize = $true; $ok.DialogResult = 'OK'; "
            "$c = New-Object System.Windows.Forms.Button; $c.Text = %s; "
            "$c.AutoSize = $true; $c.DialogResult = 'Cancel'; "
            "$r.Controls.Add($ok); $r.Controls.Add($c); "
            "$p.Controls.Add($l); $p.Controls.Add($b); $p.Controls.Add($r); "
            "$f.Controls.Add($p); $f.AcceptButton = $ok; "
            "$f.CancelButton = $c; "
            "$f.Add_Shown({ $f.Activate(); $b.Focus() }); "
            "if ($f.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) "
            "{ exit 2 }; Write-Output $b.SelectedItem"
            % (ps(TITLE), icon_line, ps(question), choices, *map(ps, labels)))


def _zenity_argv(tool_path, question, items, labels):
    argv = zenity(tool_path, 'list', question, '--radiolist', '--column=', '--column=',
                  '--print-column=2', '--ok-label=' + labels[0], '--cancel-label=' + labels[1])
    for index, label in enumerate(_labels(items)):
        argv += ['TRUE' if index == 0 else 'FALSE', label]
    return argv


def argv(tool_path, platform_name, question, items, *, labels=('Continue', 'Cancel')):
    """The command that asks one single-select question on this platform."""
    if platform_name == 'darwin':
        return [tool_path, '-l', 'JavaScript', '-e', _macos_script(question, items, labels)]
    if platform_name == 'win32':
        return powershell(_windows_script(question, items, labels), tool_path)
    return _zenity_argv(tool_path, question, items, labels)


def answer(platform_name, stdout, items):
    """The chosen item's key, or None when nothing usable came back."""
    text = (stdout or '').strip()
    for key, label in items:
        if text == label:
            return key
    return None
