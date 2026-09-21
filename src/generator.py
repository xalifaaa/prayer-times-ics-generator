"""
UAE Prayer Times Calendar Events Generator
Generates .ics calendar files for prayer times using the official UAE AWQAF Prayer Times and Locations API.
"""

import argparse
import asyncio
import calendar
import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Any, ClassVar
from urllib.parse import parse_qs, urlparse

import pytz
import requests
from icalendar import Alarm, Calendar, Event
from playwright.async_api import async_playwright


class APIError(Exception):
    """Exception raised for API-related errors."""

# Extracted credential extraction functionality
SITE = "https://www.awqaf.gov.ae"
API_HOST = "mobileappapi.awqaf.gov.ae"
CONFIG_FILE = "config.json"
CONTEXT_FILE = "browser_context.json"
SETTLE_MS = 10000
HEADLESS = True


def walk(obj, key):
    """Recursively collect every value stored under `key` in nested dicts/lists."""
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                hits.append(v)
            hits.extend(walk(v, key))
    elif isinstance(obj, list):
        for item in obj:
            hits.extend(walk(item, key))
    return hits


def extract_pair(req):
    """Pull clientGUID / clientSecret out of a request (POST body or query string)."""
    try:
        pdata = req.post_data_json or {}
    except (AttributeError, ValueError):
        pdata = {}
    
    guids = walk(pdata, "clientGUID")
    secrets = walk(pdata, "clientSecret")
    
    if not (guids and secrets):
        qs = parse_qs(urlparse(req.url).query)
        guids = guids or qs.get("clientGUID", [])
        secrets = secrets or qs.get("clientSecret", [])
    
    if guids and secrets:
        return guids[0], secrets[0]
    
    return None


def resolve(bearer_tokens, candidates):
    """Extract tokens from the authentication response."""
    for tokens, req, body in candidates:
        if body and isinstance(body, dict) and 'clientAccessToken' in body and 'clientRefreshToken' in body:
            return {
                'clientAccessToken': body['clientAccessToken'],
                'clientRefreshToken': body['clientRefreshToken'],
                'refreshTokenExpiryTime': body.get('refreshTokenExpiryTime')
            }
    
    return None


def save_config(creds):
    """Save credentials to config file."""
    config = {}
    try:
        with open(CONFIG_FILE) as fh:
            config = json.load(fh)
    except (OSError, ValueError):
        pass
    config.update(creds)
    with open(CONFIG_FILE, "w") as fh:
        json.dump(config, fh, indent=2)


