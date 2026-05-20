# """
# server.py
# ---------
# ACTION ITEM 3: Deploy forecasting model as a FastMCP server.

# HOW TO RUN:
# -----------
# 1. pip install fastmcp supabase pandas openpyxl xgboost prophet numpy
# 2. Make sure forecaster.py is in the same folder
# 3. Run: python server.py
#    OR:  fastmcp run server.py

# CONNECT TO CLAUDE DESKTOP:
# ---------------------------
# Add this to your claude_desktop_config.json:

# {
#   "mcpServers": {
#     "unilever-forecasting": {
#       "command": "python",
#       "args": ["/full/path/to/server.py"]
#     }
#   }
# }
# """

# from fastmcp import FastMCP
# from forecaster import run_forecast

# # --------------------------------------------------
# # INITIALIZE FastMCP SERVER
# # --------------------------------------------------
# mcp = FastMCP(
#     name="Unilever Price Forecasting",
#     description=(
#         "Tomato price forecasting for Unilever procurement. "
#         "Reads from Supabase S3, runs XGBoost + Prophet ensemble, "
#         "returns 45-day forecast and procurement decision."
#     )
# )


# # --------------------------------------------------
# # TOOL 1: run_price_forecast
# # --------------------------------------------------
# @mcp.tool()
# def run_price_forecast(forecast_days: int = 45) -> dict:
#     """
#     Run the Unilever tomato price forecasting model.

#     Reads input data from Supabase S3 storage, trains an
#     XGBoost + Prophet ensemble model, and returns:
#     - 45-day price forecast series
#     - Procurement decision (LOCK-IN / PARTIAL LOCK-IN / SPOT BUY)
#     - Trust score (0-100)
#     - Price direction (UP / DOWN)

#     Parameters
#     ----------
#     forecast_days : int
#         Number of days to forecast ahead. Default is 45.

#     Returns
#     -------
#     dict with keys:
#         latest_price       : float  — most recent actual modal price (₹)
#         forecast_price     : float  — predicted price at end of horizon (₹)
#         trust_score        : float  — model confidence score (0–100)
#         price_direction    : str    — "UP" or "DOWN"
#         decision           : str    — "LOCK-IN", "PARTIAL LOCK-IN", or "SPOT BUY"
#         forecast_days      : int    — horizon used
#         forecast_series    : list   — day-by-day predictions [{"date": ..., "predicted_modal_price": ...}]
#     """
#     result = run_forecast(forecast_days=forecast_days)
#     return result


# # --------------------------------------------------
# # TOOL 2: get_forecast_summary
# # --------------------------------------------------
# @mcp.tool()
# def get_forecast_summary() -> str:
#     """
#     Get a plain-English procurement summary for the next 45 days.

#     Runs the full forecast pipeline and returns a human-readable
#     summary suitable for sharing with procurement managers.

#     Returns
#     -------
#     str : Formatted summary with decision, price outlook, and trust score.
#     """
#     result = run_forecast(forecast_days=45)

#     summary = f"""
# 📊 UNILEVER TOMATO PRICE FORECAST SUMMARY
# ==========================================
# 📍 Market     : Madanapalli APMC, Chittor, Andhra Pradesh
# 🌿 Commodity  : Tomato (Local Variety)
# 📅 Horizon    : {result['forecast_days']} days

# 💰 PRICE OUTLOOK
# -----------------
# Current Modal Price  : ₹{result['latest_price']} / Quintal
# Forecasted Price     : ₹{result['forecast_price']} / Quintal
# Expected Direction   : {result['price_direction']} {'📈' if result['price_direction'] == 'UP' else '📉'}

# 🎯 MODEL CONFIDENCE
# --------------------
# Trust Score : {result['trust_score']} / 100

# ✅ PROCUREMENT RECOMMENDATION
# ------------------------------
# →  {result['decision']}

# DECISION LOGIC:
#   - LOCK-IN      = Trust ≥ 80 & prices rising → secure supply now
#   - PARTIAL LOCK-IN = Trust 60–80 & prices rising → hedge partially
#   - SPOT BUY     = Low trust OR prices falling → buy on spot market
# ==========================================
# """
#     return summary.strip()


