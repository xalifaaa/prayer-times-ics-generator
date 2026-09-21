# UAE Prayer Times Calendar Events Generator

A Python application that generates a **single `.ics` file** on a day or month basis with prayer times **fetched from the official UAE AWQAF Prayer Time and Locations API.** This single-setup, hassle-free solution allows Muslims in the UAE to **seamlessly import all adhan-to-iqamah and prayer time events** into their calendars with just **one** `.ics` file.

The `.ics` file is compatible with popular calendar platforms such as **Google Calendar, Apple Calendar, Microsoft Outlook, and more**, ensuring easy integration without the need to import multiple files.

![Proton Calendar Example](https://i.imgur.com/2kYTCyC.png)

## Core Features

- **Guided Setup** - Interactive setup with automatic credential extraction from the AWQAF website
- **Smart Defaults** - Defaults to current month and year, with saved location preferences
- **Comprehensive Location Support** - Supports all 7 emirates and 60+ cities in the UAE
- **Automated Credential Extraction** - Uses Playwright to extract API tokens automatically
- **Dual Credential Support** - Handles both traditional client credentials and direct API tokens
- **Jummah Prayer Support** - Automatically includes Jummah prayer on Fridays (12:45 PM - 1:30 PM)
- **Configurable Prayer Durations** - Customizable adhan and prayer duration times
- **Color-coded Events** - Green for Adhan, Cerise for Prayer times
- **Automatic Token Management** - Handles authorization token refresh when needed

## Installation

1. Clone the repository:
```bash
git clone https://github.com/xalifaaa/prayer-times-ics-generator.git

cd prayer-times-ics-generator
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

3. Run the guided setup:
```bash
python prayer-times-ics-generator.py --setup
```

The guided setup will:
- Automatically extract API credentials from the AWQAF website using Playwright
- Save browser context and tokens for legitimate API access (v3 API)
- Let you select your preferred emirate and city from available options (7 emirates, 60+ cities)
- Set up default preferences for easy future use

**Note:** The AWQAF API has moved to v3 endpoints. The automated extraction is designed to work with the current API structure and saves both tokens and browser context for legitimate API access.

**Important**: Keep your `config.json` and `browser_context.json` files secure and never commit them to version control. The `.gitignore` file is configured to exclude these sensitive files.

## Usage

### First Time Setup

Run the guided setup for easy configuration:
```bash
python prayer-times-ics-generator.py --setup
```

### Generating Calendars

After setup, you can generate calendars using the simple command:
```bash
python prayer-times-ics-generator.py
```

This will generate a calendar for the current month and year using your default location.

### Advanced Usage

You can override defaults or specify different options:

```bash
# Generate for specific location
python prayer-times-ics-generator.py --city "Abu Dhabi" --emirate "Abu Dhabi"

# Generate for specific time period
python prayer-times-ics-generator.py --year 2026 --month 10

# Generate for a specific day
python prayer-times-ics-generator.py --day 15

# Combine options
python prayer-times-ics-generator.py --city "Sharjah" --emirate "Sharjah" --year 2026 --month 12
```

### Command Line Arguments

- `--setup`: Run guided setup for first-time users
- `--city`: City name (overrides default from setup)
- `--emirate`: Emirate name (overrides default from setup)
- `--year`: Year (default: current year)
- `--month`: Month number (1-12, default: current month)
- `--day`: Specific day (optional)
- `--list-emirates`: List all available emirates
- `--list-cities`: List all cities in the specified emirate
- `--show-help`: Show detailed help message

### Listing Emirates and Cities

To view available emirates and cities, use the following commands:

```bash
# List all emirates
python prayer-times-ics-generator.py --list-emirates

# List all cities in a specific emirate
python prayer-times-ics-generator.py --emirate "Dubai" --list-cities
```

Example output:
```
Available emirates:
  - Abu Dhabi
  - Dubai
  - Sharjah
  - Ajman
  - Um Al Quwain
  - Ras AlKhaimah
  - Fujairah

Cities in Dubai emirate:
  - Dubai
    Location: 25.113055, 55.108333
  - Rural Area dubai
    Location: 24.708611, 55.617499
  - Hatta
    Location: 24.79861, 56.114722
```

The city listing includes coordinates which may be useful for location-based features.

## Configuration

### Prayer Times Configuration

You can customize prayer durations by modifying the `PrayerConfig` class in the script:

```python
ADHAN_DURATIONS = {
    "fajr": 25,
    "zuhr": 20,
    "asr": 20,
    "maghrib": 5,
    "isha": 20
}

PRAYER_DURATION = 10

# Jummah prayer (Friday only)
JUMMAH_ADHAN_TIME = "12:45"  # Fixed adhan time
JUMMAH_DURATION = 45  # Duration in minutes
```

### Calendar Colors

Calendar event colors can be customized:
```python
ADHAN_COLOR = "#008000"  # Green
PRAYER_COLOR = "#ba1e55"  # Cerise
```

## Output

The script generates .ics files in the following format:

### Monthly calendar:
`year/month/emirate/city/[Month][Year].ics`

### Example:
`2026/September/Abu Dhabi/September2026.ics`

### Daily calendar:
`year/month/emirate/city/Day/day-[Day][Month].ics`

### Example:
`2026/September/Abu Dhabi/Day/15-September.ics`

## Security

- **Important**: Never commit your `config.json` or `browser_context.json` files to version control and keep your credentials secure
- The `.gitignore` file is configured to exclude sensitive files

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- AWQAF UAE for providing the prayer times API
- Contributors and maintainers of the project
