#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="${CANOPY_GH_LAUNCHD_LABEL:-com.canopy.graphhopper}"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LAB_DIR="${CANOPY_GH_WORKDIR:-"$HOME/pcn-lab"}"
JAR_PATH="${CANOPY_GH_JAR:-"$LAB_DIR/graphhopper-web-11.0.jar"}"
PBF_PATH="${CANOPY_GH_PBF:-"$LAB_DIR/singapore.osm.pbf"}"
GRAPH_CACHE="${CANOPY_GH_GRAPH_CACHE:-"$LAB_DIR/graph-cache"}"
CONFIG_PATH="${CANOPY_GH_CONFIG:-"$REPO_DIR/configs/graphhopper/config.yml"}"
JAVA_BIN="${CANOPY_JAVA_BIN:-}"

mkdir -p "$HOME/Library/LaunchAgents" "$LAB_DIR/logs"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$REPO_DIR/scripts/run_graphhopper.sh</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$LAB_DIR</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>CANOPY_GH_WORKDIR</key>
    <string>$LAB_DIR</string>
    <key>CANOPY_GH_JAR</key>
    <string>$JAR_PATH</string>
    <key>CANOPY_GH_PBF</key>
    <string>$PBF_PATH</string>
    <key>CANOPY_GH_GRAPH_CACHE</key>
    <string>$GRAPH_CACHE</string>
    <key>CANOPY_GH_CONFIG</key>
    <string>$CONFIG_PATH</string>
    <key>CANOPY_JAVA_BIN</key>
    <string>$JAVA_BIN</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$LAB_DIR/logs/graphhopper.log</string>
  <key>StandardErrorPath</key>
  <string>$LAB_DIR/logs/graphhopper.err.log</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl kickstart -k "gui/$(id -u)/$LABEL"

echo "$PLIST"
