# """
# forecaster.py
# -------------
# ACTION ITEM 2: Price forecasting model that reads input files
#                directly from Supabase S3 storage.

# HOW TO USE:
# -----------
# 1. pip install supabase pandas openpyxl xgboost prophet numpy
# 2. Fill in your SUPABASE_URL and SUPABASE_KEY below
# 3. Run: python forecaster.py
#    OR  import and call run_forecast() from server.py
# """

# import io
# import os
# import numpy as np
# import pandas as pd
# from supabase import create_client, Client
# from dotenv import load_dotenv
# load_dotenv()
# os.environ["PYTHONIOENCODING"] = "utf-8"

# # --------------------------------------------------
# # PASTE YOUR SUPABASE CREDENTIALS HERE
# # --------------------------------------------------
# SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
# SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
 
# BUCKET_NAME = "Forecasting"

# # --------------------------------------------------
# # HELPER: Download file from Supabase into memory
# # --------------------------------------------------
# def download_file(supabase: Client, filename: str) -> bytes:
#     """Download a file from Supabase storage bucket into memory."""
#     print(f"  Downloading from Supabase: {filename}")
#     response = supabase.storage.from_(BUCKET_NAME).download(filename)
#     return response  # returns raw bytes


# # --------------------------------------------------
# # STEP 1: LOAD PRICE DATA (XLSX) FROM SUPABASE
# # --------------------------------------------------
# def load_price_data(supabase: Client) -> pd.DataFrame:
#     files = {
#         "2023": "Daily Price Report-01-01-2023 to 31-12-2023 for Andhra Pradesh.xlsx",
#         "2024": "Daily Price Report-01-01-2024 to 31-12-2024 for Andhra Pradesh.xlsx",
#         "2025": "Daily Price Report-01-01-2025 to 31-12-2025 for Andhra Pradesh.xlsx",
#     }

#     all_years_df = []

#     for year, filename in files.items():
#         raw_bytes = download_file(supabase, filename)
#         df = pd.read_excel(io.BytesIO(raw_bytes), header=1)

#         # Clean columns
#         df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
#         df.columns = (
#             df.columns.str.strip().str.lower().str.replace(" ", "_")
#         )

#         # Validate required columns
#         required_cols = {
#             "state", "district", "market", "commodity",
#             "variety", "min_price", "max_price", "modal_price", "price_date"
#         }
#         missing = required_cols - set(df.columns)
#         if missing:
#             raise ValueError(f"{year} price file missing columns: {missing}")

#         # Type conversion
#         df["price_date"] = pd.to_datetime(df["price_date"], errors="coerce", dayfirst=True)
#         for col in ["min_price", "max_price", "modal_price"]:
#             df[col] = df[col].astype(str).str.replace(",", "").astype(float)

#         df["data_year"] = year
#         all_years_df.append(df)

#     df_all = pd.concat(all_years_df, ignore_index=True)
#     df_all = df_all.sort_values("price_date").reset_index(drop=True)
#     print(f"Price data loaded: {df_all.shape}")
#     return df_all


# # --------------------------------------------------
# # STEP 2: LOAD ARRIVAL DATA (CSV) FROM SUPABASE
# # --------------------------------------------------
# def load_arrival_data(supabase: Client) -> pd.DataFrame:
#     import re

#     files = {
#         "2023": "Daily Arrival Report-01-01-2023 to 31-12-2023 for Andhra Pradesh.csv",
#         "2024": "Daily Arrival Report-01-01-2024 to 31-12-2024 for Andhra Pradesh.csv",
#         "2025": "Daily Arrival Report-01-01-2025 to 31-12-2025 for Andhra Pradesh.csv",
#     }

#     arrival_years = []

#     for year, filename in files.items():
#         raw_bytes = download_file(supabase, filename)
#         df_arr = pd.read_csv(io.BytesIO(raw_bytes), header=1)

#         # Clean columns
#         df_arr = df_arr.loc[:, ~df_arr.columns.str.contains("^Unnamed", na=False)]
#         df_arr.columns = (
#             df_arr.columns.astype(str).str.strip().str.lower().str.replace(" ", "_")
#         )

#         # Normalize arrival column
#         if "arrival_quantity" in df_arr.columns:
#             df_arr = df_arr.rename(columns={"arrival_quantity": "arrival"})
#         elif "arrival" not in df_arr.columns:
#             raise ValueError(f"{year}: Arrival column not found")

