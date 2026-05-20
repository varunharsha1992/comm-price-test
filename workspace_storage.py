"""
Supabase Storage helpers for shared commodity workspace JSON/CSV blobs.

Uses the same bucket as forecaster (BUCKET_NAME, default Forecasting).
Object paths default to ``{COMMODITY_SUPABASE_PREFIX}/<filename>`` e.g. ``workspace/price_forecast.json``.

Set COMMODITY_USE_SUPABASE_ARTIFACTS=true to upload forecast outputs and hydrate market_intel from bucket.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from supabase import Client, create_client


def artifacts_enabled() -> bool:
    raw = os.environ.get("COMMODITY_USE_SUPABASE_ARTIFACTS", "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _bucket_name() -> str:
    return os.environ.get("BUCKET_NAME", "Forecasting")


def _prefix() -> str:
    return os.environ.get("COMMODITY_SUPABASE_PREFIX", "workspace").strip().strip("/")


def _object_path(filename: str) -> str:
    p = _prefix()
    return f"{p}/{filename}" if p else filename


def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set for Supabase artifact mode")
    return create_client(url, key)


def download_object_bytes(sb: Client, filename: str) -> bytes:
    path = _object_path(filename)
    print(f"  Downloading workspace object: {path}")
    return sb.storage.from_(_bucket_name()).download(path)


def upload_json_object(sb: Client, filename: str, payload: dict[str, Any]) -> str:
    path = _object_path(filename)
    body = json.dumps(payload, indent=2, default=str).encode("utf-8")
    sb.storage.from_(_bucket_name()).upload(
        path=path,
        file=body,
        file_options={"content-type": "application/json", "upsert": "true"},
    )
    print(f"  Uploaded workspace object: {path}")
    return path


def materialize_workspace_dir() -> Path:
    """Download seasonal_calendar + price_forecast (required) into a temp dir."""
    import tempfile

    sb = get_supabase()
    td = Path(tempfile.mkdtemp(prefix="commodity_workspace_"))

    for required in ("seasonal_calendar.json", "price_forecast.json"):
        data = download_object_bytes(sb, required)
        (td / required).write_bytes(data)

    for optional_name, as_binary in (
        ("ndvi_latest.json", True),
        ("mandi_arrivals.csv", True),
    ):
        try:
            data = download_object_bytes(sb, optional_name)
            (td / optional_name).write_bytes(data)
        except Exception:
            continue

    return td