async def extract_credentials():
    """Extract credentials from AWQAF website using Playwright."""
    bearer_tokens = []
    candidates = []
    credentials = None

    print(f"Launching browser (headless={HEADLESS})...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context()
        page = await context.new_page()

        async def on_response(response):
            nonlocal credentials
            req = response.request
            if API_HOST not in response.url and API_HOST not in req.url:
                return

            try:
                headers = await req.all_headers()
            except (AttributeError, RuntimeError):
                headers = {}
            auth = headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                bearer_tokens.append(auth.split(None, 1)[1].strip())

            try:
                body = await response.json()
            except (AttributeError, ValueError):
                return
            
            tokens = walk(body, "clientAccessToken")
            if tokens:
                candidates.append((tokens, req, body))
            
            pair = extract_pair(req)
            if pair and not credentials:
                credentials = pair

        page.on("response", on_response)
        print(f"Navigating to {SITE}...")
        await page.goto(SITE, wait_until="domcontentloaded", timeout=60000)
        print("Waiting for network to settle...")
        await page.wait_for_load_state("networkidle")
        print(f"Waiting {SETTLE_MS/1000}s for late XHRs...")
        await page.wait_for_timeout(SETTLE_MS)

        if not candidates:
            print("No auth exchange found, reloading page...")
            await page.reload(wait_until="domcontentloaded")
            await page.wait_for_load_state("networkidle")
            print(f"Waiting {SETTLE_MS/1000}s for late XHRs...")
            await page.wait_for_timeout(SETTLE_MS)

        print("Saving browser context...")
        await context.storage_state(path=CONTEXT_FILE)

        print("Closing browser...")
        await context.close()
        await browser.close()

    print("\nHarvest complete:")
    print(f"  Bearer tokens seen:               {len(bearer_tokens)}")
    print(f"  ClientAuthorization exchanges:    {len(candidates)}")
    print(f"  Client credentials found:        {'Yes' if credentials else 'No'}")

    if credentials:
        print("Using client credentials from request")
        creds = {"clientGUID": credentials[0], "clientSecret": credentials[1]}
    else:
        print("Using tokens from response")
        creds = resolve(bearer_tokens, candidates)
        if not creds:
            print("\nNo credentials or tokens found.")
            print("Suggestions:")
            print("  1. Try setting HEADLESS = False in the script")
            print("  2. Increase SETTLE_MS if the site is slow")
            print("  3. Check if the site structure has changed")
            return None

    save_config(creds)
    masked = {
        k: (v[:4] + "..." + v[-4:]) if isinstance(v, str) and len(v) > 8 else "***"
        for k, v in creds.items()
    }
    print(f"\n[OK] Successfully wrote {CONFIG_FILE}: {masked}")
    print(f"[OK] Saved browser context to {CONTEXT_FILE}")
    
    return creds


class ConfigError(Exception):
    """Exception raised for configuration errors."""


class TokenError(Exception):
    """Exception raised for token-related errors."""


class PrayerConfig:
    """Configuration class for prayer times and calendar settings"""
    TIMEZONE: str = "Asia/Dubai"
    
    # Prayer durations in minutes
    ADHAN_DURATIONS: ClassVar[dict[str, int]] = {
        "fajr": 25,
        "zuhr": 20,
        "asr": 20,
        "maghrib": 5,
        "isha": 20
    }
    PRAYER_DURATION: ClassVar[int] = 10
    
    # Jummah prayer configuration (Friday only)
    JUMMAH_ADHAN_TIME: ClassVar[str] = "12:45"  # Fixed adhan time for Jummah
    JUMMAH_DURATION: ClassVar[int] = 45  # From 12:45 to 1:30 = 45 minutes
    
    # Calendar colors
    ADHAN_COLOR: ClassVar[str] = "#008000"  # Green
    PRAYER_COLOR: ClassVar[str] = "#ba1e55"  # Proton Calendar's Cerise

class TokenManager:
    """Manages the authentication token for AWQAF API"""
    TOKEN_FILE = "auth_token.json"
    CONFIG_FILE = "config.json"
    TOKEN_URL = "https://mobileappapi.awqaf.gov.ae/APIS/v2/sso/ClientAuthorization?lang=ar"
    REFRESH_URL = "https://mobileappapi.awqaf.gov.ae/APIS/v2/sso/ClientAuthorization?lang=ar"
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # seconds
    TIMEZONE = pytz.timezone('Asia/Dubai')
    
    @classmethod
    def _load_config(cls) -> dict:
        """
        Load client configuration from config file.
        
        Returns:
            dict: Configuration containing credentials
            
        Raises:
            Exception: If config file is missing or invalid
        """
        try:
            with open(cls.CONFIG_FILE, 'r') as f:
                config = json.load(f)
                
            # Check if we have client credentials (traditional method)
            has_client_creds = all(field in config for field in ('clientGuid', 'clientSecret'))
            # Check if we have direct tokens (automated extraction)
            has_direct_tokens = all(field in config for field in ('clientAccessToken', 'clientRefreshToken'))
            
            if not (has_client_creds or has_direct_tokens):
                raise KeyError("Missing required fields in config file")
                
            return config
        except FileNotFoundError:
            raise ConfigError(
                f"Configuration file '{cls.CONFIG_FILE}' not found. "
                "Please create it with your client credentials."
            )
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON format in {cls.CONFIG_FILE}: {e!s}")
        except KeyError as e:
            raise ConfigError(f"Invalid config file structure: {e!s}")
    
    @classmethod
    def get_token(cls) -> str:
        """
        Get a valid token, refreshing if necessary.
        
        Returns:
            str: Valid authentication token
            
        Raises:
            Exception: If token file is invalid or token refresh fails
        """
        try:
            with open(cls.TOKEN_FILE, 'r') as f:
                try:
                    token_data = json.load(f)
                except json.JSONDecodeError:
                    return cls.refresh_token()
                
                # Validate token data structure
                required_fields = {'clientAccessToken', 'clientRefreshToken', 'refreshTokenExpiryTime'}
                if not all(field in token_data for field in required_fields):
                    return cls.refresh_token()
                
                # If we have no expiry time or empty tokens, refresh
                if (token_data['refreshTokenExpiryTime'] is None or 
                    not token_data['clientAccessToken'] or 
                    not token_data['clientRefreshToken']):
                    return cls.refresh_token()
                
                return token_data['clientAccessToken']
                    
        except FileNotFoundError:
            return cls.refresh_token()

    @classmethod
    def refresh_token(cls, retry_count: int = 0) -> str:
        """
        Refresh the access token using client credentials or use direct tokens.
        
        Args:
            retry_count (int): Current retry attempt number
            
        Returns:
            str: New access token
            
        Raises:
            Exception: If token refresh fails after all retries
        """
        try:
            config = cls._load_config()
        except ConfigError as e:
            raise TokenError(f"Failed to load configuration: {e!s}")
        
        # Check if we have direct tokens (from automated extraction)
        if 'clientAccessToken' in config and 'clientRefreshToken' in config:
            print("Using direct tokens from config")
            token_data = {
                'clientAccessToken': config['clientAccessToken'],
                'clientRefreshToken': config['clientRefreshToken'],
                'refreshTokenExpiryTime': config.get('refreshTokenExpiryTime')
            }
            
            # Save to token file for consistency
            with open(cls.TOKEN_FILE, 'w') as f:
                json.dump(token_data, f, indent=4)
            
            return token_data['clientAccessToken']
            
        # Original method: use client credentials to get tokens
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        data = {
            "clientGuid": config['clientGuid'],
            "clientSecret": config['clientSecret']
        }
        
        try:
            # First attempt with existing token
            response = requests.post(cls.REFRESH_URL, headers=headers, json=data, timeout=10)
            response.raise_for_status()
            
            response_data = response.json()
            
            if not response_data.get('isSuccess', False):
                error_desc = response_data.get('errorDescription', 'Unknown error')
                raise ValueError(f"Authorization failed: {error_desc}")
            
            token_data = {
                'clientAccessToken': response_data['clientAccessToken'],
                'clientRefreshToken': response_data['clientRefreshToken'],
                'refreshTokenExpiryTime': response_data['refreshTokenExpiryTime']
            }
            
            # Save new token data
            with open(cls.TOKEN_FILE, 'w') as f:
                json.dump(token_data, f, indent=4)
            
            return token_data['clientAccessToken']
            
        except (requests.exceptions.RequestException, ValueError) as e:
            if retry_count < cls.MAX_RETRIES:
                import time
                time.sleep(cls.RETRY_DELAY * (retry_count + 1))
                return cls.refresh_token(retry_count + 1)
            raise TokenError(f"Failed to refresh token after {cls.MAX_RETRIES} attempts: {e!s}")

class AWQAFApi:
    """Handles interactions with the AWQAF Prayer Times API"""
    BASE_URL = "https://mobileappapi.awqaf.gov.ae/APIS/v3/prayer-time/prayertimes"
    LOCATIONS_URL = "https://mobileappapi.awqaf.gov.ae/APIS/v3/prayer-time/EmiratesAndCities"
    LOCATIONS_CACHE_FILE = "locations_cache.json"
    CONTEXT_FILE = "browser_context.json"

    @staticmethod
    def _api_headers(token: str) -> dict[str, str]:
        """Headers mimicking the official site's API calls."""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Authorization': f'Bearer {token}',
            'Origin': 'https://www.awqaf.gov.ae',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Referer': 'https://www.awqaf.gov.ae/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'Sec-GPC': '1'
        }

    @classmethod
    def _request_prayer_data(cls, start_date: str, end_date: str) -> dict[str, Any]:
        """
        Fetch raw prayer data for a date range via plain HTTP.
        The response contains every city; callers filter by areaNameEn.
        """
        url = f"{cls.BASE_URL}/{start_date}/{end_date}?lang=ar"

        try:
            response = requests.get(url, headers=cls._api_headers(TokenManager.get_token()))
            if response.status_code == 401:
                response = requests.get(url, headers=cls._api_headers(TokenManager.refresh_token()))
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise APIError(f"Failed to fetch prayer times: {e!s}")

    @staticmethod
    def _format_prayer_item(item: dict[str, Any]) -> dict[str, Any] | None:
        """Convert one raw prayerData entry to {date, timings} format."""
        date = item.get('gDate', '').split('T')[0]
        if not date:
            return None

        prayer_times = {}
        for prayer in ('fajr', 'zuhr', 'asr', 'maghrib', 'isha'):
            prayer_times[prayer] = ''
            time_str = item.get(prayer, '')
            if not time_str:
                continue
            time_part = time_str.split('T')[1].split('.')[0]
            try:
                time_obj = datetime.strptime(time_part, '%H:%M:%S').replace(tzinfo=pytz.timezone(PrayerConfig.TIMEZONE))
                prayer_times[prayer] = time_obj.strftime('%H:%M')
            except ValueError:
                print(f"Warning: Could not parse time {time_part} for {prayer}")

        return {"date": date, "timings": prayer_times}
    
    @classmethod
    def get_locations(cls) -> dict[str, Any]:
        """
        Get emirates and cities data from cache or API.
        
        Returns:
            Dict containing emirates and cities data
        """
        try:
            # Try to read from cache first
            if os.path.exists(cls.LOCATIONS_CACHE_FILE):
                with open(cls.LOCATIONS_CACHE_FILE, 'r') as f:
                    cached = json.load(f)
                if cached.get("emirates") and cached.get("cities"):
                    return cached
        except (OSError, json.JSONDecodeError):
            pass  # If any error occurs reading cache, fetch from API
        
        # Try using Playwright if browser context is available
        if os.path.exists(cls.CONTEXT_FILE):
            try:
                data = cls._fetch_locations_playwright()
                if data.get("emirates"):
                    with open(cls.LOCATIONS_CACHE_FILE, 'w') as f:
                        json.dump(data, f, indent=2)
                return data
            except (OSError, ValueError, RuntimeError):
                pass  # Fall back to regular API
            
        # Prepare API request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Authorization': f'Bearer {TokenManager.get_token()}',
            'Origin': 'https://www.awqaf.gov.ae',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Referer': 'https://www.awqaf.gov.ae/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'Sec-GPC': '1'
        }
        
        params = {
            'lang': 'ar',
            'source': 'web'
        }
        
        try:
            # First attempt with existing token
            response = requests.get(cls.LOCATIONS_URL, headers=headers, params=params, timeout=30)
            
            # If unauthorized, try once more with a fresh token
            if response.status_code == 401:
                headers['Authorization'] = f'Bearer {TokenManager.refresh_token()}'
                response = requests.get(cls.LOCATIONS_URL, headers=headers, params=params, timeout=30)
                
            response.raise_for_status()
            data = response.json()
            
            # Cache the results
            with open(cls.LOCATIONS_CACHE_FILE, 'w') as f:
                json.dump(data, f, indent=2)
                
            return data
        except (requests.RequestException, json.JSONDecodeError) as e:
            print(f"Error fetching locations: {e!s}")
            return {"emirates": [], "cities": []}
            
    @classmethod
    def get_emirates(cls) -> list[dict[str, str]]:
        """Get list of all emirates"""
        return cls.get_locations().get("emirates", [])
        
    @classmethod
    def get_cities_for_emirate(cls, emirate: str) -> list[dict[str, Any]]:
        """
        Get list of cities for a specific emirate
        
        Args:
            emirate: Name of the emirate (in English)
            
        Returns:
            List of city dictionaries containing name, coordinates, etc.
        """
        # Find emirate ID
        locations = cls.get_locations()
        emirate_id = None
        for e in locations.get("emirates", []):
            if e.get("emirateNameEn", "").lower() == emirate.lower():
                emirate_id = e.get("emiratesId")
                break
                
        if emirate_id is None:
            return []
            
        # Get cities for this emirate
        return [
            city for city in locations.get("cities", [])
            if city.get("emirate") == emirate_id
        ]
    
    @classmethod
    def _fetch_locations_playwright(cls) -> dict[str, Any]:
        """Fetch locations using Playwright with saved browser context."""
        # Read config file before async function
        auth_token = None
        try:
            with open(CONFIG_FILE) as f:
                config = json.load(f)
            if 'clientAccessToken' in config:
                auth_token = config['clientAccessToken']
        except (OSError, json.JSONDecodeError):
            pass
        
        async def _fetch():
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(storage_state=cls.CONTEXT_FILE)
                page = await context.new_page()
                
                # Set authorization header from saved tokens
                if auth_token:
                    await page.set_extra_http_headers({
                        'Authorization': f'Bearer {auth_token}'
                    })
                
                url = f"{cls.LOCATIONS_URL}?lang=ar"
                response = await page.goto(url)
                if response.status != 200:
                    await context.close()
                    await browser.close()
                    raise APIError(f"API request failed: {response.status}")
                
                body = await response.body()
                data = json.loads(body.decode())
                
                await context.close()
                await browser.close()
                return data
        
        return asyncio.run(_fetch())
    
    @classmethod
    def _fetch_prayer_times_playwright(cls, year: int, month: int, day: int | None, city: str) -> dict[str, Any]:
        """Fetch prayer times using Playwright with saved browser context."""
        import calendar
        
        # Format dates for API request
        if day:
            start_date = end_date = f"{year}-{month:02d}-{day:02d}"
        else:
            _, last_day = calendar.monthrange(year, month)
            start_date = f"{year}-{month:02d}-01"
            end_date = f"{year}-{month:02d}-{last_day}"
        
        url = f"{cls.BASE_URL}/{start_date}/{end_date}?lang=ar"
        
        # Read config file before async function
        auth_token = None
        try:
            with open(CONFIG_FILE) as f:
                config = json.load(f)
            if 'clientAccessToken' in config:
                auth_token = config['clientAccessToken']
        except (OSError, json.JSONDecodeError):
            pass
        
        async def _fetch():
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(storage_state=cls.CONTEXT_FILE)
                page = await context.new_page()
                
                # Set authorization header from saved tokens
                if auth_token:
                    await page.set_extra_http_headers({
                        'Authorization': f'Bearer {auth_token}'
                    })
                
                response = await page.goto(url)
                if response.status != 200:
                    await context.close()
                    await browser.close()
                    raise APIError(f"API request failed: {response.status}")
                
                body = await response.body()
                data = json.loads(body.decode())
                
                await context.close()
                await browser.close()
                return data
        
        data = asyncio.run(_fetch())
        
        # Format the data to match the expected structure
        formatted_data = {
            "prayertimes": []
        }
        
        # Process each day's prayer times
        for item in data.get('prayerData', []):
            try:
                # Check if this is for the requested city
                if item.get('areaNameEn', '').lower() != city.lower():
                    continue
                
                # Get the date
                date = item.get('gDate', '').split('T')[0]
                if not date:
                    continue
                
                # Extract prayer times
                prayer_times = {}
                for prayer, api_field in [
                    ('fajr', 'fajr'),
                    ('zuhr', 'zuhr'),
                    ('asr', 'asr'),
                    ('maghrib', 'maghrib'),
                    ('isha', 'isha')
                ]:
                    time_str = item.get(api_field, '')
                    if time_str:
                        # Extract just the time part (HH:MM:SS) from the datetime string
                        time_part = time_str.split('T')[1].split('.')[0]
                        # Convert to 24-hour format
                        try:
                            time_obj = datetime.strptime(time_part, '%H:%M:%S').replace(tzinfo=pytz.timezone(PrayerConfig.TIMEZONE))
                            prayer_times[prayer] = time_obj.strftime('%H:%M')
                        except ValueError:
                            print(f"Warning: Could not parse time {time_part} for {prayer}")
                            prayer_times[prayer] = ''
                    else:
                        prayer_times[prayer] = ''
                
                # Add prayer times
                formatted_data["prayertimes"].append({
                    "date": date,
                    "timings": prayer_times
                })
            except (ValueError, KeyError) as e:
                print(f"Error processing prayer times for a day: {e!s}")
                continue
        
        if not formatted_data["prayertimes"]:
            raise ValueError(f"No prayer times data found for city: {city}")
        
        return formatted_data

    @staticmethod
    def fetch_prayer_times(year: int, month: int, day: int | None, city: str) -> dict[str, Any]:
        """
        Fetch prayer times from AWQAF API
        Args:
            year: Year to fetch prayer times for
            month: Month to fetch prayer times for
            day: Optional specific day to fetch prayer times for
            city: City name
        Returns:
            Dictionary containing prayer times data
        """
        # Try using Playwright if browser context is available
        if os.path.exists(AWQAFApi.CONTEXT_FILE):
            try:
                print("Using Playwright with saved browser context...")
                return AWQAFApi._fetch_prayer_times_playwright(year, month, day, city)
            except (OSError, ValueError, RuntimeError, APIError) as e:
                print(f"Playwright fetch failed, falling back to regular API: {e}")
        
        # Fall back to regular API method
        print("Using regular API method...")

        # Format dates for API request
        if day:
            # If day is specified, fetch only that day
            start_date = end_date = f"{year}-{month:02d}-{day:02d}"
        else:
            # Get first and last day of the month
            _, last_day = calendar.monthrange(year, month)
            start_date = f"{year}-{month:02d}-01"
            end_date = f"{year}-{month:02d}-{last_day:02d}"

        data = AWQAFApi._request_prayer_data(start_date, end_date)

        formatted_data = {"prayertimes": []}
        for item in data.get('prayerData', []):
            if item.get('areaNameEn', '').lower() != city.lower():
                continue
            try:
                formatted = AWQAFApi._format_prayer_item(item)
                if formatted:
                    formatted_data["prayertimes"].append(formatted)
            except (ValueError, KeyError) as e:
                print(f"Error processing prayer times for a day: {e!s}")

        if not formatted_data["prayertimes"]:
            raise ValueError(f"No prayer times data found for city: {city}")

        return formatted_data