#         # Detect date column
#         date_col = None
#         date_pattern = re.compile(r"\d{2}-\d{2}-\d{4}")
#         for col in df_arr.columns:
#             sample = df_arr[col].astype(str).dropna().head(5)
#             if len(sample) > 0 and sample.apply(lambda x: bool(date_pattern.fullmatch(x))).all():
#                 date_col = col
#                 break

#         if date_col is None:
#             raise ValueError(f"{year}: No valid date column detected")

#         df_arr = df_arr.rename(columns={date_col: "date"})

#         # Validate columns
#         required_cols = {"state", "district", "market", "commodity", "arrival", "date"}
#         missing = required_cols - set(df_arr.columns)
#         if missing:
#             raise ValueError(f"{year} arrival file missing columns: {missing}")

#         # Type conversion
#         df_arr["date"] = pd.to_datetime(df_arr["date"], dayfirst=True, errors="coerce")
#         df_arr["arrival"] = df_arr["arrival"].astype(str).str.replace(",", "").astype(float)
#         df_arr["data_year"] = year
#         arrival_years.append(df_arr)

#     df_all_arrival = (
#         pd.concat(arrival_years, ignore_index=True)
#         .sort_values("date")
#         .reset_index(drop=True)
#     )
#     print(f"Arrival data loaded: {df_all_arrival.shape}")
#     return df_all_arrival


# # --------------------------------------------------
# # STEP 3: LOAD NDVI DATA (CSV) FROM SUPABASE
# # --------------------------------------------------
# def load_ndvi_data(supabase: Client) -> pd.DataFrame:
#     raw_bytes = download_file(supabase, "andhra_pradesh_ndvi_2023_2025.csv")
#     df_ndvi = pd.read_csv(io.BytesIO(raw_bytes))
#     df_ndvi["date"] = pd.to_datetime(df_ndvi["date"])
#     print(f"NDVI data loaded: {df_ndvi.shape}")
#     return df_ndvi


# # --------------------------------------------------
# # STEP 4: FILTER TO POC SCOPE
# # --------------------------------------------------
# def filter_poc(df_all: pd.DataFrame, df_all_arrival: pd.DataFrame):
#     # Price filter
#     df_poc = df_all[
#         (df_all["state"] == "Andhra Pradesh") &
#         (df_all["district"] == "Chittor") &
#         (df_all["market"] == "Madanapalli APMC") &
#         (df_all["commodity"].str.lower() == "tomato") &
#         (df_all["variety"] == "Local")
#     ].copy()

#     df_poc = (
#         df_poc.sort_values("price_date")
#         .drop_duplicates(subset=["price_date"])
#         .reset_index(drop=True)
#     )

#     df_poc = df_poc[["price_date", "min_price", "max_price", "modal_price"]]
#     df_poc = df_poc.rename(columns={"price_date": "date"})

#     # Arrival filter
#     df_arrival_poc = df_all_arrival[
#         (df_all_arrival["state"] == "Andhra Pradesh") &
#         (df_all_arrival["district"] == "Chittor") &
#         (df_all_arrival["market"] == "Madanapalli APMC") &
#         (df_all_arrival["commodity"].str.lower() == "tomato")
#     ][["date", "arrival"]].copy()

#     df_arrival_poc = df_arrival_poc.sort_values("date").reset_index(drop=True)

#     print(f"POC price rows: {len(df_poc)}, arrival rows: {len(df_arrival_poc)}")
#     return df_poc, df_arrival_poc


# # --------------------------------------------------
# # STEP 5: MERGE + FEATURE ENGINEERING
# # --------------------------------------------------
# def build_features(df_poc, df_arrival_poc, df_ndvi):
#     # Merge price + arrival
#     df_merged = df_poc.merge(df_arrival_poc, on="date", how="left")
#     df_merged["arrival"] = df_merged["arrival"].ffill(limit=2)

#     # Monthly NDVI
#     df_ndvi["year"] = df_ndvi["date"].dt.year
#     df_ndvi["month"] = df_ndvi["date"].dt.month
#     df_ndvi_monthly = (
#         df_ndvi.groupby(["year", "month"], as_index=False)
#         .agg(mean_ndvi=("mean_ndvi", "mean"))
#     )

#     df_merged["year"] = df_merged["date"].dt.year
#     df_merged["month"] = df_merged["date"].dt.month
#     df_merged = df_merged.merge(df_ndvi_monthly, on=["year", "month"], how="left")

#     # Feature engineering
#     df_feat = df_merged.copy().sort_values("date").reset_index(drop=True)

