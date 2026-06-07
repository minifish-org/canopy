#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAB_DIR="${CANOPY_GH_WORKDIR:-"$HOME/pcn-lab"}"
JAR_PATH="${CANOPY_GH_JAR:-"$LAB_DIR/graphhopper-web-11.0.jar"}"
PBF_PATH="${CANOPY_GH_PBF:-"$LAB_DIR/singapore.osm.pbf"}"
GRAPH_CACHE="${CANOPY_GH_GRAPH_CACHE:-"$LAB_DIR/graph-cache"}"
CONFIG_PATH="${CANOPY_GH_CONFIG:-"$REPO_DIR/configs/graphhopper/config.yml"}"
JAVA_BIN="${CANOPY_JAVA_BIN:-}"

if [[ -z "$JAVA_BIN" ]]; then
  if [[ -x /opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home/bin/java ]]; then
    JAVA_BIN=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home/bin/java
  elif [[ -x /opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home/bin/java ]]; then
    JAVA_BIN=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home/bin/java
  elif [[ -x /opt/homebrew/opt/java/libexec/openjdk.jdk/Contents/Home/bin/java ]]; then
    JAVA_BIN=/opt/homebrew/opt/java/libexec/openjdk.jdk/Contents/Home/bin/java
  else
    JAVA_BIN=java
  fi
fi

if [[ ! -f "$JAR_PATH" ]]; then
  echo "Missing GraphHopper jar: $JAR_PATH" >&2
  exit 1
fi
if [[ ! -f "$PBF_PATH" ]]; then
  echo "Missing Singapore OSM PBF: $PBF_PATH" >&2
  exit 1
fi

mkdir -p "$LAB_DIR" "$LAB_DIR/logs"
cp "$REPO_DIR/configs/graphhopper/pcn.json" "$LAB_DIR/pcn.json"

cd "$LAB_DIR"
exec "$JAVA_BIN" \
  -Ddw.graphhopper.datareader.file="$PBF_PATH" \
  -Ddw.graphhopper.graph.location="$GRAPH_CACHE" \
  -jar "$JAR_PATH" server "$CONFIG_PATH"
