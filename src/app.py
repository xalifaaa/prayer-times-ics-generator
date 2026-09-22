"""
Flask web app for UAE Prayer Times Calendar Generator
Server-side rendered for speed and SEO
"""

import asyncio
import calendar
import importlib.util
import io
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import date as date_cls
from datetime import datetime
from pathlib import Path

import pytz
import requests
from flask import Flask, redirect, render_template, request, send_file, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import safe_join

# Initialize Azure Application Insights telemetry when configured
if os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING'):
    from azure.monitor.opentelemetry import configure_azure_monitor
    configure_azure_monitor()

logger = logging.getLogger('prayer-times-app')
logger.setLevel(logging.INFO)

# Set template folder to absolute path
# Get the root directory (parent of src/)
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
template_folder = os.path.join(root_dir, 'templates')
# Make it absolute
template_folder = os.path.abspath(template_folder)
app = Flask(__name__, template_folder=template_folder)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Trust X-Forwarded-* headers from the Azure App Service reverse proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Load the main script as a module
script_path = Path(__file__).parent / 'generator.py'
spec = importlib.util.spec_from_file_location('generator', script_path)
prayer_module = importlib.util.module_from_spec(spec)
sys.modules['generator'] = prayer_module
spec.loader.exec_module(prayer_module)

# Get the classes we need
AWQAFApi = prayer_module.AWQAFApi
CalendarGenerator = prayer_module.CalendarGenerator
PrayerConfig = prayer_module.PrayerConfig


AI_APP_ID = os.environ.get('APPINSIGHTS_APP_ID')
AI_API_KEY = os.environ.get('APPINSIGHTS_API_KEY')
COUNT_CACHE_SECONDS = 300
_count_cache = {'value': None, 'fetched_at': 0}

# Hosted deployments serve pre-generated calendars only; localhost uses the live AWQAF API
STATIC_MODE = os.environ.get('STATIC_MODE', '').lower() in ('1', 'true', 'yes')

_availability_cache = {}