#     df_feat["price_lag_1"]  = df_feat["modal_price"].shift(1)
#     df_feat["price_lag_7"]  = df_feat["modal_price"].shift(7)
#     df_feat["price_lag_30"] = df_feat["modal_price"].shift(30)
#     df_feat["price_change_1d"] = df_feat["modal_price"] - df_feat["modal_price"].shift(1)
#     df_feat["price_change_7d"] = df_feat["modal_price"] - df_feat["modal_price"].shift(7)
#     df_feat["price_pct_change_7d"] = df_feat["price_change_7d"] / df_feat["modal_price"].shift(7)
#     df_feat["price_acceleration"] = df_feat["price_change_1d"] - df_feat["price_change_7d"] / 7
#     df_feat["price_std_7"]  = df_feat["modal_price"].rolling(7).std()
#     df_feat["price_std_30"] = df_feat["modal_price"].rolling(30).std()
#     df_feat["volatility_ratio"] = df_feat["price_std_7"] / df_feat["price_std_30"]
#     df_feat["arrival_lag_7"] = df_feat["arrival"].shift(7)
#     df_feat["arrival_pct_change_7d"] = (df_feat["arrival"] - df_feat["arrival"].shift(7)) / df_feat["arrival"].shift(7)
#     df_feat["price_arrival_ratio"] = df_feat["modal_price"] / df_feat["arrival"]
#     df_feat["ndvi_lag_1m"] = df_feat["mean_ndvi"].shift(30)
#     df_feat["ndvi_lag_2m"] = df_feat["mean_ndvi"].shift(60)
#     df_feat["ndvi_change_1m"] = df_feat["mean_ndvi"] - df_feat["ndvi_lag_1m"]
#     df_feat["month_sin"] = np.sin(2 * np.pi * df_feat["month"] / 12)
#     df_feat["month_cos"] = np.cos(2 * np.pi * df_feat["month"] / 12)

#     df_feat = df_feat.dropna().reset_index(drop=True)
#     print(f"Feature dataset shape: {df_feat.shape}")
#     return df_feat


# # --------------------------------------------------
# # STEP 6: TRAIN + FORECAST
# # --------------------------------------------------
# def train_and_forecast(df_feat: pd.DataFrame, forecast_days: int = 45) -> dict:
#     from xgboost import XGBRegressor
#     from prophet import Prophet

#     # Prepare supervised dataset
#     df_model = df_feat.copy().sort_values("date").reset_index(drop=True)
#     df_model["target_next_day"] = df_model["modal_price"].shift(-1)
#     df_model = df_model.dropna().reset_index(drop=True)

#     drop_cols = ["date", "modal_price", "month", "mean_ndvi", "target_next_day"]
#     X = df_model.drop(columns=drop_cols, errors="ignore")
#     y = df_model["target_next_day"]

#     # Train XGBoost
#     model_xgb = XGBRegressor(
#         n_estimators=500, learning_rate=0.05,
#         max_depth=5, subsample=0.8,
#         colsample_bytree=0.8, random_state=42
#     )
#     model_xgb.fit(X, y)

#     # Train Prophet
#     prophet_df = df_model[["date", "modal_price"]].rename(
#         columns={"date": "ds", "modal_price": "y"}
#     )
#     prophet_model = Prophet(
#         yearly_seasonality=True,
#         weekly_seasonality=False,
#         daily_seasonality=False
#     )
#     prophet_model.fit(prophet_df)
#     future = prophet_model.make_future_dataframe(periods=forecast_days)
#     prophet_forecast = prophet_model.predict(future)
#     prophet_future_preds = prophet_forecast.tail(forecast_days)["yhat"].values

#     # Recursive XGBoost 45-day forecast
#     history = df_feat.copy().sort_values("date").reset_index(drop=True)
#     xgb_future_preds = []

#     for step in range(forecast_days):
#         last_row = history.iloc[-1:].copy()
#         X_input = last_row.drop(
#             columns=["date", "modal_price", "month", "mean_ndvi"], errors="ignore"
#         )
#         next_price = model_xgb.predict(X_input)[0]
#         next_date = last_row["date"].values[0] + np.timedelta64(1, "D")

#         new_row = last_row.copy()
#         new_row["date"] = next_date
#         new_row["modal_price"] = next_price
#         history = pd.concat([history, new_row], ignore_index=True)

