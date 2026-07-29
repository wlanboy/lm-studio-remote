#!/bin/bash
set -e

LMSTUDIO_VERSION="0.4.20-1"

# Prüft ob eine Datei/AppImage existiert und nicht leer ist
need_file() {
  local path="$1"
  local name="$2"
  if [ -f "$path" ] && [ -s "$path" ]; then
    echo "  $name ist bereits vorhanden -> übersprungen"
    return 1
  fi
  [ -f "$path" ] && rm -f "$path"
  echo "  $name ist nicht vorhanden -> wird installiert"
  return 0
}

# --- LM Studio ---
LMSTUDIO_APPIMAGE="$HOME/Applications/LM-Studio-${LMSTUDIO_VERSION}-x64.AppImage"
mkdir -p "$(dirname "$LMSTUDIO_APPIMAGE")"
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

ICON_FILE="$HOME/.local/share/icons/lmstudio.png"
mkdir -p "$(dirname "$ICON_FILE")"
if need_file "$ICON_FILE" "LM Studio Icon"; then
  wget -q --show-progress "https://lmstudio.ai/assets/android-chrome-512x512.png" \
       -O "$ICON_FILE" || true
fi

# Update Desktop Database
command -v update-desktop-database &>/dev/null && update-desktop-database "$HOME/.local/share/applications/"
