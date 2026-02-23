#!/usr/bin/env bash
# Build Asta Mac App: release binary → .app bundle → DMG.
# Usage: ./build-release.sh [VERSION]
# Run from MACAPP/ directory. Output: MACAPP/build/Asta.app and MACAPP/build/Asta-VERSION.dmg

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Version ──────────────────────────────────────────────────────────────
if [ -n "${1:-}" ]; then
  VERSION="$1"
elif [ -f "${SCRIPT_DIR}/../VERSION" ]; then
  VERSION=$(tr -d '\n' < "${SCRIPT_DIR}/../VERSION")
else
  VERSION="1.0.0"
fi

BUILD_DIR="${SCRIPT_DIR}/build"
BINARY_NAME="AstaMacApp"
APP_DISPLAY="Asta"
APP_BUNDLE="${BUILD_DIR}/${APP_DISPLAY}.app"

echo "══════════════════════════════════════════════════"
echo "  Building ${APP_DISPLAY} v${VERSION}"
echo "══════════════════════════════════════════════════"

# ── 1. Swift release build ───────────────────────────────────────────────
echo ""
echo "→ Compiling release binary..."
swift build -c release 2>&1 | tail -5

BINARY=".build/release/${BINARY_NAME}"
if [ ! -f "$BINARY" ]; then
  echo "ERROR: Missing $BINARY — build failed."
  exit 1
fi
echo "  Binary: $(du -h "$BINARY" | cut -f1) ($(file -b "$BINARY" | head -c 60))"

# ── 2. Create .app bundle ───────────────────────────────────────────────
echo ""
echo "→ Creating ${APP_DISPLAY}.app bundle..."
rm -rf "$APP_BUNDLE"
mkdir -p "${APP_BUNDLE}/Contents/MacOS"
mkdir -p "${APP_BUNDLE}/Contents/Resources"

cp "$BINARY" "${APP_BUNDLE}/Contents/MacOS/${APP_DISPLAY}"
chmod +x "${APP_BUNDLE}/Contents/MacOS/${APP_DISPLAY}"

# ── 3. Info.plist ────────────────────────────────────────────────────────
cat > "${APP_BUNDLE}/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleExecutable</key>
	<string>${APP_DISPLAY}</string>
	<key>CFBundleIdentifier</key>
	<string>ai.asta.macapp</string>
	<key>CFBundleName</key>
	<string>${APP_DISPLAY}</string>
	<key>CFBundleDisplayName</key>
	<string>${APP_DISPLAY}</string>
	<key>CFBundlePackageType</key>
	<string>APPL</string>
	<key>CFBundleShortVersionString</key>
	<string>${VERSION}</string>
	<key>CFBundleVersion</key>
	<string>${VERSION}</string>
	<key>CFBundleInfoDictionaryVersion</key>
	<string>6.0</string>
	<key>LSMinimumSystemVersion</key>
	<string>13.0</string>
	<key>LSApplicationCategoryType</key>
	<string>public.app-category.productivity</string>
	<key>NSHighResolutionCapable</key>
	<true/>
	<key>NSPrincipalClass</key>
	<string>NSApplication</string>
	<key>NSSupportsAutomaticTermination</key>
	<false/>
	<key>NSSupportsSuddenTermination</key>
	<false/>
	<key>NSAppTransportSecurity</key>
	<dict>
		<key>NSAllowsArbitraryLoads</key>
		<true/>
	</dict>
</dict>
</plist>
PLIST

# ── 4. App icon ──────────────────────────────────────────────────────────
# Use pre-built .icns if available, otherwise generate from AppIcon.png
ICNS_FILE="${BUILD_DIR}/AppIcon.icns"
ICON_SRC=""
[ -f "${SCRIPT_DIR}/Assets/AppIcon.png" ] && ICON_SRC="${SCRIPT_DIR}/Assets/AppIcon.png"
[ -z "$ICON_SRC" ] && [ -f "${SCRIPT_DIR}/Assets/AppIcon.jpg" ] && ICON_SRC="${SCRIPT_DIR}/Assets/AppIcon.jpg"

if [ -f "$ICNS_FILE" ]; then
  echo "  Using existing AppIcon.icns"
