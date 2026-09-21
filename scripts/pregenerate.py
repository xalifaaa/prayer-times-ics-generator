"""Batch-generate .ics calendars for all UAE cities from official AWQAF data.

Must run from a residential UAE connection (AWQAF blocks datacenter IPs).
Each month is fetched once - the response contains every city. Generated
files under calendars/ are committed and served statically by the hosted app.

Usage:
    python scripts/pregenerate.py
"""

import asyncio
import calendar
import os
import sys
from datetime import datetime
from pathlib import Path

import pytz

REPO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(REPO_ROOT)
sys.path.insert(0, str(REPO_ROOT))

from src.generator import AWQAFApi, CalendarGenerator, extract_credentials


def month_window() -> list[tuple[int, int]]:
    """Current month through December of next year."""
    now = datetime.now(tz=pytz.timezone('Asia/Dubai'))
    return [(y, m) for y in (now.year, now.year + 1) for m in range(1, 13)
            if (y, m) >= (now.year, now.month)]


def fetch_month(year: int, month: int) -> list[dict]:
    """One API call returns prayerData for all cities in the range."""
    _, last_day = calendar.monthrange(year, month)
    start = f"{year}-{month:02d}-01"
    end = f"{year}-{month:02d}-{last_day:02d}"
    return AWQAFApi._request_prayer_data(start, end).get("prayerData", [])


def main() -> None:
    locations = AWQAFApi.get_locations()
    emirates = locations.get("emirates", [])
    cities = locations.get("cities", [])
    if not emirates or not cities:
        sys.exit("No locations data - run setup first: python main.py --setup")

    city_pairs = [
        (e["emirateNameEn"], c["cityNameEn"])
        for e in emirates for c in cities
        if c.get("emirate") == e.get("emiratesId") and c.get("cityNameEn")
    ]
    print(f"{len(city_pairs)} cities, {len(month_window())} months")

    generated = skipped = 0
    refreshed = False
    for year, month in month_window():
        try:
            items = fetch_month(year, month)
        except Exception as e:  # noqa: BLE001
            if refreshed:
                sys.exit(f"Fetch failed for {year}-{month:02d} even after re-auth: {e}")
            print(f"Fetch failed for {year}-{month:02d}: {e} - re-running credential extraction")
            if not asyncio.run(extract_credentials()):
                sys.exit("Credential extraction failed - run python main.py --setup manually")
            refreshed = True
            items = fetch_month(year, month)

        for emirate_name, city_name in city_pairs:
            formatted = {"prayertimes": [
                fmt for it in items
                if it.get("areaNameEn", "").lower() == city_name.lower()
                for fmt in [AWQAFApi._format_prayer_item(it)] if fmt
            ]}
            if not formatted["prayertimes"]:
                print(f"  ! no data: {emirate_name}/{city_name} {year}-{month:02d}")
                skipped += 1
                continue
            try:
                CalendarGenerator(formatted, city_name, emirate_name, base_dir="calendars").generate()
                generated += 1
            except Exception as e:  # noqa: BLE001
                print(f"  ! generate failed {emirate_name}/{city_name} {year}-{month:02d}: {e}")
                skipped += 1
        print(f"{calendar.month_name[month]} {year}: done")

    print(f"Done: {generated} calendars generated, {skipped} skipped")


if __name__ == "__main__":
    main()
