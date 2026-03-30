#!/bin/bash
set -e

APP_NAME="IconGuard"
DMG_NAME="IconGuard"
VERSION="1.1.0"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

DIST_DIR="$SCRIPT_DIR/dist"
BUILD_DIR="$SCRIPT_DIR/build"
DMG_DIR="$SCRIPT_DIR/dmg_staging"
DMG_OUTPUT="$SCRIPT_DIR/${DMG_NAME}-${VERSION}.dmg"

echo "═══════════════════════════════════════════════"
echo " IconGuard – Build & DMG"
echo "═══════════════════════════════════════════════"
echo ""

# ─── 1. Aufräumen ─────────────────────────────────────────────────
echo "🧹 Räume vorherige Builds auf..."
rm -rf "$DIST_DIR" "$BUILD_DIR" "$DMG_DIR" "$DMG_OUTPUT"

# ─── 2. App bauen ─────────────────────────────────────────────────
echo "🔨 Baue ${APP_NAME}.app mit py2app..."
"$SCRIPT_DIR/.venv/bin/python3" setup_app.py py2app 2>&1 | tail -20

APP_PATH="$DIST_DIR/${APP_NAME}.app"

if [ ! -d "$APP_PATH" ]; then
    echo "❌ Build fehlgeschlagen – ${APP_NAME}.app nicht gefunden."
    exit 1
fi

echo "✅ App gebaut: $APP_PATH"

# ─── 3. Boot-Script patchen (venv-Pfad entfernen) ────────────────
BOOT_PY="$APP_PATH/Contents/Resources/__boot__.py"
if [ -f "$BOOT_PY" ]; then
    # Ersetze den hartcodierten venv-Pfad durch den Bundle-lib-Pfad
    python3 -c "
import re
path = '$BOOT_PY'
with open(path, 'r') as f:
    content = f.read()
# Ersetze _site_packages('/abs/venv/path', '/abs/python/path', N)
# durch Code der den Bundle-lib-Pfad zum sys.path hinzufügt
replacement = '''import os, sys, site
_lib = os.path.join(os.environ['RESOURCEPATH'], 'lib', 'python%d.%d' % sys.version_info[:2])
site.addsitedir(_lib)'''
content = re.sub(
    r\"_site_packages\('[^']*',\s*'[^']*',\s*\d+\)\",
    replacement,
    content
)
with open(path, 'w') as f:
    f.write(content)
"
    echo "✅ Boot-Script gepatcht (Bundle-lib-Pfad statt venv)"
fi

# ─── 4. Icon kopieren (Menüleiste) ───────────────────────────────
if [ -f "$SCRIPT_DIR/icon.png" ]; then
    cp "$SCRIPT_DIR/icon.png" "$APP_PATH/Contents/Resources/icon.png"
    echo "✅ Menüleisten-Icon kopiert"
fi

# ─── 4. DMG erstellen ────────────────────────────────────────────
echo "📦 Erstelle DMG-Installationsimage..."

mkdir -p "$DMG_DIR"
cp -R "$APP_PATH" "$DMG_DIR/"

# Symlink zu /Applications für Drag&Drop Installer
ln -s /Applications "$DMG_DIR/Applications"

# Hintergrund-Hinweis als versteckte Datei
mkdir -p "$DMG_DIR/.background"
cat > /tmp/dmg_readme.txt << 'EOF'
Drag "IconGuard" to Applications to install.
EOF

# DMG erzeugen
hdiutil create \
    -volname "${APP_NAME}" \
    -srcfolder "$DMG_DIR" \
    -ov \
    -format UDZO \
    -imagekey zlib-level=9 \
    "$DMG_OUTPUT"

# ─── 5. Aufräumen ────────────────────────────────────────────────
rm -rf "$DMG_DIR"
rm -f /tmp/dmg_readme.txt

echo ""
echo "═══════════════════════════════════════════════"
echo " ✅ Build abgeschlossen!"
echo "═══════════════════════════════════════════════"
echo ""
echo " App:  $APP_PATH"
echo " DMG:  $DMG_OUTPUT"
echo ""

# Größe anzeigen
DMG_SIZE=$(du -h "$DMG_OUTPUT" | cut -f1)
APP_SIZE=$(du -sh "$APP_PATH" | cut -f1)
echo " App-Größe: $APP_SIZE"
echo " DMG-Größe: $DMG_SIZE"
echo ""
echo " Installation:"
echo "   1. DMG öffnen (Doppelklick)"
echo "   2. App nach 'Programme' ziehen"
echo "   3. App aus Launchpad starten"
echo ""
