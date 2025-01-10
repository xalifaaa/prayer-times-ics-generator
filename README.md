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
git clone https://github.com/xalifaaa/prayer-times-ics-generator.git
cd prayer-times-ics-generator
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

3. Rename `config-example.json` to `config.json` and follow the instructions in the `Setup` section to set up UAE AWQAF API credentials:
```json
{
    "clientGuid": "your_client_guid",
    "clientSecret": "your_client_secret"
}
```

4. Rename `auth_token-example.json` to `auth_token.json` in the project root for the program to store the authentication token:
```json
{
    "clientAccessToken": "your_Access_Token",
    "clientRefreshToken": "your_Refresh_Token",
    "refreshTokenExpiryTime": null
}
```

**Important**: Keep your `config.json` and `auth_token.json` files secure and never commit it to version control.

## Setup

Follow the steps below to locate your clientGUID and clientSecret and start using the script:
1. Head to https://www.awqaf.gov.ae
2. Clear Cookies
3. Open Developer Tools (Ctrl+Shift+I)/(F12)
4. Navigate to 'Network' tab
5. Refresh the page
6. Filter by JSON or XHR, depending on your browser
7. Locate 'mobileappapi.awqaf.gov.ae' within the 'Domain' column
8. Find the JSON file with today's date and click on it
9. Under 'Request Headers', locate 'Authorization' and note down the last 6 characters
10. Search through 'Reponse' of every JSON file called 'ClientAuthorization' to find the clientAccessToken with the same last 6 characters you noted down
11. Upon finding the matching 'ClientAuthorization' JSON file, copy the 'clientGUID' and 'clientSecret' values located within the 'Request' tab, and paste them into the 'config.json' file
12. Save the 'config.json' file

Video tutorial:

> **Work in progress**

After completing the setup, navigate to the 'Usage' section below to begin using the script.

## Usage

Run the script with the following command:
```bash
python prayer-times-ics-generator.py --year 2025 --month 1 --city "Abu Dhabi" --emirate "Abu Dhabi"
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
