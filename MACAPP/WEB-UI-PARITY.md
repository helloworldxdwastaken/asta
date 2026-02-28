# Mac App vs Legacy browser client – Page & Feature Parity

This document compares every Legacy browser client page/section with the Mac app (Asta Panel + Chat overlay) and lists gaps.

---

## 1. Page / Tab Mapping

| Legacy browser client (route)        | Mac app equivalent                          | Notes |
|-----------------------|---------------------------------------------|-------|
| **/** Dashboard       | **Dashboard** tab                           | Bento-style overview; some cards differ. |
| **/chat** Chat        | **Chat overlay** (Option+Space)             | No dedicated Chat tab in Panel. |
| **/files** Files      | ❌ None                                     | No Files page in Mac app. |
| **/notes** Notes      | ❌ None                                     | No Notes page in Mac app. |
| **/drive** Drive      | ❌ None                                     | No Drive page in Mac app. |
| **/learning** RAG      | ❌ None                                     | No RAG/Learning page in Mac app. |
| **/audio-notes** Audio| ❌ None                                     | No Audio notes page in Mac app. |
| **/skills** Skills    | **Settings → Skills** sub-tab               | Toggle list; parity. |
| **/channels** Channels| **Channels** tab                            | Telegram, Pingram; parity. |
| **/cron** Cron        | **Cron** tab                                | List + Add; Cron has fewer fields. |
| **/settings** Settings | **Settings** tab (General, Vision, Models, Keys, Skills) | Sub-tabs; most parity, some missing. |
| (not a page) Notifications | **Notifications** tab                    | List + Delete; Web shows in Dashboard. |

---

## 2. Dashboard

| Feature | Legacy browser client | Mac app |
|--------|--------|---------|
| Title + subtitle | ✅ "Asta Dashboard" / "System Overview & Diagnostics" | ✅ Same |
| System status badge | ✅ Online/Offline + version | ✅ Same |
| **Update available** badge + **Update Asta** button | ✅ In header + Body card | ✅ Header + Body card (checkUpdate / triggerUpdate) |
| Error banner + retry | ✅ Connection lost + Retry | ✅ Error text + Retry button (calls load()) |
| **The Brain** (AI providers + models) | ✅ List with model names, Ollama list | ✅ Provider list + model; similar |
| **The Body** (CPU, RAM, Disk, Uptime) | ✅ Vitals + update prompt | ✅ Vitals + update prompt in card |
| **The Eyes** (Vision) | ✅ OpenRouter vision status + model name | ✅ Vision Ready / not configured |
| **Channels** (Telegram, Pingram) | ✅ Connector cards + "Configure Channels →" | ✅ Channel row + link to **Web** `/channels` (not in-app Channels tab) |
| **Notes** (workspace notes count + link to /notes) | ✅ Bento card | ✅ Notes card (count + Open Notes →) |
| **Schedule** (reminders + cron count + link to /cron) | ✅ Bento card | ✅ Same idea; link opens **Web** `/cron` |
| **Capabilities** (skills count + link to /skills) | ✅ Bento card | ✅ Same; link opens **Web** `/skills` |
| Memory health / Security | ✅ Can exist in Web Dashboard | ❌ Not in Mac Dashboard |

**Done:**  
- Mac Dashboard now has **Update available** badge + **Update Asta** button (header and in Body card); loads `checkUpdate` in `loadPanel` and calls `triggerUpdate()` on button tap.  
- **Notes** card added: workspace notes count from `GET /api/settings/notes` + "Open Notes →" link to Web `/notes`.

---

## 3. Chat

| Feature | Legacy browser client | Mac app (overlay) |
|--------|--------|--------------------|
| Thread (user + assistant messages) | ✅ | ✅ |
| Provider/channel selector | ✅ Web / Telegram | N/A (single context) |
| Model badge, "Working" pill, New chat | ✅ | ❌ No model badge; has "Thinking…"; no New chat |
| Input + Send | ✅ | ✅ |
| **Markdown rendering** in replies | Plain text in Web Chat | ✅ Markdown (AttributedString) in Mac |
| Web search toggle | N/A (or in UI) | ✅ Globe = web tool |
| Image attach | N/A in snippet | ✅ Plus = image picker |
| Streaming / live reasoning | ✅ | ❌ Single request/response |
| Conversation history (load from API) | ✅ | ❌ No history load (session-only) |