#         # Recalculate rolling features
#         history["price_lag_1"] = history["modal_price"].shift(1)
#         history["price_lag_7"] = history["modal_price"].shift(7)
#         history["price_lag_30"] = history["modal_price"].shift(30)
#         history["price_change_1d"] = history["modal_price"] - history["price_lag_1"]
#         history["price_change_7d"] = history["modal_price"] - history["price_lag_7"]
#         history["price_std_7"] = history["modal_price"].rolling(7).std()
#         history["price_std_30"] = history["modal_price"].rolling(30).std()
#         history["volatility_ratio"] = history["price_std_7"] / history["price_std_30"]

#         xgb_future_preds.append((next_date, float(next_price)))

#     # Ensemble (60% XGBoost + 40% Prophet)
#     ensemble_preds = [
#         0.6 * xgb_p + 0.4 * proph_p
#         for (_, xgb_p), proph_p in zip(xgb_future_preds, prophet_future_preds)
#     ]
#     forecast_dates = [str(d[0])[:10] for d in xgb_future_preds]

#     # Trust score
#     recent_vol = df_model["modal_price"].rolling(30).std().iloc[-1]
#     long_term_vol = df_model["modal_price"].rolling(180).std().mean()
#     vol_penalty = min(1.0, long_term_vol / recent_vol)
#     direction_acc = 0.785  # from walk-forward validation
#     trust_score = round((0.6 * direction_acc + 0.4 * vol_penalty) * 100, 2)

#     # Procurement decision
#     latest_price = float(df_model["modal_price"].iloc[-1])
#     forecast_price = float(ensemble_preds[-1])
#     price_up = forecast_price > latest_price

#     if trust_score >= 80:
#         decision = "LOCK-IN" if price_up else "SPOT BUY"
#     elif trust_score >= 60:
#         decision = "PARTIAL LOCK-IN" if price_up else "SPOT BUY"
#     else:
#         decision = "SPOT BUY"

#     return {
#         "latest_price": latest_price,
#         "forecast_price": round(forecast_price, 2),
#         "trust_score": trust_score,
#         "price_direction": "UP" if price_up else "DOWN",
#         "decision": decision,
#         "forecast_days": forecast_days,
#         "forecast_series": [
#             {"date": d, "predicted_modal_price": round(p, 2)}
#             for d, p in zip(forecast_dates, ensemble_preds)
#         ]
#     }


# # --------------------------------------------------
# # MAIN ENTRY POINT
# # --------------------------------------------------
# def run_forecast(forecast_days: int = 45) -> dict:
#     """
#     Full pipeline: load from Supabase → process → forecast → return result dict.
#     Called by server.py FastMCP tool.
#     """
#     print("Connecting to Supabase...")
#     supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

#     print("\n[1/5] Loading price data...")
#     df_all = load_price_data(supabase)

#     print("\n[2/5] Loading arrival data...")
#     df_all_arrival = load_arrival_data(supabase)

#     print("\n[3/5] Loading NDVI data...")
#     df_ndvi = load_ndvi_data(supabase)

#     print("\n[4/5] Filtering & engineering features...")
#     df_poc, df_arrival_poc = filter_poc(df_all, df_all_arrival)
#     df_feat = build_features(df_poc, df_arrival_poc, df_ndvi)

#     print("\n[5/5] Training models & generating forecast...")
#     result = train_and_forecast(df_feat, forecast_days=forecast_days)

#     print("\n FORECAST COMPLETE")
#     print(f"  Latest Price  : Rs.{result['latest_price']}")
#     print(f"  Forecast Price: Rs.{result['forecast_price']}")
#     print(f"  Trust Score   : {result['trust_score']}/100")
#     print(f"  Direction     : {result['price_direction']}")
#     print(f"  Decision      : {result['decision']}")

#     return result

    


# if __name__ == "__main__":
#     result = run_forecast()
#     print("\nFull result:")
#     import json
#     print(json.dumps(result, indent=2, default=str))
"""
forecaster.py
-------------
ACTION ITEM 2: Price forecasting model that reads input files
               directly from Supabase S3 storage.

HOW TO USE:
-----------
1. pip install supabase pandas openpyxl xgboost prophet numpy
2. Fill in your SUPABASE_URL and SUPABASE_KEY below
3. Run: python forecaster.py
   OR  import and call run_forecast() from server.py
"""

import io
import os
import sys
import logging

from dotenv import load_dotenv

load_dotenv()

# Fix encoding
os.environ["PYTHONIOENCODING"] = "utf-8"

# Suppress noisy logs
logging.getLogger("prophet").setLevel(logging.ERROR)
logging.getLogger("cmdstanpy").setLevel(logging.ERROR)
logging.getLogger("matplotlib").setLevel(logging.ERROR)
import numpy as np
import pandas as pd
from supabase import create_client, Client

