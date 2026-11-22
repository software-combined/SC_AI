"""Native key window: platform dialogs, the submit flow and its fallbacks."""
import io
import json
import subprocess
import sys
import threading
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from ai_router import key_dialog, key_prompt, provider_defs

KEY = 'sk-or-v1-secret'


def _ok(stdout):
    return subprocess.CompletedProcess([], 0, stdout=stdout, stderr='')


class ToolTests(unittest.TestCase):
    def test_tool_per_platform(self):
        which = lambda name: '/usr/bin/' + name  # noqa: E731
        self.assertTrue(key_dialog.tool('darwin', which).endswith('osascript'))
        self.assertTrue(key_dialog.tool('linux', which).endswith('zenity'))
        self.assertTrue(key_dialog.tool('win32', which).endswith('powershell'))
        self.assertIsNone(key_dialog.tool('plan9', which))

    def test_linux_needs_zenity(self):
        self.assertIsNone(key_dialog.tool('linux', lambda name: None))


class DialogArgvTests(unittest.TestCase):
    def test_macos_asks_only_for_the_key(self):
        argv = key_dialog.argv('/usr/bin/osascript', 'darwin')
        script = argv[argv.index('-e') + 1]
        self.assertIn('with hidden answer', script)
        self.assertIn('buttons {"Cancel", "Continue"}', script)
        self.assertEqual(script.count('display dialog'), 1)
        self.assertIn(key_dialog.ICON.name, script)

    def test_windows_form_masks_the_key(self):
        argv = key_dialog.argv(r'C:\powershell.exe', 'win32')
        script = argv[argv.index('-Command') + 1]
        self.assertIn('UseSystemPasswordChar = $true', script)
        self.assertNotIn('ComboBox', script)
        self.assertTrue(script.endswith('[Console]::Out.Write($k.Text)'))
        self.assertIn(key_dialog.ICON.name, script)

    def test_linux_zenity_form_fields(self):
        argv = key_dialog.argv('/usr/bin/zenity', 'linux')
        self.assertIn('--forms', argv)
        self.assertIn('--add-password=%s key' % provider_defs.OPENROUTER.label, argv)
        self.assertFalse([arg for arg in argv if arg.startswith('--add-combo')])
        self.assertIn('--window-icon=' + str(key_dialog.ICON), argv)

    def test_no_subscription_or_starter_question_is_asked(self):
        for platform_name, tool_path in (('darwin', '/usr/bin/osascript'),
                                         ('linux', '/usr/bin/zenity'),
                                         ('win32', 'C:/powershell.exe')):
            with self.subTest(platform_name):
                text = ' '.join(key_dialog.argv(tool_path, platform_name)).lower()
                for words in ('subscription', 'write for you', 'everyday help', 'coding help'):
                    self.assertNotIn(words, text)

    def test_the_key_never_reaches_argv(self):
        for platform_name, tool_path in (('darwin', '/usr/bin/osascript'),
                                         ('linux', '/usr/bin/zenity'),
                                         ('win32', 'C:/powershell.exe')):
            with self.subTest(platform_name):
                self.assertNotIn(KEY, ' '.join(key_dialog.argv(tool_path, platform_name)))


class CollectTests(unittest.TestCase):
    def test_each_platform_returns_only_the_key(self):
        for platform_name, out in (('darwin', KEY + '\n'), ('linux', KEY + '\n'),
                                   ('win32', KEY + '\r\n')):
            with self.subTest(platform_name):
                run = lambda argv, out=out, **kw: _ok(out)  # noqa: E731
                self.assertEqual(key_dialog.collect('/a', platform_name, run), {'key': KEY})

    def test_blank_key_comes_back_blank_for_a_reprompt(self):
        for out in ('', '\n'):
            run = lambda argv, out=out, **kw: _ok(out)  # noqa: E731
            self.assertEqual(key_dialog.collect('/usr/bin/osascript', 'darwin', run),
                             {'key': ''})

    def test_cancelling_each_platform(self):
        darwin = lambda argv, **kw: subprocess.CompletedProcess(  # noqa: E731
            [], 1, stdout='', stderr='execution error: User canceled. (-128)')
        darwin_british = lambda argv, **kw: subprocess.CompletedProcess(  # noqa: E731
            [], 1, stdout='', stderr='execution error: User cancelled. (-128)')
        linux = lambda argv, **kw: subprocess.CompletedProcess(  # noqa: E731
            [], 1, stdout='', stderr='')
        win32 = lambda argv, **kw: subprocess.CompletedProcess(  # noqa: E731
            [], 2, stdout='', stderr='')
        self.assertIsNone(key_dialog.collect('/a', 'darwin', darwin))
        self.assertIsNone(key_dialog.collect('/a', 'darwin', darwin_british))
        self.assertIsNone(key_dialog.collect('/a', 'linux', linux))
        self.assertIsNone(key_dialog.collect('/a', 'win32', win32))

    def test_headless_zenity_is_not_a_cancel(self):
        headless = lambda argv, **kw: subprocess.CompletedProcess(  # noqa: E731
            [], 1, stdout='', stderr='Gtk-WARNING: cannot open display:')
        with self.assertRaises(OSError):
            key_dialog.collect('/usr/bin/zenity', 'linux', headless)

    def test_failed_dialog_is_an_error(self):
        run = lambda argv, **kw: subprocess.CompletedProcess(  # noqa: E731
            [], 1, stdout='', stderr='synthetic failure')
        with self.assertRaises(OSError):
            key_dialog.collect('/usr/bin/osascript', 'darwin', run)


