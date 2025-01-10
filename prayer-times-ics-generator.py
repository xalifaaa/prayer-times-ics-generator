#!/usr/bin/env python3
"""
Prayer Times Calendar Generator
Generates ICS calendar files for prayer times using the AWQAF API.
"""

import argparse
import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
import calendar

import pytz
import requests
from icalendar import Calendar, Event, Alarm

class PrayerConfig:
    """Configuration class for prayer times and calendar settings"""
    TIMEZONE = "Asia/Dubai"
    
    # Prayer durations in minutes
    ADHAN_DURATIONS = {
        "fajr": 25,
        "zuhr": 20,
        "asr": 20,
        "maghrib": 5,
        "isha": 20
    }
    PRAYER_DURATION = 10
    
    # Calendar colors
    ADHAN_COLOR = "#008000"  # Green
    PRAYER_COLOR = "#ba1e55"  # Proton Calendar's Cerise

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
            dict: Configuration containing clientGuid and clientSecret
            
        Raises:
            Exception: If config file is missing or invalid
        """
        try:
            with open(cls.CONFIG_FILE, 'r') as f:
                config = json.load(f)
                
            required_fields = {'clientGuid', 'clientSecret'}
            if not all(field in config for field in required_fields):
                raise KeyError("Missing required fields in config file")
                
            return config
        except FileNotFoundError:
            raise Exception(
                f"Configuration file '{cls.CONFIG_FILE}' not found. "
                "Please create it with your client credentials."
            )
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON format in {cls.CONFIG_FILE}: {str(e)}")
        except KeyError as e:
            raise Exception(f"Invalid config file structure: {str(e)}")
    
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
                    print(f"Read token data: {token_data}")  # Debug log
                except json.JSONDecodeError as e:
                    print(f"JSON decode error: {str(e)}")  # Debug log
                    raise
                
                # Validate token data structure
                required_fields = {'clientAccessToken', 'clientRefreshToken', 'refreshTokenExpiryTime'}
                if not all(field in token_data for field in required_fields):
                    raise KeyError("Missing required fields in token data")
                
                # If we have no expiry time or empty tokens, refresh
                if (token_data['refreshTokenExpiryTime'] is None or 
                    not token_data['clientAccessToken'] or 
                    not token_data['clientRefreshToken']):
                    return cls.refresh_token()
                
                current_time = datetime.now(cls.TIMEZONE)
                # Convert Unix timestamp to timezone-aware datetime
                expiry_time = datetime.fromtimestamp(token_data['refreshTokenExpiryTime'], cls.TIMEZONE)
                
                # Add buffer time to ensure token doesn't expire during use
                if current_time < expiry_time - timedelta(minutes=5):
                    return token_data['clientAccessToken']
                else:
                    return cls.refresh_token()
                    
        except FileNotFoundError:
            raise Exception(f"Token file '{cls.TOKEN_FILE}' not found")
        except KeyError as e:
            raise Exception(f"Invalid token file structure: {str(e)}")

    @classmethod
    def refresh_token(cls, retry_count: int = 0) -> str:
        """
        Refresh the access token using client credentials.
        
        Args:
            retry_count (int): Current retry attempt number
            
        Returns:
            str: New access token
            
        Raises:
            Exception: If token refresh fails after all retries
        """
        try:
            config = cls._load_config()
        except Exception as e:
            raise Exception(f"Failed to load configuration: {str(e)}")
            
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        data = {
            "clientGuid": config['clientGuid'],
            "clientSecret": config['clientSecret']
        }
        
        try:
            response = requests.post(cls.REFRESH_URL, headers=headers, json=data, timeout=10)
            response.raise_for_status()
            
            response_data = response.json()
            print(f"Response from server: {response_data}")  # Debug log
            
            if not response_data.get('isSuccess', False):
                error_desc = response_data.get('errorDescription', 'Unknown error')
                raise ValueError(f"Authorization failed: {error_desc}")
            
            token_data = {
                'clientAccessToken': response_data['clientAccessToken'],
                'clientRefreshToken': response_data['clientRefreshToken'],
                'refreshTokenExpiryTime': response_data['refreshTokenExpiryTime']
            }
            print(f"Token data to save: {token_data}")  # Debug log
            
            # Save new token data
            with open(cls.TOKEN_FILE, 'w') as f:
                json.dump(token_data, f, indent=4)
            
            return token_data['clientAccessToken']
            
        except (requests.exceptions.RequestException, ValueError) as e:
            if retry_count < cls.MAX_RETRIES:
                import time
                time.sleep(cls.RETRY_DELAY * (retry_count + 1))
                return cls.refresh_token(retry_count + 1)
            raise Exception(f"Failed to refresh token after {cls.MAX_RETRIES} attempts: {str(e)}")

class AWQAFApi:
    """Handles interactions with the AWQAF Prayer Times API"""
    BASE_URL = "https://mobileappapi.awqaf.gov.ae/APIS/v2/prayer-time/prayertimes"
    
    @staticmethod
    def fetch_prayer_times(year: int, month: int, day: Optional[int], city: str) -> Dict[str, Any]:
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
        # Format dates for API request
        if day:
            # If day is specified, fetch only that day
            start_date = end_date = f"{year}-{month:02d}-{day:02d}"
        else:
            # Get first and last day of the month
            _, last_day = calendar.monthrange(year, month)
            start_date = f"{year}-{month:02d}-01"
            end_date = f"{year}-{month:02d}-{last_day:02d}"
        
        # Prepare API request
        url = f"{AWQAFApi.BASE_URL}/{start_date}/{end_date}"
        
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
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # Format the data
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
                    date = item.get('gDate', '').split('T')[0]  # Get just the date part
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
                                time_obj = datetime.strptime(time_part, '%H:%M:%S')
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
                except Exception as e:
                    print(f"Error processing prayer times for a day: {str(e)}")
                    continue
            
            if not formatted_data["prayertimes"]:
                raise ValueError(f"No prayer times data found for city: {city}")
            
            return formatted_data
            
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch prayer times: {str(e)}")

class CalendarGenerator:
    """Handles generation of ICS calendar files"""
    def __init__(self, prayer_data: Dict[str, Any], city: str, emirate: str):
        self.prayer_data = prayer_data
        self.city = city
        self.emirate = emirate
        self.first_date = datetime.strptime(prayer_data["prayertimes"][0]["date"], "%Y-%m-%d")
    
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
    
    def _parse_datetime(self, time_str: str) -> datetime:
        """Parse prayer time string into datetime object"""
        return datetime.fromisoformat(time_str).replace(tzinfo=pytz.timezone(PrayerConfig.TIMEZONE))
    
    def _get_output_path(self, day: Optional[int] = None) -> Tuple[str, str]:
        """Get output directory and filename for calendar file"""
        year = self.first_date.year
        month_name = self.first_date.strftime("%B")
        base_dir = os.path.join(str(year), month_name, self.emirate, self.city)
        
        if day:
            # Daily calendar
            output_dir = os.path.join(base_dir, f"{day:02d}")
            filename = f"Prayer-Times-On-{day:02d}{month_name}.ics"
        else:
            # Monthly calendar
            output_dir = base_dir
            last_day = self.prayer_data["prayertimes"][-1]["date"]
            first_day_num = self.first_date.day
            last_day_num = datetime.strptime(last_day, "%Y-%m-%d").day
            filename = f"Prayer-Times-From-{first_day_num:02d}-To-{last_day_num:02d}.ics"
        
        return output_dir, filename
    
    def generate(self, day: Optional[int] = None) -> str:
        """
        Generate ICS calendar file
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
                current_day = datetime.strptime(date, "%Y-%m-%d").day
                if current_day != day:
                    continue
            
            # Process each prayer
            for prayer in ["fajr", "zuhr", "asr", "maghrib", "isha"]:
                time = day_data["timings"][prayer]
                if not time:  # Skip if no time available
                    continue
                
                try:
                    # Create Adhan event
                    adhan_event = self._create_adhan_event(date, prayer, time)
                    cal.add_component(adhan_event)
                    
                    # Create Prayer event
                    prayer_event = self._create_prayer_event(date, prayer, time, PrayerConfig.ADHAN_DURATIONS[prayer])
                    cal.add_component(prayer_event)
                    
                except Exception as e:
                    print(f"Error creating events for {date} {prayer}: {str(e)}")
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
    --city CITY         City name (default: Dubai)
    --emirate EMIRATE   Emirate name (default: Dubai)
    --year YEAR         Year (default: 2025)
    --month MONTH       Month number (1-12)
    --day DAY           Optional: Generate calendar for specific day only
    --show-help         Show this help message

