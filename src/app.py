"""
Flask web app for UAE Prayer Times Calendar Generator
Server-side rendered for speed and SEO
"""

import asyncio
import calendar
import importlib.util
import os
import sys
from datetime import datetime
from pathlib import Path

import pytz
from flask import Flask, redirect, render_template, request, send_file, url_for

# Set template folder to parent directory
app = Flask(__name__, template_folder='../templates')

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

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size


@app.route('/')
def index():
    """Render the main page with the form"""
    emirates = []
    
    # Try to fetch emirates, but don't fail if credentials aren't available
    try:
        if os.path.exists('config.json'):
            emirates = AWQAFApi.get_emirates()
            if not emirates:
                emirates = []
    except Exception as e:  # noqa: BLE001
        print(f"Error fetching emirates: {e}")
        emirates = []
    
    # If no emirates available, show setup
    if not emirates:
        return render_template('setup-form.html')
    
    current_year = datetime.now(pytz.timezone(PrayerConfig.TIMEZONE)).year
    current_month = datetime.now(pytz.timezone(PrayerConfig.TIMEZONE)).month
    
    months = {i: name for i, name in enumerate(calendar.month_name, start=1)}  # January through December
    years = list(range(current_year, current_year + 2))  # Current year and next year
    
    return render_template('index.html', 
                         emirates=emirates,
                         years=years,
                         months=months,
                         current_year=current_year,
                         current_month=current_month)


@app.route('/generate', methods=['POST'])
def generate():
    """Generate prayer times calendar"""
    emirate = request.form.get('emirate')
    city = request.form.get('city')
    year = int(request.form.get('year'))
    month = int(request.form.get('month'))
    
    if not all([emirate, city, year, month]):
        return redirect(url_for('index'))
    
    try:
        # Fetch prayer times
        prayer_data = AWQAFApi.fetch_prayer_times(year, month, None, city)
        
        # Generate calendar
        generator = CalendarGenerator(prayer_data, city, emirate)
        filepath = generator.generate()
        
        # Extract filename for download
        filename = os.path.basename(filepath)
        
        return render_template('success.html',
                             filename=filename,
                             city=city,
                             emirate=emirate,
                             year=year,
                             month=calendar.month_name[month])
    
    except Exception as e:  # noqa: BLE001
        return render_template('error.html', error=str(e))


@app.route('/download/<path:filename>')
def download(filename):
    """Download the generated ICS file"""
    # Find the file in the generated directories
    for root, dirs, files in os.walk('.'):
        if filename in files:
            filepath = os.path.join(root, filename)
            return send_file(filepath, as_attachment=True, download_name=filename)
    
    return "File not found", 404


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    """Handle setup through the web interface"""
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


if __name__ == '__main__':
    # Use environment variable for port, default to 5000
    port = int(os.environ.get('PORT', '5000'))
    # Disable debug mode in production
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
