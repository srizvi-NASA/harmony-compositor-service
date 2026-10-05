"""Optional helper for downloading a known granule with earthaccess.

The helper intentionally accepts identifiers on the command line rather than
embedding a test granule in service code.  For UAT, authenticate using the
Earthdata/earthaccess UAT setup used by your local Harmony development
environment, then pass the UAT granule concept ID.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import earthaccess


def main() -> None:
    parser = argparse.ArgumentParser(description="Download one test granule")
    parser.add_argument("--granule-concept-id", required=True)
    parser.add_argument("--output-dir", default="tests/data/in_data")
    parser.add_argument(
        "--login-strategy",
        default="environment",
        choices=["environment", "interactive", "netrc"],
    )
    args = parser.parse_args()

    target = Path(args.output_dir)
    target.mkdir(parents=True, exist_ok=True)
    earthaccess.login(strategy=args.login_strategy)
    granules = earthaccess.search_data(concept_id=args.granule_concept_id, count=1)
    if not granules:
        raise SystemExit(f"No granule found for {args.granule_concept_id}")
    print(earthaccess.download(granules, target))


if __name__ == "__main__":
    main()
