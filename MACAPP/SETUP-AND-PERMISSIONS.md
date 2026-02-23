# Setup & Permissions (reference; not yet implemented)

Answers to: *Does the app analyze the computer for Asta? Can it give Terminal commands? What about permissions (like OpenClaw)?*

---

## 1. Does the app analyze the computer for “Asta already installed”?

**Currently: no.** The first-run setup only:

- **Checks if the backend is running** (HTTP health to `http://localhost:8010`).
- It does **not** scan the disk for:
  - An Asta repo (e.g. `~/asta`, `~/Projects/asta`).
  - A Python/uvicorn or `asta.sh` install.
  - Whether the backend is installed but stopped.

**Possible improvements (not implemented):**

- **Discover install:** Check common paths (`~/asta`, `$HOME/Projects/asta`, current directory if launched from Terminal) for `asta.sh` or `backend/` and show “Asta found at …” with a **Start backend** or **Copy start command** button.
- **Backend not running:** If we knew an install path, we could show a **copyable command** (e.g. `cd ~/asta && ./asta.sh start`) and a **Copy** button instead of generic “Open Terminal” steps.

---

## 2. Can the app give us the commands we need (Terminal, etc.)?

**Partially.** The setup window already shows:

- “Run: `./asta.sh start`”
- “Or: `cd backend && uvicorn app.main:app --port 8010`”

**Not there yet:**

- **Copy button** – One tap to copy the exact command to the pasteboard so the user can paste in Terminal.
- **Tailored command** – If we ever detect an install path (see above), we could show a command with that path (e.g. `cd /Users/you/asta && ./asta.sh start`).
- **Open Terminal** – Optional “Open Terminal” button that opens `Terminal.app` (we can’t reliably `cd` into the user’s repo from there without knowing the path).

So: the app can and does show the commands; adding **Copy** and (later) **path-aware** commands would make it much more “installer-like”.

---

## 3. What OpenClaw (clawd) does for permissions

From **reference/openclaw/apps/macos**:

### PermissionManager

- **Check status** – Uses system APIs to see what’s granted:
  - **Accessibility:** `AXIsProcessTrusted()`
  - **Screen recording:** `CGPreflightScreenCaptureAccess()`
  - **Microphone / Camera:** `AVCaptureDevice.authorizationStatus(for:)`
  - **Speech recognition:** `SFSpeechRecognizer.authorizationStatus()`
  - **Location:** `CLLocationManager().authorizationStatus`
  - **Notifications:** `UNUserNotificationCenter.current().notificationSettings()`
  - **Automation (AppleScript):** Runs a benign `tell application "Terminal"` and checks for consent error.
- **Request (trigger system prompt):**
  - **Accessibility:** `AXIsProcessTrustedWithOptions(["AXTrustedCheckOptionPrompt": true])` – this triggers the system dialog to add the app to **Privacy & Security → Accessibility**.
  - **Screen recording:** `CGRequestScreenCaptureAccess()`.
  - **Microphone / Camera / Speech:** Standard `requestAccess` / `requestAuthorization` APIs.
- **When already denied:** They **open System Settings** to the right pane using URL schemes, e.g.:
  - Notifications: `x-apple.systempreferences:com.apple.Notifications-Settings.extension`
  - Microphone: `x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone`
  - Camera: `x-apple.systempreferences:com.apple.preference.security?Privacy_Camera`
  - Location: `…?Privacy_LocationServices`
  - Automation: `…?Privacy_Automation`
  - (For **Accessibility** the system prompt is the main flow; if the user dismissed it, opening `…?Privacy_Accessibility` can help.)

### PermissionsSettings UI

- A **Permissions** settings tab lists capabilities (Accessibility, Screen Recording, Notifications, Microphone, etc.) with:
  - Status: **Granted** or a **Grant** button.
  - Tapping **Grant** calls `PermissionManager.ensure([cap], interactive: true)`, which either triggers the system prompt or opens System Settings.

### Onboarding

- Onboarding includes a **permissions** step that uses the same `PermissionManager` and a **PermissionMonitor** (timer) to refresh status so the UI updates when the user grants permission in System Settings.

So: **yes**, the app can both **trigger the system permission dialogs** and **open System Settings** to the correct Privacy pane when the user needs to grant something.

---

## 4. Can we get permissions with the Asta app?

**Yes**, in the same way as OpenClaw:

1. **Accessibility (for Option+Space from any app)**  
   - Check: `AXIsProcessTrusted()`.  
   - Request: `AXIsProcessTrustedWithOptions(["AXTrustedCheckOptionPrompt": true])` – macOS shows the “Allow?” dialog and adds the app under **Privacy & Security → Accessibility**.  
   - If the user already denied: open `x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility` so they can add Asta manually.

2. **Other permissions** (if we add features that need them – e.g. microphone for voice, screen recording)  
   - Same pattern: check status → if not determined, request (system prompt) → if denied, open the right `x-apple.systempreferences:…?Privacy_…` URL.

**Currently in the Asta Mac app:** We only log that “Option+Space from anywhere requires Accessibility”; we do **not** call `AXIsProcessTrustedWithOptions` or open System Settings. So we *could* get the permissions from the app (trigger prompt + “Open System Settings” if needed), but we have not implemented that yet.

---

## Summary

| Question | Short answer |
|----------|--------------|
| Does it analyze the computer for Asta already installed? | No; it only checks if the backend is **running** (HTTP). No disk scan for repo/backend. |
| Can the app give us Terminal (and other) commands? | It shows commands in the setup window; adding a **Copy** button and (optionally) path-aware commands would make it better. |
| What does OpenClaw do for permissions? | Uses `PermissionManager`: check status with system APIs, request with `AXIsProcessTrustedWithOptions` / `CGRequestScreenCaptureAccess` / etc., and open `x-apple.systempreferences` URLs when denied. |
| Can we get permissions with the app? | Yes: trigger the system dialog (e.g. Accessibility) and/or open System Settings to the right Privacy pane; not implemented in Asta yet. |

Implementing these would mean:

- **Setup:** Optional “detect Asta install path” + copyable (and ideally path-aware) start commands.
- **Permissions:** A small “Permissions” section (e.g. in setup or Settings) that checks Accessibility, shows **Grant** / **Open System Settings** using the same patterns as OpenClaw.