**Done:**  
- **New chat** button in overlay header (when there are messages) clears messages and attached image.  
- Optional later: Load conversation history.

---

## 4. Files, Notes, Drive, Learning (RAG), Audio Notes

| Page | Legacy browser client | Mac app |
|------|--------|---------|
| **Files** | Browse roots, read/write files, User.md edit | ❌ No equivalent |
| **Notes** | Workspace notes list + edit + markdown preview | ❌ No equivalent |
| **Drive** | Drive OAuth / file list (stub) | ❌ No equivalent |
| **Learning (RAG)** | RAG status, sources, learn | ❌ No equivalent |
| **Audio notes** | Upload audio, transcribe, format | ❌ No equivalent |

**Recommendation:**  
- These are content/workspace-focused. Mac app could add them later (e.g. Notes as native, or open Web in browser for Files/Drive/RAG/Audio).

---

## 5. Skills

| Feature | Legacy browser client | Mac app (Settings → Skills) |
|--------|--------|------------------------------|
| List skills with enabled/available | ✅ | ✅ |
| Toggle enabled | ✅ | ✅ |
| Install/setup hints (install_cmd, required_bins) | ✅ Shown per card | ✅ Shown as caption (e.g. action_hint) |
| Link to Settings for "Set API key" etc. | ✅ | N/A (same panel) |
| **Upload skill ZIP** | ✅ | ❌ Not in Mac app |

**Done:**  
- **Upload skill (ZIP)** in Settings → Skills: button opens file picker (.zip), uploads via POST `/api/skills/upload`, refreshes skills list on success.

---

## 6. Channels

| Feature | Legacy browser client | Mac app |
|--------|--------|---------|
| Telegram token (save/remove) | ✅ | ✅ |
| Telegram username (voice) | N/A on Channels (token only) | ✅ |
| BotFather + commands hint | ✅ | ✅ (text) |
| Pingram: Client ID, Secret, API Key, Notification ID, Template ID, Phone | ✅ | ✅ |
| Pingram Save + Test call | ✅ | ✅ |
| Quick start / subtitle | ✅ | ✅ | 
| Status badges (Connected / Not configured etc.) | ✅ | ✅ (Mac: in section text) |

**Status:** **Parity** (already aligned).

---

## 7. Cron

| Feature | Legacy browser client | Mac app |
|--------|--------|---------|
| List jobs (name, expr, tz, message, …) | ✅ Table with full columns | ✅ List with name + expr + message |
| **Channel** (Web / Telegram) per job | ✅ Toggle + channel_target | ❌ Not shown; not in add form |
| **Payload kind** (Call AI vs Notify) | ✅ Toggle | ❌ Not in list or add |
| **Voice call** (tlg_call) | ✅ Toggle | ❌ Not in list or add |
| **Enabled** toggle per job | ✅ | ❌ Not in Mac list (backend has it) |
| **Edit** job (expr, tz, message, channel, etc.) | ✅ Via update API | ❌ Mac only has Delete; no edit |
| **Add job** | ✅ Full form: name, cron, tz, message, **channel**, **channel_target**, **payload_kind**, **tlg_call** | ✅ Name, cron, message, tz only |
| One-shot (@at) display | ✅ Badge | ❌ Not shown |

**Backend:**  
- `POST /api/cron` accepts `channel`, `channel_target`, `payload_kind`, `tlg_call`.  
- `PUT /api/cron/{id}` accepts `enabled`, `channel`, `payload_kind`, `tlg_call`, etc.

**Done:**  
- **AstaCronJob** and API client extended with `channel`, `channel_target`, `payload_kind`, `tlg_call`.  
- Cron tab shows per-job **channel**, **enabled**, **payload_kind** (Call AI / Notify), **tlg_call** (Call).  
- **CronAddForm** has channel (Web/Telegram), channel target, mode (Call AI / Notify), voice call toggle; **cronAdd** sends full body.  
- **Edit** opens a sheet (**CronEditSheet**) with all fields; Save calls `cronUpdate`.

---

## 8. Settings