def calendar_relpath(year: int, month: int, emirate: str, city: str, day: int | None = None) -> str:
    """Relative path of a generated calendar file under the output root."""
    month_name = calendar.month_name[month]
    base = os.path.join(str(year), month_name, emirate)
    if emirate != city:
        base = os.path.join(base, city)
    if day:
        return os.path.join(base, "Daily", f"{day:02d}{month_name}.ics")
    return os.path.join(base, f"{month_name}{year}.ics")


class CalendarGenerator:
    """Handles generation of .ics calendar files"""
    def __init__(self, prayer_data: dict[str, Any], city: str, emirate: str, base_dir: str = ""):
        self.prayer_data = prayer_data
        self.city = city
        self.emirate = emirate
        self.base_dir = base_dir
        self.first_date = datetime.strptime(prayer_data["prayertimes"][0]["date"], "%Y-%m-%d").replace(tzinfo=pytz.timezone(PrayerConfig.TIMEZONE))
    
    def _create_base_calendar(self) -> Calendar:
        """Create a base calendar with common properties"""
        cal = Calendar()
        cal.add('prodid', '-//Prayer Times Calendar Generator//EN')
        cal.add('version', '2.0')
        cal.add('calscale', 'GREGORIAN')
        cal.add('method', 'PUBLISH')
        cal.add('x-wr-calname', f'{self.city} Prayer Times')
        cal.add('x-wr-timezone', PrayerConfig.TIMEZONE)
        return cal
    
    def _create_event_uid(self, event_str: str) -> str:
        """Generate a unique identifier for calendar events"""
        return hashlib.md5(event_str.encode()).hexdigest()
    
    def _create_alarm(self, description: str, trigger: timedelta) -> Alarm:
        """Create an alarm component for events"""
        alarm = Alarm()
        alarm.add('action', 'DISPLAY')
        alarm.add('description', description)
        alarm.add('trigger', trigger)
        return alarm
    
    def _create_adhan_event(self, date: str, prayer: str, time: str) -> Event:
        """Create an Adhan event"""
        event_dt = self._parse_datetime(f"{date} {time}")
        
        event = Event()
        event_str = f"{date}_{prayer}_adhan_{self.city}"
        event['uid'] = self._create_event_uid(event_str)
        
        # Set event times
        duration = PrayerConfig.ADHAN_DURATIONS[prayer]
        event.add('dtstart', event_dt)
        event.add('dtend', event_dt + timedelta(minutes=duration))
        
        # Set event properties
        event.add('summary', f'{prayer.title()} Adhan till Iqamah')
        event.add('description', f'{prayer.title()} Adhan Time for {self.city}')
        event.add('location', self.city)
        event.add('color', PrayerConfig.ADHAN_COLOR)
        
        # Add notification
        alarm = self._create_alarm(f'{prayer.title()} Adhan', timedelta(minutes=0))
        event.add_component(alarm)
        
        return event
    
    def _create_prayer_event(self, date: str, prayer: str, time: str, adhan_duration: int) -> Event:
        """Create a Prayer event"""
        event_dt = self._parse_datetime(f"{date} {time}")
        prayer_start = event_dt + timedelta(minutes=adhan_duration)
        
        event = Event()
        event_str = f"{date}_{prayer}_prayer_{self.city}"
        event['uid'] = self._create_event_uid(event_str)
        
        # Set event times
        event.add('dtstart', prayer_start)
        event.add('dtend', prayer_start + timedelta(minutes=PrayerConfig.PRAYER_DURATION))
        
        # Set event properties
        event.add('summary', f'{prayer.title()} Prayer')
        event.add('description', f'{prayer.title()} Prayer Time for {self.city}')
        event.add('location', self.city)
        event.add('color', PrayerConfig.PRAYER_COLOR)
        
        # Add notification
        alarm = self._create_alarm(f'{prayer.title()} Prayer in 5 minutes', timedelta(minutes=-5))
        event.add_component(alarm)
        
        return event
    
    def _create_jummah_event(self, date: str) -> Event:
        """Create a Jummah prayer event (Friday only)"""
        event_dt = self._parse_datetime(f"{date} {PrayerConfig.JUMMAH_ADHAN_TIME}")
        
        event = Event()
        event_str = f"{date}_jummah_{self.city}"
        event['uid'] = self._create_event_uid(event_str)
        
        # Set event times (Jummah lasts from 12:45 to 1:30 = 45 minutes)
        event.add('dtstart', event_dt)
        event.add('dtend', event_dt + timedelta(minutes=PrayerConfig.JUMMAH_DURATION))
        
        # Set event properties
        event.add('summary', 'Jummah Prayer')
        event.add('description', 'Jummah (Friday) Prayer Time')
        event.add('location', self.city)
        event.add('color', PrayerConfig.PRAYER_COLOR)
        
        # Add notification
        alarm = self._create_alarm('Jummah Prayer in 5 minutes', timedelta(minutes=-5))
        event.add_component(alarm)
        
        return event
    
    def _parse_datetime(self, time_str: str) -> datetime:
        """Parse prayer time string into datetime object"""
        return datetime.fromisoformat(time_str).replace(tzinfo=pytz.timezone(PrayerConfig.TIMEZONE))
    
    def _get_output_path(self, day: int | None = None) -> tuple[str, str]:
        """Get output directory and filename for calendar file"""
        rel = calendar_relpath(self.first_date.year, self.first_date.month,
                               self.emirate, self.city, day)
        return os.path.join(self.base_dir, os.path.dirname(rel)), os.path.basename(rel)
    
    def generate(self, day: int | None = None) -> str:
        """
        Generate .ics calendar file
        Args:
            day: Optional specific day to generate calendar for
        Returns:
            Path to generated calendar file
        """
        cal = self._create_base_calendar()
        
        # Process each day's prayer times
        for day_data in self.prayer_data["prayertimes"]:
            date = day_data["date"]
            
            # If specific day is requested, skip other days
            if day:
                current_day = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=pytz.timezone(PrayerConfig.TIMEZONE)).day
                if current_day != day:
                    continue
            
            # Check if this is Friday (weekday 4 in Python)
            date_obj = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=pytz.timezone(PrayerConfig.TIMEZONE))
            is_friday = date_obj.weekday() == 4  # Monday=0, Friday=4
            
            # Process each prayer
            for prayer in ["fajr", "zuhr", "asr", "maghrib", "isha"]:
                time = day_data["timings"][prayer]
                if not time:  # Skip if no time available
                    continue
                
                try:
                    # On Friday, replace Zuhr with Jummah
                    if prayer == "zuhr" and is_friday:
                        # Create Jummah event instead of Zuhr
                        jummah_event = self._create_jummah_event(date)
                        cal.add_component(jummah_event)
                        continue
                    
                    # Create Adhan event
                    adhan_event = self._create_adhan_event(date, prayer, time)
                    cal.add_component(adhan_event)
                    
                    # Create Prayer event
                    prayer_event = self._create_prayer_event(date, prayer, time, PrayerConfig.ADHAN_DURATIONS[prayer])
                    cal.add_component(prayer_event)
                    
                except (ValueError, KeyError) as e:
                    print(f"Error creating events for {date} {prayer}: {e!s}")
                    continue
        
        # Save calendar to file
        output_dir, filename = self._get_output_path(day)
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'wb') as f:
            f.write(cal.to_ical())
        
        return filepath

