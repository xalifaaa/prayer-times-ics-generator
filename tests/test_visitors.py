import importlib.util
import json
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
