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
YELLOW = "\033[38;5;226m"


def divider() -> str:
    return f"  {GRAY}─────────────────────────────────────────{RESET}"

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

    # --- Separated status blocks ---
    print(divider())
    print(f"  {WHITE}{BOLD}server{RESET}")
    if server and server.get("ok"):
        cpu = server.get("cpu_percent", 0)
        ram = server.get("ram", {})
        uptime = server.get("uptime_str", "?")
        ram_str = f"{ram.get('used_gb', 0)}/{ram.get('total_gb', 0)}GB"
        print(f"    {CYAN}cpu{RESET} {cpu}%")
        print(f"    {CYAN}ram{RESET} {ram_str}")
        print(f"    {CYAN}uptime{RESET} {uptime}")
    else:
        print(f"    {YELLOW}status unavailable{RESET}")

    print(divider())
    print(f"  {WHITE}{BOLD}channels{RESET}")
    integrations = status.get("integrations", {})
    channels = status.get("channels", {}) if isinstance(status, dict) else {}

    t = f"{GREEN}active{RESET}" if integrations.get("telegram") else f"{GRAY}off{RESET}"
    print(f"    telegram {t}")

    # Skills list only when running `asta status` (not on restart/update/start)
    show_skills = os.environ.get("ASTA_STATUS_FULL") == "1" or "--full" in sys.argv
    if show_skills:
        print(divider())
        print(f"  {WHITE}{BOLD}skills{RESET}")
        skills = status.get("skills", [])
        enabled_skills = [s for s in skills if s.get("enabled")]
        if enabled_skills:
            print(f"    enabled {len(enabled_skills)}")
            max_show = 12
            for s in enabled_skills[:max_show]:
                print(f"    {BLUE}● {s['name']}{RESET}")
            if len(enabled_skills) > max_show:
                print(f"    {GRAY}... +{len(enabled_skills) - max_show} more{RESET}")
        else:
            print(f"    {GRAY}none{RESET}")
    print(divider())

if __name__ == "__main__":
    main()
