---
name: youtube-upload
description: Upload videos to YouTube via Data API v3 with metadata (title, description, tags, thumbnail). Use when the user wants to upload a finished video to their YouTube channel. NEVER upload without explicit user approval.
metadata: {"clawdbot":{"emoji":"📤","requires":{"bins":["curl","python3"]}}}
---

# YouTube Upload

Upload videos to YouTube using the YouTube Data API v3. **NEVER upload without explicit user approval.**

## Prerequisites

- `$YOUTUBE_API_KEY` — for read operations (trends, search)
- **OAuth2 access token** — required for uploads (API key alone cannot upload)
- The user must complete OAuth2 setup once (see Setup section below)

## OAuth2 Setup (one-time)

YouTube uploads require OAuth2 (not just an API key). The user needs to:

1. Create OAuth2 credentials in Google Cloud Console:
   - Go to APIs & Services > Credentials
   - Create OAuth 2.0 Client ID (Desktop app)
   - Download the `client_secret.json`

2. Save credentials:
```bash
# Save client_secret.json to agent knowledge
cp client_secret.json workspace/agent-knowledge/youtube-creator/references/client_secret.json
```

3. First-time authorization (generates refresh token):
```bash
python3 << 'PYEOF'
import json, http.server, urllib.parse, webbrowser

# Load client credentials
with open("workspace/agent-knowledge/youtube-creator/references/client_secret.json") as f:
    creds = json.load(f)["installed"]

client_id = creds["client_id"]
client_secret = creds["client_secret"]
redirect_uri = "http://localhost:8085"
scope = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube"

# Open browser for auth
auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope={scope}&access_type=offline&prompt=consent"
print(f"Opening browser for YouTube authorization...")
webbrowser.open(auth_url)

# Wait for callback
class Handler(http.server.BaseHTTPRequestHandler):
    code = None
    def do_GET(self):
        Handler.code = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("code", [None])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Authorization complete! You can close this tab.")
    def log_message(self, *args): pass

server = http.server.HTTPServer(("localhost", 8085), Handler)
server.handle_request()

if Handler.code:
    # Exchange code for tokens
    import urllib.request
    data = urllib.parse.urlencode({
        "code": Handler.code, "client_id": client_id,
        "client_secret": client_secret, "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
    resp = json.loads(urllib.request.urlopen(req).read())
    # Save tokens
    with open("workspace/agent-knowledge/youtube-creator/references/youtube_tokens.json", "w") as f:
        json.dump({"refresh_token": resp["refresh_token"], "client_id": client_id, "client_secret": client_secret}, f, indent=2)
    print("Tokens saved! YouTube upload is ready.")
else:
    print("Authorization failed — no code received.")
PYEOF
```

## Refresh Access Token

Before every upload, refresh the access token:

```bash
python3 -c "
import json, urllib.request, urllib.parse

with open('workspace/agent-knowledge/youtube-creator/references/youtube_tokens.json') as f:
    t = json.load(f)

data = urllib.parse.urlencode({
    'client_id': t['client_id'],
    'client_secret': t['client_secret'],
    'refresh_token': t['refresh_token'],
    'grant_type': 'refresh_token'
}).encode()

req = urllib.request.Request('https://oauth2.googleapis.com/token', data=data)
resp = json.loads(urllib.request.urlopen(req).read())
print(resp['access_token'])
" > /tmp/yt_access_token.txt
```

## Upload Video

