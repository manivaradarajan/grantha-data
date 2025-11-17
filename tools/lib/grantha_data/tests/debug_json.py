import json
from pathlib import Path

# Use a path within the workspace
file_path = Path("tools/lib/grantha_data/tests/test_data/isavasya.json")

try:
    with open(file_path, 'rb') as f:
        raw_content = f.read()

    # Try decoding with utf-8, which is common for JSON
    decoded_content = raw_content.decode('utf-8')

    # Attempt to load as JSON to catch the error
    json_data = json.loads(decoded_content)
    print("Successfully decoded and loaded JSON.")
    # If successful, print a portion or specific keys to verify
    print(json.dumps(json_data, indent=2)[:1000]) # Print first 1000 chars of pretty-printed JSON

except UnicodeDecodeError as e:
    print(f"UnicodeDecodeError: {e}")
    print(f"Problematic bytes: {raw_content[e.start:e.end]}")
    # Optionally, try other encodings or more robust error handling
except json.JSONDecodeError as e:
    print(f"JSONDecodeError: {e}")
    print(f"Error at character {e.pos}: {decoded_content[max(0, e.pos-50):e.pos+50]}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
