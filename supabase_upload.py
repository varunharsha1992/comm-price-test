"""
supabase_upload.py
------------------
ACTION ITEM 1: Upload input files to Supabase S3 Storage.

HOW TO USE:
-----------
1. pip install supabase
2. Fill in your SUPABASE_URL and SUPABASE_KEY below
3. Place all your input files in the same folder as this script
4. Run: python supabase_upload.py
"""

import os
from supabase import create_client, Client

# --------------------------------------------------
# PASTE YOUR SUPABASE CREDENTIALS HERE
# --------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
 
BUCKET_NAME = "Forecasting"

# --------------------------------------------------
# FILES TO UPLOAD
# --------------------------------------------------
files_to_upload = [
    # Price Report Excel files
    "Daily Price Report-01-01-2023 to 31-12-2023 for Andhra Pradesh.xlsx",
    "Daily Price Report-01-01-2024 to 31-12-2024 for Andhra Pradesh.xlsx",
    "Daily Price Report-01-01-2025 to 31-12-2025 for Andhra Pradesh.xlsx",

    # Arrival Report CSV files
    "Daily Arrival Report-01-01-2023 to 31-12-2023 for Andhra Pradesh.csv",
    "Daily Arrival Report-01-01-2024 to 31-12-2024 for Andhra Pradesh.csv",
    "Daily Arrival Report-01-01-2025 to 31-12-2025 for Andhra Pradesh.csv",

    # NDVI data
    "andhra_pradesh_ndvi_2023_2025.csv",
]

# --------------------------------------------------
# UPLOAD FUNCTION
# --------------------------------------------------
def upload_files():
    print("Connecting to Supabase...")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

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
        else:
            content_type = "application/octet-stream"

        try:
            # Upload (upsert=True so re-running overwrites old files)
            supabase.storage.from_(BUCKET_NAME).upload(
                path=filename,
                file=file_bytes,
                file_options={
                    "content-type": content_type,
                    "upsert": "true"
                }
            )
            print(f"  ✅ Uploaded: {filename}")
        except Exception as e:
            print(f"  ❌ Failed: {filename} → {e}")

    print("\nAll uploads done!")


if __name__ == "__main__":
    upload_files()
