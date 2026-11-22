"""Public downloads carry no credentials and keep the last good model cache."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.install_fixtures import install_mod

feed = install_mod._svc._feed
ROOT = Path(__file__).resolve().parents[1]
models = install_mod._svc.load('private_control_models', ROOT / 'packaging/control_models.py')


class PrivateTransportTests(unittest.TestCase):
    def test_update_pass_removes_a_leftover_sign_in_session_without_following_links(self):
        updater = install_mod._updater
        with tempfile.TemporaryDirectory() as tmp:
            home, outside = Path(tmp, 'home'), Path(tmp, 'outside.json')
            home.mkdir()
            (home / 'download-session.json').write_text('{"refresh_token": "synthetic"}')
            updater._remove_retired_session(home)
            self.assertFalse((home / 'download-session.json').exists())
            updater._remove_retired_session(home)
            outside.write_text('{}')
            try:
                (home / 'download-session.json').symlink_to(outside)
            except OSError:
                self.skipTest('symlinks need extra rights on this Windows account')
            updater._remove_retired_session(home)
            self.assertTrue(outside.exists())

    def test_public_downloads_send_no_staff_credentials(self):
        req = feed._request(feed.FEED_ORIGIN + '/stable/latest.json')
        self.assertIsNone(req.get_header('Cookie'))
        for url in ('https://other.example/file', 'http://dist.softwarecombined.com/file',
                    'https://dist.softwarecombined.com.attacker.invalid/file'):
            with self.subTest(url=url), self.assertRaises(SystemExit):
                feed.fetch(url)
        with self.assertRaises(SystemExit):
            feed._PinnedRedirects().redirect_request(
                req, None, 302, 'redirect', {}, 'https://other.example/file')


class ControlledModelTests(unittest.TestCase):
    def test_verified_models_refresh_without_a_download_account(self):
        import hashlib
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            body = b'[]'
            self.assertTrue(models.accept(home, {
                'models_url': feed.FEED_ORIGIN + '/stable/models.json',
                'models_sha256': hashlib.sha256(body).hexdigest()}))
            run = mock.Mock(return_value=SimpleNamespace(returncode=0))
            self.assertTrue(models.refresh(home, lambda _: body, run=run, now=4000))
            self.assertEqual((home / 'models-cache.json').read_bytes(), body)
            self.assertFalse((home / 'download-auth.json').exists())
            run.assert_called_once()

    def test_tampered_model_download_keeps_the_last_good_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            (home / 'download-auth.json').write_text('{}')
            models.accept(home, {'models_url': feed.FEED_ORIGIN + '/stable/models.json',
                                 'models_sha256': 'a' * 64})
            cache = home / 'models-cache.json'
            cache.write_text('last good model list')
            called = mock.Mock()
            self.assertFalse(models.refresh(home, lambda _: b'changed', run=called, now=4000))
            self.assertEqual(cache.read_text(), 'last good model list')
            called.assert_not_called()

    def test_untrusted_feed_cannot_choose_a_model_download(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.assertFalse(models.accept(temporary, {
                'models_url': 'https://other.example/models.json', 'models_sha256': 'a' * 64}))
            self.assertFalse((Path(temporary) / 'controlled-models.json').exists())


if __name__ == '__main__':
    unittest.main()
