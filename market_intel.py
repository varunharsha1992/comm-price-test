"""
Market intelligence pipeline for the commodity MCP server.

Reads ``price_forecast.json`` (written by ``run_price_forecast`` into the workspace),
``seasonal_calendar.json``, optional NDVI / mandi arrivals, and scrapes IMD rainfall context.

Filesystem workspace: ``MARKET_INTEL_DATA_DIR`` (default: cwd).

Alternatively set ``COMMODITY_USE_SUPABASE_ARTIFACTS=true``—inputs are fetched from bucket
``BUCKET_NAME`` under ``COMMODITY_SUPABASE_PREFIX`` (see ``workspace_storage.py``).
"""


from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import warnings
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

warnings.filterwarnings("ignore")

_INTEL_CACHE: dict[str, dict[str, Any]] = {}


def _data_dir() -> Path:
    raw = os.environ.get("MARKET_INTEL_DATA_DIR", ".")
    return Path(raw).expanduser().resolve()


def _load_price_levels(base_dir: Path) -> tuple[float, float, float, float]:
    path = base_dir / "price_forecast.json"
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing price_forecast.json under {base_dir}. "
            "Run the run_price_forecast tool first (it writes price_forecast.json "
            "to MARKET_INTEL_DATA_DIR), or add the file manually."
        )
    with open(path, encoding="utf-8") as f:
        pf = json.load(f)
    # Support plugin-style keys and forecaster-style aliases
    p0 = pf.get("current_price", pf.get("P0", pf.get("latest_price")))
    p50 = pf.get("P50", pf.get("forecast_price"))
    p10 = pf.get("P10")
    p90 = pf.get("P90")
    if p0 is None or p50 is None:
        raise ValueError(
            "price_forecast.json must include current_price/P0/latest_price and P50/forecast_price"
        )
    if p10 is None or p90 is None:
        fp = float(p50)
        p10 = fp * 0.85 if p10 is None else float(p10)
        p90 = fp * 1.15 if p90 is None else float(p90)
    return float(p0), float(p10), float(p50), float(p90)


