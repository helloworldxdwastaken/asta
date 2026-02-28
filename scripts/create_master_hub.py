import asyncio
import sys
import os
import json

# Add backend to path
sys.path.insert(0, os.path.abspath("backend"))

from app.exec_tool import run_allowlisted_command

async def run_curl(cmd_args):
    """Run curl command via exec_tool (gets auth automatically)."""
    # cmd_args is list of args for curl
    # We reconstruct the full command string for run_allowlisted_command
    # But wait, run_allowlisted_command takes a string cmd.
    # We need to be careful with quoting.
    # Let's just pass the full string.
    pass

async def create_master_hub():
    print("--- Creating Master Hub ---")
    
    # 1. Search for a parent page
    print("Searching for shared pages...")
    search_cmd = 'curl -s -X POST "https://api.notion.com/v1/search" -H "Authorization: Bearer $NOTION_API_KEY" -H "Content-Type: application/json" -H "Notion-Version: 2022-06-28" --data \'{"page_size": 1, "filter": {"value": "page", "property": "object"}}\''
    
    stdout, stderr, ok = await run_allowlisted_command(search_cmd, allowed_bins={"curl"})
    
    if not ok:
        print(f"❌ Search failed: {stdout} {stderr}")
        return

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        print(f"❌ Failed to parse search response: {stdout}")
        return

    results = data.get("results", [])
    if not results:
        print("❌ No shared pages found. Please share a page with the Asta integration first.")
        return

    parent_id = results[0]["id"]
    parent_title = "Unknown"
    # Try to find title
    props = results[0].get("properties", {})
    for key, val in props.items():
        if val.get("type") == "title":
            title_obj = val.get("title", [])
            if title_obj:
                parent_title = title_obj[0].get("plain_text", "Untitled")
            break

    print(f"✅ Found parent page: {parent_title} ({parent_id})")
    
    # 2. Create Master Hub Page
    print("Creating 'Master Hub' page...")
    create_page_payload = {
        "parent": {"page_id": parent_id},
        "properties": {
            "title": [
                {
                    "text": {
                        "content": "Master Hub"
                    }
                }
            ]
        },
        "children": [
            {
                "object": "block",
                "type": "heading_1",
                "heading_1": {
                    "rich_text": [{"text": {"content": "Welcome to Your Master Hub"}}]
                }
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"text": {"content": "This is your central command center created by Asta."}}]
                }
            }
        ]
    }
    
    # We need to escape the JSON for the shell command
    payload_json = json.dumps(create_page_payload).replace("'", "'\\''")
    create_cmd = f'curl -s -X POST "https://api.notion.com/v1/pages" -H "Authorization: Bearer $NOTION_API_KEY" -H "Content-Type: application/json" -H "Notion-Version: 2022-06-28" --data \'{payload_json}\''
    
    stdout, stderr, ok = await run_allowlisted_command(create_cmd, allowed_bins={"curl"})
    
    if not ok:
        print(f"❌ Failed to create Hub page: {stdout} {stderr}")
        return

    try:
        hub_data = json.loads(stdout)
    except:
        print(f"❌ Failed to parse create response: {stdout}")
        return
        
    hub_id = hub_data.get("id")
    hub_url = hub_data.get("url")
    print(f"✅ Created Master Hub: {hub_url} ({hub_id})")

    # 3. Create sub-databases (Tasks, Links, Programs)
    # Creating inline databases requires creating child blocks? 
    # Actually, simpler is to create child PAGES that contain databases, or just create databases with parent=hub_id.
    # Creating a database with parent=page_id creates it as a child database (full page or inline? API defaults to full page usually, but let's see).
    
    print("Creating 'Tasks' database...")
    tasks_payload = {
        "parent": {"page_id": hub_id},
        "title": [{"type": "text", "text": {"content": "Tasks"}}],
        "properties": {
            "Name": {"title": {}},
            "Status": {
                "select": {
                    "options": [
                        {"name": "To Do", "color": "red"},
                        {"name": "In Progress", "color": "blue"},
                        {"name": "Done", "color": "green"}
                    ]
                }
            },
            "Due Date": {"date": {}}
        }
    }
    
    tasks_json = json.dumps(tasks_payload).replace("'", "'\\''")
    tasks_cmd = f'curl -s -X POST "https://api.notion.com/v1/databases" -H "Authorization: Bearer $NOTION_API_KEY" -H "Content-Type: application/json" -H "Notion-Version: 2022-06-28" --data \'{tasks_json}\''
    
    stdout, _, ok = await run_allowlisted_command(tasks_cmd, allowed_bins={"curl"})
    if ok:
        print("✅ Created 'Tasks' database.")
    else:
        print(f"❌ Failed to create Tasks DB: {stdout}")

    print("Creating 'Links & Resources' database...")
    links_payload = {
        "parent": {"page_id": hub_id},
        "title": [{"type": "text", "text": {"content": "Links & Resources"}}],
        "properties": {
            "Name": {"title": {}},
            "URL": {"url": {}},
            "Tags": {"multi_select": {}}
        }
    }
    links_json = json.dumps(links_payload).replace("'", "'\\''")
    links_cmd = f'curl -s -X POST "https://api.notion.com/v1/databases" -H "Authorization: Bearer $NOTION_API_KEY" -H "Content-Type: application/json" -H "Notion-Version: 2022-06-28" --data \'{links_json}\''
    
    stdout, _, ok = await run_allowlisted_command(links_cmd, allowed_bins={"curl"})
    if ok:
        print("✅ Created 'Links & Resources' database.")
    else:
        print(f"❌ Failed to create Links DB: {stdout}")

    print("--- Done! ---")
    print(f"Open your Master Hub here: {hub_url}")

if __name__ == "__main__":
    try:
        asyncio.run(create_master_hub())
    except Exception as e:
        print(f"Error: {e}")
