import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path

# Load the main script as a module
script_path = Path(__file__).parent / "prayer-times-ics-generator.py"
spec = importlib.util.spec_from_file_location("prayer_times_ics_generator", script_path)
prayer_module = importlib.util.module_from_spec(spec)
sys.modules["prayer_times_ics_generator"] = prayer_module
spec.loader.exec_module(prayer_module)

# Get the needed items from the module
CONFIG_FILE = "config.json"
CONTEXT_FILE = "browser_context.json"
extract_credentials = prayer_module.extract_credentials


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
