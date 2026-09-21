"""
Flask web app for UAE Prayer Times Calendar Generator
Server-side rendered for speed and SEO
"""

import asyncio
import calendar
import importlib.util
import io
import logging
import os
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


@app.after_request
def track_unique_visitor(response):
    """Assign a visitor cookie and log one telemetry event per unique browser."""
    if request.path == '/' and request.method == 'GET' and 'visitor_id' not in request.cookies:
        visitor_id = str(uuid.uuid4())
        response.set_cookie('visitor_id', visitor_id, max_age=60 * 60 * 24 * 365 * 5,
                            samesite='Lax', secure=request.is_secure, httponly=True)
        logger.info('unique_visitor %s', visitor_id)
    return response


def get_visitor_count():
    """Query Application Insights for the count of unique visitors (cached)."""
    if not (AI_APP_ID and AI_API_KEY):
        return None
    now = time.time()
    if _count_cache['value'] is not None and now - _count_cache['fetched_at'] < COUNT_CACHE_SECONDS:
        return _count_cache['value']
    try:
        resp = requests.get(
            f'https://api.applicationinsights.io/v1/apps/{AI_APP_ID}/query',
            params={'query': 'traces | where message startswith "unique_visitor " | summarize dcount(message)'},
            headers={'x-api-key': AI_API_KEY}, timeout=10)
        resp.raise_for_status()
        count = int(resp.json()['tables'][0]['rows'][0][0])
        _count_cache.update(value=count, fetched_at=now)
        return count
    except Exception as e:  # noqa: BLE001
        print(f'Error fetching visitor count: {e}')
        return _count_cache['value']


@app.route('/')
def index():
    """Render the main page with the form"""
    emirates = []
    
    # Emirates come from the committed locations cache; no credentials needed
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
    date_str = request.form.get('date')
    scope = request.form.get('scope', 'month')

    if not all([emirate, city, date_str]):
        return redirect(url_for('index'))

    try:
        sel = date_cls.fromisoformat(date_str)
        year, month = sel.year, sel.month
        day = sel.day if scope == 'day' else None

        if STATIC_MODE:
            month_rel = prayer_module.calendar_relpath(year, month, emirate, city)
            month_path = safe_join(root_dir, os.path.join('calendars', month_rel))
            if not month_path or not os.path.isfile(month_path):
                raise FileNotFoundError('Calendar not available for the selected period.')
            day_params = {'date': date_str, 'emirate': emirate, 'city': city} if day else None
            relpath = None if day else os.path.join('calendars', month_rel)
        else:
            prayer_data = AWQAFApi.fetch_prayer_times(year, month, day, city)
            filepath = CalendarGenerator(prayer_data, city, emirate, base_dir=root_dir).generate(day)
            relpath = os.path.relpath(filepath, root_dir)
            day_params = None

        if relpath:
            relpath = relpath.replace(os.sep, '/')
        return render_template('success.html',
                             relpath=relpath,
                             day_params=day_params,
                             filename=os.path.basename(relpath) if relpath else f'{date_str}.ics',
                             city=city,
                             emirate=emirate,
                             year=year,
                             month=calendar.month_name[month])

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
    filepath = safe_join(root_dir, os.path.join('calendars', rel))
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
