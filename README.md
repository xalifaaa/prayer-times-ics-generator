# Prayer Times Calendar Generator

A Python application that generates .ics calendar files for Islamic prayer times using the UAE AWQAF API. The generated calendar can be imported into various calendar applications like Google Calendar, Apple Calendar, Microsoft Outlook, or any other calendar application that supports .ics files.

## Features

- Generates prayer times calendar in .ics format
- Uses official UAE AWQAF API for accurate prayer times
- Supports all seven emirates and cities in the UAE
- Configurable Adhan and prayer duration times
- Color-coded events for Adhan and prayer times
- Automatic token refresh handling

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/prayer_times_calendar.git
cd prayer_times_calendar
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `config.json` file in the project root with your AWQAF API credentials:
```json
{
    "clientGuid": "your_client_guid",
    "clientSecret": "your_client_secret"
}
```

**Important**: Keep your `config.json` file secure and never commit it to version control.

## Usage

Run the script with the following command:
```bash
python prayer_times_calendar.py --year 2025 --month 1 --city "Abu Dhabi" --emirate "Abu Dhabi"
```

### Command Line Arguments

- `--year`: Year to generate calendar for (required)
- `--month`: Month to generate calendar for (required)
- `--city`: City name (required)
- `--emirate`: Emirate name (required)
- `--day`: Specific day (optional)
- `--help`: Show help message

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
```

### Calendar Colors

Calendar event colors can be customized:
```python
ADHAN_COLOR = "#008000"  # Green
PRAYER_COLOR = "#ba1e55"  # Cerise
```

## Output

The script generates .ics files in the following format:
- Monthly calendar: `[YEAR]/[MONTH]_[CITY]_prayer_times.ics`
- Daily calendar: `[YEAR]/[MONTH]_[DAY]_[CITY]_prayer_times.ics`

## Security

- Never commit your `config.json` or `auth_token.json` files to version control
- Keep your client credentials secure
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
