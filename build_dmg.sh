#!/bin/bash
# Baut die Swift-App als .app-Bundle und verpackt sie in ein DMG-Installationsimage.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="Desktop Profile Manager"
DMG_NAME="DesktopProfileManager-Swift"
VERSION="${VERSION:-1.5.9}"
NOTARIZE="${NOTARIZE:-1}"

if [ -z "${SIGNING_IDENTITY:-}" ]; then
    SIGNING_IDENTITY="$(security find-identity -v -p codesigning 2>/dev/null | \
        sed -n 's/.*"\(Developer ID Application:.*\)"/\1/p' | head -n 1)"
fi
if [ -z "$SIGNING_IDENTITY" ]; then
    echo "❌ Keine 'Developer ID Application'-Signaturidentität gefunden."
    exit 1
fi
export SIGNING_IDENTITY VERSION

if [ "$NOTARIZE" = "1" ]; then
    if [ -n "${NOTARYTOOL_PROFILE:-}" ]; then
        NOTARY_AUTH=(--keychain-profile "$NOTARYTOOL_PROFILE")
    elif [ -n "${NOTARYTOOL_KEY:-}" ] && [ -n "${NOTARYTOOL_KEY_ID:-}" ]; then
        NOTARY_AUTH=(--key "$NOTARYTOOL_KEY" --key-id "$NOTARYTOOL_KEY_ID")
        if [ -n "${NOTARYTOOL_ISSUER:-}" ]; then
            NOTARY_AUTH+=(--issuer "$NOTARYTOOL_ISSUER")
        fi
    else
        echo "❌ Notarisierungszugang fehlt. Setze NOTARYTOOL_PROFILE oder NOTARYTOOL_KEY und NOTARYTOOL_KEY_ID."
        echo "   Für ein Keychain-Profil: xcrun notarytool store-credentials <Profilname>"
        exit 1
    fi
fi

APP_PATH="$SCRIPT_DIR/dist/${APP_NAME}.app"
DMG_DIR="$SCRIPT_DIR/dmg_staging"
DMG_OUTPUT="$SCRIPT_DIR/${DMG_NAME}-${VERSION}.dmg"

echo "═══════════════════════════════════════════════"
echo " Desktop Profile Manager – DMG"
echo "═══════════════════════════════════════════════"

# 1. App-Bundle bauen
"$SCRIPT_DIR/build_app.sh"

if [ ! -d "$APP_PATH" ]; then
    echo "❌ App-Bundle nicht gefunden: $APP_PATH"
    exit 1
fi

if [ "$NOTARIZE" = "1" ]; then
    APP_ARCHIVE="$SCRIPT_DIR/dist/${DMG_NAME}-${VERSION}-notarization.zip"
    rm -f "$APP_ARCHIVE"
    echo "☁️  Reiche App zur Notarisierung ein..."
    ditto -c -k --keepParent "$APP_PATH" "$APP_ARCHIVE"
    xcrun notarytool submit "$APP_ARCHIVE" "${NOTARY_AUTH[@]}" --wait
    echo "📌 Heftet Notarisierungs-Ticket an die App..."
    xcrun stapler staple "$APP_PATH"
    xcrun stapler validate "$APP_PATH"
fi

# 2. DMG erstellen
echo "📦 Erstelle DMG-Installationsimage..."
rm -rf "$DMG_DIR" "$DMG_OUTPUT"
mkdir -p "$DMG_DIR"
ditto "$APP_PATH" "$DMG_DIR/${APP_NAME}.app"
ln -s /Applications "$DMG_DIR/Applications"

hdiutil create \
    -volname "$APP_NAME" \
    -srcfolder "$DMG_DIR" \
    -ov \
    -format UDZO \
    -imagekey zlib-level=9 \
    "$DMG_OUTPUT"

rm -rf "$DMG_DIR"

echo "✍️  Signiere DMG mit: $SIGNING_IDENTITY"
codesign --force --sign "$SIGNING_IDENTITY" --timestamp "$DMG_OUTPUT"
codesign --verify --verbose=2 "$DMG_OUTPUT"

if [ "$NOTARIZE" = "1" ]; then
    echo "☁️  Reiche DMG zur Notarisierung ein..."
    xcrun notarytool submit "$DMG_OUTPUT" "${NOTARY_AUTH[@]}" --wait
    echo "📌 Heftet Notarisierungs-Ticket an..."
    xcrun stapler staple "$DMG_OUTPUT"
    xcrun stapler validate "$DMG_OUTPUT"
    spctl --assess --type open --verbose=4 --context context:primary-signature "$DMG_OUTPUT"
fi

echo ""
echo "═══════════════════════════════════════════════"
echo " ✅ Fertig!"
echo "═══════════════════════════════════════════════"
echo " App:  $APP_PATH"
echo " DMG:  $DMG_OUTPUT"
echo " Größe: $(du -h "$DMG_OUTPUT" | cut -f1)"
