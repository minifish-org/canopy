#!/usr/bin/env bash
set -euo pipefail

LAB_DIR="${CANOPY_GH_WORKDIR:-"$HOME/pcn-lab"}"
URL="${CANOPY_SINGAPORE_PBF_URL:-https://download.bbbike.org/osm/bbbike/Singapore/Singapore.osm.pbf}"

mkdir -p "$LAB_DIR"
curl -L "$URL" -o "$LAB_DIR/singapore.osm.pbf"
echo "$LAB_DIR/singapore.osm.pbf"
