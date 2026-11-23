"""Offline regressions for the one single-select question every platform shows."""
import unittest
from pathlib import Path

from tests.loading import load


_ROOT = Path(__file__).resolve().parents[1]
dialog = load(_ROOT / 'packaging' / 'client_dialog.py', 'router_client_dialog')


QUESTION = 'What would you like to do?'
ITEMS = (('resume', 'Update or repair'), ('status', 'Check setup'), ('key', 'Set up model access'))


class ClientDialogTests(unittest.TestCase):
    def test_macos_accepts_only_continue(self):
        command = dialog.argv('/usr/bin/osascript', 'darwin', QUESTION, ITEMS)
        self.assertEqual(command[:4], ['/usr/bin/osascript', '-l', 'JavaScript', '-e'])
        self.assertIn('alert.runModal !== $.NSAlertFirstButtonReturn', command[-1])
        self.assertIn('return ""', command[-1])
        self.assertIn('ObjC.unwrap(picker.titleOfSelectedItem)', command[-1])

    def test_windows_close_and_escape_require_explicit_continue(self):
        script = dialog.argv('powershell', 'win32', QUESTION, ITEMS)[-1]
        self.assertIn("$ok.DialogResult = 'OK'", script)
        self.assertIn("$c.DialogResult = 'Cancel'", script)
        self.assertIn('$f.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK', script)
        self.assertIn('$f.TopMost = $true', script)
        self.assertIn('$f.Add_Shown({ $f.Activate(); $b.Focus() })', script)

    def test_linux_offers_every_item_with_a_single_default(self):
        command = dialog.argv('zenity', 'linux', QUESTION, ITEMS)
        self.assertEqual(command[-6:], ['TRUE', 'Update or repair', 'FALSE', 'Check setup',
                                        'FALSE', 'Set up model access'])

    def test_answer_maps_a_label_back_to_its_key(self):
        self.assertEqual(dialog.answer('linux', 'Check setup\n', ITEMS), 'status')
        self.assertIsNone(dialog.answer('linux', 'Something else', ITEMS))


if __name__ == '__main__':
    unittest.main()