def _load_locations():
    """Read the committed locations cache; never calls the AWQAF API."""
    try:
        data = json.loads((Path(root_dir) / 'locations_cache.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'emirates': [], 'cities': []}
    return data if isinstance(data, dict) else {'emirates': [], 'cities': []}


def _availability_index():
    """Map (emirate, city) -> sorted 'YYYY-MM' months with a calendar file on disk."""
    if 'index' in _availability_cache:
        return _availability_cache['index']
    index = {}
    locations = _load_locations()
    emirate_names = {e.get('emiratesId'): e.get('emirateNameEn')
                     for e in locations.get('emirates', [])}
    pairs = [(emirate_names[c.get('emirate')], c.get('cityNameEn'))
             for c in locations.get('cities', [])
             if c.get('cityNameEn') and c.get('emirate') in emirate_names]
    month_names = list(calendar.month_name)
    cal_root = Path(root_dir) / 'calendars'
    if cal_root.is_dir():
        for year_dir in sorted(cal_root.iterdir()):
            if not year_dir.is_dir() or not year_dir.name.isdigit():
                continue
            for month_dir in year_dir.iterdir():
                if month_dir.name not in month_names:
                    continue
                month = month_names.index(month_dir.name)
                for emirate, city in pairs:
                    rel = prayer_module.calendar_relpath(int(year_dir.name), month, emirate, city)
                    if (cal_root / rel).is_file():
                        index.setdefault((emirate, city), []).append(f'{year_dir.name}-{month:02d}')
    _availability_cache['index'] = {key: sorted(months) for key, months in index.items()}
    return _availability_cache['index']


def _month_span(start, end):
    """Yield (year, month) for every month overlapping [start, end]."""
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        yield year, month
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


def _format_date(value):
    return f'{value.day} {calendar.month_name[value.month]} {value.year}'


def _format_period(start, end):
    if start == end:
        return _format_date(start)
    return f'{_format_date(start)} – {_format_date(end)}'


@app.after_request
def track_unique_visitor(response):
    """Assign a visitor cookie and log one telemetry event per unique browser."""
    if request.path == '/' and request.method == 'GET' and 'visitor_id' not in request.cookies:
        visitor_id = str(uuid.uuid4())
        response.set_cookie('visitor_id', visitor_id, max_age=60 * 60 * 24 * 365 * 5,
                            samesite='Lax', secure=request.is_secure, httponly=True)
        logger.info('unique_visitor %s', visitor_id)
    return response


def _persisted_visitor_count():
    """High-water mark committed to visitors.json by the daily snapshot workflow."""
    try:
        badge = json.loads((Path(root_dir) / 'visitors.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    message = badge.get('message') if isinstance(badge, dict) else None
    return int(message) if isinstance(message, str) and message.isdigit() else None


def _live_visitor_count():
    """Query Application Insights for the count of unique visitors (cached)."""
    if not (AI_APP_ID and AI_API_KEY):
        return None
    now = time.time()
    if _count_cache['value'] is not None and now - _count_cache['fetched_at'] < COUNT_CACHE_SECONDS:
        return _count_cache['value']
    try:
        resp = requests.get(
            f'https://api.applicationinsights.io/v1/apps/{AI_APP_ID}/query',
            params={'query': 'traces | where message startswith "unique_visitor " | summarize by message | count'},
            headers={'x-api-key': AI_API_KEY}, timeout=10)
        resp.raise_for_status()
        count = int(resp.json()['tables'][0]['rows'][0][0])
        _count_cache.update(value=count, fetched_at=now)
        return count
    except Exception as e:  # noqa: BLE001
        print(f'Error fetching visitor count: {e}')
        return _count_cache['value']


def get_visitor_count():
    """Unique visitors: the live count floored at the committed high-water mark.

    Application Insights retains telemetry for 90 days, so the live figure
    decays as old visitors age out; visitors.json never does.
    """
    counts = [c for c in (_live_visitor_count(), _persisted_visitor_count()) if c is not None]
    return max(counts) if counts else None


def _static_assets_ready():
    try:
        root = Path(root_dir)
        locations = json.loads((root / 'locations_cache.json').read_text(encoding='utf-8'))
        if not isinstance(locations, dict) or not all(
            isinstance(locations.get(key), list) and locations[key]
            for key in ('emirates', 'cities')
        ):
            return False
        calendar_file = next(
            (path for path in (root / 'calendars').rglob('*.ics') if path.is_file()), None
        )
        if calendar_file is None:
            return False
        with calendar_file.open('rb') as stream:
            return stream.readline(64).strip() == b'BEGIN:VCALENDAR'
    except (OSError, ValueError):
        return False


@app.route('/health', methods=['GET'])
def health():
    healthy = not STATIC_MODE or _static_assets_ready()
    return (
        {'status': 'healthy' if healthy else 'unhealthy'},
        200 if healthy else 503,
        {'Cache-Control': 'no-store'},
    )


@app.route('/')
def index():
    """Render the main page with the form"""
    # Emirates come from the committed locations cache; no credentials needed
    if STATIC_MODE:
        emirates = _load_locations().get('emirates', [])
    else:
        try:
            emirates = AWQAFApi.get_emirates() or []
        except Exception as e:  # noqa: BLE001
            print(f"Error fetching emirates: {e}")
            emirates = []
    
    # If no emirates available, show setup
    if not emirates:
        return render_template('setup-form.html')
    
    today = datetime.now(pytz.timezone(PrayerConfig.TIMEZONE)).strftime('%Y-%m-%d')

    return render_template('index.html',
                         emirates=emirates,
                         today=today,
                         static_mode=STATIC_MODE)


@app.route('/generate', methods=['POST'])
def generate():
    """Generate prayer times calendar"""
    emirate = request.form.get('emirate')
    city = request.form.get('city')
    start_str = request.form.get('start')
    end_str = (request.form.get('end') or '').strip()

    if not all([emirate, city, start_str]):
        return redirect(url_for('index'))

    try:
        start = date_cls.fromisoformat(start_str)
        end = date_cls.fromisoformat(end_str) if end_str else start
    except ValueError:
        return render_template('error.html', error='Invalid date format.')

    if start > end:
        return render_template('error.html', error='Start date must be on or before the end date.')
    if (end - start).days > 365:
        return render_template('error.html', error='Date range cannot exceed 366 days.')

    try:
        if STATIC_MODE:
            months = _availability_index().get((emirate, city), [])
            covered = set(months)
            has_data = any(f'{year}-{month:02d}' in covered
                           for year, month in _month_span(start, end))
            if not has_data:
                if months:
                    first_year, first_month = map(int, months[0].split('-'))
                    last_year, last_month = map(int, months[-1].split('-'))
                    last_day = calendar.monthrange(last_year, last_month)[1]
                    window = _format_period(date_cls(first_year, first_month, 1),
                                            date_cls(last_year, last_month, last_day))
                    error = (f'No calendar data is available for {city} in the selected range. '
                             f'Data is available {window}.')
                else:
                    error = f'No calendar data is available for {city}.'
                return render_template('error.html', error=error)

        return render_template('success.html',
                               emirate=emirate,
                               city=city,
                               start=start.isoformat(),
                               end=end.isoformat(),
                               period=_format_period(start, end))

    except Exception as e:  # noqa: BLE001
        return render_template('error.html', error=str(e))


@app.route('/download/<path:relpath>')
def download(relpath):
    """Download a generated .ics file by its path relative to the app root."""
    if not relpath.endswith('.ics'):
        return "File not found", 404
    filepath = safe_join(root_dir, relpath)
    if not filepath or not os.path.isfile(filepath):
        return "File not found", 404
    return send_file(filepath, as_attachment=True, download_name=os.path.basename(relpath))


@app.route('/download/day/<date>/<emirate>/<city>')
def download_day(date, emirate, city):
    """Serve a single-day calendar filtered from the month's pre-generated file."""
    from icalendar import Calendar

    try:
        sel = date_cls.fromisoformat(date)
    except ValueError:
        return "Invalid date", 400
    rel = prayer_module.calendar_relpath(sel.year, sel.month, emirate, city)
    filepath = safe_join(root_dir, 'calendars', *rel.split(os.sep))
    if not filepath or not os.path.isfile(filepath):
        return "File not found", 404

    cal = Calendar.from_ical(Path(filepath).read_bytes())
    out = Calendar()
    for key, val in cal.items():
        out.add(key, val)
    for comp in cal.walk('VEVENT'):
        dt = comp.decoded('dtstart')
        if (dt.date() if hasattr(dt, 'date') else dt).isoformat() == date:
            out.add_component(comp)

    return send_file(io.BytesIO(out.to_ical()), as_attachment=True,
                     download_name=f"{sel.day:02d}{calendar.month_name[sel.month]}.ics",
                     mimetype='text/calendar')


def _merged_static_range(start, end, emirate, city):
    """Merge in-range VEVENTs from monthly calendar files into one Calendar."""
    from icalendar import Calendar

    merged = None
    events = 0
    for year, month in _month_span(start, end):
        rel = prayer_module.calendar_relpath(year, month, emirate, city)
        path = safe_join(root_dir, 'calendars', *rel.split(os.sep))
        if not path or not os.path.isfile(path):
            continue
        source = Calendar.from_ical(Path(path).read_bytes())
        if merged is None:
            merged = Calendar()
            for key, val in source.items():
                merged.add(key, val)
        for comp in source.walk('VEVENT'):
            dt = comp.decoded('dtstart')
            event_date = dt.date() if hasattr(dt, 'date') else dt
            if start <= event_date <= end:
                merged.add_component(comp)
                events += 1
    return merged, events


def _live_range_calendar(start, end, emirate, city):
    """Build a range calendar from one AWQAF API response, in memory."""
    data = AWQAFApi._request_prayer_data(start.isoformat(), end.isoformat())
    prayertimes = []
    for item in data.get('prayerData', []):
        if item.get('areaNameEn', '').lower() != city.lower():
            continue
        formatted = AWQAFApi._format_prayer_item(item)
        if formatted:
            prayertimes.append(formatted)
    if not prayertimes:
        return None
    return CalendarGenerator({'prayertimes': prayertimes}, city, emirate,
                             base_dir=root_dir).build(date_range=(start, end))


@app.route('/download/range/<start>/<end>/<emirate>/<city>')
def download_range(start, end, emirate, city):
    """Serve one merged calendar covering an arbitrary date range."""
    try:
        start_date = date_cls.fromisoformat(start)
        end_date = date_cls.fromisoformat(end)
    except ValueError:
        return "Invalid date", 400
    if start_date > end_date:
        return "Invalid date range", 400
    if (end_date - start_date).days > 365:
        return "Date range cannot exceed 366 days", 400

    if STATIC_MODE:
        cal, event_count = _merged_static_range(start_date, end_date, emirate, city)
        if not event_count:
            return "File not found", 404
    else:
        try:
            cal = _live_range_calendar(start_date, end_date, emirate, city)
        except Exception as e:  # noqa: BLE001
            return f"Failed to fetch prayer times: {e}", 502
        if cal is None:
            return "File not found", 404

    safe_city = re.sub(r'[^A-Za-z0-9_-]+', '_', city)
    filename = f'PrayerTimes_{safe_city}_{start}_to_{end}.ics'
    return send_file(io.BytesIO(cal.to_ical()), as_attachment=True,
                     download_name=filename, mimetype='text/calendar')


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    """Handle setup through the web interface (local mode only)"""
    if STATIC_MODE:
        return redirect(url_for('index'))
    if request.method == 'POST':
        # Run the credential extraction
        try:
            creds = asyncio.run(prayer_module.extract_credentials())
            
            if creds:
                return render_template('setup-success.html')
            else:
                return render_template('setup-fail.html')
        except Exception as e:  # noqa: BLE001
            return render_template('setup-fail.html', error=str(e))
    
    # GET request - show setup form
    return render_template('setup-form.html')


@app.route('/cities/<emirate>')
def cities(emirate):
    """API endpoint to get cities for an emirate (for AJAX)"""
    try:
        cities = AWQAFApi.get_cities_for_emirate(emirate)
        return {'cities': cities}
    except Exception as e:  # noqa: BLE001
        return {'error': str(e)}, 500


@app.route('/api/locations')
def api_locations():
    """Emirates and cities with coordinates for the map selector."""
    locations = _load_locations()
    emirate_names = {e.get('emiratesId'): e.get('emirateNameEn')
                     for e in locations.get('emirates', [])}
    availability = _availability_index() if STATIC_MODE else {}
    cities = []
    for city in locations.get('cities', []):
        if city.get('enabled') is False:
            continue
        lat, lon = city.get('latitude'), city.get('longitude')
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        emirate = emirate_names.get(city.get('emirate'))
        name = city.get('cityNameEn')
        if not emirate or not name:
            continue
        cities.append({
            'id': city.get('cityID'),
            'emirate_id': city.get('emirate'),
            'emirate': emirate,
            'name': name,
            'lat': lat,
            'lon': lon,
            'available': bool(availability.get((emirate, name))) if STATIC_MODE else True,
        })
    emirates = [{'id': e.get('emiratesId'), 'name': e.get('emirateNameEn')}
                for e in locations.get('emirates', [])
                if e.get('emiratesId') is not None and e.get('emirateNameEn')]
    return {'emirates': emirates, 'cities': cities}


@app.route('/api/availability')
def api_availability():
    """Months with pre-generated data for a city, plus the usable date window."""
    if not STATIC_MODE:
        return {'static': False, 'months': None, 'min': None, 'max': None}
    emirate = request.args.get('emirate', '')
    city = request.args.get('city', '')
    if city:
        months = _availability_index().get((emirate, city), [])
    else:
        months = sorted({month for city_months in _availability_index().values()
                         for month in city_months})
    if not months:
        return {'static': True, 'months': [], 'min': None, 'max': None}
    last_year, last_month = map(int, months[-1].split('-'))
    last_day = calendar.monthrange(last_year, last_month)[1]
    return {
        'static': True,
        'months': months,
        'min': f'{months[0]}-01',
        'max': f'{months[-1]}-{last_day:02d}',
    }


@app.route('/api/visitors')
def api_visitors():
    """Return the unique visitor count for display on the site."""
    return {'count': get_visitor_count()}


@app.route('/badge/visitors')
def badge_visitors():
    """Shields.io endpoint-format JSON for the README visitor badge."""
    count = get_visitor_count()
    return {
        'schemaVersion': 1,
        'label': 'visitors',
        'message': str(count) if count is not None else 'n/a',
        'color': 'green',
    }


@app.route('/debug/net')
def debug_net():
    """Diagnostic endpoint: test connectivity to AWQAF services from this container"""
    targets = {
        'website': 'https://www.awqaf.gov.ae',
        'api': 'https://mobileappapi.awqaf.gov.ae/APIS/v3/prayer-time/EmiratesAndCities?lang=ar',
    }
    results = {}
    for name, url in targets.items():
        start = time.time()
        try:
            code = urllib.request.urlopen(url, timeout=15).status
            results[name] = f'HTTP {code} in {time.time() - start:.1f}s'
        except urllib.error.HTTPError as e:
            results[name] = f'HTTP {e.code} in {time.time() - start:.1f}s'
        except Exception as e:  # noqa: BLE001
            results[name] = f'{type(e).__name__}: {e} ({time.time() - start:.1f}s)'
    return results


if __name__ == '__main__':
    # For development only
    import os
    port = int(os.environ.get('PORT', '8080'))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
