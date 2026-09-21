# UAE Prayer (Salah) Times Calendar Event Generator

![Working Status](https://github.com/xalifaaa/prayer-times-ics-generator/actions/workflows/working.yml/badge.svg)

**Easily import accurate UAE prayer times into any modern calendar.** This tool generates a ready-made `.ics` calendar file with all five daily prayers + Jummah that works with Google Calendar, Apple Calendar, Outlook, and more. Just import once and get accurate prayer time events for your emirate and city.

![Proton Calendar Example](https://i.imgur.com/2kYTCyC.png)

## What You Get

- **All 5 Daily Prayers**
- **Jummah Prayer**
- **Adhan Reminders**
- **One-Time Import**
- **Mobile-Friendly**
- **7 Emirates, 60+ Cities**
- **Official UAE AWQAF Data**

## How It Works

**1. Set up once** — Run setup or use the web interface (30 seconds)
**2. Choose your location** — Select your emirate and city
**3. Generate .ics file** — One click for any month
**4. Import to calendar** — Google, Apple, Outlook — whatever you use
**5. Done** — Your calendar now has all prayer times automatically

## Quick Start

### Web Interface

Visit the web app to generate your calendar directly in your browser — works on iOS, Android, MacOS, Windows, Linux, and more!

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
python app.py
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
python prayer-times-ics-generator.py --setup

# Generate your calendar
python prayer-times-ics-generator.py
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
python prayer-times-ics-generator.py
```

**Generate for a specific month:**
```bash
python prayer-times-ics-generator.py --year 2026 --month 10
```

**Generate for a different city:**
```bash
python prayer-times-ics-generator.py --city "Dubai" --emirate "Dubai"
```

**List available locations:**
```bash
python prayer-times-ics-generator.py --list-emirates
python prayer-times-ics-generator.py --emirate "Dubai" --list-cities
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
- **Timezone:** Asia/Dubai (UAE Standard Time)

## Security

Your credentials are stored locally in `config.json` and `browser_context.json`. These files are automatically excluded from version control (see `.gitignore`). Never share these files — they contain your API tokens.

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