def compute_market_intel(
    base_dir: Path,
    commodity: str,
    origin: str,
    horizon_days: int,
) -> tuple[dict[str, Any], str]:
    """Load inputs from base_dir, write market_intel.json / summary files, return payload + markdown."""
    today = date.today()
    current_month = today.month

    P0, P10, P50, P90 = _load_price_levels(base_dir)

    cal_path = base_dir / "seasonal_calendar.json"
    with open(cal_path, encoding="utf-8") as f:
        cal = json.load(f)

    active_season = None
    for s in cal["seasons"]:
        if current_month in s["months"]:
            active_season = s
            break

    if active_season is None:
        active_season = {
            "name": "Unknown",
            "historical_price_direction": "FLAT",
            "price_drift_magnitude": 0.0,
            "procurement_advice": "No seasonal data for this month.",
            "weeks_to_next_transition": 0,
        }

    season_direction = active_season["historical_price_direction"]
    season_magnitude = float(active_season.get("price_drift_magnitude", 0.0))
    season_bias = season_magnitude * (
        1 if season_direction == "UP" else -1 if season_direction == "DOWN" else 0
    )

    ndvi_value = None
    ndvi_signal = "UNKNOWN"
    ndvi_bias = 0.0
    ndvi_healthy = cal.get("ndvi_thresholds", {}).get("healthy", 0.60)
    ndvi_stress = cal.get("ndvi_thresholds", {}).get("stress", 0.40)

    ndvi_path = base_dir / "ndvi_latest.json"
    try:
        with open(ndvi_path, encoding="utf-8") as f:
            nd = json.load(f)
        ndvi_value = float(nd.get("ndvi", nd.get("value", 0.55)))
    except FileNotFoundError:
        ndvi_value = 0.55

    if ndvi_value < ndvi_stress:
        ndvi_signal = "STRESS"
        ndvi_bias = 0.15
    elif ndvi_value < ndvi_healthy:
        ndvi_signal = "MODERATE"
        ndvi_bias = 0.04
    else:
        ndvi_signal = "HEALTHY"
        ndvi_bias = -0.05

    arrivals_bias = 0.0
    arrivals_signal = "UNKNOWN"
    arrivals_value = None

    arrivals_path = base_dir / "mandi_arrivals.csv"
    try:
        arr = pd.read_csv(arrivals_path, parse_dates=["arrival_date"])
        arr = arr.sort_values("arrival_date")
        if len(arr) >= 4:
            recent_4w = arr["arrivals_quintals"].tail(4).mean()
            prior_4w = (
                arr["arrivals_quintals"].iloc[-8:-4].mean()
                if len(arr) >= 8
                else recent_4w
            )
            arrivals_value = float(recent_4w)
            ratio = recent_4w / prior_4w if prior_4w > 0 else 1.0
            if ratio < 0.80:
                arrivals_signal = "FALLING"
                arrivals_bias = 0.10
            elif ratio < 0.95:
                arrivals_signal = "SLIGHTLY_FALLING"
                arrivals_bias = 0.04
            elif ratio > 1.20:
                arrivals_signal = "SURGING"
                arrivals_bias = -0.12
            elif ratio > 1.05:
                arrivals_signal = "RISING"
                arrivals_bias = -0.05
            else:
                arrivals_signal = "STABLE"
                arrivals_bias = 0.0
    except FileNotFoundError:
        arrivals_signal = "NO_DATA"
        arrivals_bias = 0.0

    rainfall_signal = "NEUTRAL"
    rainfall_bias = 0.0
    rainfall_raw_label = "unavailable"
    imd_url = "https://mausam.imd.gov.in/responsive/rainfallinformation.php"

    try:
        import requests
        from bs4 import BeautifulSoup

        resp = requests.get(
            imd_url,
            timeout=12,
            headers={"User-Agent": "Mozilla/5.0 (research bot)"},
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        ap_pattern = re.compile(r"andhra\s*pradesh|A\.?P\.?", re.IGNORECASE)
        rainfall_found = False

        for tag in soup.find_all(string=ap_pattern):
            parent = tag.find_parent()
            if parent is None:
                continue
            region_block = parent.find_parent(["table", "div", "section"])
            if region_block is None:
                continue
            block_text = region_block.get_text(" ", strip=True).lower()
            for lbl in ["below normal", "normal", "above normal", "excess", "deficient"]:
                if lbl in block_text:
                    rainfall_raw_label = lbl
                    rainfall_found = True
                    break
            if rainfall_found:
                break

        if not rainfall_found:
            page_text = soup.get_text(" ", strip=True).lower()
            for lbl in ["excess", "above normal", "normal", "below normal", "deficient"]:
                if lbl in page_text:
                    rainfall_raw_label = lbl
                    break

        label_map = {
            "excess": ("EXCESS", -0.08),
            "above normal": ("ABOVE_NORMAL", -0.04),
            "normal": ("NORMAL", 0.00),
            "slightly below": ("SLIGHTLY_BELOW", 0.03),
            "below normal": ("BELOW_NORMAL", 0.06),
            "deficient": ("BELOW_NORMAL", 0.06),
        }
        for key, (sig, bias) in label_map.items():
            if key in rainfall_raw_label:
                rainfall_signal = sig
                rainfall_bias = bias
                break

    except Exception as e:  # noqa: BLE001 — scrape/network resilience
        rainfall_signal = "NEUTRAL"
        rainfall_bias = 0.0
        rainfall_raw_label = f"scrape_failed: {e}"

    weights = {"ndvi": 0.35, "arrivals": 0.30, "season": 0.25, "rainfall": 0.10}

    aggregate_price_drift_adjustment = (
        weights["ndvi"] * ndvi_bias
        + weights["arrivals"] * arrivals_bias
        + weights["season"] * season_bias
        + weights["rainfall"] * rainfall_bias
    )

    output: dict[str, Any] = {
        "meta": {
            "commodity": commodity,
            "origin": origin,
            "horizon_days": horizon_days,
            "data_dir": str(base_dir),
        },
        "generated_date": today.isoformat(),
        "current_price": P0,
        "price_forecast": {"P10": P10, "P50": P50, "P90": P90},
        "signals": {
            "ndvi": {
                "value": ndvi_value,
                "signal": ndvi_signal,
                "bias": round(ndvi_bias, 4),
                "weight": weights["ndvi"],
            },
            "arrivals": {
                "value_quintals_4w_avg": arrivals_value,
                "signal": arrivals_signal,
                "bias": round(arrivals_bias, 4),
                "weight": weights["arrivals"],
            },
            "season": {
                "name": active_season["name"],
                "direction": season_direction,
                "magnitude": season_magnitude,
                "bias": round(season_bias, 4),
                "weight": weights["season"],
                "weeks_to_transition": active_season.get("weeks_to_next_transition", 0),
                "procurement_advice": active_season.get("procurement_advice", ""),
            },
            "rainfall": {
                "imd_label": rainfall_raw_label,
                "signal": rainfall_signal,
                "bias": round(rainfall_bias, 4),
                "weight": weights["rainfall"],
            },
        },
        "aggregate_price_drift_adjustment": round(aggregate_price_drift_adjustment, 4),
        "risk_events": [
            e
            for e in cal.get("major_risk_events", [])
            if current_month in e.get("months", [])
        ],
    }

    intel_json = base_dir / "market_intel.json"
    with open(intel_json, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    def rag(b: float) -> str:
        if b > 0.07:
            return "HIGH_UP"
        if b > 0.02:
            return "UP"
        if b < -0.02:
            return "DOWN"
        return "NEUTRAL"

    summary_lines = [
        f"# Market Intelligence Summary",
        f"**Generated:** {today.isoformat()}",
        f"**Commodity:** {commodity} — {origin}",
        f"**Horizon (days):** {horizon_days}",
        "",
        "---",
        "",
        "## Price Context",
        "| Metric | Value |",
        "|---|---|",
        f"| Current market price | Rs.{P0:,.0f}/quintal |",
        f"| P50 forecast | Rs.{P50:,.0f}/quintal |",
        f"| Forecast range (P10-P90) | Rs.{P10:,.0f} - Rs.{P90:,.0f}/quintal |",
        "",
        "---",
        "",
        "## Market Signals",
        "",
        "| Signal | Status | Bias | Weight |",
        "|---|---|---|---|",
        f"| NDVI (crop health) | {rag(ndvi_bias)} {ndvi_signal} (NDVI={ndvi_value:.2f}) | {ndvi_bias:+.3f} | 35% |",
        f"| Mandi arrivals | {rag(arrivals_bias)} {arrivals_signal} | {arrivals_bias:+.3f} | 30% |",
        f"| Season | {rag(season_bias)} {active_season['name']} ({season_direction}) | {season_bias:+.3f} | 25% |",
        f"| Rainfall (IMD) | {rag(rainfall_bias)} {rainfall_signal} | {rainfall_bias:+.3f} | 10% |",
        "",
        f"**Aggregate drift adjustment:** {aggregate_price_drift_adjustment:+.4f}",
        "",
        "---",
        "",
        "## Seasonal Context",
        f"**Season:** {active_season['name']}",
        f"**Advice:** {active_season.get('procurement_advice', '-')}",
        f"**Weeks to next transition:** {active_season.get('weeks_to_next_transition', '-')}",
        "",
        "---",
        "",
        "## Active Risk Events",
        "",
    ]

    risk_events = [
        e
        for e in cal.get("major_risk_events", [])
        if current_month in e.get("months", [])
    ]
    if risk_events:
        for e in risk_events:
            summary_lines.append(f"- **{e['event']}**: {e['impact']}")
    else:
        summary_lines.append("_No major risk events flagged for this month._")

    summary_lines.extend(
        [
            "",
            "---",
            "",
            "## Simulation pass-through",
            f"- aggregate_price_drift_adjustment = {aggregate_price_drift_adjustment:+.4f}",
            f"- ndvi_signal = {ndvi_signal}",
            f"- season_direction = {season_direction}",
            f"- rainfall_signal = {rainfall_signal}",
            "",
        ]
    )

    summary_md = "\n".join(summary_lines)
    summary_path = base_dir / "market_intel_summary.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary_md)

    return output, summary_md


def run_market_intel_impl(
    commodity: str = "Tomato",
    origin: str = "Madanapalli APMC",
    horizon_days: int = 45,
) -> dict[str, Any]:
    """Compute market intelligence; returns intel_id and full payload."""
    from workspace_storage import artifacts_enabled, materialize_workspace_dir

    tmp_workspace: Path | None = None
    if artifacts_enabled():
        tmp_workspace = materialize_workspace_dir()
        base_dir = tmp_workspace
    else:
        base_dir = _data_dir()

    try:
        payload, summary_md = compute_market_intel(base_dir, commodity, origin, horizon_days)
    finally:
        if tmp_workspace is not None and tmp_workspace.is_dir():
            shutil.rmtree(tmp_workspace, ignore_errors=True)

    intel_id = secrets.token_hex(16)
    _INTEL_CACHE[intel_id] = {"payload": payload, "summary_md": summary_md}
    return {"intel_id": intel_id, "market_intel": payload}


def get_market_intel_summary_impl(intel_id: str) -> str:
    """Markdown summary for a prior run (same server process)."""
    row = _INTEL_CACHE.get(intel_id)
    if not row:
        return (
            f"No market intelligence cached for id {intel_id!r}. "
            "Run run_market_intel first in this session."
        )
    return str(row["summary_md"])
