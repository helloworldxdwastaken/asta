import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.abspath("backend"))

from app.db import get_db
from app.exec_tool import run_allowlisted_command

async def test_injection():
    print("--- Testing DB Key Injection ---")
    db = get_db()
    await db.connect()

    # 1. Set a test key
    test_key = "ntn_test_12345"
    print(f"Setting notion_api_key = {test_key} in DB...")
    await db.set_stored_api_key("notion_api_key", test_key)

    # 2. Run exec command to echo it
    # We use 'sh -c' to ensure shell variable expansion happens, 
    # but run_allowlisted_command expects a binary in the allowlist.
    # 'sh' might not be in the allowlist.
    # But 'curl' is. We can use curl to inspect env or just rely on the fact that if we can run *any* command
    # that uses the env var, we are good.
    # Actually, let's use python if available (it might not be allowlisted).
    # Safe bet: `bash -c "echo $NOTION_API_KEY"` if bash is allowed?
    # Or just `curl` with the key in a header and use -v to see it? No, that's hard to parse.
    
    # Wait, exec_tool checks allowlist. 'bash' is usually allowed if 'full' mode or if explicitly added.
    # Let's assume 'bash' or 'sh' is allowlisted for this test, OR temporarily allow it.
    # Actually, `run_allowlisted_command` checks `allowed_bins`. We can pass a custom allowlist to it!
    
    cmd = 'bash -c "echo KEY_IS:$NOTION_API_KEY"'
    print(f"Running command: {cmd}")
    stdout, stderr, ok = await run_allowlisted_command(
        cmd, 
        allowed_bins={"bash"} # Force allow bash for this test
    )

    print(f"Output: {stdout.strip()}")
    
    # 3. Verify
    if f"KEY_IS:{test_key}" in stdout:
        print("✅ SUCCESS: NOTION_API_KEY was injected from DB.")
    else:
        print("❌ FAILURE: Key not found in output.")

    # 4. Cleanup
    # Optional: remove the key? Maybe better to leave itempty or delete row?
    # db.set_stored_api_key updates or inserts. 
    # We should probably clear it to not confuse user.
    print("Cleaning up...")
    await db._conn.execute("DELETE FROM api_keys WHERE key_name = 'notion_api_key'")
    await db._conn.commit()

if __name__ == "__main__":
    try:
        asyncio.run(test_injection())
    except Exception as e:
        print(f"Error: {e}")
