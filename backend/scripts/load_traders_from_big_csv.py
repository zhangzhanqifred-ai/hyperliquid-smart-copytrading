import pandas as pd
import requests
import sys
from pathlib import Path

# --- Configuration ---
# CSV File Name (in backend/ directory)
CSV_FILENAME = "traders-2025年12月2日 23_32_47.csv"
CSV_PATH = Path(__file__).resolve().parent.parent / CSV_FILENAME

# Backend API Configuration
BACKEND_URL = "http://127.0.0.1:8000"

# Column Names Mapping (Based on inspection of traders-2025年12月2日 23_32_47.csv)
ADDRESS_COL = "Trader Address"
# We will use "PNL (All time)" as the total PnL for filtering
PNL_COL = "PNL (All time)"
# Optional columns for further filtering if available
VOLUME_COL = "Trading Volume (All time)" 
# Note: 'trade_count' does not seem to exist in the first few lines, setting to None for now.
# If needed, we can check headers dynamically.
TRADES_COL = None 

# Filtering Parameters
MIN_PNL = 0.0
MIN_VOLUME = 0.0 # Set to > 0 if you want to filter by volume
MIN_TRADES = 0   # Set to > 0 if TRADES_COL is available

# Max addresses to sync
MAX_ADDRESSES = 1000
BATCH_SIZE = 50
WINDOW_DAYS = 30


def load_filtered_addresses() -> list[str]:
    """
    Reads the CSV, applies filters (valid address, PnL > 0, etc.),
    deduplicates, sorts by PnL, and returns the top N addresses.
    """
    if not CSV_PATH.exists():
        print(f"[Error] CSV file not found at: {CSV_PATH}")
        print(f"Please ensure '{CSV_FILENAME}' is placed in the backend root directory.")
        sys.exit(1)

    print(f"Loading traders from {CSV_PATH}...")
    try:
        # 尝试多种常见编码，适配 Windows/中文 Excel 导出的 CSV
        encodings_to_try = ["utf-8", "utf-8-sig", "gbk", "gb18030", "latin1"]
        last_err = None
        df = None

        for enc in encodings_to_try:
            try:
                df = pd.read_csv(CSV_PATH, encoding=enc)
                print(f"[Info] Loaded CSV with encoding = {enc}")
                break
            except UnicodeDecodeError as e:
                print(f"[Warn] Failed to read with encoding={enc}: {e}")
                last_err = e
        else:
            # 所有编码都失败，抛出最后一个错误
            if last_err:
                raise last_err
            else:
                raise ValueError("Failed to read CSV with any supported encoding.")

        print(f"Total rows in CSV: {len(df)}")

        # 1. Check Required Columns
        if ADDRESS_COL not in df.columns:
            print(f"[Error] Address column '{ADDRESS_COL}' not found in CSV.")
            print(f"Available columns: {df.columns.tolist()}")
            sys.exit(1)
        
        if PNL_COL not in df.columns:
            print(f"[Error] PnL column '{PNL_COL}' not found in CSV.")
            print(f"Available columns: {df.columns.tolist()}")
            sys.exit(1)

        # 2. Basic Cleaning
        # Convert Address to string
        df[ADDRESS_COL] = df[ADDRESS_COL].astype(str)
        
        # Filter out 'Other' / aggregated rows
        lower_addr = df[ADDRESS_COL].str.lower()
        is_other_like = lower_addr.isin(["other", "others", "other users", "aggregated"])
        is_empty = lower_addr.str.strip().eq("")
        # Also filter out potential "nan" strings if pandas read empty cells as NaN
        is_nan_str = lower_addr == "nan"
        
        df = df[~(is_other_like | is_empty | is_nan_str)]
        print(f"Rows after filtering invalid addresses: {len(df)}")

        # 3. PnL Filtering
        # Convert PnL to numeric, forcing errors to NaN then 0
        df[PNL_COL] = pd.to_numeric(df[PNL_COL], errors="coerce").fillna(0.0)
        
        # Keep only positive PnL
        df = df[df[PNL_COL] > MIN_PNL]
        print(f"Rows after PnL > {MIN_PNL}: {len(df)}")

        # 4. Optional Volume Filtering
        if VOLUME_COL and VOLUME_COL in df.columns:
            df[VOLUME_COL] = pd.to_numeric(df[VOLUME_COL], errors="coerce").fillna(0.0)
            if MIN_VOLUME > 0:
                df = df[df[VOLUME_COL] >= MIN_VOLUME]
                print(f"Rows after Volume >= {MIN_VOLUME}: {len(df)}")

        # 5. Optional Trades Count Filtering
        if TRADES_COL and TRADES_COL in df.columns:
            df[TRADES_COL] = pd.to_numeric(df[TRADES_COL], errors="coerce").fillna(0.0)
            if MIN_TRADES > 0:
                df = df[df[TRADES_COL] >= MIN_TRADES]
                print(f"Rows after Trades >= {MIN_TRADES}: {len(df)}")

        # 6. Deduplication and Sorting
        df = df.drop_duplicates(subset=[ADDRESS_COL])
        print(f"Rows after deduplication: {len(df)}")

        # Sort by PnL descending (highest profit first)
        df = df.sort_values(PNL_COL, ascending=False)

        # 7. Select Top N
        top_n = min(len(df), MAX_ADDRESSES)
        addresses = df[ADDRESS_COL].head(top_n).tolist()

        print(f"\nSelected top {top_n} addresses.")
        if addresses:
            print(f"Sample addresses (top 5): {addresses[:5]}")

        return addresses

    except Exception as e:
        print(f"[Error] Failed to process CSV file: {e}")
        # Print traceback for easier debugging
        import traceback
        traceback.print_exc()
        sys.exit(1)


def sync_traders(addresses: list[str]) -> None:
    """
    Batches addresses and calls the backend sync API.
    """
    total = len(addresses)
    if total == 0:
        print("No addresses to sync, aborting.")
        return

    print(f"\nStarting sync for {total} addresses in batches of {BATCH_SIZE} ...")
    print(f"Target Backend: {BACKEND_URL}/hyperliquid/sync-traders")

    for i in range(0, total, BATCH_SIZE):
        batch = addresses[i : i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        
        payload = {
            "window_days": WINDOW_DAYS,
            "min_trades": 0,
            "limit": len(batch),
            "addresses": batch,
        }

        try:
            print(f"Sending batch {batch_num}/{total_batches} ({len(batch)} addrs) ... ", end="", flush=True)
            resp = requests.post(
                f"{BACKEND_URL}/hyperliquid/sync-traders",
                json=payload,
                timeout=120, # Long timeout for batch sync
            )
            
            try:
                body = resp.json()
            except Exception:
                body = resp.text[:200] + "..." # Truncate if not JSON

            if resp.status_code == 200:
                print(f"OK. Stats: {body}")
            else:
                print(f"FAILED. Status: {resp.status_code} Body: {body}")

        except requests.exceptions.ConnectionError:
            print(f"\n[Error] Could not connect to backend at {BACKEND_URL}. Is the server running?")
            return
        except Exception as e:
            print(f"\n[Error] Request failed for batch {i}..{i+len(batch)}: {e}")


def main():
    addresses = load_filtered_addresses()
    sync_traders(addresses)


if __name__ == "__main__":
    main()

