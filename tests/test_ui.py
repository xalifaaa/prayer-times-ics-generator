import calendar as calendar_mod
import importlib
import json
import os
import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import quote


def make_prayer_data(start, end):
    """Synthetic {'prayertimes': [...]} covering each day in [start, end]."""
    days = []
    current = start
    while current <= end:
        days.append({'date': current.isoformat(), 'timings': {
            'fajr': '05:00', 'zuhr': '12:15', 'asr': '15:30',
            'maghrib': '18:05', 'isha': '19:30'}})
        current += timedelta(days=1)
    return {'prayertimes': days}


def api_item(day, city):
    """One raw prayerData entry as returned by the AWQAF API."""
    item = {'gDate': f'{day.isoformat()}T00:00:00', 'areaNameEn': city}
    for prayer, hour in (('fajr', 5), ('zuhr', 12), ('asr', 15), ('maghrib', 18), ('isha', 19)):
        item[prayer] = f'{day.isoformat()}T{hour:02d}:30:00'
    return item


def event_dates(cal):
    dates = set()
    for comp in cal.walk('VEVENT'):
        dt = comp.decoded('dtstart')
        dates.add(dt.date() if hasattr(dt, 'date') else dt)
    return dates


class UITests(unittest.TestCase):
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
        self.enterContext(patch.object(self.web.prayer_module, 'extract_credentials',
                                       side_effect=AssertionError('Unexpected setup')))
        self.web._availability_cache.clear()
        self.create_locations()

    def create_locations(self):
        locations = {
            'emirates': [
                {'emiratesId': 1, 'emirateNameEn': 'Abu Dhabi'},
                {'emiratesId': 2, 'emirateNameEn': 'Dubai'},
            ],
            'cities': [
                {'cityID': 1, 'emirate': 1, 'cityNameEn': 'Abu Dhabi',
                 'latitude': 24.459444, 'longitude': 54.300555, 'enabled': True},
                {'cityID': 2, 'emirate': 1, 'cityNameEn': 'Al Ain',
                 'latitude': 24.212777, 'longitude': 55.53111, 'enabled': True},
                {'cityID': 3, 'emirate': 2, 'cityNameEn': 'Dubai',
                 'latitude': 25.2048, 'longitude': 55.2708, 'enabled': True},
                {'cityID': 4, 'emirate': 2, 'cityNameEn': 'No Data City',
                 'latitude': 25.1, 'longitude': 55.2, 'enabled': True},
                {'cityID': 5, 'emirate': 1, 'cityNameEn': 'No Coords',
                 'latitude': None, 'longitude': None, 'enabled': True},
                {'cityID': 6, 'emirate': 1, 'cityNameEn': 'Disabled City',
                 'latitude': 24.0, 'longitude': 54.0, 'enabled': False},
            ],
        }
        (self.root / 'locations_cache.json').write_text(json.dumps(locations), encoding='utf-8')

    def create_month(self, year, month, emirate='Dubai', city='Dubai'):
        """Generate one monthly .ics fixture through the real generator code path."""
        last_day = calendar_mod.monthrange(year, month)[1]
        data = make_prayer_data(date(year, month, 1), date(year, month, last_day))
        return self.web.prayer_module.CalendarGenerator(
            data, city, emirate, base_dir=str(self.root / 'calendars')).generate()

    def parse_ics(self, response):
        from icalendar import Calendar
        return Calendar.from_ical(response.data)

    # /api/locations

    def test_locations_shape_and_filtering(self):
        data = self.client.get('/api/locations').get_json()
        self.assertEqual(data['emirates'], [{'id': 1, 'name': 'Abu Dhabi'},
                                            {'id': 2, 'name': 'Dubai'}])
        names = {c['name'] for c in data['cities']}
        self.assertEqual(names, {'Abu Dhabi', 'Al Ain', 'Dubai', 'No Data City'})
        dubai = next(c for c in data['cities'] if c['name'] == 'Dubai')
        self.assertEqual(dubai['id'], 3)
        self.assertEqual(dubai['emirate_id'], 2)
        self.assertEqual(dubai['emirate'], 'Dubai')
        self.assertEqual(dubai['lat'], 25.2048)
        self.assertEqual(dubai['lon'], 55.2708)
        self.assertFalse(dubai['available'])  # no calendars on disk yet

    def test_locations_available_flag(self):
        self.create_month(2026, 9)
        self.web._availability_cache.clear()
        data = self.client.get('/api/locations').get_json()
        availability = {c['name']: c['available'] for c in data['cities']}
        self.assertTrue(availability['Dubai'])
        self.assertFalse(availability['Al Ain'])
        self.assertFalse(availability['No Data City'])

    def test_locations_live_mode_all_available(self):
        with patch.object(self.web, 'STATIC_MODE', False):
            data = self.client.get('/api/locations').get_json()
        self.assertTrue(all(c['available'] for c in data['cities']))

    # /api/availability

    def test_availability_months_and_window(self):
        self.create_month(2026, 9)
        self.create_month(2026, 10)
        data = self.client.get('/api/availability?emirate=Dubai&city=Dubai').get_json()
        self.assertEqual(data, {'static': True, 'months': ['2026-09', '2026-10'],
                                'min': '2026-09-01', 'max': '2026-10-31'})

    def test_availability_unknown_city(self):
        response = self.client.get('/api/availability?emirate=Dubai&city=Nowhere')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(),
                         {'static': True, 'months': [], 'min': None, 'max': None})

    def test_availability_live_mode_unconstrained(self):
        with patch.object(self.web, 'STATIC_MODE', False):
            self.assertEqual(
                self.client.get('/api/availability?emirate=Dubai&city=Dubai').get_json(),
                {'static': False, 'months': None, 'min': None, 'max': None})
            self.assertEqual(
                self.client.get('/api/availability').get_json(),
                {'static': False, 'months': None, 'min': None, 'max': None})

    def test_availability_no_city_returns_union_window(self):
        self.create_month(2026, 9, emirate='Dubai', city='Dubai')
        self.create_month(2026, 10, emirate='Dubai', city='Dubai')
        self.create_month(2026, 10, emirate='Abu Dhabi', city='Al Ain')
        self.create_month(2026, 11, emirate='Abu Dhabi', city='Al Ain')
        data = self.client.get('/api/availability').get_json()
        self.assertEqual(data, {'static': True, 'months': ['2026-09', '2026-10', '2026-11'],
                                'min': '2026-09-01', 'max': '2026-11-30'})

    def test_availability_no_city_no_data(self):
        data = self.client.get('/api/availability').get_json()
        self.assertEqual(data, {'static': True, 'months': [], 'min': None, 'max': None})

    # GET /

    def test_index_static_mode_never_calls_awqaf(self):
        with patch.object(self.web.AWQAFApi, 'get_locations',
                          side_effect=AssertionError('Unexpected AWQAF lookup')):
            response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="generate-form"', response.get_data(as_text=True))

    def test_index_static_mode_empty_cache_shows_setup(self):
        (self.root / 'locations_cache.json').unlink()
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="initial-form"', response.get_data(as_text=True))

    # Visitor telemetry

    def test_visitor_logged_once_and_cookie_suppresses(self):
        self.assertEqual(self.web.logger.getEffectiveLevel(), 20)  # INFO
        with self.assertLogs('prayer-times-app', level='INFO') as logs:
            self.client.get('/')
        self.assertEqual(sum('unique_visitor' in line for line in logs.output), 1)
        self.client.set_cookie('visitor_id', 'returning-visitor')
        with self.assertNoLogs('prayer-times-app', level='INFO'):
            self.client.get('/')

    # /download/range (static)

    def test_range_single_month(self):
        self.create_month(2026, 9)
        response = self.client.get('/download/range/2026-09-10/2026-09-12/Dubai/Dubai')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'text/calendar')
        self.assertIn('attachment', response.headers['Content-Disposition'])
        self.assertIn('PrayerTimes_Dubai_2026-09-10_to_2026-09-12.ics',
                      response.headers['Content-Disposition'])
        cal = self.parse_ics(response)
        self.assertEqual(str(cal['VERSION']), '2.0')
        self.assertEqual(str(cal['X-WR-CALNAME']), 'Dubai Prayer Times')
        self.assertEqual(event_dates(cal),
                         {date(2026, 9, 10), date(2026, 9, 11), date(2026, 9, 12)})

    def test_range_across_month_boundary(self):
        self.create_month(2026, 9)
        self.create_month(2026, 10)
        response = self.client.get('/download/range/2026-09-25/2026-10-05/Dubai/Dubai')
        self.assertEqual(response.status_code, 200)
        cal = self.parse_ics(response)
        dates = event_dates(cal)
        self.assertEqual(dates, {date(2026, 9, d) for d in range(25, 31)}
                         | {date(2026, 10, d) for d in range(1, 6)})
        events = cal.walk('VEVENT')
        fridays = {date(2026, 9, 25), date(2026, 10, 2)}
        expected = sum(9 if d in fridays else 10 for d in dates)
        self.assertEqual(len(events), expected)

    def test_range_skips_missing_month(self):
        self.create_month(2026, 9)
        self.create_month(2026, 11)
        response = self.client.get('/download/range/2026-09-28/2026-11-02/Dubai/Dubai')
        self.assertEqual(response.status_code, 200)
        dates = event_dates(self.parse_ics(response))
        self.assertIn(date(2026, 9, 30), dates)
        self.assertIn(date(2026, 11, 1), dates)
        self.assertFalse(any(d.month == 10 for d in dates))

    def test_range_no_events_404(self):
        self.create_month(2026, 9)
        response = self.client.get('/download/range/2026-10-01/2026-10-05/Dubai/Dubai')
        self.assertEqual(response.status_code, 404)

    def test_range_bad_dates_400(self):
        self.assertEqual(self.client.get('/download/range/not-a-date/2026-09-12/Dubai/Dubai')
                         .status_code, 400)
        self.assertEqual(self.client.get('/download/range/2026-09-10/nope/Dubai/Dubai')
                         .status_code, 400)

    def test_range_start_after_end_400(self):
        self.assertEqual(self.client.get('/download/range/2026-09-12/2026-09-10/Dubai/Dubai')
                         .status_code, 400)

    def test_range_over_366_days_400(self):
        self.assertEqual(self.client.get('/download/range/2026-01-01/2027-01-02/Dubai/Dubai')
                         .status_code, 400)

    def test_range_filename_sanitised(self):
        self.create_month(2026, 9, emirate='Abu Dhabi', city='Al Ain')
        response = self.client.get(
            f'/download/range/2026-09-10/2026-09-10/{quote("Abu Dhabi")}/{quote("Al Ain")}')
        self.assertEqual(response.status_code, 200)
        self.assertIn('PrayerTimes_Al_Ain_2026-09-10_to_2026-09-10.ics',
                      response.headers['Content-Disposition'])

    # /download/range (live)

    def test_range_live_mode(self):
        days = [date(2026, 9, 3), date(2026, 9, 4), date(2026, 9, 5)]
        payload = {'prayerData': [api_item(d, city) for d in days
                                  for city in ('Dubai', 'Abu Dhabi')]}
        with patch.object(self.web, 'STATIC_MODE', False), \
                patch.object(self.web.AWQAFApi, '_request_prayer_data',
                             return_value=payload) as request:
            response = self.client.get('/download/range/2026-09-04/2026-09-05/Dubai/Dubai')
        request.assert_called_once_with('2026-09-04', '2026-09-05')
        self.assertEqual(response.status_code, 200)
        cal = self.parse_ics(response)
        dates = event_dates(cal)
        # 2026-09-03 is in the payload but outside the requested range
        self.assertEqual(dates, {date(2026, 9, 4), date(2026, 9, 5)})
        summaries = [str(c['SUMMARY']) for c in cal.walk('VEVENT')]
        self.assertIn('Jummah Prayer', summaries)
        friday_events = [c for c in cal.walk('VEVENT')
                         if c.decoded('dtstart').date() == date(2026, 9, 4)]
        self.assertFalse(any('Zuhr' in str(c['SUMMARY']) for c in friday_events))
        self.assertFalse(any('Abu Dhabi' in str(c.get('LOCATION', ''))
                             for c in cal.walk('VEVENT')))
        # Live mode must not write files to disk
        self.assertEqual(list(self.root.rglob('*.ics')), [])

    # POST /generate

    def post(self, **fields):
        return self.client.post('/generate', data=fields)

    def test_generate_success_links_range_download(self):
        self.create_month(2026, 9)
        response = self.post(emirate='Dubai', city='Dubai',
                             start='2026-09-01', end='2026-09-30')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('/download/range/2026-09-01/2026-09-30/Dubai/Dubai', html)
        self.assertIn('1 September 2026', html)

    def test_generate_blank_end_means_single_day(self):
        self.create_month(2026, 9)
        response = self.post(emirate='Dubai', city='Dubai', start='2026-09-10', end='')
        html = response.get_data(as_text=True)
        self.assertIn('/download/range/2026-09-10/2026-09-10/Dubai/Dubai', html)

    def test_generate_unavailable_range_renders_error(self):
        self.create_month(2026, 9)
        response = self.post(emirate='Dubai', city='Dubai',
                             start='2028-01-01', end='2028-01-31')
        html = response.get_data(as_text=True)
        self.assertIn('No calendar data is available for Dubai', html)
        self.assertIn('1 September 2026', html)  # names the available window

    def test_generate_missing_fields_redirect(self):
        response = self.post(emirate='Dubai', start='2026-09-01')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], '/')

    def test_generate_unexpected_error_renders_error_page(self):
        with patch.object(self.web, '_availability_index', side_effect=OSError('test')):
            response = self.post(emirate='Dubai', city='Dubai',
                                 start='2026-09-01', end='2026-09-30')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('Try Again', html)
        self.assertIn('test', html)

    def test_generate_invalid_range_renders_error(self):
        response = self.post(emirate='Dubai', city='Dubai',
                             start='2026-09-30', end='2026-09-01')
        self.assertIn('Start date', response.get_data(as_text=True))

    # Regression: existing download routes unchanged

    def test_download_relpath_still_works(self):
        self.create_month(2026, 9)
        response = self.client.get('/download/calendars/2026/September/Dubai/September2026.ics')
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response.headers['Content-Disposition'])

    def test_download_day_still_works(self):
        self.create_month(2026, 9)
        response = self.client.get('/download/day/2026-09-10/Dubai/Dubai')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(event_dates(self.parse_ics(response)), {date(2026, 9, 10)})

    def test_download_rejects_non_ics(self):
        self.assertEqual(self.client.get('/download/calendars/evil.txt').status_code, 404)