class SubmitTests(unittest.TestCase):
    def _response(self, payload, status=200):
        class Resp:
            def __init__(self):
                self.status = status
            def __enter__(self):
                return self
            def __exit__(self, *exc):
                return False
            def read(self):
                return json.dumps(payload).encode()
        return Resp()

    def test_posts_form_encoded_with_json_accept(self):
        seen = {}

        def opener(request, timeout=None):
            seen['url'] = request.full_url
            seen['body'] = request.data.decode()
            seen['accept'] = request.get_header('Accept')
            return self._response({'ok': True, 'label': 'probe'})

        status, payload = key_prompt.submit(
            'http://127.0.0.1:1/t/setup/n',
            {'key': KEY}, opener)
        self.assertEqual((status, payload['label']), (200, 'probe'))
        self.assertIn('key=sk-or-v1-secret', seen['body'])
        self.assertEqual(seen['accept'], 'application/json')

    def test_http_error_carries_the_json_reason(self):
        def opener(request, timeout=None):
            raise urllib.error.HTTPError(
                request.full_url, 422, 'no', {}, None)

        status, payload = key_prompt.submit('http://127.0.0.1:1/x', {}, opener)
        self.assertEqual(status, 422)
        self.assertIn('setup failed', payload['error'])


class RunWindowTests(unittest.TestCase):
    def test_the_browser_opener_is_never_used_for_the_post(self):
        # The router path passes the browser fallback opener; it must not
        # reach submit(), whose opener is a urllib-style POST seam.
        def browser_only(url, new=0, autoraise=True):
            raise AssertionError('the key POST must not use the browser opener')
        with mock.patch.object(key_dialog, 'collect',
                               return_value={'key': KEY}), \
                mock.patch.object(key_dialog, 'message'), \
                mock.patch.object(key_prompt, 'submit',
                                  return_value=(200, {'ok': True})) as posted:
            rc = key_prompt.run_window('http://127.0.0.1:1/t/setup/n',
                                       tool_path='/usr/bin/osascript',
                                       platform_name='darwin', opener=browser_only)
        self.assertEqual(rc, 0)
        self.assertIsNone(posted.call_args.kwargs['opener'],
                          'browser opener leaked into the POST')

    def test_no_dialog_tool_falls_back_to_the_page(self):
        opened = []
        rc = key_prompt.run_window('http://127.0.0.1:1/t/setup/n',
                                   platform_name='plan9',
                                   opener=opened.append)
        self.assertEqual(rc, 3)
        self.assertEqual(opened, ['http://127.0.0.1:1/t/setup/n'])

    def test_cancel_changes_nothing(self):
        with mock.patch.object(key_dialog, 'collect', return_value=None):
            rc = key_prompt.run_window('http://127.0.0.1:1/t/setup/n',
                                       tool_path='/usr/bin/osascript',
                                       platform_name='darwin')
        self.assertEqual(rc, 2)

    def test_empty_key_reprompts_then_stores(self):
        replies = [{'key': ''}, {'key': KEY}]
        messages = []
        with mock.patch.object(key_dialog, 'collect', side_effect=replies), \
                mock.patch.object(key_dialog, 'message',
                                  side_effect=lambda *a, **k: messages.append(a[1])), \
                mock.patch.object(key_prompt, 'submit',
                                  return_value=(200, {'ok': True, 'label': 'probe'})):
            rc = key_prompt.run_window('http://127.0.0.1:1/t/setup/n',
                                       tool_path='/usr/bin/osascript',
                                       platform_name='darwin')
        self.assertEqual(rc, 0)
        self.assertIn('Paste an OpenRouter key before saving.', messages)
        self.assertEqual(messages[-1], 'Your key is saved on this computer.\n\n'
                         'Key: probe\nCredit left: unlimited')

    def test_refused_key_reprompts_and_expired_link_stops(self):
        with mock.patch.object(key_dialog, 'collect',
                               return_value={'key': KEY}), \
                mock.patch.object(key_dialog, 'message'), \
                mock.patch.object(key_prompt, 'submit',
                                  side_effect=[(422, {'ok': False, 'error': 'bad'}),
                                               (404, {'ok': False, 'error': 'gone'})]):
            rc = key_prompt.run_window('http://127.0.0.1:1/t/setup/n',
                                       tool_path='/usr/bin/osascript',
                                       platform_name='darwin')
        self.assertEqual(rc, 1)

    def test_unreachable_router_is_an_error_not_a_loop(self):
        with mock.patch.object(key_dialog, 'collect',
                               return_value={'key': KEY}), \
                mock.patch.object(key_dialog, 'message'), \
                mock.patch.object(key_prompt, 'submit', side_effect=OSError('down')):
            rc = key_prompt.run_window('http://127.0.0.1:1/t/setup/n',
                                       tool_path='/usr/bin/osascript',
                                       platform_name='darwin')
        self.assertEqual(rc, 1)

    def test_own_key_posts_only_the_key(self):
        posted = []
        with mock.patch.object(key_dialog, 'collect', return_value={'key': KEY}), \
                mock.patch.object(key_dialog, 'message') as shown, \
                mock.patch.object(key_prompt, 'submit',
                                  side_effect=lambda url, fields, opener=None:
                                  posted.append(fields) or (200, {'ok': True})):
            rc = key_prompt.run_window('http://127.0.0.1:1/t/setup/n',
                                       tool_path='/usr/bin/osascript', platform_name='darwin')
        self.assertEqual(rc, 0)
        self.assertEqual(posted, [{'key': KEY}])
        self.assertNotIn('subscription', shown.call_args.args[1].lower())

    def test_cli_accepts_and_ignores_the_installer_client_set(self):
        self.assertEqual(key_prompt._parse(['http://127.0.0.1:1/x']), 'http://127.0.0.1:1/x')
        self.assertEqual(key_prompt._parse(['http://127.0.0.1:1/x', '--clients', 'both']),
                         'http://127.0.0.1:1/x')
        self.assertIsNone(key_prompt._parse(['https://example.com/x']))

    def test_cli_reads_the_url_from_stdin(self):
        with mock.patch.object(key_prompt.sys, 'stdin',
                               io.StringIO('http://127.0.0.1:1/t/setup/n\n')):
            self.assertEqual(key_prompt._parse(['--stdin', '--clients', 'both']),
                             'http://127.0.0.1:1/t/setup/n')
        with mock.patch.object(key_prompt.sys, 'stdin', io.StringIO('https://example.com/x\n')):
            self.assertIsNone(key_prompt._parse(['--stdin']))


