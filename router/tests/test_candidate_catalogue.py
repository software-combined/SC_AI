"""Fresh candidate rows must project through the registry used by the probe."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ai_router import candidate, models, registry


class CandidateCatalogueTests(unittest.TestCase):
    def test_fresh_preview_absent_from_imported_registry_uses_its_own_capabilities(self):
        with tempfile.TemporaryDirectory() as folder:
            root, source = Path(folder), Path(candidate.ROOT)
            package = root / 'ai_router'
            for file in (source / 'ai_router').rglob('*'):
                if file.is_file() and file.suffix in ('.py', '.json', '.txt'):
                    target = package / file.relative_to(source / 'ai_router')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(file.read_bytes())
            path = root / 'catalogue.json'
            path.write_text(json.dumps({'models': []}))
            rows = json.loads((package / 'models.json').read_text())
            carbon = next(item for item in rows if item['slug'] == 'google/gemini-4-carbon')
            fresh = {**carbon, 'slug': 'google/synthetic-fresh', 'tier': 'preview',
                     'listed': False, 'reasoning': ['low', 'high'],
                     'excluded_efforts': ['medium'], 'modalities': ['text', 'image']}
            rows.append(fresh)
            (package / 'models.json').write_text(json.dumps(models.renumbered(rows)))
            row = registry.load(json.dumps([fresh]))[0]
            self.assertIsNone(registry.by_slug(row.slug))
            with mock.patch.object(candidate, 'ROOT', root):
                candidate._include_probe_candidate(path, row)
            entry = json.loads(path.read_text())['models'][0]
            self.assertEqual(entry['slug'], row.slug)
            self.assertIn('Preview', entry['display_name'])
            self.assertEqual(entry['input_modalities'], ['text', 'image'])
            self.assertEqual([level['effort'] for level in entry['supported_reasoning_levels']],
                             ['low', 'high'])
            self.assertIn(row.slug, entry['model_messages']['instructions_template'])
            self.assertFalse(row.listed)


if __name__ == '__main__':
    unittest.main()
