"""Claude Desktop discovery and saved-session routing contracts."""
import hashlib
import json
from dataclasses import replace
import unittest
from unittest import mock

from ai_router import availability, claude, registry
from ai_router.errors import UnknownModel


class DesktopDiscoveryTests(unittest.TestCase):
    def test_discovery_uses_stable_ids_with_actual_vendor_names_and_capabilities(self):
        with mock.patch.object(availability, 'combined_ids', return_value=None):
            rows = claude.models_listing()['data']
        expected = {m.slug: m.display_name for m in registry.MODELS
                    if m.listed and m.provider == 'openrouter'}
        self.assertEqual(len(rows), len(expected))
        for row in rows:
            with self.subTest(model=row['display_name']):
                slug = claude.resolve(row['id'])
                expected_id = slug.removeprefix('~')
                if not expected_id.startswith('anthropic/'):
                    expected_id = 'claude/scg/' + hashlib.sha256(slug.encode()).hexdigest()
                self.assertEqual(row['id'], expected_id)
                if not row['id'].startswith('anthropic/claude-'):
                    self.assertNotIn('anthropic_family_tier', row)
                self.assertEqual(row['display_name'], expected[slug])

    def test_tracking_alias_and_saved_direct_id_resolve_to_the_same_provider(self):
        entry = replace(registry.by_slug('deepseek/deepseek-v4.1-flash-1017'),
                        slug='~deepseek/deepseek-v4.1-flash-1017')
        rows = {entry.slug: entry}
        identifier = claude.row_alias(entry)
        self.assertEqual(identifier, 'claude/scg/' + hashlib.sha256(entry.slug.encode()).hexdigest())
        self.assertEqual(claude.resolve(identifier, rows), entry.slug)
        self.assertEqual(claude.resolve(entry.slug.removeprefix('~'), rows), entry.slug)
        with mock.patch.object(availability, 'permitted', return_value=True):
            provider = claude.select(identifier, '/v1/messages',
                                     allowed=[entry.slug], catalogue=rows)
        self.assertEqual(provider.name, entry.provider)

    def test_discovered_and_saved_aliases_keep_the_same_billing_and_body(self):
        slug = 'deepseek/deepseek-v4.1-flash-1017'
        payload = {'model': slug, 'max_tokens': 64,
                   'messages': [{'role': 'user', 'content': 'synthetic probe'}]}
        credentials = mock.Mock()
        credentials.key_for.return_value = 'test-provider-key'
        for model in (claude.claude_alias(slug), slug):
            with self.subTest(model=model), \
                    mock.patch.object(availability, 'permitted', return_value=True):
                provider = claude.select(model, '/v1/messages', allowed=[slug])
                body = dict(payload, model=model)
                prepared = provider.prepare(model, '/v1/messages', body,
                                            json.dumps(body).encode(),
                                            {'Authorization': 'Bearer client-secret'},
                                            credentials)
                self.assertEqual(provider.name, 'openrouter')
                self.assertEqual(json.loads(prepared.body), payload)
                self.assertNotIn('client-secret', str(prepared.headers))
                with self.assertRaises(UnknownModel):
                    claude.select(model, '/v1/messages', allowed=[])

    def test_alias_routing_keeps_canonical_policy_and_key_availability_gates(self):
        slug = 'deepseek/deepseek-v4.1-flash-1017'
        identifier = 'claude/scg/caf1ef1f3bdf5452e389231c9ade544bae824aff51e08ebffbd85cd0fb65f1f0'
        self.assertEqual(claude.claude_alias(slug), identifier)
        with mock.patch.object(availability, 'permitted', return_value=True):
            for allowed in ([], [identifier]):
                with self.subTest(allowed=allowed), self.assertRaises(UnknownModel):
                    claude.select(identifier, '/v1/messages', allowed=allowed)
        with mock.patch.object(availability, 'permitted', return_value=False):
            with self.assertRaises(UnknownModel):
                claude.select(identifier, '/v1/messages', allowed=[slug])

    def test_alias_resolution_uses_the_captured_generation_and_rejects_removed_rows(self):
        slug = 'deepseek/deepseek-v4.1-flash-1017'
        entry = registry.by_slug(slug)
        rows = {slug: entry}
        identifier = 'claude/scg/' + hashlib.sha256(slug.encode()).hexdigest()
        with mock.patch.object(registry, 'BY_SLUG', {}), \
                mock.patch.object(availability, 'permitted', return_value=True):
            self.assertEqual(claude.resolve(identifier, rows), slug)
            self.assertEqual(claude.select(identifier, '/v1/messages',
                                          allowed=[slug], catalogue=rows).name, entry.provider)
            with self.assertRaises(UnknownModel):
                claude.select(identifier, '/v1/messages', catalogue={})

    def test_unknown_router_alias_cannot_fall_through_to_subscription(self):
        for model in ('claude/scg/' + '0' * 64, 'claude/deepseek/deepseek-v4.1-flash-1017'):
            with self.subTest(model=model), self.assertRaises(UnknownModel):
                claude.select(model, '/v1/messages')


if __name__ == '__main__':
    unittest.main()
