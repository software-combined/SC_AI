"""Plan 131 step 2: the shared state-reader contract."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ai_router import atomic_write, state


class StateReadTests(unittest.TestCase):
    def _home(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)

    def test_read_degrades_on_every_unusable_document(self):
        home = self._home()
        path = state.path(home)
        self.assertIsNone(state.read(path))
        path.write_text('{not json')
        self.assertIsNone(state.read(path))
        path.write_text('[1, 2]')
        self.assertIsNone(state.read(path))
        path.write_text('{"port": 1}')
        self.assertEqual(state.read(path), {'port': 1})

    def test_read_strict_reports_the_reason(self):
        home = self._home()
        path = state.path(home)
        with self.assertRaises(state.StateUnreadable) as missing:
            state.read_strict(path)
        self.assertEqual(missing.exception.reason, 'missing')
        path.write_text('{not json')
        with self.assertRaises(state.StateUnreadable) as invalid:
            state.read_strict(path)
        self.assertEqual((invalid.exception.reason, invalid.exception.detail),
                         ('invalid', 'JSONDecodeError'))
        path.write_text('[1]')
        with self.assertRaises(state.StateUnreadable) as scalar:
            state.read_strict(path)
        self.assertEqual(scalar.exception.detail, 'not a JSON object')

    def test_read_strict_marks_a_present_but_unreadable_path(self):
        # A path that exists but cannot be read must not be reported as
        # missing, or the operator hunts for a file that is right there.
        home = self._home()
        path = state.path(home)
        path.mkdir()
        with self.assertRaises(state.StateUnreadable) as unreadable:
            state.read_strict(path)
        self.assertEqual(unreadable.exception.reason, 'unreadable')
        self.assertTrue(unreadable.exception.detail)

    def test_required_keys_names_missing_and_mistyped(self):
        self.assertEqual(state.required_keys({}, {'port': int, 'token': str}),
                         ['port', 'token'])
        self.assertEqual(state.required_keys({'port': 'x', 'token': 't'},
                                             {'port': int, 'token': str}),
                         ['port'])
        self.assertEqual(state.required_keys({'port': 1, 'token': 't'},
                                             {'port': int}), [])


class StateUpdateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)

    def test_two_writers_keep_both_changes(self):
        state.path(self.home).write_text('{"port": 1}')
        calls = []

        def installer(doc):
            calls.append(dict(doc))
            if len(calls) == 1:  # Another process saves between this read and this write.
                state.update(self.home, lambda other: other.update(setup='window'), atomic_write)
            doc['component_repairs'] = {'controls': 'ready'}
        saved = state.update(self.home, installer, atomic_write)
        expected = {'port': 1, 'setup': 'window', 'component_repairs': {'controls': 'ready'}}
        self.assertEqual((saved, state.read(state.path(self.home))), (expected, expected))
        self.assertEqual(calls, [{'port': 1}, {'port': 1, 'setup': 'window'}])

    def test_update_fails_loudly_after_every_attempt_lost_a_race(self):
        path = state.path(self.home)
        path.write_text('{"n": 0}')

        def contended(doc):
            path.write_text('{"n": %d}' % (state.read(path)['n'] + 1))
            doc['mine'] = True
        with self.assertRaises(atomic_write.ConcurrentChange):
            state.update(self.home, contended, atomic_write, attempts=3)
        self.assertEqual(state.read(path), {'n': 3})

    def test_missing_or_unchanged_documents_are_not_written(self):
        mutate = mock.Mock()
        self.assertIsNone(state.update(self.home, mutate, atomic_write))
        mutate.assert_not_called()
        path = state.path(self.home)
        path.write_text('{"port":1}')
        self.assertEqual(state.update(self.home, lambda doc: doc.update(port=1), atomic_write), {'port': 1})
        self.assertEqual(path.read_text(), '{"port":1}')
