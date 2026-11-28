"""One style for every dialog the router shows (docs/UI-UX.md).

`packaging/client_dialog.py` owns the title, the icon and each platform's
dialog launch; this test pins that ownership and the shared vocabulary.
"""
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from ai_router import key_dialog

from tests.loading import load

_ROOT = Path(__file__).resolve().parents[1]

# Internals a non-technical operator should never read in a dialog.
JARGON = ('nonce', 'loopback', 'catalogue', 'owner-only', '127.0.0.1',
          'token', 'endpoint', 'process', 'daemon')


def _notice():
    return load(_ROOT / 'packaging' / 'notice.py', 'router_notice')


def _dialog():
    """The single-select question, which is not importable as part of a package."""
    return load(_ROOT / 'packaging' / 'client_dialog.py', 'router_client_dialog')


QUESTION = ('What would you like to do?', (('resume', 'Update or repair'), ('status', 'Check setup')))


def _offer():
    """The Switch Codex offer, with its dialog tool found on every platform."""
    return load(_ROOT / 'packaging' / 'codex_switch_offer.py', 'router_codex_switch_offer')


def _warning():
    return load(_ROOT / 'packaging' / 'update_warning.py', 'router_warning_copy')


def _popup_text():
    """Every user-visible string the dialog producers can show."""
    notice = _notice()
    dialog = _dialog()
    offer = _offer()
    completion = load(_ROOT / 'packaging' / 'setup_completion.py', 'router_setup_completion_style')
    text = [notice._message('0.6.25'),
            notice._message('0.6.25', names=['Z.ai: GLM 5.3 Flash', '+2 more'])]
    text += [completion.finish_message(clients) for clients in ({}, {'codex': {}}, {'claude-desktop': {}})]
    text += list(offer.MESSAGES.values()) + [offer.BACK_OPENROUTER]
    warning = _warning()
    text.append(warning.message(dict(clients={'codex': {}, 'claude': {}}, update={})))
    for platform_name, tool_path in (('darwin', '/usr/bin/osascript'),
                                     ('linux', '/usr/bin/zenity'),
                                     ('win32', 'C:/powershell.exe')):
        text.append(' '.join(key_dialog.argv(tool_path, platform_name)))
        text.append(' '.join(key_dialog.message_argv(tool_path, 'message',
                                                     platform_name)))
        text.append(' '.join(dialog.argv(tool_path, platform_name, *QUESTION)))
    return ' '.join(text).lower()


# Files that may name a dialog tool or draw a window without the owner.
OWNER = 'packaging/client_dialog.py'
EXEMPT = {
    'ai_router/dialog_tool.py': 'finds the dialog tool the owner uses',
    'ai_router/key_dialog.py': "the key window's masked entry form",
    'packaging/codex_switch_launch.py': 'a self-contained copy that runs beside older releases',
    'packaging/native/native_build.py': 'build tooling, not a dialog',
    'packaging/native/native_linux_gui.py': 'bundles the Linux dialog tool at build time',
    'packaging/windows_shell.py': 'the one PowerShell launcher the owner uses',
}
MARKERS = ('display dialog', 'NSAlert', '--window-icon', '--title', 'System.Windows.Forms.Form', 'MessageBox')


def _dialog_code(path):
    """Module-level TITLE or ICON names and dialog launch strings in one file."""
    tree = ast.parse(path.read_text(encoding='utf-8'))
    found = []
    for statement in tree.body:
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            found += [node.id for node in ast.walk(statement)
                      if isinstance(node, ast.Name) and node.id in ('TITLE', 'ICON')]
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            found += [mark for mark in MARKERS if mark in node.value]
            if node.value in ('zenity', '-Command'):
                found.append(node.value)
    return found


