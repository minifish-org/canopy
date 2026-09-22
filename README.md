# Canopy

Canopy is a local self-hosted MCP server for Singapore cycling and walking route planning. It is built for AI agents, not end users: Claude, Codex, LangChain, and other MCP clients call Canopy tools; the calling agent handles conversation and presentation.

Canopy is a stateless Streamable HTTP MCP server backed by a self-hosted
GraphHopper 11 service. The GraphHopper bike profile uses a PCN-biased custom
model that strongly prefers cycleways, PCN-like paths, and low-car links while
heavily penalizing motor roads. OneMap is used only for geocoding and POIs,
never for routing.

## Tools

The MCP server exposes:

- `geocode(query)` returns OneMap address/place matches.
- `plan_loop(start, distance_km, direction?, prefer="pcn")` returns a PCN-biased round trip with actual distance, audit percentages, and dense GeoJSON geometry.
- `route(origin, destination, prefer="pcn")` returns an A-to-B PCN-biased route.
- `pois_along(geometry, types=[...])` returns OneMap theme POIs near a route corridor.
- `audit_route(geometry)` computes car-free/on-road percentages from Canopy route geometry.
- `export_gpx(geometry, name)` returns a portable filename, media type, and dense GPX `<trk>` content. It never exposes a host path.

The `route` tool uses `origin` and `destination` parameter names because `from` is a Python reserved word.

## Honest Boundaries

- Canopy optimizes for low-car and away-from-traffic routing. It does not avoid pedestrians; Singapore PCNs are shared paths.
- `round_trip.distance` is approximate in GraphHopper. Canopy tries multiple seeds and scaled requests, then always returns the actual distance.
- OneMap routing is intentionally unused because it cannot express the PCN preference.
- There is no bundled web UI or turn-by-turn navigation. Downstream apps can load the generated GPX track, for example OsmAnd "Navigate by Track" or CoMaps visual following.

## Quick start (Docker Compose)

Requires Docker with Compose and enough memory for GraphHopper (the default
Java heap limit is 1.2 GB, plus application/container overhead).

```bash
git clone https://github.com/minifish-org/canopy.git
cd canopy
docker compose up --build -d
docker compose ps
```

The first start imports the Singapore map before starting Canopy. Connect your
MCP client to `http://localhost:8000/mcp`. Coordinate-based routes do not need
OneMap credentials. Configure OneMap below for address lookup and theme POIs.
Canopy has no built-in authentication: this example publishes MCP on loopback
only and leaves GraphHopper inside the Compose network.

Stop with `docker compose down`; the graph cache remains in a named volume.
After changing the map snapshot, remove the old graph cache with
`docker compose down -v` before rebuilding. This deletes only this Compose
project's generated cache.

### Updating the map snapshot

BBBike refreshes its download URL. The image verifies a reviewed SHA-256 and
fails closed if upstream data changes. If a build reports a checksum mismatch,
download and inspect the new extract, record its SHA-256, then rebuild:

```bash
curl --fail --location --output /tmp/singapore.osm.pbf \
  https://download.bbbike.org/osm/bbbike/Singapore/Singapore.osm.pbf
shasum -a 256 /tmp/singapore.osm.pbf
# After reviewing the source and digest:
export SINGAPORE_PBF_SHA256=<reviewed-sha256>
docker compose build graphhopper
docker compose up -d
```

The digest detects changes; a digest calculated from the same download is not
an independent authenticity check. For repeatable builds, archive the reviewed
extract at an immutable URL and set `SINGAPORE_PBF_URL` as well.

## Containers

The canonical deployment consists of two images:

- `ghcr.io/minifish-org/canopy` serves Streamable HTTP MCP on `/mcp`.
- `ghcr.io/minifish-org/canopy-graphhopper` serves routing internally on port 8989.

Prebuilt GHCR packages currently require registry access. The public quick start
builds from source and does not need registry credentials.

The GraphHopper image pins the JVM artifact and Singapore OSM snapshot by
SHA-256. Only its generated graph cache is persisted.

## Native development (optional)

Use Python 3.10+ for the MCP server.

```bash
git clone https://github.com/minifish-org/canopy.git
cd canopy
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

If the Singapore OSM extract is missing:

```bash
scripts/download_singapore_osm.sh
```

## Native GraphHopper on macOS (optional)

The launchd installer starts GraphHopper on `localhost:8989` and keeps it alive:

```bash
scripts/install_graphhopper_launchd.sh
```

The runner defaults to `~/pcn-lab`. Override paths with:

- `CANOPY_GH_WORKDIR`
- `CANOPY_GH_JAR`
- `CANOPY_GH_PBF`
- `CANOPY_GH_GRAPH_CACHE`
- `CANOPY_JAVA_BIN`

GraphHopper 11 needs Java 17+. The runner prefers Homebrew OpenJDK 17/21 when available instead of the system default `java`.

Check the service:

```bash
canopy-gh-health
```

## OneMap

OneMap credentials stay server-side. Configure either a token:

```bash
export CANOPY_ONEMAP_TOKEN=...
```

or credentials so Canopy can refresh the 72-hour token:

```bash
export CANOPY_ONEMAP_EMAIL=...
export CANOPY_ONEMAP_PASSWORD=...
```

Token cache defaults to `~/.canopy/onemap-token.json` with local file permissions tightened to `0600`.

POI aliases such as `water`, `toilet`, `bicycle_parking`, and `shelter` are best-effort because OneMap theme query names vary. Exact OneMap query names can be passed directly, or configured:

```bash
export CANOPY_POI_THEME_MAP='{"toilet":["public_toilets"],"bicycle_parking":["bicycleparking"]}'
```

## MCP Client Config

For native development, start the server with
`CANOPY_MCP_HOST=127.0.0.1 canopy-mcp`.

Connect MCP clients to `http://localhost:8000/mcp` in local Docker or
`http://canopy:8000/mcp` from another service on the Compose network. Canopy
has no stdio deployment path.

Example request an agent can decompose into tool calls:

> Plan a low-car loop from Eunos, heading east, about 20 km, and give me the GPX.

The agent should call `plan_loop(start="Eunos", distance_km=20, direction="east")`.
If a GPX is required, it then calls `export_gpx` and writes the returned
`content` through its artifact capability.

## LangChain

LangChain can consume the same Streamable HTTP server through
`langchain-mcp-adapters`; no Canopy-specific integration is required.

## Development

Run tests that do not require GraphHopper or OneMap:

```bash
python -m pytest
```

Run a live GraphHopper health check:

```bash
CANOPY_GRAPHHOPPER_URL=http://localhost:8989 canopy-gh-health
```

Official API references used for OneMap integration:

- [OneMap Authentication](https://www.onemap.gov.sg/apidocs/authentication)
- [OneMap Search](https://www.onemap.gov.sg/apidocs/search)
- [OneMap Themes](https://www.onemap.gov.sg/apidocs/themes)

## License and data

Canopy code is AGPL-3.0-or-later; see [LICENSE](LICENSE). Map data, GraphHopper
and OneMap are separate dependencies with their own terms. See
[third-party notices](THIRD_PARTY_NOTICES.md) for source and attribution links.
This is an experimental routing tool: preferences and audit percentages describe
map-derived estimates, not a guarantee of real-world access or conditions.
