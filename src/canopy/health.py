from __future__ import annotations

import json
import sys

from .config import Settings
from .graphhopper import GraphHopperClient, GraphHopperError


def main() -> None:
    settings = Settings.from_env()
    client = GraphHopperClient(
        settings.graphhopper_url,
        profile=settings.graphhopper_profile,
        timeout_s=settings.graphhopper_timeout_s,
    )
    try:
        info = client.info()
    except GraphHopperError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps(info, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