Examples:
    # Generate monthly calendar for Dubai, January 2025
    python prayer-times-ics-generator.py --city Dubai --emirate Dubai --year 2025 --month 1

    # Generate daily calendar for Dubai, January 15, 2025
    python prayer-times-ics-generator.py --city Dubai --emirate Dubai --year 2025 --month 1 --day 15

Output:
    Monthly calendar: {year}/{month}/{emirate}/{city}/Prayer-Times-From-{firstDay}-To-{lastDay}.ics
    Daily calendar:   {year}/{month}/{emirate}/{city}/{day}/Prayer-Times-On-{day}{month}.ics

Events:
    1. Adhan till Iqamah (Green)
       - Duration varies by prayer:
         * Fajr: 25 minutes
         * Dhuhr: 20 minutes
         * Asr: 20 minutes
         * Maghrib: 5 minutes
         * Isha: 20 minutes
       - Notification: At event start

    2. Prayer (Cerise)
       - Duration: 10 minutes
       - Notification: 5 minutes before
    """
    print(help_text)

def main():
    """Main function to handle command line arguments and generate calendar"""
    parser = argparse.ArgumentParser(
        description='Generate prayer times calendar',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--city', type=str, default='Dubai', help='City name')
    parser.add_argument('--emirate', type=str, default='Dubai', help='Emirate name')
    parser.add_argument('--year', type=int, default=2025, help='Year')
    parser.add_argument('--month', type=int, default=1, help='Month')
    parser.add_argument('--day', type=int, help='Optional: Specific day to generate calendar for')
    parser.add_argument('--show-help', action='store_true', help='Show detailed help message')
    
    args = parser.parse_args()
    
    if args.show_help:
        print_help()
        return
    
    try:
        # Fetch prayer times from API
        prayer_data = AWQAFApi.fetch_prayer_times(args.year, args.month, args.day, args.city)
        
        # Generate calendar file
        generator = CalendarGenerator(prayer_data, args.city, args.emirate)
        filepath = generator.generate(args.day)
        
        print(f"\nSuccessfully generated prayer time calendar file!")
        print(f"File is located at: {filepath}")
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {str(e)}")
        print(f"File path: {e.doc}")
        print(f"Line number: {e.lineno}")
        print(f"Column: {e.colno}")
        print(f"Position: {e.pos}")
    except requests.exceptions.RequestException as e:
        print(f"API request error: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status code: {e.response.status_code}")
            print(f"Response content: {e.response.text}")
    except Exception as e:
        print(f"Error generating calendar: {str(e)}")
        import traceback
        print(f"Full error: {traceback.format_exc()}")

if __name__ == "__main__":
    main()