import importlib
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


class HealthCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.dict(os.environ, {'APPLICATIONINSIGHTS_CONNECTION_STRING': ''}):
            cls.web = importlib.import_module('src.app')

    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.enterContext(patch.object(self.web, 'root_dir', str(self.root)))
        self.enterContext(patch.object(self.web, 'STATIC_MODE', True))
        self.enterContext(patch.dict(self.web.app.config, {'TESTING': True}))
        self.client = self.web.app.test_client()
        self.enterContext(patch('requests.sessions.Session.request',
                                side_effect=AssertionError('Unexpected network request')))
        self.enterContext(patch('urllib.request.urlopen',
                                side_effect=AssertionError('Unexpected network request')))
        self.enterContext(patch.object(self.web.AWQAFApi, 'get_locations',
                                       side_effect=AssertionError('Unexpected AWQAF lookup')))
        self.enterContext(patch.object(self.web.AWQAFApi, 'fetch_prayer_times',
                                       side_effect=AssertionError('Unexpected AWQAF lookup')))
        self.enterContext(patch.object(self.web.prayer_module, 'extract_credentials',
                                       side_effect=AssertionError('Unexpected setup')))
        self.enterContext(patch.object(self.web, 'get_visitor_count',
                                       side_effect=AssertionError('Unexpected telemetry query')))
        self.visitor_log = self.enterContext(patch.object(self.web.logger, 'info'))

    def create_assets(self):
        locations = {
            'emirates': [{'emiratesId': 2, 'emirateNameEn': 'Dubai'}],
            'cities': [{'emirate': 2, 'cityNameEn': 'Dubai'}],
        }
        (self.root / 'locations_cache.json').write_text(json.dumps(locations), encoding='utf-8')
        calendar_file = self.root / 'calendars' / '2026' / 'September' / 'Dubai' / 'September2026.ics'
        calendar_file.parent.mkdir(parents=True)
        calendar_file.write_bytes(b'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nEND:VCALENDAR\r\n')
        return calendar_file

    def assert_health(self, status):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, status)
        self.assertEqual(response.get_json(), {'status': 'healthy' if status == 200 else 'unhealthy'})
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertNotIn('Set-Cookie', response.headers)
        self.assertNotIn('Location', response.headers)
        self.visitor_log.assert_not_called()

    def test_static_ready(self):
        self.create_assets()
        self.assert_health(200)

    def test_live_mode_needs_no_assets(self):
        with patch.object(self.web, 'STATIC_MODE', False):
            self.assert_health(200)

    def test_missing_locations(self):
        self.create_assets()
        (self.root / 'locations_cache.json').unlink()
        self.assert_health(503)

    def test_invalid_location_documents(self):
        self.create_assets()
        for document in ('{', 'null', '[]', '{}', '{"emirates":[],"cities":[]}',
                         '{"emirates":[{}]}', '{"emirates":[{}],"cities":[]}',
                         '{"emirates":{},"cities":[{}]}', '{"emirates":[{}],"cities":"invalid"}'):
            with self.subTest(document=document):
                (self.root / 'locations_cache.json').write_text(document, encoding='utf-8')
                self.assert_health(503)

    def test_invalid_location_encoding(self):
        self.create_assets()
        (self.root / 'locations_cache.json').write_bytes(b'\xff')
        self.assert_health(503)

    def test_unreadable_locations(self):
        self.create_assets()
        with patch.object(Path, 'read_text', side_effect=PermissionError('test')):
            self.assert_health(503)

    def test_missing_calendars_directory(self):
        self.create_assets()
        (self.root / 'calendars').rename(self.root / 'other')
        self.assert_health(503)

    def test_no_calendar_files(self):
        calendar_file = self.create_assets()
        calendar_file.unlink()
        (self.root / 'calendars' / '.gitkeep').touch()
        self.assert_health(503)

    def test_directory_with_ics_suffix_is_not_a_calendar(self):
        calendar_file = self.create_assets()
        calendar_file.unlink()
        calendar_file.mkdir()
        self.assert_health(503)

    def test_invalid_calendar_header(self):
        calendar_file = self.create_assets()
        for content in (b'', b'not a calendar\n'):
            with self.subTest(content=content):
                calendar_file.write_bytes(content)
                self.assert_health(503)

    def test_unreadable_calendar(self):
        self.create_assets()
        original_open = Path.open

        def open_file(path, *args, **kwargs):
            if path.suffix == '.ics':
                raise PermissionError('test')
            return original_open(path, *args, **kwargs)

        with patch.object(Path, 'open', new=open_file):
            self.assert_health(503)

    def test_head_request(self):
        self.create_assets()
        response = self.client.head('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b'')
        self.assertNotIn('Set-Cookie', response.headers)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.visitor_log.assert_not_called()

    def test_assets_can_recover_without_restart(self):
        self.assert_health(503)
        self.create_assets()
        self.assert_health(200)
