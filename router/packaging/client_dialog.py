"""One single-select question in the router's popup style.

Runs on the installer's Python 3.9 with no router imports, next to the
update notice and the first-run key window, and follows the same popup
style (AGENTS.md 4a): the title `SCG Router`, the bundled icon, plain
language, a single selection and two actions with the safe one last.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loader  # noqa: E402
_tool = loader.load(Path(__file__).resolve().parents[1] / 'ai_router/dialog_tool.py')
_shell = loader.load(Path(__file__).resolve().with_name('windows_shell.py'))

TITLE = 'SCG Router'
ICON = Path(__file__).resolve().parent / 'assets' / 'router-icon.png'


def tool(platform_name=None, which=None, home=None):
    """This platform's dialog tool, or None when the machine has no GUI."""
    return _tool.tool(platform_name, which, home)


def _quote(text):
    return json.dumps(text, ensure_ascii=False)


def _icon():
    return str(ICON) if ICON.is_file() else None


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
            '}\n' % (_quote(TITLE), _quote(TITLE), _quote(question),
                     _quote(str(ICON)), _quote(_labels(items)), *map(_quote, labels)))


def _windows_script(question, items, labels):
    """One PowerShell question: a small list with Continue and Cancel.

    Every control sits in a layout panel: WinForms gives a control added
    straight to a form the location (0, 0), so a flat script stacks the
    list and both buttons in the corner (found live on Windows).
    """
    icon, quote = _icon(), _shell.ps_quote
    icon_line = ("$f.Icon = [System.Drawing.Icon]::FromHandle("
                 "(New-Object System.Drawing.Bitmap %s).GetHicon()); " % quote(icon)) if icon else ''
    choices = ','.join(quote(label) for label in _labels(items))
    return ("Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
            "$f = New-Object System.Windows.Forms.Form; $f.TopMost = $true; "
            "$f.AutoSize = $true; $f.AutoSizeMode = 'GrowAndShrink'; $f.StartPosition = 'CenterScreen'; "
            "$f.Text = '%s'; %s"
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
            % (TITLE, icon_line, quote(question), choices, *map(quote, labels)))


def _zenity_argv(tool_path, question, items, labels):
    argv = [tool_path, '--list', '--radiolist', '--title=' + TITLE,
            '--text=' + question, '--column=', '--column=', '--print-column=2',
            '--ok-label=' + labels[0], '--cancel-label=' + labels[1]]
    if _icon():
        argv.append('--window-icon=' + _icon())
    for index, label in enumerate(_labels(items)):
        argv += ['TRUE' if index == 0 else 'FALSE', label]
    return argv


def argv(tool_path, platform_name, question, items, *, labels=('Continue', 'Cancel')):
    """The command that asks one single-select question on this platform."""
    if platform_name == 'darwin':
        return [tool_path, '-l', 'JavaScript', '-e', _macos_script(question, items, labels)]
    if platform_name == 'win32':
        return _shell.argv(_windows_script(question, items, labels), tool_path)
    return _zenity_argv(tool_path, question, items, labels)


def answer(platform_name, stdout, items):
    """The chosen item's key, or None when nothing usable came back."""
    text = (stdout or '').strip()
    for key, label in items:
        if text == label:
            return key
    return None
