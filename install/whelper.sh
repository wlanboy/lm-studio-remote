#!/bin/bash
# Hilfsfunktionen für Tool-Installation

LMSTUDIO_VERSION="0.4.20-1"

# Ermittelt die installierte Version eines Tools, oder "" falls nicht vorhanden
installed_version() {
  local cmd="$1"
  if ! command -v "$cmd" &>/dev/null; then
    echo ""
    return
  fi
  case "$cmd" in
    *)         echo "installed" ;;
  esac
}

# Prüft ob eine SDK-Candidate-Version installiert ist (sdkman)
sdk_need_install() {
  local candidate="$1"
  local want="$2"
  if [ ! -d "$HOME/.sdkman/candidates/$candidate/$want" ]; then
    echo "  $candidate $want ist nicht installiert -> wird installiert"
    return 0
  fi
  echo "  $candidate $want ist bereits installiert -> übersprungen"
  return 1
}

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

need_install() {
  local cmd="$1"
  local want="$2"
  local have
  have=$(installed_version "$cmd")
  if [ -z "$have" ]; then
    echo "  $cmd ist nicht installiert -> wird installiert"
    return 0
  fi
  if [ "$have" = "installed" ]; then
    echo "  $cmd ist bereits installiert -> übersprungen"
    return 1
  fi
  if [ "$have" = "$want" ]; then
    echo "  $cmd ist bereits in Version $want installiert -> übersprungen"
    return 1
  fi
  echo "  $cmd Version $have -> wird auf $want aktualisiert"
  return 0
}