# --------------------------------------------------
# CREDENTIALS — loaded from environment variables
# Set these in .env locally or in Render dashboard
# --------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
BUCKET_NAME = os.environ.get("BUCKET_NAME", "Forecasting")

# --------------------------------------------------
# HELPER: Download file from Supabase into memory
# --------------------------------------------------
def download_file(supabase: Client, filename: str) -> bytes:
    """Download a file from Supabase storage bucket into memory."""
    print(f"  Downloading from Supabase: {filename}")
    response = supabase.storage.from_(BUCKET_NAME).download(filename)
    return response  # returns raw bytes


def _without_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """XGBoost + pandas align break on duplicated column labels; normalize before fit/predict."""
    if df.columns.is_unique:
        return df
    dup_names = sorted(set(df.columns[df.columns.duplicated(keep=False)].tolist()))
    print(f"[forecaster] Dropping duplicated column labels: {dup_names}")
    return df.loc[:, ~df.columns.duplicated()].copy()


# --------------------------------------------------
# STEP 1: LOAD PRICE DATA (XLSX) FROM SUPABASE
# --------------------------------------------------
def load_price_data(supabase: Client) -> pd.DataFrame:
    files = {
        "2023": "Daily Price Report-01-01-2023 to 31-12-2023 for Andhra Pradesh.xlsx",
        "2024": "Daily Price Report-01-01-2024 to 31-12-2024 for Andhra Pradesh.xlsx",
        "2025": "Daily Price Report-01-01-2025 to 31-12-2025 for Andhra Pradesh.xlsx",
    }

    all_years_df = []

    for year, filename in files.items():
        raw_bytes = download_file(supabase, filename)
        df = pd.read_excel(io.BytesIO(raw_bytes), header=1)

        # Clean columns
        df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
        df.columns = (
            df.columns.str.strip().str.lower().str.replace(" ", "_")
        )
        df = _without_duplicate_columns(df)

        # Validate required columns
        required_cols = {
            "state", "district", "market", "commodity",
            "variety", "min_price", "max_price", "modal_price", "price_date"
        }
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"{year} price file missing columns: {missing}")

        # Type conversion
        df["price_date"] = pd.to_datetime(df["price_date"], errors="coerce", dayfirst=True)
        for col in ["min_price", "max_price", "modal_price"]:
            df[col] = df[col].astype(str).str.replace(",", "").astype(float)

        df["data_year"] = year
        all_years_df.append(df)

    df_all = pd.concat(all_years_df, ignore_index=True)
    df_all = _without_duplicate_columns(df_all)
    df_all = df_all.sort_values("price_date").reset_index(drop=True)
    print(f"Price data loaded: {df_all.shape}")
    return df_all


# --------------------------------------------------
# STEP 2: LOAD ARRIVAL DATA (CSV) FROM SUPABASE
# --------------------------------------------------
def load_arrival_data(supabase: Client) -> pd.DataFrame:
    import re

    files = {
        "2023": "Daily Arrival Report-01-01-2023 to 31-12-2023 for Andhra Pradesh.csv",
        "2024": "Daily Arrival Report-01-01-2024 to 31-12-2024 for Andhra Pradesh.csv",
        "2025": "Daily Arrival Report-01-01-2025 to 31-12-2025 for Andhra Pradesh.csv",
    }

    arrival_years = []

    for year, filename in files.items():
        raw_bytes = download_file(supabase, filename)
        df_arr = pd.read_csv(io.BytesIO(raw_bytes), header=1)

        # Clean columns
        df_arr = df_arr.loc[:, ~df_arr.columns.str.contains("^Unnamed", na=False)]
        df_arr.columns = (
            df_arr.columns.astype(str).str.strip().str.lower().str.replace(" ", "_")
        )

        # Normalize arrival column
        if "arrival_quantity" in df_arr.columns:
            df_arr = df_arr.rename(columns={"arrival_quantity": "arrival"})
        elif "arrival" not in df_arr.columns:
            raise ValueError(f"{year}: Arrival column not found")

        # Detect date column
        date_col = None
        date_pattern = re.compile(r"\d{2}-\d{2}-\d{4}")
        for col in df_arr.columns:
            sample = df_arr[col].astype(str).dropna().head(5)
            if len(sample) > 0 and sample.apply(lambda x: bool(date_pattern.fullmatch(x))).all():
                date_col = col
                break

        if date_col is None:
            raise ValueError(f"{year}: No valid date column detected")

        df_arr = df_arr.rename(columns={date_col: "date"})
        df_arr = _without_duplicate_columns(df_arr)

        # Validate columns
        required_cols = {"state", "district", "market", "commodity", "arrival", "date"}
        missing = required_cols - set(df_arr.columns)
        if missing:
            raise ValueError(f"{year} arrival file missing columns: {missing}")

        # Type conversion
        df_arr["date"] = pd.to_datetime(df_arr["date"], dayfirst=True, errors="coerce")
        df_arr["arrival"] = df_arr["arrival"].astype(str).str.replace(",", "").astype(float)
        df_arr["data_year"] = year
        arrival_years.append(df_arr)

    df_all_arrival = pd.concat(arrival_years, ignore_index=True)
    df_all_arrival = _without_duplicate_columns(df_all_arrival)
    df_all_arrival = df_all_arrival.sort_values("date").reset_index(drop=True)
    print(f"Arrival data loaded: {df_all_arrival.shape}")
    return df_all_arrival


