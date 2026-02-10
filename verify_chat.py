import requests
import sys

API_URL = "http://localhost:8010/api/chat"

def test_chat():
    print("Testing Chat API...")
    payload = {
        "text": "Hello, are you working?",
        "provider": "groq", 
        "user_id": "test_user",
        "conversation_id": "test_conv"
    }
    try:
        # We might get an error if GROQ_API_KEY is not set, but we want to ensure the CODE path works.
        # The handler catches exceptions and returns "Error: ..." or "No AI provider..."
        # We consider it a pass if we get a 200 OK and a JSON response with "reply".
        r = requests.post(API_URL, json=payload)
        if r.status_code == 200:
            data = r.json()
            if "reply" in data:
                print(f"Success! Reply: {data['reply'][:100]}...")
                return True
            else:
                print("Failed: No 'reply' field in response.")
                print(data)
                return False
        else:
            print(f"Failed: Status {r.status_code}")
            print(r.text)
            return False
            
    except Exception as e:
        print(f"Failed to connect: {e}")
        return False

if __name__ == "__main__":
    if test_chat():
        sys.exit(0)
    else:
        sys.exit(1)
