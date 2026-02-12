#!/usr/bin/env python3
import urllib.request
import json
import os
import sys

# Colors and formatting
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[38;5;46m"
RED = "\033[38;5;196m"
BLUE = "\033[38;5;39m"
CYAN = "\033[38;5;51m"
GRAY = "\033[38;5;240m"
WHITE = "\033[38;5;255m"

def fetch_json(url):
    try:
        with urllib.request.urlopen(url) as response:
            if response.status == 200:
                return json.loads(response.read().decode())
    except Exception:
        return None

def main():
    api_base = os.environ.get("ASTA_BASE_URL", "http://localhost:8010").rstrip("/")
    
    # 1. Fetch Status (Integrations, Skills, APIs)
    status = fetch_json(f"{api_base}/api/status")
    
    # 2. Fetch Server Vitals
    server = fetch_json(f"{api_base}/api/settings/server-status")

    if not status or not status.get("apis"):
        print(f"{RED}Error: Could not reach API at {api_base}{RESET}")
        sys.exit(1)

    # --- Server Health ---
    if server and server.get("ok"):
        cpu = server.get("cpu_percent", 0)
        ram = server.get("ram", {})
        uptime = server.get("uptime_str", "?")
        
        ram_str = f"{ram.get('used_gb', 0)}/{ram.get('total_gb', 0)}GB"
        
        print(f"{WHITE}{BOLD}Server Health:{RESET}")
        print(f"  CPU: {CYAN}{cpu}%{RESET} | RAM: {CYAN}{ram_str}{RESET} | Uptime: {CYAN}{uptime}{RESET}")
        print("")

    # --- Channels (Integrations) ---
    integrations = status.get("integrations", {})
    t_status = f"{GREEN}Active{RESET}" if integrations.get("telegram") else f"{GRAY}Disconnected{RESET}"
    w_status = f"{GREEN}Active{RESET}" if integrations.get("whatsapp") else f"{GRAY}Disconnected{RESET}"

    print(f"{WHITE}{BOLD}Channels:{RESET}")
    print(f"  Telegram : {t_status}")
    print(f"  WhatsApp : {w_status}")
    print("")

    # --- Skills ---
    skills = status.get("skills", [])
    enabled_skills = [s for s in skills if s.get("enabled")]
    
    if enabled_skills:
        print(f"{WHITE}{BOLD}Active Skills:{RESET}")
        # Print in columns or simple list
        # Let's do a simple space-separated list with bullets
        skill_names = [f"● {s['name']}" for s in enabled_skills]
        # Join them with some spacing, maybe 3 per line or just wrap
        # Simple join for now
        print(f"  {BLUE}" + f"{RESET}   {BLUE}".join(skill_names) + f"{RESET}")
    else:
        print(f"{WHITE}{BOLD}Active Skills:{RESET}")
        print(f"  {GRAY}None{RESET}")
    print("")

if __name__ == "__main__":
    main()
