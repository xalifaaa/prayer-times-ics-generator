import importlib
import importlib.util
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

_spec = importlib.util.spec_from_file_location(
    'update_visitors',
    Path(__file__).resolve().parent.parent / 'scripts' / 'update_visitors.py')
update_visitors = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(update_visitors)

PREVIOUS = json.dumps({'schemaVersion': 1, 'label': 'visitors',
                       'message': '42', 'color': 'green'})


class NextBadgeTests(unittest.TestCase):
    def test_queried_greater_updates(self):
        badge, changed = update_visitors.next_badge(PREVIOUS, 100)
        self.assertTrue(changed)
        self.assertEqual(badge['message'], '100')

    def test_queried_lower_keeps_previous(self):
        badge, changed = update_visitors.next_badge(PREVIOUS, 2)
        self.assertFalse(changed)
        self.assertEqual(badge['message'], '42')

    def test_queried_equal_unchanged(self):
        badge, changed = update_visitors.next_badge(PREVIOUS, 42)
        self.assertFalse(changed)
        self.assertEqual(badge['message'], '42')

    def test_malformed_previous_raises(self):
        for text in ('{', 'null', '[]', '"42"',
                     '{"schemaVersion": 1, "label": "visitors", "color": "green"}',
                     '{"message": "many"}', '{"message": "1,234"}', '{"message": 42}'):
            with self.subTest(text=text), self.assertRaises((ValueError, TypeError)):
                update_visitors.next_badge(text, 50)

    def test_invalid_queried_raises(self):
        for queried in ('50', 4.5, -1, True, None):
            with self.subTest(queried=queried), self.assertRaises(ValueError):
                update_visitors.next_badge(PREVIOUS, queried)

    def test_emitted_badge_is_shields_compliant(self):
        badge, _ = update_visitors.next_badge(PREVIOUS, 100)
        self.assertLessEqual(set(badge), update_visitors.ALLOWED_KEYS)
        self.assertEqual(badge['schemaVersion'], 1)
        self.assertTrue(badge['message'].isdigit())

    def test_main_writes_only_on_change(self):
        with TemporaryDirectory() as tmp:
            badge_file = Path(tmp) / 'visitors.json'
            badge_file.write_text(PREVIOUS, encoding='utf-8')
            with patch.object(update_visitors, 'BADGE_FILE', badge_file):
                update_visitors.main(['100'])
                self.assertEqual(json.loads(badge_file.read_text())['message'], '100')
                update_visitors.main(['7'])
                self.assertEqual(json.loads(badge_file.read_text())['message'], '100')

    def test_main_rejects_non_integer_arg(self):
        with self.assertRaises(SystemExit):
            update_visitors.main(['not-a-number'])


class VisitorFloorTests(unittest.TestCase):
    """The app floors the live Application Insights count at the committed
    visitors.json high-water mark, so the on-site counter never decays."""

    @classmethod
    def setUpClass(cls):
        with patch.dict(os.environ, {'APPLICATIONINSIGHTS_CONNECTION_STRING': ''}):
            cls.web = importlib.import_module('src.app')

    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.enterContext(patch.object(self.web, 'root_dir', str(self.root)))
        self.web._count_cache.update(value=None, fetched_at=0)

    def write_badge(self, text):
        (self.root / 'visitors.json').write_text(text, encoding='utf-8')

    def test_persisted_count_parsed(self):
        self.write_badge(PREVIOUS)
        self.assertEqual(self.web._persisted_visitor_count(), 42)

    def test_persisted_count_missing_or_malformed(self):
        self.assertIsNone(self.web._persisted_visitor_count())
        for text in ('{', 'null', '{"message": "many"}', '{"message": 42}'):
            with self.subTest(text=text):
                self.write_badge(text)
                self.assertIsNone(self.web._persisted_visitor_count())

    def test_floor_when_live_count_is_lower(self):
        self.write_badge(PREVIOUS)
        with patch.object(self.web, '_live_visitor_count', return_value=2):
            self.assertEqual(self.web.get_visitor_count(), 42)

    def test_live_count_wins_when_higher(self):
        self.write_badge(PREVIOUS)
        with patch.object(self.web, '_live_visitor_count', return_value=100):
            self.assertEqual(self.web.get_visitor_count(), 100)

    def test_floor_when_live_count_unavailable(self):
        self.write_badge(PREVIOUS)
        with patch.object(self.web, '_live_visitor_count', return_value=None):
            self.assertEqual(self.web.get_visitor_count(), 42)

    def test_none_when_no_data(self):
        with patch.object(self.web, '_live_visitor_count', return_value=None):
            self.assertIsNone(self.web.get_visitor_count())

    def test_api_and_badge_use_floored_count(self):
        self.write_badge(PREVIOUS)
        with patch.object(self.web, '_live_visitor_count', return_value=2), \
                patch.dict(self.web.app.config, {'TESTING': True}):
            client = self.web.app.test_client()
            self.assertEqual(client.get('/api/visitors').get_json()['count'], 42)
            self.assertEqual(client.get('/badge/visitors').get_json()['message'], '42')
