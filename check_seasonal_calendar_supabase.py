"""
Verify seasonal_calendar.json exists in Supabase Storage at the artifact path used by market_intel.

Uses .env via python-dotenv: SUPABASE_URL, SUPABASE_SERVICE_KEY, BUCKET_NAME, COMMODITY_SUPABASE_PREFIX
(same semantics as workspace_storage.py).

Usage:
    python check_seasonal_calendar_supabase.py
    python check_seasonal_calendar_supabase.py --also-forecast   # price_forecast.json too
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from workspace_storage import _bucket_name, _object_path, get_supabase  # noqa: E402


def _exists(sb, bucket: str, object_key: str) -> tuple[bool, int | None, str | None]:
    try:
        data = sb.storage.from_(bucket).download(object_key)
        return True, len(data), None
    except Exception as e:  # noqa: BLE001
        return False, None, str(e)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check workspace JSON objects in Supabase Storage.")
    parser.add_argument(
        "--also-forecast",
        action="store_true",
        help="Also check price_forecast.json.",
    )
    args = parser.parse_args()

    prefix = os.environ.get("COMMODITY_SUPABASE_PREFIX", "workspace")
    bucket = _bucket_name()
    print(f"Bucket: {bucket!r}")
    print(f"COMMODITY_SUPABASE_PREFIX: {prefix!r}")
    print()

    try:
        sb = get_supabase()
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return 1

    keys = ["seasonal_calendar.json"]
    if args.also_forecast:
        keys.append("price_forecast.json")

    rc = 0
    for name in keys:
        key = _object_path(name)
        ok, nbytes, err = _exists(sb, bucket, key)
        if ok:
            print(f"OK   {bucket}/{key}  ({nbytes} bytes)")
        else:
            print(f"MISS {bucket}/{key}")
            print(f"     {err}")
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
