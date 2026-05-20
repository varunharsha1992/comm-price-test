"""
Write forecast outputs to disk so downstream steps (e.g. market_intel) can read price_forecast.json.

Uses MARKET_INTEL_DATA_DIR (same as market_intel.py); defaults to cwd.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np


def get_commodity_data_dir() -> Path:
    raw = os.environ.get("MARKET_INTEL_DATA_DIR", ".")
    return Path(raw).expanduser().resolve()


def build_price_forecast_payload(result: dict[str, Any]) -> dict[str, Any]:
    """
    Canonical JSON matching market_intel + plugin conventions:
    aliases for current/P50 plus optional horizon bands derived from forecast_series.
    """
    lp = float(result["latest_price"])
    fp = float(result["forecast_price"])
    payload: dict[str, Any] = dict(result)
    payload["current_price"] = lp
    payload["P0"] = lp
    payload["P50"] = fp

    series = result.get("forecast_series") or []
    if isinstance(series, list) and series:
        prices = [float(row["predicted_modal_price"]) for row in series if "predicted_modal_price" in row]
        if len(prices) >= 2:
            payload["P10"] = round(float(np.percentile(prices, 10)), 2)
            payload["P90"] = round(float(np.percentile(prices, 90)), 2)

    return payload


def save_price_forecast_json(result: dict[str, Any], base_dir: Path | None = None) -> Path:
    """Persist price_forecast.json; returns path written."""
    root = base_dir if base_dir is not None else get_commodity_data_dir()
    root.mkdir(parents=True, exist_ok=True)
    path = root / "price_forecast.json"
    payload = build_price_forecast_payload(result)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)

    try:
        from workspace_storage import artifacts_enabled, get_supabase, upload_json_object

        if artifacts_enabled():
            sb = get_supabase()
            upload_json_object(sb, "price_forecast.json", payload)
    except Exception as exc:  # noqa: BLE001 — remote sync optional; local file is canonical
        print(f"[forecast_artifacts] Supabase workspace upload failed (local saved): {exc}", flush=True)

    return path