def print_help():
    """Print help information about the script"""
    help_text = """
Prayer Times Calendar Generator

Usage:
    python prayer-times-ics-generator.py [options]

Options:
    --setup              Run guided setup for first-time users
    --city CITY          City name (overrides default from setup)
    --emirate EMIRATE    Emirate name (overrides default from setup)
    --year YEAR          Year (default: current year)
    --month MONTH        Month number (1-12, default: current month)
    --day DAY            Optional: Generate calendar for specific day only
    --list-emirates     List all emirates
    --list-cities       List all cities for the specified emirate
    --show-help         Show this help message

Examples:
    # First-time setup (recommended)
    python prayer-times-ics-generator.py --setup

    # Generate calendar for current month/year using default location
    python prayer-times-ics-generator.py

    # Generate calendar for specific location and time
    python prayer-times-ics-generator.py --city "Abu Dhabi" --emirate "Abu Dhabi" --year 2026 --month 10

    # Generate daily calendar for specific day
    python prayer-times-ics-generator.py --day 15
    
    # List all emirates
    python prayer-times-ics-generator.py --list-emirates
    
    # List all cities in Dubai emirate
    python prayer-times-ics-generator.py --emirate Dubai --list-cities

Output:
    Monthly calendar: {year}/{month}/{emirate}/{city}/{month}{year}.ics
    Daily calendar:   {year}/{month}/{emirate}/Daily/{day}{month}.ics

Events:
    1. Adhan till Iqamah (Green)
       - Duration varies by prayer:
         * Fajr: 25 minutes
         * Zuhr: 20 minutes (except Friday)
         * Asr: 20 minutes
         * Maghrib: 5 minutes
         * Isha: 20 minutes
       - Notification: At event start

    2. Prayer (Cerise)
       - Duration: 10 minutes
       - Notification: 5 minutes before

    3. Jummah Prayer (Friday only, Cerise)
       - Adhan: 12:45 PM
       - Duration: 45 minutes (until 1:30 PM)
       - Notification: 5 minutes before
    """
    print(help_text)