# --------------------------------------------------
# STEP 3: LOAD NDVI DATA (CSV) FROM SUPABASE
# --------------------------------------------------
def load_ndvi_data(supabase: Client) -> pd.DataFrame:
    raw_bytes = download_file(supabase, "andhra_pradesh_ndvi_2023_2025.csv")
    df_ndvi = pd.read_csv(io.BytesIO(raw_bytes))
    df_ndvi = _without_duplicate_columns(df_ndvi)
    df_ndvi["date"] = pd.to_datetime(df_ndvi["date"])
    print(f"NDVI data loaded: {df_ndvi.shape}")
    return df_ndvi


# --------------------------------------------------
# STEP 4: FILTER TO POC SCOPE
# --------------------------------------------------
def filter_poc(df_all: pd.DataFrame, df_all_arrival: pd.DataFrame):
    df_poc = df_all[
        (df_all["state"] == "Andhra Pradesh") &
        (df_all["district"] == "Chittor") &
        (df_all["market"] == "Madanapalli APMC") &
        (df_all["commodity"].str.lower() == "tomato") &
        (df_all["variety"] == "Local")
    ].copy()

    df_poc = (
        df_poc.sort_values("price_date")
        .drop_duplicates(subset=["price_date"])
        .reset_index(drop=True)
    )

    df_poc = df_poc[["price_date", "min_price", "max_price", "modal_price"]]
    df_poc = df_poc.rename(columns={"price_date": "date"})

    df_arrival_poc = df_all_arrival[
        (df_all_arrival["state"] == "Andhra Pradesh") &
        (df_all_arrival["district"] == "Chittor") &
        (df_all_arrival["market"] == "Madanapalli APMC") &
        (df_all_arrival["commodity"].str.lower() == "tomato")
    ][["date", "arrival"]].copy()

    # Multiple arrival rows per date break merge-many-to-one and can trigger downstream
    # pandas alignment errors ("cannot reindex on an axis with duplicate labels").
    df_arrival_poc = (
        df_arrival_poc.groupby("date", as_index=False)["arrival"]
        .sum()
        .sort_values("date")
        .reset_index(drop=True)
    )

    print(f"POC price rows: {len(df_poc)}, arrival rows (1 per date): {len(df_arrival_poc)}")
    return df_poc, df_arrival_poc


