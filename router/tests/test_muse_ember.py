"""Muse Ember is discoverable and routed without replacing other Muse models."""
import unittest
from unittest import mock

from ai_router import availability, catalogue, claude, providers
from ai_router.registry import by_slug


class MuseEmberTests(unittest.TestCase):
    def test_picker_listing_and_routes_respect_availability_and_policy(self):
        slug = 'meta/muse-ember'
        model = by_slug(slug)
        self.assertIsNotNone(model)
        self.assertEqual(model.display_name, 'Meta: Muse Ember · OpenRouter')
        self.assertEqual((model.tier, model.listed), ('verified', True))
        self.assertEqual(model.default_reasoning, 'low')
        self.assertEqual(model.modalities, ('text', 'image', 'audio'))
        self.assertEqual((model.context_window, model.max_output_tokens), (1048576, 943718))
        for other in ('meta/muse-wonder', 'meta/muse-spark-1.3',
                      'meta/muse-spark-1.3-contributor'):
            self.assertIsNotNone(by_slug(other))

        entries = {row['slug']: row for row in catalogue.merge({'models': []})['models']}
        self.assertIn(slug, entries)
        self.assertEqual(entries[slug]['display_name'], model.display_name)
        self.assertNotIn(slug, {row['slug'] for row in
                                catalogue.merge({'models': []}, allowed=())['models']})
        self.assertNotIn(slug, {row['slug'] for row in
                                catalogue.merge({'models': []}, available=())['models']})
        with mock.patch.object(availability, 'combined_ids', return_value={slug}):
            self.assertIn(slug, {row['id'] for row in claude.models_listing()['data']})
            self.assertNotIn(slug, {row['id'] for row in claude.models_listing(allowed=())['data']})
        with mock.patch.object(availability, 'combined_ids', return_value=set()):
            self.assertNotIn(slug, {row['id'] for row in claude.models_listing()['data']})
        self.assertIsInstance(providers.select(slug, '/responses', ()),
                              providers.ExternalResponsesProvider)
        with self.assertRaises(ValueError):
            providers.select(slug, '/responses', (), allowed=())
