import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.abspath("backend"))

from app.exec_tool import run_allowlisted_command

async def test_notion_access():
    print("--- Testing Notion Access ---")
    # This relies on run_allowlisted_command injecting NOTION_API_KEY from DB
    cmd = 'curl -s -o /dev/null -w "%{http_code}" https://api.notion.com/v1/users/me -H "Authorization: Bearer $NOTION_API_KEY" -H "Notion-Version: 2022-06-28"'
    print(f"Running command: {cmd}")
    
    # Force allow 'curl' for this test (it's usually allowed anyway)
    stdout, stderr, ok = await run_allowlisted_command(
        cmd, 
        allowed_bins={"curl"}
    )
    
    print(f"Status Code: {stdout.strip()}")
    
    if stdout.strip() == "200":
        print("✅ SUCCESS: Notion API accessible with stored key.")
    else:
        print(f"❌ FAILURE: API returned {stdout.strip()}. Check key or permissions.")
        if stderr:
            print(f"Stderr: {stderr}")

if __name__ == "__main__":
    try:
        asyncio.run(test_notion_access())
    except Exception as e:
        print(f"Error: {e}")
