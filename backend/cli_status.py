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

    # --- Server & Channels (compact) ---
    if server and server.get("ok"):
        cpu = server.get("cpu_percent", 0)
        ram = server.get("ram", {})
        uptime = server.get("uptime_str", "?")
        ram_str = f"{ram.get('used_gb', 0)}/{ram.get('total_gb', 0)}GB"
        print(f"  {WHITE}server{RESET}   {CYAN}cpu {cpu}%{RESET}  {CYAN}ram {ram_str}{RESET}  {CYAN}uptime {uptime}{RESET}")

    integrations = status.get("integrations", {})
    t = f"{GREEN}active{RESET}" if integrations.get("telegram") else f"{GRAY}off{RESET}"
    w = f"{GREEN}active{RESET}" if integrations.get("whatsapp") else f"{GRAY}off{RESET}"
    print(f"  {WHITE}channels{RESET} telegram {t}  whatsapp {w}")

    # Skills list only when running `asta status` (not on restart/update/start)
    show_skills = os.environ.get("ASTA_STATUS_FULL") == "1" or "--full" in sys.argv
    if show_skills:
        skills = status.get("skills", [])
        enabled_skills = [s for s in skills if s.get("enabled")]
        if enabled_skills:
            skill_names = [f"● {s['name']}" for s in enabled_skills]
            print(f"  {WHITE}skills{RESET}   {BLUE}" + f"{RESET}   {BLUE}".join(skill_names) + f"{RESET}")
        else:
            print(f"  {WHITE}skills{RESET}   {GRAY}none{RESET}")

if __name__ == "__main__":
    main()
