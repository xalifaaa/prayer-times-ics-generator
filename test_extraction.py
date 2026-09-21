import asyncio
import json
import os
import sys

from prayer_times_ics_generator import CONFIG_FILE, CONTEXT_FILE, extract_credentials


async def test_extraction():
    print("Testing credential extraction...")
    creds = await extract_credentials()
    if creds:
        print("SUCCESS: Credentials extracted")
        print(f"Config file exists: {os.path.exists(CONFIG_FILE)}")
        print(f"Context file exists: {os.path.exists(CONTEXT_FILE)}")
        return True
    else:
        print("FAIL: No credentials extracted")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_extraction())
    
    # Verify config has tokens (after async function completes)
    if result and os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            config = json.load(f)
            if 'clientAccessToken' in config:
                print("SUCCESS: Access token found in config")
            else:
                print("FAIL: No access token in config")
                result = False
    
    sys.exit(0 if result else 1)