# --------------------------------------------------
# STEP 5: MERGE + FEATURE ENGINEERING
# --------------------------------------------------
def build_features(df_poc, df_arrival_poc, df_ndvi):
    df_merged = df_poc.merge(df_arrival_poc, on="date", how="left")
    df_merged["arrival"] = df_merged["arrival"].ffill(limit=2)

    df_ndvi["year"] = df_ndvi["date"].dt.year
    df_ndvi["month"] = df_ndvi["date"].dt.month
    df_ndvi_monthly = (
        df_ndvi.groupby(["year", "month"], as_index=False)
        .agg(mean_ndvi=("mean_ndvi", "mean"))
        .drop_duplicates(subset=["year", "month"], keep="last")
    )

    df_merged["year"] = df_merged["date"].dt.year
    df_merged["month"] = df_merged["date"].dt.month
    df_merged = df_merged.merge(df_ndvi_monthly, on=["year", "month"], how="left")

    df_feat = df_merged.copy().sort_values("date").reset_index(drop=True)

    df_feat["price_lag_1"]  = df_feat["modal_price"].shift(1)
    df_feat["price_lag_7"]  = df_feat["modal_price"].shift(7)
    df_feat["price_lag_30"] = df_feat["modal_price"].shift(30)
    df_feat["price_change_1d"] = df_feat["modal_price"] - df_feat["modal_price"].shift(1)
    df_feat["price_change_7d"] = df_feat["modal_price"] - df_feat["modal_price"].shift(7)
    df_feat["price_pct_change_7d"] = df_feat["price_change_7d"] / df_feat["modal_price"].shift(7)
    df_feat["price_acceleration"] = df_feat["price_change_1d"] - df_feat["price_change_7d"] / 7
    df_feat["price_std_7"]  = df_feat["modal_price"].rolling(7).std()
    df_feat["price_std_30"] = df_feat["modal_price"].rolling(30).std()
    df_feat["volatility_ratio"] = df_feat["price_std_7"] / df_feat["price_std_30"]
    df_feat["arrival_lag_7"] = df_feat["arrival"].shift(7)
    df_feat["arrival_pct_change_7d"] = (df_feat["arrival"] - df_feat["arrival"].shift(7)) / df_feat["arrival"].shift(7)
    df_feat["price_arrival_ratio"] = df_feat["modal_price"] / df_feat["arrival"]
    df_feat["ndvi_lag_1m"] = df_feat["mean_ndvi"].shift(30)
    df_feat["ndvi_lag_2m"] = df_feat["mean_ndvi"].shift(60)
    df_feat["ndvi_change_1m"] = df_feat["mean_ndvi"] - df_feat["ndvi_lag_1m"]
    df_feat["month_sin"] = np.sin(2 * np.pi * df_feat["month"] / 12)
    df_feat["month_cos"] = np.cos(2 * np.pi * df_feat["month"] / 12)

    if df_feat["date"].duplicated().any():
        n_dup = int(df_feat["date"].duplicated().sum())
        print(f"[forecaster] Dedup feature rows with duplicate dates (n_extra={n_dup}), keep='last'.")
        df_feat = df_feat.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(
            drop=True
        )

    df_feat = _without_duplicate_columns(df_feat)

    df_feat = df_feat.dropna().reset_index(drop=True)
    print(f"Feature dataset shape: {df_feat.shape}")
    return df_feat