elif [ -n "$ICON_SRC" ]; then
  echo "  Generating AppIcon.icns from ${ICON_SRC}..."
  ICONSET="${BUILD_DIR}/AppIcon.iconset"
  rm -rf "$ICONSET"
  mkdir -p "$ICONSET"
  sips -s format png -z 16 16      "$ICON_SRC" --out "$ICONSET/icon_16x16.png"      > /dev/null
  sips -s format png -z 32 32      "$ICON_SRC" --out "$ICONSET/icon_16x16@2x.png"   > /dev/null
  sips -s format png -z 32 32      "$ICON_SRC" --out "$ICONSET/icon_32x32.png"       > /dev/null
  sips -s format png -z 64 64      "$ICON_SRC" --out "$ICONSET/icon_32x32@2x.png"   > /dev/null
  sips -s format png -z 128 128    "$ICON_SRC" --out "$ICONSET/icon_128x128.png"     > /dev/null
  sips -s format png -z 256 256    "$ICON_SRC" --out "$ICONSET/icon_128x128@2x.png"  > /dev/null
  sips -s format png -z 256 256    "$ICON_SRC" --out "$ICONSET/icon_256x256.png"     > /dev/null
  sips -s format png -z 512 512    "$ICON_SRC" --out "$ICONSET/icon_256x256@2x.png"  > /dev/null
  sips -s format png -z 512 512    "$ICON_SRC" --out "$ICONSET/icon_512x512.png"     > /dev/null
  sips -s format png -z 1024 1024  "$ICON_SRC" --out "$ICONSET/icon_512x512@2x.png"  > /dev/null
  iconutil -c icns "$ICONSET" -o "$ICNS_FILE"
  rm -rf "$ICONSET"
  echo "  Generated AppIcon.icns"
fi

if [ -f "$ICNS_FILE" ]; then
  cp "$ICNS_FILE" "${APP_BUNDLE}/Contents/Resources/AppIcon.icns"
  /usr/libexec/PlistBuddy -c "Add :CFBundleIconFile string AppIcon" "${APP_BUNDLE}/Contents/Info.plist" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Set :CFBundleIconFile AppIcon" "${APP_BUNDLE}/Contents/Info.plist"
  echo "  Icon embedded in app bundle"
fi

echo "  ${APP_BUNDLE} ready"

# ── 5. DMG ───────────────────────────────────────────────────────────────
echo ""
echo "→ Creating DMG..."

DMG_NAME="${APP_DISPLAY}-${VERSION}.dmg"
DMG_PATH="${BUILD_DIR}/${DMG_NAME}"
DMG_STAGING="${BUILD_DIR}/.dmg-staging"

# Also create a latest symlink
DMG_LATEST="${BUILD_DIR}/${APP_DISPLAY}.dmg"

rm -rf "$DMG_STAGING"
mkdir -p "$DMG_STAGING"
cp -R "$APP_BUNDLE" "$DMG_STAGING/"
ln -s /Applications "$DMG_STAGING/Applications"

if command -v create-dmg &>/dev/null; then
  rm -f "$DMG_PATH"
  create-dmg \
    --volname "Install ${APP_DISPLAY}" \
    --window-pos 200 120 \
    --window-size 540 380 \
    --icon-size 80 \
    --app-drop-link 400 220 \
    --no-internet-enable \
    "$DMG_PATH" \
    "$APP_BUNDLE" 2>&1 | grep -v "^$" || true
else
  rm -f "$DMG_PATH" "${BUILD_DIR}/.dmg-tmp.dmg"
  hdiutil create -volname "Install ${APP_DISPLAY}" -srcfolder "$DMG_STAGING" -ov -format UDZO "${BUILD_DIR}/.dmg-tmp.dmg" > /dev/null
  mv "${BUILD_DIR}/.dmg-tmp.dmg" "$DMG_PATH"
fi

rm -rf "$DMG_STAGING"

# Symlink latest
rm -f "$DMG_LATEST"
ln -sf "$DMG_NAME" "$DMG_LATEST"

# Also copy to Desktop for convenience
cp "$DMG_PATH" ~/Desktop/"${DMG_NAME}"

echo "  $(du -h "$DMG_PATH" | cut -f1)  ${DMG_PATH}"
echo "  Copied to ~/Desktop/${DMG_NAME}"

# ── Done ─────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════"
echo "  Done!"
echo "  App:  ${APP_BUNDLE}"
echo "  DMG:  ${DMG_PATH}"
echo "  Open the DMG and drag Asta to Applications."
echo "══════════════════════════════════════════════════"
