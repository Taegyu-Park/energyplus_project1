"""
split_case2_ks_dataset.py
=========================
Splits 'data/case2_ks_bipv_tide_dataset.csv' into Train, Validation, and Test sets
using a seasonal block-wise split strategy (Monthly balanced):
- Train: Days 1 to 21 of each month (~69.0%)
- Validation: Days 22 to 25 of each month (~13.2%)
- Test: Days 26 to month-end of each month (~17.8%)

Ensures all four seasons (Spring, Summer, Fall, Winter) and extreme climate conditions
are evenly represented across Train, Val, and Test without time-series lookahead leakage within blocks.
"""

import os
import pandas as pd
from pathlib import Path

BASE_DIR = Path("C:/Users/taegyu/Codes/energyplus_project1")
DATA_DIR = BASE_DIR / "data"
SRC_CSV = DATA_DIR / "case2_ks_bipv_tide_dataset.csv"

TRAIN_CSV = DATA_DIR / "case2_ks_train.csv"
VAL_CSV   = DATA_DIR / "case2_ks_val.csv"
TEST_CSV  = DATA_DIR / "case2_ks_test.csv"


def main():
    print("=" * 70)
    print("Starting Seasonal Block-wise Dataset Split Pipeline")
    print("=" * 70)
    
    if not SRC_CSV.exists():
        raise FileNotFoundError(f"Source dataset missing: {SRC_CSV}")
        
    print(f"[*] Loading master dataset from: {SRC_CSV.name}...")
    df = pd.read_csv(SRC_CSV)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    total_rows = len(df)
    print(f"    -> Total rows: {total_rows:,} (Expected: 52,560)")
    
    # Extract day of month
    days = df['timestamp'].dt.day
    
    # Masks
    train_mask = (days >= 1) & (days <= 21)
    val_mask   = (days >= 22) & (days <= 25)
    test_mask  = (days >= 26)
    
    df_train = df[train_mask].copy()
    df_val   = df[val_mask].copy()
    df_test  = df[test_mask].copy()
    
    # ── Integrity Validations ──────────────────────────────────────────────────
    n_train = len(df_train)
    n_val   = len(df_val)
    n_test  = len(df_test)
    
    pct_train = n_train / total_rows * 100.0
    pct_val   = n_val / total_rows * 100.0
    pct_test  = n_test / total_rows * 100.0
    
    print("\n" + "=" * 70)
    print("Split Size & Ratio Verification")
    print("=" * 70)
    print(f"Train Set : {n_train:>6,} rows ({pct_train:5.2f}%)  [Days 01-21 of each month, 252 days]")
    print(f"Val Set   : {n_val:>6,} rows ({pct_val:5.2f}%)  [Days 22-25 of each month,  48 days]")
    print(f"Test Set  : {n_test:>6,} rows ({pct_test:5.2f}%)  [Days 26-End of each month, 65 days]")
    print(f"Total Sum : {n_train + n_val + n_test:>6,} rows (Match: {n_train + n_val + n_test == total_rows})")
    
    if n_train + n_val + n_test != total_rows:
        raise ValueError("Critical error: Sum of split rows does not match original dataset!")
        
    # Check nulls
    for name, subset in [("Train", df_train), ("Val", df_val), ("Test", df_test)]:
        null_count = subset.isnull().sum().sum()
        if null_count > 0:
            raise ValueError(f"Subset {name} contains {null_count} NaN values!")
            
    # Check monthly representation
    print("\n[*] Monthly distribution across splits (number of 10-min timesteps per month):")
    month_summary = pd.DataFrame({
        "Train": df_train['timestamp'].dt.month.value_counts(),
        "Val":   df_val['timestamp'].dt.month.value_counts(),
        "Test":  df_test['timestamp'].dt.month.value_counts(),
    }).sort_index()
    month_summary['Total'] = month_summary.sum(axis=1)
    month_summary.index.name = "Month"
    print(month_summary.to_string())
    
    # Verify seasonal energy distribution (Summer cooling vs Winter heating)
    print("\n" + "=" * 70)
    print("Seasonal Energy Representation Check (Optimal Net Energy / Loads in MWh)")
    print("=" * 70)
    
    for name, subset in [("Train", df_train), ("Val", df_val), ("Test", df_test)]:
        # Summer (Jun-Aug) cooling load (angle 30)
        summer_mask = subset['timestamp'].dt.month.isin([6, 7, 8])
        summer_cool_mwh = subset.loc[summer_mask, 'cool_load_30'].sum() / 1000.0
        
        # Winter (Dec-Feb) heating load (angle 30)
        winter_mask = subset['timestamp'].dt.month.isin([12, 1, 2])
        winter_heat_mwh = subset.loc[winter_mask, 'heat_load_30'].sum() / 1000.0
        
        # Total PV gen (angle 30)
        total_pv_mwh = subset['pv_gen_30'].sum() / 1000.0
        
        # Optimal net energy
        opt_net_mwh = subset['optimal_net_energy'].sum() / 1000.0
        
        print(f"[{name:>5}] Summer Cool: {summer_cool_mwh:6.2f} MWh | Winter Heat: {winter_heat_mwh:6.2f} MWh | PV: {total_pv_mwh:6.2f} MWh | Net: {opt_net_mwh:6.2f} MWh")

    # ── Exporting CSVs ─────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("Exporting Split CSV Files")
    print("=" * 70)
    for path, data, name in [
        (TRAIN_CSV, df_train, "Train"),
        (VAL_CSV,   df_val,   "Val"),
        (TEST_CSV,  df_test,  "Test")
    ]:
        print(f"[*] Saving {name} dataset to: {path.name}...")
        data.to_csv(path, index=False)
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f"    -> Done! File size: {size_mb:.2f} MB ({len(data):,} rows)")
        
    print("\nAll 3 datasets successfully generated and verified!")
    print("=" * 70)


if __name__ == "__main__":
    main()
