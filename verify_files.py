import requests
import time
import sys

API_URL = "http://localhost:8010/api/files/read"
TEST_FILE = "/home/tokyo/api_test_files/secret.txt"

print(f"Testing file read from {TEST_FILE}...")
try:
    r = requests.get(API_URL, params={"path": TEST_FILE})
    if r.status_code == 200:
        print("Success! File content:")
        print(r.text)
        if r.text.strip() == "Secret Data":
            print("Verification PASSED.")
        else:
            print("Verification FAILED: Content mismatch.")
            sys.exit(1)
    else:
        print(f"Verification FAILED: Status {r.status_code}")
        print(r.text)
        sys.exit(1)
except Exception as e:
    print(f"Verification FAILED: {e}")
    sys.exit(1)