### 8.1 General (Default AI, Thinking, Reasoning, Final mode, Providers)

| Feature | Legacy browser client | Mac app (Settings → General) |
|--------|--------|-------------------------------|
| Default AI provider | ✅ | ✅ |
| Thinking level | ✅ | ✅ |
| Reasoning mode | ✅ | ✅ |
| Final mode | ✅ | ✅ |
| Provider toggles (enable/disable per provider) | ✅ | ✅ |

**Status:** **Parity.**

### 8.2 Vision

| Feature | Legacy browser client | Mac app (Settings → Vision) |
|--------|--------|-----------------------------|
| Preprocess toggle, Provider order, OpenRouter model | ✅ | ✅ |

**Status:** **Parity.**

### 8.3 Models

| Feature | Legacy browser client | Mac app (Settings → Models) |
|--------|--------|-----------------------------|
| Model per provider (Claude presets, Ollama list, OpenRouter list) | ✅ Rich presets + custom | ✅ Picker or text; Ollama/OpenRouter options from API |
| Default vs custom model | ✅ | ✅ "(default)" option |

**Status:** **Parity** (Mac may have fewer presets in UI; same API).

### 8.4 API Keys

| Feature | Legacy browser client | Mac app (Settings → Keys) |
|--------|--------|----------------------------|
| Status list (which keys are set) | ✅ | ✅ |
| Edit fields (masked when set) + Save | ✅ | ✅ KeysEditView |
| Keys: Groq, Google/Gemini, Claude, OpenAI, OpenRouter, Telegram, Giphy, Spotify, Notion | ✅ | ✅ |

**Status:** **Parity.**

### 8.5 Settings only in Web (not in Mac)

| Feature | Legacy browser client | Mac app |
|--------|--------|---------|
| **Restart / Stop backend** button | ✅ | ✅ Settings → General → Backend |
| **Auto-updater** (Daily Auto-Update cron edit) | ✅ Details + save cron expr/tz | ❌ |
| **Allowed paths** (workspace / file access) | ✅ | ❌ |
| **Memory health** | ✅ | ❌ |
| **Security audit** | ✅ | ❌ |
| **Provider order** (reorder providers) | ✅ | ❌ (only enable/disable) |

**Done:**  
- **Restart backend**: Settings → General → Backend section with "Stop backend" button (POST /api/restart); help text to start again in terminal.  
- Optional later: Auto-updater cron edit, Allowed paths, Memory health, Security audit. Provider **order** (reorder) if API supports it.

---

## 9. Notifications

| Feature | Legacy browser client | Mac app |
|--------|--------|---------|
| List recent notifications | Shown in Dashboard; no dedicated page | ✅ Notifications tab |
| Delete notification | ✅ (API) | ✅ |

**Status:** Mac has dedicated Notifications tab; Web uses Dashboard. **Parity** for list + delete.

---

## 10. Summary Table

| Area | Parity | Gaps |
|------|--------|------|
| Dashboard | ~90% | Update badge + Update button; Notes card; optional Memory/Security |
| Chat | Good | New chat; optional history; Web has streaming |
| Files / Notes / Drive / RAG / Audio | N/A | No Mac pages (by design or future) |
| Skills | Good | No skill ZIP upload in Mac |
| Channels | ✅ | — |
| Cron | Partial | No channel/payload_kind/tlg_call/enabled in list or add; no edit |
| Settings (General, Vision, Models, Keys) | ✅ | Restart, Auto-updater, Allowed paths, Memory, Security, Provider order |
| Notifications | ✅ | — |

---

## 11. Suggested Implementation Order

1. ✅ **Cron parity** – Done.
2. ✅ **Dashboard** – Update badge + Update Asta; Notes card; Retry on error.
3. ✅ **Settings** – Restart backend (Stop backend in General). Optional later: Auto-updater, Allowed paths, Memory, Security.
4. ✅ **Chat overlay** – New chat button. Optional later: load history.
5. ✅ **Skills** – Upload skill ZIP in Mac app.

Remaining optional: Auto-updater cron edit in Settings, Allowed paths UI, Memory health / Security audit cards, Chat conversation history load, Provider order reorder.

This file can be updated as features are added or when the Legacy browser client changes.
