# Asta Mac App

Desktop Mac app for Asta — same idea as [OpenClaw’s desktop Mac app](https://github.com/openclaw/openclaw/tree/main/apps/macos): a native menubar/standalone app that talks to the backend.

**Current scope:**
- **Tray → native menu:** Tap the menu bar icon to open a **dropdown menu** (OpenClaw-style: `.menuBarExtraStyle(.menu)` so Asta Panel, About, and Chat overlay open reliably). Menu shows status, RAM, then Asta Panel, Chat overlay, API docs, About, Quit.
- **Previous “mini dashboard”:** Replaced with native menu so item actions run after the menu closes (Open Chat, **Chat overlay (⌥ Space)**, Open API docs, **Asta Panel**), About, Quit.
- **Asta Panel:** Opens a **native Swift settings window** for app/backend configuration (General, Persona, Models, API Keys, Skills, Knowledge, Channels, Schedule, Google, Connection, Permissions, About). The **Settings** scene (Cmd+,) is a quick General tab; full control is in Asta Panel.
- **Agents hub:** In chat sidebar, directly under **New chat**, tap **Agents** to open the agent overlay (search, add/remove, create, edit, delete). Agent creation is no longer inside Settings tabs.
- **Chat message actions:** User and assistant bubbles include inline **Copy**. User bubbles also include **Edit**, which rewinds chat history from that turn and reruns in the same conversation.
- **Chat overlay:** Press **Option+Space** (or use “Chat overlay (⌥ Space)” from the tray) to open a dark-themed floating chat (Ask anything, toolbar: + / globe / screen / Thinking / mic / send), tall enough for two messages. Option+Space works when the app is active; for from-anywhere, grant **Accessibility** permission.

## Reference

- OpenClaw’s Mac app: `reference/openclaw/apps/macos/` (Swift/SwiftUI, gateway WebSocket, exec approvals, nodes, etc.).
- Asta backend: FastAPI on port **8010** by default; base URL `http://localhost:8010` (or `ASTA_BASE_URL`).

## Layout

- **README.md** (this file) — overview and setup.
- **Endpoints.md** — list of Asta API routes the app can call.
- **SETTINGS-ASTA-ONLY.md** — **Settings must use only Asta’s API** (default AI, thinking, providers, keys, skills, Telegram, Pingram, cron, etc.). Do not copy OpenClaw’s config schema or gateway-specific options; see that file for the exact mapping.
- **Sources/AstaAPIClient/** — Swift package that connects to those endpoints (health, chat, settings, etc.).

## First run (installer-like setup)

The **first time** you open the app (click the menu bar icon), a **Setup** window appears:

1. **Check backend** — The app checks if the Asta backend is running at `http://localhost:8010`.
2. **If connected** — You see “Backend connected” and can tap **Continue** to close setup.
3. **If not connected** — You see steps to start the backend (Terminal → `./asta.sh start` or `uvicorn app.main:app --port 8010`). Use **Retry** after starting the backend, or **Skip for now** to use the app without the backend (menu and panels will work; chat and API features need the backend).

Setup is shown only once; the choice is stored and the window does not open again unless you reset it (delete the app’s UserDefaults or reinstall).

## Build and run

From repo root:

```bash
cd MACAPP
swift build
swift run AstaMacApp
```

Or run the binary: `MACAPP/.build/debug/AstaMacApp`. The app appears in the **menu bar** (brain icon). Click it to open the menu. Use **Asta Panel** for native settings and use the chat sidebar **Agents** button for agent marketplace/creation. Press **Option+Space** (or the tray button) for the chat overlay; for Option+Space from any app, grant Accessibility permission.

## Build .app and DMG (installer)

To build a release **.app** bundle and a **DMG** for distribution:

```bash
cd MACAPP
./build-release.sh
```

- Uses `../VERSION` if present (e.g. `1.3.17`), or pass a version: `./build-release.sh 2.0.0`.
- Output:
  - **`build/AstaMacApp.app`** — Double-click to run or drag to Applications.
  - **`build/AstaMacApp-<version>.dmg`** — Disk image to share; open and drag Asta into Applications.

The script runs `swift build -c release`, builds the app bundle with an Info.plist, then creates the DMG with `hdiutil` (or `create-dmg` if installed).

## Debug (panel / menu)

If **Asta Panel**, **About**, or **Chat overlay** don’t open from the tray, run from Terminal so you can see logs:

```bash
cd MACAPP
swift run AstaMacApp
```

Then click the tray icon and choose **Asta Panel**, **About Asta**, or **Chat overlay**. In the same Terminal you’ll see logs like:

- `menu tapped: Asta Panel` — the menu action ran.
- `showAstaPanel() entered` / `creating new panel` / `done, isVisible=…` — PanelManager ran and whether the panel is visible.

If you see “menu tapped” but no PanelManager lines, the `Task { @MainActor in … }` may not be running. If you see “done, isVisible=true” but no window, the panel is created but something (activation policy, window level, or focus) is hiding it. You can also open **Console.app**, filter by `AstaMacApp` or subsystem `ai.asta.macapp`, and watch the same messages.

## Testing

Swift uses **XCTest** (like Python’s `unittest`). From `MACAPP`:

```bash
swift test
```

Runs all tests in `Tests/AstaMacAppTests/`:
- **PanelManagerTests** — singleton exists; `showAstaPanel()` / `showAbout()` don’t crash.
- **AppStateTests** — `statusLine` when disconnected, loading, or connected.
- **AstaAPIClientDecodeTests** — API DTOs decode from JSON (health, check-update, server-status).

In Xcode: open the package, then **Product → Test** (⌘U).

To use only the API client in another Xcode project, add this package as a dependency (local path or Git URL).

## Config

- **Base URL:** default `http://localhost:8010`. Override via `AstaAPIClient.baseURL` or environment (e.g. `ASTA_BASE_URL`).
- **CORS:** Backend allows `http://localhost:5173` and `127.0.0.1` by default; native app requests are not browser CORS-bound.
