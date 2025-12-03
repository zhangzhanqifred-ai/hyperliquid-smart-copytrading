import requests
import pandas as pd
from pathlib import Path
import sys

# Configuration
BACKEND_URL = "http://127.0.0.1:8000"
# Assumes the script is run from the backend directory or backend/scripts
# We want to find "hyperliquid.xlsx" in the backend root directory
# Path(__file__) is backend/scripts/load_hyperliquid_addresses.py
# .parent is backend/scripts
# .parent.parent is backend
EXCEL_PATH = Path(__file__).resolve().parent.parent / "hyperliquid.xlsx"
MAX_ADDRESSES = 200
BATCH_SIZE = 50
WINDOW_DAYS = 30

def load_top_addresses() -> list[str]:
    """
    Loads addresses from the Excel file, filters out 'Other',
    aggregates Daily USD Volume, and returns the top N addresses.
    """
    if not EXCEL_PATH.exists():
        print(f"[Error] Excel file not found at: {EXCEL_PATH}")
        print("Please ensure 'hyperliquid.xlsx' is placed in the backend root directory.")
        sys.exit(1)

    print(f"Loading addresses from {EXCEL_PATH}...")
    try:
        df = pd.read_excel(EXCEL_PATH)
        
        # Check required columns
        required_columns = ["User", "Daily USD Volume"]
        if not all(col in df.columns for col in required_columns):
            print(f"[Error] Excel file must contain columns: {required_columns}")
            sys.exit(1)

        # Filter out 'Other' (case-insensitive)
        # Ensure 'User' column is string to avoid errors with non-string data
        df["User"] = df["User"].astype(str)
        df = df[df["User"].str.lower() != "other"]

        # Aggregate volume by User
        grouped = (
            df.groupby("User", as_index=False)["Daily USD Volume"]
            .sum()
            .sort_values("Daily USD Volume", ascending=False)
        )

        # Select top addresses
        top_addresses = grouped["User"].tolist()[:MAX_ADDRESSES]
        print(f"Found {len(grouped)} unique addresses. Selecting top {len(top_addresses)} by volume.")
        
        return top_addresses

    except Exception as e:
        print(f"[Error] Failed to process Excel file: {e}")
        sys.exit(1)

def sync_traders(addresses: list[str], window_days: int = 30):
    """
    Batches addresses and calls the backend sync API.
    """
    if not addresses:
        print("No addresses to sync.")
        return

    total_batches = (len(addresses) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"Starting sync for {len(addresses)} addresses in {total_batches} batches (Batch Size: {BATCH_SIZE})...")

    for i in range(0, len(addresses), BATCH_SIZE):
        batch = addresses[i : i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        
        payload = {
            "window_days": window_days,
            "min_trades": 0,
            "limit": len(batch),
            "addresses": batch,
        }

        try:
            print(f"Sending batch {batch_num}/{total_batches} ({len(batch)} addresses)...")
            resp = requests.post(
                f"{BACKEND_URL}/hyperliquid/sync-traders",
                json=payload,
                timeout=120 # Generous timeout for syncing multiple addresses
            )
            
            if resp.status_code == 200:
                print(f"  -> Success: {resp.json()}")
            else:
                print(f"  -> Failed: status={resp.status_code} body={resp.text}")
                
        except requests.exceptions.ConnectionError:
            print(f"[Error] Could not connect to backend at {BACKEND_URL}. Is the server running?")
            return
        except Exception as e:
            print(f"[Error] Request failed for batch {batch_num}: {e}")

def main():
    addresses = load_top_addresses()
    sync_traders(addresses, window_days=WINDOW_DAYS)
    print("Done.")

if __name__ == "__main__":
    main()