# # --------------------------------------------------
# # RUN SERVER
# # --------------------------------------------------
# if __name__ == "__main__":
#     import sys
#     print("Starting Unilever Price Forecasting MCP Server...", file=sys.stderr)
#     sys.stderr.flush()
    
#     # Force stdio transport explicitly
#     mcp.run(transport="stdio")
"""
server.py
---------
FastMCP server for Unilever Price Forecasting.
Deployed on Prefect Horizon (FastMCP Cloud).
"""

from dotenv import load_dotenv

load_dotenv()

from fastmcp import FastMCP
from forecast_artifacts import get_commodity_data_dir, save_price_forecast_json
from forecaster import run_forecast
from market_intel import get_market_intel_summary_impl, run_market_intel_impl
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Initialize FastMCP server (v3 syntax)
mcp = FastMCP("Unilever Price Forecasting")


@mcp.tool()
def run_price_forecast(forecast_days: int = 45) -> dict:
    """
    Run the Unilever tomato price forecasting model.
    Reads input data from Supabase S3 storage, trains an
    XGBoost + Prophet ensemble model, and returns a 45-day
    price forecast and procurement decision (LOCK-IN / SPOT BUY).

    Also writes ``price_forecast.json`` under ``MARKET_INTEL_DATA_DIR`` when local mode is used.
    With ``COMMODITY_USE_SUPABASE_ARTIFACTS=true``, also upserts ``workspace/price_forecast.json``
    (path prefix configurable via ``COMMODITY_SUPABASE_PREFIX``) in bucket ``BUCKET_NAME``.
    """
    result = run_forecast(forecast_days=forecast_days)
    artifact_path = save_price_forecast_json(result)
    out = dict(result)
    out["forecast_data_dir"] = str(get_commodity_data_dir())
    out["saved_price_forecast_json"] = str(artifact_path)
    return out


@mcp.tool()
def get_forecast_summary() -> str:
    """
    Get a plain-English procurement summary for the next 45 days.
    Returns a human-readable summary for procurement managers.

    Persists ``price_forecast.json`` (same directory as ``run_price_forecast``)
    under ``MARKET_INTEL_DATA_DIR`` for use by market intelligence.
    """
    result = run_forecast(forecast_days=45)
    save_price_forecast_json(result)

    summary = f"""
UNILEVER TOMATO PRICE FORECAST SUMMARY
=======================================
Market     : Madanapalli APMC, Chittor, Andhra Pradesh
Commodity  : Tomato (Local Variety)
Horizon    : {result['forecast_days']} days

PRICE OUTLOOK
--------------
Current Modal Price  : Rs.{result['latest_price']} / Quintal
Forecasted Price     : Rs.{result['forecast_price']} / Quintal
Expected Direction   : {result['price_direction']}

MODEL CONFIDENCE
-----------------
Trust Score : {result['trust_score']} / 100

PROCUREMENT RECOMMENDATION
---------------------------
{result['decision']}
=======================================
"""
    return summary.strip()


@mcp.tool()
def run_market_intel(
    commodity: str = "Tomato",
    origin: str = "Madanapalli APMC",
    horizon_days: int = 45,
) -> dict:
    """
    Build market intelligence from filesystem or Supabase workspace.

    Filesystem (default): ``MARKET_INTEL_DATA_DIR`` with ``seasonal_calendar.json``
    + ``price_forecast.json``. Call ``run_price_forecast`` first to emit the latter.

    Supabase: set ``COMMODITY_USE_SUPABASE_ARTIFACTS=true``. Objects live under bucket
    ``BUCKET_NAME`` at ``{COMMODITY_SUPABASE_PREFIX}/seasonal_calendar.json`` and
    ``.../price_forecast.json`` (upload calendar via ``supabase_upload.py`` + ``run_price_forecast``).
    """
    return run_market_intel_impl(
        commodity=commodity,
        origin=origin,
        horizon_days=horizon_days,
    )


@mcp.tool()
def get_market_intel_summary(intel_id: str) -> str:
    """
    Return the markdown summary for a prior run_market_intel call (same server process).
    """
    return get_market_intel_summary_impl(intel_id)


if __name__ == "__main__":
    mcp.run()