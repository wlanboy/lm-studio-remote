#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/whelper.sh"

# --- LM Studio ---
LMSTUDIO_APPIMAGE="$HOME/Applications/LM-Studio-${LMSTUDIO_VERSION}-x64.AppImage"
if need_file "$LMSTUDIO_APPIMAGE" "LM Studio"; then
  wget --show-progress "https://installers.lmstudio.ai/linux/x64/${LMSTUDIO_VERSION}/LM-Studio-${LMSTUDIO_VERSION}-x64.AppImage" -O "$LMSTUDIO_APPIMAGE" || { rm -f "$LMSTUDIO_APPIMAGE"; echo "  LM Studio Download fehlgeschlagen"; }
  [ -s "$LMSTUDIO_APPIMAGE" ] && chmod +x "$LMSTUDIO_APPIMAGE"
fi

DESKTOP_FILE="$HOME/.local/share/applications/lmstudio.desktop"
if [ ! -f "$DESKTOP_FILE" ] || ! grep -qF "Exec=$LMSTUDIO_APPIMAGE --no-sandbox" "$DESKTOP_FILE"; then
  echo "  LM Studio Desktop-Eintrag wird erstellt/aktualisiert"
  mkdir -p "$(dirname "$DESKTOP_FILE")"
  cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Name=LM Studio
Exec=$LMSTUDIO_APPIMAGE --no-sandbox
Icon=lmstudio
Type=Application
Categories=Utility;Development;
Terminal=false
EOF
  chmod +x "$DESKTOP_FILE"
  gio set "$DESKTOP_FILE" metadata::trusted true 2>/dev/null || true
  echo "  Desktop-Datei erstellt unter: $DESKTOP_FILE"
else
  echo "  LM Studio Desktop-Eintrag ist bereits aktuell -> übersprungen"
fi

if need_file "$HOME/.local/share/icons/lmstudio.png" "LM Studio Icon"; then
  wget -q --show-progress "https://lmstudio.ai/assets/android-chrome-512x512.png" \
       -O "$HOME/.local/share/icons/lmstudio.png" || true
fi

# Update Desktop Database
update-desktop-database ~/.local/share/applications/