class PopupStyleTests(unittest.TestCase):
    def test_only_the_owner_names_the_title_icon_or_dialog_tools(self):
        files = sorted((_ROOT / 'packaging').rglob('*.py')) + sorted((_ROOT / 'ai_router').rglob('*.py'))
        for path in files:
            rel = path.relative_to(_ROOT).as_posix()
            if rel != OWNER and rel not in EXEMPT:
                with self.subTest(rel):
                    self.assertEqual(_dialog_code(path), [], 'ask packaging/client_dialog.py instead')
        self.assertEqual(sorted(_dialog_code(_ROOT / OWNER)[:2]), ['ICON', 'TITLE'])

    def test_shared_title(self):
        self.assertEqual(_dialog().TITLE, key_dialog.owner().TITLE, 'SCG Router')

    def test_shared_icon_asset(self):
        icon = _dialog().ICON
        self.assertEqual(icon, key_dialog.owner().ICON)
        self.assertEqual(icon, _ROOT / 'packaging' / 'assets' / 'router-icon.png')
        self.assertTrue(icon.is_file())

    def test_every_platform_carries_the_icon(self):
        for platform_name, tool_path in (('darwin', '/usr/bin/osascript'),
                                         ('linux', '/usr/bin/zenity'),
                                         ('win32', 'C:/powershell.exe')):
            with self.subTest(platform_name):
                blob = ' '.join(key_dialog.argv(tool_path, platform_name))
                self.assertIn(_dialog().ICON.name, blob)
        self.assertIn('POSIX file', _notice()._darwin_script('0.6.25', '/icon.png'))

    def test_no_jargon_in_user_visible_text(self):
        text = _popup_text()
        for word in JARGON:
            with self.subTest(word):
                self.assertNotIn(word, text)

    def test_bedrock_dialog_names_its_own_key(self):
        for platform_name, tool_path in (('darwin', '/usr/bin/osascript'),
                                         ('linux', '/usr/bin/zenity'),
                                         ('win32', 'C:/powershell.exe')):
            with self.subTest(platform_name):
                blob = ' '.join(key_dialog.argv(
                    tool_path, platform_name, provider_id='bedrock'))
                self.assertIn('aws bedrock key', blob.lower())
                self.assertIn(_dialog().TITLE, blob)
                self.assertIn('saved as you paste it', blob.lower())

    def test_plain_language_prompts(self):
        text = _popup_text()
        self.assertIn('openrouter key', text)
        self.assertIn('chatgpt subscription', text)
        self.assertIn('codex', text)
        self.assertTrue('reopen codex' in text or 'restart codex' in text,
                        'the dialog tells the operator what to do next')

    def test_the_safe_action_is_always_offered(self):
        macos = key_dialog.argv('/usr/bin/osascript', 'darwin')[-1]
        self.assertIn('"Cancel"', macos)
        self.assertIn("'Cancel'", key_dialog.argv('C:/powershell.exe', 'win32')[-1])

    def test_windows_dialog_lays_every_control_out(self):
        # WinForms gives a control added straight to a form the Location
        # (0, 0), so with no layout container every control stacks in the
        # corner: the key box and both buttons are covered and unusable.
        # Found live on Windows, 2026-09-16.
        script = key_dialog.argv('C:/powershell.exe', 'win32')[-1]
        self.assertEqual(script.count('$f.Controls.Add('), 1,
                         'only the layout panel belongs to the form itself')
        for control in ('$p.Controls.Add($pic)', '$p.Controls.Add($t)',
                        '$p.Controls.Add($k)', '$p.Controls.Add($r)',
                        '$r.Controls.Add($b)', '$r.Controls.Add($c)'):
            with self.subTest(control):
                self.assertIn(control, script)

    def test_every_platform_question_carries_the_icon(self):
        dialog = _dialog()
        for platform_name, tool_path in (('darwin', '/usr/bin/osascript'),
                                         ('linux', '/usr/bin/zenity'),
                                         ('win32', 'C:/powershell.exe')):
            with self.subTest(platform=platform_name):
                blob = ' '.join(dialog.argv(tool_path, platform_name, *QUESTION))
                self.assertIn(dialog.ICON.name, blob)
                self.assertIn(dialog.TITLE, blob)

    def test_the_question_uses_selection_controls_and_two_actions(self):
        dialog = _dialog()
        question, items = QUESTION
        macos = dialog.argv('/usr/bin/osascript', 'darwin', question, items)[-1]
        self.assertIn('NSPopUpButton', macos)
        self.assertEqual(macos.count('addButtonWithTitle('), 2)
        self.assertIn('addButtonWithTitle("Continue")', macos)
        self.assertIn('addButtonWithTitle("Cancel")', macos)
        windows = dialog.argv('C:/powershell.exe', 'win32', question, items)[-1]
        self.assertIn('System.Windows.Forms.ListBox', windows)
        self.assertEqual(windows.count('System.Windows.Forms.Button'), 2)
        self.assertIn("'Continue'", windows)
        self.assertIn("'Cancel'", windows)
        self.assertIn('$f.CancelButton = $c', windows)
        linux = dialog.argv('/usr/bin/zenity', 'linux', question, items)
        self.assertIn('--radiolist', linux)
        self.assertIn('--ok-label=Continue', linux)
        self.assertIn('--cancel-label=Cancel', linux)

    def test_the_codex_offer_shares_the_style(self):
        offer = _offer()
        for kind in offer.MESSAGES:
            with self.subTest(kind=kind):
                script = _dialog().dialog_script(offer.MESSAGES[kind], True, ('Open Switch Codex', 'Later'))
                self.assertIn('with title "SCG Router"', script)
                self.assertIn('router-icon.png', script)
                self.assertIn('buttons {"Later", "Open Switch Codex"}', script)
                self.assertIn('cancel button "Later"', script)
                message = offer.MESSAGES[kind].lower()
                for words in ('the chatgpt app (codex)', 'chatgpt subscription',
                              'openrouter models'):
                    self.assertIn(words, message)

    def test_confirmations_default_to_the_action_and_notices_offer_ok(self):
        platform = load(_ROOT / 'packaging' / 'claude_desktop_platform.py', 'router_claude_desktop_platform')
        dialog = platform._dialogs
        self.assertIn('buttons {"Cancel", "Continue"} default button "Continue" cancel button "Cancel"',
                      dialog.dialog_script('Switch Claude to OpenRouter?', True))
        # Setup progress keeps Cancel: it is the only way to stop setup.
        self.assertIn('buttons {"Cancel"}', dialog.dialog_script('Setting up SCG Router.'))
        calls = []
        run = lambda argv, **_: calls.append(argv) or SimpleNamespace(returncode=0, stdout='', stderr='')
        with mock.patch.object(dialog, 'tool', return_value='/usr/bin/zenity'):
            for name in ('darwin', 'win32', 'linux'):
                platform.show_message('SCG Router is up to date.', name, run=run)
        self.assertIn('buttons {"OK"} default button "OK"', calls[0][-1])
        self.assertIn("$c.Text='OK'", calls[1][-1])
        self.assertIn('--ok-label=OK', calls[2])
        self.assertNotIn('Cancel', ' '.join(calls[0] + calls[2]))

    def test_windows_question_lays_every_control_out(self):
        script = _dialog().argv('C:/powershell.exe', 'win32', *QUESTION)[-1]
        self.assertEqual(script.count('$f.Controls.Add('), 1,
                         'only the layout panel belongs to the form itself')
        for control in ('$p.Controls.Add($l)', '$p.Controls.Add($b)',
                        '$p.Controls.Add($r)', '$r.Controls.Add($ok)',
                        '$r.Controls.Add($c)'):
            with self.subTest(control):
                self.assertIn(control, script)


class WarningCopyTests(unittest.TestCase):
    def test_warning_names_failed_parts_and_keeps_only_the_safety_rule(self):
        warning = _warning()
        cases = (({'controls': 'failed'}, 'Router controls need repair.'),
                 ({'controller': 'failed', 'scheduler': 'failed'},
                  'Updates and scheduled checks need repair.'),
                 ({key: 'failed' for key in warning.COMPONENT_LABELS},
                  'Updates, scheduled checks, assistant connections and router controls need repair.'))
        for repairs, first in cases:
            with self.subTest(repairs=repairs):
                doc = dict(routing_healthy=True, update=dict(component_repairs=repairs))
                self.assertEqual(warning.message(doc), first + '\nSCG Router is still running. '
                                 'Finish active work before you repair.')

    def test_warning_omits_health_and_support_metadata(self):
        warning = _warning()
        doc = dict(running_version='1.2.6.174', channel='beta', routing_healthy=False,
                   update=dict(installation_repair_required=True,
                               latest_known_version='1.3.2.185'))
        self.assertEqual(warning.message(doc), 'An update or repair did not finish.\n'
                         'Finish active work before you repair.')


if __name__ == '__main__':
    unittest.main()
