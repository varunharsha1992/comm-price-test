"""
supabase_upload.py
------------------
ACTION ITEM 1: Upload input files to Supabase S3 Storage.

HOW TO USE:
-----------
1. pip install supabase python-dotenv
2. SUPABASE_* and optionally COMMODITY_SUPABASE_PREFIX in .env

   Seasonal calendar on disk defaults to ./seasonal_calendar.json (cwd is where you run the script).

   Override the local path in .env, e.g.:
     SEASONAL_CALENDAR_LOCAL_PATH=data/seasonal_calendar.json

   Uploaded object key remains: {COMMODITY_SUPABASE_PREFIX}/seasonal_calendar.json

3. Run: python supabase_upload.py
"""

import os

from dotenv import load_dotenv

load_dotenv()

from supabase import create_client, Client

# --------------------------------------------------
# PASTE YOUR SUPABASE CREDENTIALS HERE
# --------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

BUCKET_NAME = os.environ.get("BUCKET_NAME", "Forecasting")


def _storage_object_key(local_filepath: str) -> str:
    """Map local file to bucket path. seasonal_calendar.json always uploads under COMMODITY_SUPABASE_PREFIX."""
    base = os.path.basename(local_filepath.replace("\\", "/"))
    prefix = os.environ.get("COMMODITY_SUPABASE_PREFIX", "workspace").strip().strip("/")
    if base == "seasonal_calendar.json":
        return f"{prefix}/{base}" if prefix else base
    return local_filepath.replace("\\", "/")


def _seasonal_calendar_local_path() -> str:
    raw = os.environ.get("SEASONAL_CALENDAR_LOCAL_PATH", "").strip()
    return raw if raw else "seasonal_calendar.json"

# --------------------------------------------------
# UPLOAD FUNCTION
# --------------------------------------------------
def upload_files():
    print("Connecting to Supabase...")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    files_to_upload = [_seasonal_calendar_local_path()]
    print(f"  Local seasonal file: {files_to_upload[0]}")

    # Create bucket if it doesn't exist
    try:
        supabase.storage.create_bucket(BUCKET_NAME, options={"public": False})
        print(f"Bucket '{BUCKET_NAME}' created.")
    except Exception as e:
        print(f"Bucket already exists or error: {e}")

    # Upload each file
    for filename in files_to_upload:
        if not os.path.exists(filename):
            print(f"  SKIPPED (not found locally): {filename}")
            continue

        print(f"  Uploading: {filename} ...")

        with open(filename, "rb") as f:
            file_bytes = f.read()

        # Determine content type
        if filename.endswith(".xlsx"):
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif filename.endswith(".csv"):
            content_type = "text/csv"
        elif filename.endswith(".json"):
            content_type = "application/json"
        else:
            content_type = "application/octet-stream"

        try:
            object_key = _storage_object_key(filename)
            # Upload (upsert=True so re-running overwrites old files)
            supabase.storage.from_(BUCKET_NAME).upload(
                path=object_key,
                file=file_bytes,
                file_options={
                    "content-type": content_type,
                    "upsert": "true"
                }
            )
            print(f"  Uploaded: {object_key}")
        except Exception as e:
            print(f"   Failed: {filename} → {e}")

    print("\nAll uploads done!")


if __name__ == "__main__":
    upload_files()