# --------------------------------------------------
# STEP 6: TRAIN + FORECAST
# --------------------------------------------------
def train_and_forecast(df_feat: pd.DataFrame, forecast_days: int = 45) -> dict:
    from xgboost import XGBRegressor
    from prophet import Prophet

    df_model = df_feat.copy().sort_values("date").reset_index(drop=True)
    df_model["target_next_day"] = df_model["modal_price"].shift(-1)
    df_model = df_model.dropna().reset_index(drop=True)
    df_model = _without_duplicate_columns(df_model)

    drop_cols = ["date", "modal_price", "month", "mean_ndvi", "target_next_day"]
    X_df = _without_duplicate_columns(df_model.drop(columns=drop_cols, errors="ignore"))
    feature_cols = list(X_df.columns)
    # pandas to_numeric accepts Series/array only — apply column-wise for DataFrame compatibility.
    X_num = X_df.apply(pd.to_numeric, errors="coerce").fillna(0.0)
    X_np = np.ascontiguousarray(X_num.to_numpy(dtype=np.float64, copy=False))

    y = df_model["target_next_day"]

    model_xgb = XGBRegressor(
        n_estimators=500, learning_rate=0.05,
        max_depth=5, subsample=0.8,
        colsample_bytree=0.8, random_state=42
    )
    # Pass NumPy arrays so sklearn / XGBoost never call pandas.align / reindex on duplicate labels.
    model_xgb.fit(X_np, y.to_numpy(dtype=np.float64, copy=False))

    prophet_df = (
        df_model[["date", "modal_price"]]
        .rename(columns={"date": "ds", "modal_price": "y"})
        .drop_duplicates(subset=["ds"], keep="last")
        .sort_values("ds")
        .reset_index(drop=True)
    )
    prophet_model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False
    )
    prophet_model.fit(prophet_df)
    future = prophet_model.make_future_dataframe(periods=forecast_days)
    prophet_forecast = prophet_model.predict(future)
    prophet_future_preds = prophet_forecast.tail(forecast_days)["yhat"].values

    history = _without_duplicate_columns(
        df_feat.copy().sort_values("date").reset_index(drop=True)
    )
    predict_drop = ["date", "modal_price", "month", "mean_ndvi"]
    xgb_future_preds = []

    for step in range(forecast_days):
        history = _without_duplicate_columns(history)
        tail = history.iloc[-1:, :].reset_index(drop=True)
        Xi = tail.drop(columns=predict_drop, errors="ignore")
        Xi = _without_duplicate_columns(Xi).reindex(columns=feature_cols, fill_value=0.0)
        Xi_num = Xi.apply(pd.to_numeric, errors="coerce").fillna(0.0)
        X_row = np.ascontiguousarray(
            Xi_num.to_numpy(dtype=np.float64, copy=False)
        )
        X_row = np.nan_to_num(X_row, nan=0.0, posinf=0.0, neginf=0.0)
        next_price = float(model_xgb.predict(X_row)[0])

        next_date = pd.Timestamp(tail["date"].iloc[0]) + pd.Timedelta(days=1)

        new_row = tail.copy()
        new_row["date"] = next_date
        new_row["modal_price"] = next_price
        history = _without_duplicate_columns(
            pd.concat([history, new_row], ignore_index=True)
        )

        history["price_lag_1"] = history["modal_price"].shift(1)
        history["price_lag_7"] = history["modal_price"].shift(7)
        history["price_lag_30"] = history["modal_price"].shift(30)
        history["price_change_1d"] = history["modal_price"] - history["price_lag_1"]
        history["price_change_7d"] = history["modal_price"] - history["price_lag_7"]
        history["price_std_7"] = history["modal_price"].rolling(7).std()
        history["price_std_30"] = history["modal_price"].rolling(30).std()
        history["volatility_ratio"] = history["price_std_7"] / history["price_std_30"]

        xgb_future_preds.append((next_date, float(next_price)))

    ensemble_preds = [
        0.6 * xgb_p + 0.4 * proph_p
        for (_, xgb_p), proph_p in zip(xgb_future_preds, prophet_future_preds)
    ]
    forecast_dates = [str(d[0])[:10] for d in xgb_future_preds]

    recent_vol = df_model["modal_price"].rolling(30).std().iloc[-1]
    long_term_vol = df_model["modal_price"].rolling(180).std().mean()
    vol_penalty = min(1.0, long_term_vol / recent_vol)
    direction_acc = 0.785
    trust_score = round((0.6 * direction_acc + 0.4 * vol_penalty) * 100, 2)

    latest_price = float(df_model["modal_price"].iloc[-1])
    forecast_price = float(ensemble_preds[-1])
    price_up = forecast_price > latest_price

    if trust_score >= 80:
        decision = "LOCK-IN" if price_up else "SPOT BUY"
    elif trust_score >= 60:
        decision = "PARTIAL LOCK-IN" if price_up else "SPOT BUY"
    else:
        decision = "SPOT BUY"

    return {
        "latest_price": latest_price,
        "forecast_price": round(forecast_price, 2),
        "trust_score": trust_score,
        "price_direction": "UP" if price_up else "DOWN",
        "decision": decision,
        "forecast_days": forecast_days,
        "forecast_series": [
            {"date": d, "predicted_modal_price": round(p, 2)}
            for d, p in zip(forecast_dates, ensemble_preds)
        ]
    }


# --------------------------------------------------
# MAIN ENTRY POINT
# --------------------------------------------------
def run_forecast(forecast_days: int = 45) -> dict:
    print("Connecting to Supabase...")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    print("\n[1/5] Loading price data...")
    df_all = load_price_data(supabase)

    print("\n[2/5] Loading arrival data...")
    df_all_arrival = load_arrival_data(supabase)

    print("\n[3/5] Loading NDVI data...")
    df_ndvi = load_ndvi_data(supabase)

    print("\n[4/5] Filtering & engineering features...")
    df_poc, df_arrival_poc = filter_poc(df_all, df_all_arrival)
    df_feat = build_features(df_poc, df_arrival_poc, df_ndvi)

    print("\n[5/5] Training models & generating forecast...")
    result = train_and_forecast(df_feat, forecast_days=forecast_days)

    print("\nFORECAST COMPLETE")
    print(f"  Latest Price  : Rs.{result['latest_price']}")
    print(f"  Forecast Price: Rs.{result['forecast_price']}")
    print(f"  Trust Score   : {result['trust_score']}")
    print(f"  Direction     : {result['price_direction']}")
    print(f"  Decision      : {result['decision']}")

    return result


if __name__ == "__main__":
    result = run_forecast()
    from forecast_artifacts import save_price_forecast_json

    out_path = save_price_forecast_json(result)
    print(f"\nWrote price_forecast.json → {out_path}")

    print("\nFull result:")
    import json

    print(json.dumps(result, indent=2, default=str))