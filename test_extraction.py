import asyncio
import json
import os
from prayer_times_ics_generator import extract_credentials, CONFIG_FILE, CONTEXT_FILE

async def test_extraction():
    print("Testing credential extraction...")
    creds = await extract_credentials()
    if creds:
        print("SUCCESS: Credentials extracted")
        print(f"Config file exists: {os.path.exists(CONFIG_FILE)}")
        print(f"Context file exists: {os.path.exists(CONTEXT_FILE)}")
        # Verify config has tokens
        with open(CONFIG_FILE) as f:
            config = json.load(f)
            if 'clientAccessToken' in config:
                print("SUCCESS: Access token found in config")
            else:
                print("FAIL: No access token in config")
                return False
        return True
    else:
        print("FAIL: No credentials extracted")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_extraction())
    exit(0 if result else 1)
