#!/usr/bin/env bash
set -euo pipefail

cp /opt/graphhopper/pcn.json /data/pcn.json
exec java ${JAVA_OPTS:-} \
  -jar /opt/graphhopper/graphhopper.jar server /opt/graphhopper/config.yml
