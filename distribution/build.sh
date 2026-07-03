#!/usr/bin/env bash
#
# Build & package Gomoku as a distributable macOS .app.zip
#
# Usage:
#   1. Edit the CONFIG block below if needed.
#   2. chmod +x distribution/build.sh    (once)
#   3. ./distribution/build.sh
#
# Outputs (both dropped in distribution/):
#   - Gomoku.app.zip   ← the file to send
#   - Gomoku.app       ← unzipped alongside, ready to test locally

set -euo pipefail

# The script lives in distribution/ but everything runs from the project root.
cd "$(dirname "$0")/.."

# ================== CONFIG — edit if needed ==================
ENTRY="main.py"
APP_NAME="Gomoku"
DIST_DIR="distribution"
ICON_PNG="${DIST_DIR}/app.png"
PY_DEPS=(PyInstaller pygame)          # add here anything your app imports
# =============================================================

# ---- sanity ----
[[ "$(uname)" == "Darwin" ]] || { echo "Run this on macOS."; exit 1; }
[[ -f "$ENTRY" ]]      || { echo "Missing $ENTRY";     exit 1; }
[[ -d "$DIST_DIR" ]]   || { echo "Missing folder $DIST_DIR/"; exit 1; }
[[ -f "$ICON_PNG" ]]   || { echo "Missing icon $ICON_PNG";    exit 1; }

# ---- deps ----
for mod in "${PY_DEPS[@]}"; do
    if ! python -c "import $mod" 2>/dev/null; then
        echo "→ Installing $mod..."
        pip install "$mod"
    fi
done

# ---- clean everything from a previous run ----
rm -rf build dist \
       "${APP_NAME}.spec" \
       "${APP_NAME}.iconset" \
       "${APP_NAME}.icns" \
       "${DIST_DIR}/${APP_NAME}.app" \
       "${DIST_DIR}/${APP_NAME}.app.zip"

# ---- build .icns from the source image (sips forces PNG conversion) ----
echo "→ Generating .icns from $ICON_PNG..."
mkdir "${APP_NAME}.iconset"

resize() {   # $1 = pixel size, $2 = target filename
    sips -s format png -z "$1" "$1" "$ICON_PNG" --out "${APP_NAME}.iconset/$2" >/dev/null
}

resize 16   icon_16x16.png
resize 32   icon_16x16@2x.png
resize 32   icon_32x32.png
resize 64   icon_32x32@2x.png
resize 128  icon_128x128.png
resize 256  icon_128x128@2x.png
resize 256  icon_256x256.png
resize 512  icon_256x256@2x.png
resize 512  icon_512x512.png
resize 1024 icon_512x512@2x.png

iconutil -c icns "${APP_NAME}.iconset" -o "${APP_NAME}.icns"

# ---- build the .app ----
echo "→ Building ${APP_NAME}.app with PyInstaller..."

pyinstaller \
    --onedir \
    --windowed \
    --noconfirm \
    --name "$APP_NAME" \
    --icon "${APP_NAME}.icns" \
    "$ENTRY"

# ---- zip the .app straight into distribution/ ----
echo "→ Zipping into ${DIST_DIR}/..."
ZIP_PATH="${DIST_DIR}/${APP_NAME}.app.zip"
( cd dist && zip -qr "../${ZIP_PATH}" "${APP_NAME}.app" )

# ---- also drop the unzipped .app next to it (for local testing) ----
cp -R "dist/${APP_NAME}.app" "${DIST_DIR}/${APP_NAME}.app"

# ---- tidy build intermediates ----
rm -rf build dist "${APP_NAME}.spec" "${APP_NAME}.iconset" "${APP_NAME}.icns"

ZIP_SIZE=$(du -h "$ZIP_PATH" | cut -f1)
ARCH=$(uname -m)

cat <<EOF

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Build complete.

  File to send : ${ZIP_PATH}   (${ZIP_SIZE})
  Local test   : open ${DIST_DIR}/${APP_NAME}.app
  Built for    : ${ARCH}
                   (arm64 = Apple Silicon, x86_64 = Intel)
                 Receiver's Mac MUST match — check with 'uname -m'.

  For her:
    1. double-click the .zip → macOS extracts ${APP_NAME}.app next to it
    2. FIRST launch only: right-click ${APP_NAME}.app → Open → confirm
       (Gatekeeper warning — the app is not Apple-signed)
    3. from then on, double-click works normally.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EOF
