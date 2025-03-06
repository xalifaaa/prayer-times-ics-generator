# UAE Prayer Times Calendar Events Generator

A Python application that generates a **single `.ics` file** on a day or month basis with prayer times **fetched from the official UAE AWQAF Prayer Time and Locations API.** This single-setup, hassle-free solution allows Muslims in the UAE to **seamlessly import all adhan-to-iqamah and prayer time events** into their calendars with just **one** `.ics` file.

The `.ics` file is compatible with popular calendar platforms such as **Google Calendar, Apple Calendar, Microsoft Outlook, and more**, ensuring easy integration without the need to import multiple files.

![Proton Calendar Example](https://i.imgur.com/2kYTCyC.png)

## Core Features

- One-time setup and easy configuration
- Generates adhan-to-iqamah and prayer time calendar events in `.ics` format to import into any commercially available calendar
- Uses official UAE AWQAF Prayer Times API for accurate prayer times
- Supports all seven emirates and sixty cities in the UAE
- Configurable Adhan and prayer duration times
- Color-coded events for Adhan and Prayer times
- Automatic authorization token refresh handling

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

3. Rename [config-example.json](config-example.json) to `config.json` and follow the instructions in the **Setup** section to set up UAE AWQAF API credentials:
```json
{
    "clientGuid": "your_client_guid",
    "clientSecret": "your_client_secret"
}
```

4. Rename [auth_token-example.json](auth_token-example.json) to `auth_token.json` in the project root for the program to store the authentication token:
```json
{
    "clientAccessToken": "your_Access_Token",
    "clientRefreshToken": "your_Refresh_Token",
    "refreshTokenExpiryTime": null
}
```

**Important**: Keep your `config.json` and `auth_token.json` files secure and never commit it to version control.

## Setup Guide

Follow the steps below to locate your `clientGUID` and `clientSecret` and start using the script: 
1. Visit https://www.awqaf.gov.ae.
2. Clear your browser cookies.
3. Open the Developer Tools (Ctrl+Shift+I or F12).
4. Navigate to the **Network** tab.
5. Refresh the page.
6. Filter by **JSON** or **XHR**, depending on your browser.
7. Look for `mobileappapi.awqaf.gov.ae` in the **Domain** column.
8. Find the JSON file with today’s date and click on it.
9. Under the **Request Headers** section, locate the `Authorization: Bearer:` field and note down the last 6 characters of its value.
10. Search through the **Response** tab of every JSON file labeled `ClientAuthorization` to find the `clientAccessToken` that matches the last 6 characters you noted.
11. Once you find the matching `ClientAuthorization` JSON file, copy the `clientGUID` and `clientSecret` values from the **Request** tab and paste them into the `config.json` file.
12. Save the `config.json` file.

After completing the setup, proceed to the **Usage** section below to begin using the script.

### Video tutorial:

> **Work in progress**

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
- `--list-emirates`: List all available emirates
- `--list-cities`: List all cities in the specified emirate
- `--help`: Show help message

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
>year\\month\\emirate\\city\\[Month][Year].ics

### Example: 
>2025\August\Dubai\Dubai\January2025.ics


### Daily calendar: 
>year\\month\\emirate\\city\\day\\prayer-times-[Day][Month].ics

### Example: 
>2025\August\Dubai\Dubai\prayer-times-01August.ics

## Security

- **Important**: Never commit your `config.json` or `auth_token.json` files to version control and keep your client credentials secure
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