```bash
# Upload video with metadata
ACCESS_TOKEN=$(cat /tmp/yt_access_token.txt)
VIDEO_FILE="workspace/youtube/2026-03-15/output.mp4"
TITLE="Your Video Title"
DESCRIPTION="Your video description..."
TAGS='["tag1","tag2","tag3"]'
CATEGORY_ID=28
PRIVACY="private"

# Step 1: Initialize resumable upload
UPLOAD_URL=$(curl -s -X POST \
  "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status,contentDetails" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"snippet\": {
      \"title\": \"${TITLE}\",
      \"description\": $(python3 -c "import json; print(json.dumps('''${DESCRIPTION}'''))"),
      \"tags\": ${TAGS},
      \"categoryId\": \"${CATEGORY_ID}\",
      \"defaultLanguage\": \"en\"
    },
    \"status\": {
      \"privacyStatus\": \"${PRIVACY}\",
      \"selfDeclaredMadeForKids\": false
    }
  }" \
  -D - -o /dev/null | grep -i "location:" | tr -d '\r' | awk '{print $2}')

# Step 2: Upload the video file
FILESIZE=$(stat -f%z "${VIDEO_FILE}" 2>/dev/null || stat --printf="%s" "${VIDEO_FILE}")
RESPONSE=$(curl -s -X PUT "${UPLOAD_URL}" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: video/mp4" \
  -H "Content-Length: ${FILESIZE}" \
  --data-binary "@${VIDEO_FILE}")

echo "$RESPONSE" | python3 -c "
import sys, json
r = json.load(sys.stdin)
print(f\"Upload complete!\")
print(f\"Video ID: {r['id']}\")
print(f\"URL: https://youtube.com/watch?v={r['id']}\")
print(f\"Status: {r['status']['uploadStatus']}\")
print(f\"Privacy: {r['status']['privacyStatus']}\")
"

# Save upload result
echo "$RESPONSE" > "workspace/youtube/$(date +%Y-%m-%d)/upload_result.json"
```

## Set Thumbnail

```bash
# Upload custom thumbnail (after video is uploaded)
ACCESS_TOKEN=$(cat /tmp/yt_access_token.txt)
VIDEO_ID="your_video_id"
THUMBNAIL="workspace/youtube/2026-03-15/thumbnail.jpg"

curl -s -X POST \
  "https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId=${VIDEO_ID}" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: image/jpeg" \
  --data-binary "@${THUMBNAIL}"
```

## Check Upload Status

```bash
ACCESS_TOKEN=$(cat /tmp/yt_access_token.txt)
VIDEO_ID="your_video_id"

curl -s "https://www.googleapis.com/youtube/v3/videos?part=status,processingDetails&id=${VIDEO_ID}" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  | python3 -c "
import sys, json
r = json.load(sys.stdin)
v = r['items'][0]
s = v['status']
print(f\"Upload status: {s['uploadStatus']}\")
print(f\"Privacy: {s['privacyStatus']}\")
if 'processingDetails' in v:
    p = v['processingDetails']
    print(f\"Processing: {p.get('processingStatus', '?')}\")
"
```

## Publish (change from private to public)

```bash
ACCESS_TOKEN=$(cat /tmp/yt_access_token.txt)
VIDEO_ID="your_video_id"

curl -s -X PUT \
  "https://www.googleapis.com/youtube/v3/videos?part=status" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"id\": \"${VIDEO_ID}\",
    \"status\": {
      \"privacyStatus\": \"public\",
      \"selfDeclaredMadeForKids\": false
    }
  }"
```

## Workflow

1. **Pre-check**: Verify `youtube_tokens.json` exists, refresh access token.
2. **Load metadata**: Read `workspace/youtube/YYYY-MM-DD/metadata.json` for title, description, tags.
3. **Confirm with user**: Present the video file path, title, description, tags, and privacy status. **Wait for explicit "yes" / "approve" / "upload it".**
4. **Upload**: Use resumable upload (handles large files, supports resume on failure).
5. **Set thumbnail**: If a thumbnail image exists, upload it.
6. **Report**: Show the YouTube URL, processing status.
7. **Save**: Write upload result to `upload_result.json`.

## Rules

- **CRITICAL: NEVER upload without explicit user approval.** Always show metadata and ask first.
- Always upload as **private** first. User can publish later.
- Use resumable uploads for reliability.
- If OAuth tokens are missing, guide the user through setup.
- If upload fails, save the error and suggest retry.
- Never expose access tokens or refresh tokens in output.
- Keep `client_secret.json` and `youtube_tokens.json` in agent-knowledge (not in workspace root).