def guided_setup():
    """Interactive guided setup for first-time users."""
    print("\n" + "="*60)
    print("UAE Prayer Times Calendar Generator - Guided Setup")
    print("="*60 + "\n")
    
    # Check if running in non-interactive mode (Docker container)
    import sys
    is_interactive = sys.stdin.isatty()
    auto_mode = os.environ.get('AUTO_SETUP', '').lower() == 'true'
    
    # Check if config exists
    if os.path.exists(CONFIG_FILE):
        print(f"Configuration file '{CONFIG_FILE}' already exists.")
        if is_interactive:
            choice = input("Do you want to reconfigure? (y/n): ").strip().lower()
            if choice != 'y':
                print("Setup cancelled. Using existing configuration.")
                return
        else:
            print("Non-interactive mode detected. Using existing configuration.")
            return
    
    print("Step 1: API Credentials Setup")
    print("-" * 40)
    print("The generator needs credentials to access the AWQAF API.")
    print("We can automatically extract these from the AWQAF website.\n")
    
    # In non-interactive or auto mode, automatically extract without prompting
    if not is_interactive or auto_mode:
        print("Non-interactive mode detected. Automatically extracting credentials...")
        auto_extract = 'y'
    else:
        auto_extract = input("Would you like to automatically extract credentials? (y/n): ").strip().lower()
    
    if auto_extract == 'y':
        print("\nStarting automatic credential extraction...")
        try:
            creds = asyncio.run(extract_credentials())
            if creds:
                print("\nCredentials extracted successfully!")
            else:
                print("\nAutomatic extraction failed. Please set up manually.")
                print("Follow the manual instructions in the README.md file.")
                return
        except (OSError, ValueError, RuntimeError, APIError) as e:
            print(f"\nError during extraction: {e}")
            print("Please try manual setup instead.")
            return
    else:
        print("\nManual setup selected.")
        print("Please follow the manual instructions in README.md to set up credentials.")
        print("Then run this script again with the --setup flag to continue.")
        return
    
    # Skip location selection in non-interactive mode (use environment variables or defaults)
    if not is_interactive or auto_mode:
        print("\nNon-interactive mode detected. Using environment variables or defaults.")
        emirate_name = os.environ.get('DEFAULT_EMIRATE', 'Dubai')
        city_name = os.environ.get('DEFAULT_CITY', 'Dubai')
        print(f"Using emirate: {emirate_name}")
        print(f"Using city: {city_name}")
        
        # Save preferences
        preferences = {
            "default_emirate": emirate_name,
            "default_city": city_name
        }
        
        try:
            with open(CONFIG_FILE) as f:
                config = json.load(f)
            config.update(preferences)
        except (OSError, json.JSONDecodeError):
            config = preferences
        
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        
        print("\nSetup complete!")
        return
    
    else:
        # Interactive mode - fetch available emirates
        print("\nStep 2: Location Selection")
        print("-" * 40)
        
        # Fetch available emirates
        print("Fetching available emirates...")
        try:
            emirates = AWQAFApi.get_emirates()
            if not emirates:
                print("Error: Could not fetch emirates. Please check your credentials.")
                return
            
            print("\nAvailable emirates:")
            for i, emirate in enumerate(emirates, 1):
                print(f"  {i}. {emirate['emirateNameEn']}")
            
            emirate_choice = input(f"\nSelect an emirate (1-{len(emirates)}): ").strip()
            try:
                emirate_index = int(emirate_choice) - 1
                if 0 <= emirate_index < len(emirates):
                    selected_emirate = emirates[emirate_index]
                    emirate_name = selected_emirate['emirateNameEn']
                    print(f"Selected: {emirate_name}")
                else:
                    print("Invalid selection. Defaulting to Dubai.")
                    emirate_name = "Dubai"
            except ValueError:
                print("Invalid input. Defaulting to Dubai.")
                emirate_name = "Dubai"
            
            # Fetch cities for selected emirate
            print(f"\nFetching cities in {emirate_name}...")
            cities = AWQAFApi.get_cities_for_emirate(emirate_name)
            
            if not cities:
                print("Error: Could not fetch cities. Please check your credentials.")
                return
            
            print(f"\nCities in {emirate_name}:")
            for i, city in enumerate(cities, 1):
                print(f"  {i}. {city['cityNameEn']}")
            
            city_choice = input(f"\nSelect a city (1-{len(cities)}): ").strip()
            try:
                city_index = int(city_choice) - 1
                if 0 <= city_index < len(cities):
                    selected_city = cities[city_index]
                    city_name = selected_city['cityNameEn']
                    print(f"Selected: {city_name}")
                else:
                    print("Invalid selection. Defaulting to Dubai.")
                    city_name = "Dubai"
            except ValueError:
                print("Invalid input. Defaulting to Dubai.")
                city_name = "Dubai"
            
            # Save preferences
            preferences = {
                "default_emirate": emirate_name,
                "default_city": city_name
            }
            
            try:
                with open(CONFIG_FILE) as f:
                    config = json.load(f)
                config.update(preferences)
            except (OSError, json.JSONDecodeError):
                config = preferences
            
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=2)
            
            print("\nStep 3: Default Settings")
            print("-" * 40)
            print(f"Default emirate: {emirate_name}")
            print(f"Default city: {city_name}")
            print("Default time period: Current month and year")
            
            print("\n" + "="*60)
            print("Setup Complete!")
            print("="*60)
            print("\nYou can now generate prayer times calendars using:")
            print("  python prayer-times-ics-generator.py")
            print("\nOr specify different options:")
            print("  python prayer-times-ics-generator.py --city \"Abu Dhabi\" --emirate \"Abu Dhabi\"")
            print("  python prayer-times-ics-generator.py --year 2026 --month 10")
            
        except (OSError, ValueError, RuntimeError, APIError) as e:
            print(f"\nError during setup: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Main function to handle command line arguments and generate calendar"""
    # Get current date for defaults
    current_date = datetime.now(pytz.timezone(PrayerConfig.TIMEZONE))
    current_year = current_date.year
    current_month = current_date.month
    
    parser = argparse.ArgumentParser(
        description='Generate prayer times calendar',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--setup', action='store_true', help='Run guided setup for first-time users')
    parser.add_argument('--city', type=str, help='City name (overrides default from setup)')
    parser.add_argument('--emirate', type=str, help='Emirate name (overrides default from setup)')
    parser.add_argument('--year', type=int, default=current_year, help=f'Year (default: {current_year})')
    parser.add_argument('--month', type=int, default=current_month, help=f'Month (default: {current_month})')
    parser.add_argument('--day', type=int, help='Optional: Specific day to generate calendar for')
    parser.add_argument('--list-emirates', action='store_true', help='List all emirates')
    parser.add_argument('--list-cities', action='store_true', help='List all cities for the specified emirate')
    parser.add_argument('--show-help', action='store_true', help='Show detailed help message')
    
    args = parser.parse_args()
    
    if args.setup:
        guided_setup()
        return
    
    if args.show_help:
        print_help()
        return
        
    if args.list_emirates:
        emirates = AWQAFApi.get_emirates()
        if emirates:
            print("\nAvailable emirates:")
            for emirate in emirates:
                print(f"  - {emirate['emirateNameEn']}")
        else:
            print("\nNo emirates found or an error occurred.")
        return
        
    if args.list_cities:
        cities = AWQAFApi.get_cities_for_emirate(args.emirate)
        if cities:
            print(f"\nCities in {args.emirate} emirate:")
            for city in cities:
                print(f"  - {city['cityNameEn']}")
                if 'latitude' in city and 'longitude' in city:
                    print(f"    Location: {city['latitude']}, {city['longitude']}")
        else:
            print(f"\nNo cities found for {args.emirate} emirate or an error occurred.")
        return
    
    # Load default settings from config if available
    config_city = args.city
    config_emirate = args.emirate
    
    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f)
            if not args.city and 'default_city' in config:
                config_city = config['default_city']
            if not args.emirate and 'default_emirate' in config:
                config_emirate = config['default_emirate']
    except (OSError, json.JSONDecodeError):
        pass
    
    # Use command line args or defaults
    city = config_city or 'Dubai'
    emirate = config_emirate or 'Dubai'
    
    # Check if credentials are configured
    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f)
            has_creds = 'clientGuid' in config or 'clientAccessToken' in config
            has_defaults = 'default_city' in config and 'default_emirate' in config
    except (OSError, json.JSONDecodeError):
        has_creds = False
        has_defaults = False
    
    if not has_creds:
        print("No credentials found in config.json")
        print("Starting guided setup...")
        guided_setup()
        return
    
    if not has_defaults:
        print("Credentials found, but no default location set.")
        print("Run: python prayer-times-ics-generator.py --setup")
        print("to set your preferred location, or specify location with --city and --emirate flags.")
        # Continue with current values
    
    try:
        # Fetch prayer times from API
        prayer_data = AWQAFApi.fetch_prayer_times(args.year, args.month, args.day, city)
        
        # Generate calendar file
        generator = CalendarGenerator(prayer_data, city, emirate)
        filepath = generator.generate(args.day)
        
        print("\nSuccessfully generated prayer time calendar file!")
        print(f"File is located at: {filepath}")
        print(f"Location: {city}, {emirate}")
        print(f"Period: {calendar.month_name[args.month]} {args.year}")
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e!s}")
        print(f"File path: {e.doc}")
        print(f"Line number: {e.lineno}")
        print(f"Column: {e.colno}")
        print(f"Position: {e.pos}")
    except requests.exceptions.RequestException as e:
        print(f"API request error: {e!s}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status code: {e.response.status_code}")
            print(f"Response content: {e.response.text}")
    except (ConfigError, TokenError, APIError) as e:
        print(f"Error generating calendar: {e!s}")
        import traceback
        print(f"Full error: {traceback.format_exc()}")

if __name__ == "__main__":
    main()