class OpenWindowTests(unittest.TestCase):
    def test_router_path_starts_a_thread_and_returns(self):
        started = []
        with mock.patch.object(key_prompt, 'run_window',
                               side_effect=lambda *a, **k: started.append(a) or 0):
            self.assertTrue(key_prompt.open_window(
                'http://127.0.0.1:1/t/setup/n', thread=True,
                platform_name='darwin', which=lambda name: '/usr/bin/' + name))
        for thread in threading.enumerate():
            if thread.name == 'Thread':
                thread.join(timeout=5)
        self.assertEqual(len(started), 1)

    def test_installer_path_runs_inline(self):
        with mock.patch.object(key_prompt, 'run_window', return_value=0) as ran:
            self.assertTrue(key_prompt.open_window(
                'http://127.0.0.1:1/t/setup/n', platform_name='darwin',
                which=lambda name: '/usr/bin/' + name))
        ran.assert_called_once()

    def test_no_tool_opens_the_page(self):
        opened = []
        self.assertTrue(key_prompt.open_window(
            'http://127.0.0.1:1/t/setup/n', thread=True, platform_name='plan9',
            opener=opened.append))
        self.assertEqual(opened, ['http://127.0.0.1:1/t/setup/n'])


class CliTests(unittest.TestCase):
    def test_rejects_anything_but_a_loopback_url(self):
        self.assertEqual(key_prompt.main([]), 1)
        self.assertEqual(key_prompt.main(['https://example.com/setup']), 1)

    @unittest.skipUnless(sys.platform == 'darwin', 'compiles AppleScript')
    def test_macos_script_compiles(self):
        argv = key_dialog.argv('/usr/bin/osascript', 'darwin')
        with tempfile.TemporaryDirectory() as tmp:
            out = subprocess.run(
                ['osacompile', '-e', argv[argv.index('-e') + 1],
                 '-o', str(Path(tmp) / 'key.scpt')],
                capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)

    @unittest.skipUnless(sys.platform == 'darwin', 'runs osascript')
    def test_real_osascript_output_parses(self):
        # The real tool ends its return value with a newline; the parser must
        # accept that shape, not just the fakes the other tests feed it.
        for value in ('sk-or-v1-live', ''):
            result = subprocess.run(['osascript', '-e', 'return "%s"' % value],
                                    capture_output=True, text=True)
            fields = key_dialog.collect('/usr/bin/osascript', 'darwin',
                                        lambda *a, **k: result)
            self.assertEqual(fields, {'key': value})


if __name__ == '__main__':
    unittest.main()
