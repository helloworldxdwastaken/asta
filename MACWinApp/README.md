# Asta Cross-Platform App (Mac + Windows)

## Tech Stack Decision

**Tauri** — same tech as Claude Desktop and ChatGPT Desktop.
- Rust shell handles: tray icon, window management, auto-start, OS notifications
- Web UI (React/Svelte/Vue) handles: all visual screens — same code on Mac and Windows
- App connects to backend via HTTP (`localhost:8010` or Tailscale URL)
- ~10MB app size, no Electron bloat

## Backend
The Python/FastAPI backend (`localhost:8010`) stays **completely unchanged**.
The app is purely a frontend that calls the existing API.

## Tailscale / Remote Access
The app lets the user set a custom backend URL.
- Default: `http://localhost:8010`
- Tailscale: `http://100.x.x.x:8010` (remote machine)
- LAN: `http://192.168.x.x:8010`
Stored in local app storage (equivalent of UserDefaults).

## Screens Index
1. [Tray Icon](./screens/01-tray.md)
2. [Setup / Onboarding](./screens/02-setup.md)
3. [Main Window](./screens/03-main-window.md)
4. [Sidebar](./screens/04-sidebar.md)
5. [Chat View](./screens/05-chat.md)
6. [Settings Sheet](./screens/06-settings.md)
7. [Agents Sheet](./screens/07-agents.md)
