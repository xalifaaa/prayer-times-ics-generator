# UAE Prayer (Salah) Times Calendar Event Generator

![Working Status](https://github.com/xalifaaa/prayer-times-ics-generator/actions/workflows/working.yml/badge.svg)

**Coming soon:** [https://prayer-times-uae.example.com](https://prayer-times-uae.example.com) *(To Be Hosted Soon..)*

**Easily import accurate UAE prayer times into any modern calendar as events with preset reminders.** This tool generates a ready-made `.ics` calendar file with all five daily prayers + Jummah. 

Works with Google Calendar, Microsoft Teams, Outlook Calendar, Apple Calendar, Proton Calendar, and more. 

Setup once, generate, and import once to get accurate prayer time events for your emirate and city in less than 30 seconds.

![Proton Calendar Example](https://i.imgur.com/2kYTCyC.png)

**All 5 Daily Prayers** | **Jummah Prayer** | **Adhan Reminders** | **One-Time Import** | **Mobile-Friendly** | **All 7 UAE Emirates, 60+ Cities** | **Official UAE AWQAF Data**

1. **Set up once:** Quick setup in 20 seconds
2. **Choose your location:** Select your emirate and city through the interactive GUI or command line
3. **Generate .ics file:** One tap or click for any month or day
4. **Import to any calendar:** Google Calendar, Microsoft Teams, Outlook, Apple Calendar, Proton Calendar
5. **Done:** Now your calendar has all 5 daily prayers automatically as calendar events

## Quick Start

### Web Interface

Visit the web app to generate your calendar directly in your browser - works on iOS, Android, MacOS, Windows, Linux, and more!

**Coming soon:** [https://prayer-times-uae.example.com](https://prayer-times-uae.example.com) *(To Be Hosted Soon..)*

### Self-Host Web App

Want to host it yourself? It's easy:

```bash
# Clone the repository
git clone https://github.com/xalifaaa/prayer-times-ics-generator.git
cd prayer-times-ics-generator

# Install dependencies
pip install -r requirements.txt

# Run the web app
python src/app.py
```

Visit `http://localhost:5000` in your browser.

### Command Line

```bash
# Clone the repository
git clone https://github.com/xalifaaa/prayer-times-ics-generator.git
cd prayer-times-ics-generator

# Install dependencies
pip install -r requirements.txt

# Run setup (30 seconds)
python main.py --setup

# Generate your calendar
python main.py
```

That's it. Import the `.ics` file into your calendar and you're done.

## Usage

### Web Interface

```bash
python app.py
```

Visit `http://localhost:5000` — works on mobile too.

### Command Line

**Generate for current month (your default location):**
```bash
python main.py
```

**Generate for a specific month:**
```bash
python main.py --year 2026 --month 10
```

**Generate for a different city:**
```bash
python main.py --city "Dubai" --emirate "Dubai"
```

**List available locations:**
```bash
python main.py --list-emirates
python main.py --emirate "Dubai" --list-cities
```

## Calendar Events

Each prayer includes two events:

**1. Adhan (Green)**
- Shows when adhan starts
- Duration varies by prayer (Fajr: 25min, Zuhr: 20min, etc.)
- Get notified exactly when adhan begins

**2. Prayer (Cerise)**
- Starts after adhan time (before iqamah)
- 10-minute duration
- 5-minute reminder before prayer time

**3. Jummah (Friday only, Cerise)**
- Friday at 12:45 PM
- 45-minute duration (until 1:30 PM)
- Replaces regular Zuhr on Fridays

## Customization

Want to adjust prayer durations or colors? Edit the `PrayerConfig` class in the script.

```python
ADHAN_DURATIONS = {
    "fajr": 25,
    "zuhr": 20,
    "asr": 20,
    "maghrib": 5,
    "isha": 20
}

JUMMAH_ADHAN_TIME = "12:45"
JUMMAH_DURATION = 45
```

## Tech Details

- **Data Source:** Official AWQAF UAE API (v3)
- **Coverage:** 7 emirates, 60+ cities across UAE
- **Format:** Standard .ics calendar file
- **Compatibility:** Google Calendar, Apple Calendar, Outlook, and more
- **Timezone:** GST (Gulf Standard Time)

## Security

Your credentials are stored locally in `config.json` and `browser_context.json`. These files are automatically excluded from version control (see `.gitignore`). Never share these files - they contain your API tokens.

## Reliability

Automated testing runs daily to ensure the tool works correctly:
- Code quality checks
- Security vulnerability scanning
- API connectivity verification

Check the "Working Status" badge at the top of this page.

## License

MIT License — use it freely for personal or commercial purposes.

---

**Made with ❤️ for Muslims in the UAE who want to stay connected to their faith without it disrupting their professional life.**
