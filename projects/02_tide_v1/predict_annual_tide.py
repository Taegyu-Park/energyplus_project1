"""
predict_annual_tide.py
======================
Generates full-year (52,560 timesteps, 10-min interval) optimal BIPV tilt angles
using the trained TiDE (Time-series Dense Encoder) model.

Handles initial 24h lookback boundary with replicate padding to ensure exactly
52,560 output timesteps matching the annual EnergyPlus simulation timeline.
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from pathlib import Path
import torch
from torch.utils.data import DataLoader, TensorDataset

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

from tide_model import TiDEModel
from train_tide import (
    ANGLES,
    PAST_COV_COLS,
    FUTURE_COV_COLS,
    CHECKPOINT_DIR,
    DATA_DIR
)
PRED_DIR = CURRENT_DIR / "data" / "predictions"
PRED_DIR.mkdir(parents=True, exist_ok=True)


def run_annual_prediction(strategy: int = 1, batch_size: int = 256):
    print("=" * 80)
    print(f"Generating Full-Year (52,560 Timesteps) BIPV Optimal Angles via TiDE [Strategy {strategy}]")
    print("=" * 80)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[*] Compute Device: {device}")

    # 1. Load Checkpoint and Scaler
    ckpt_path = CHECKPOINT_DIR / f"tide_strategy{strategy}_best.pt"
    scaler_path = CHECKPOINT_DIR / f"tide_strategy{strategy}_scaler.json"

    if not ckpt_path.exists() or not scaler_path.exists():
        raise FileNotFoundError(f"Checkpoint or scaler not found at: {ckpt_path}")

    with open(scaler_path, "r", encoding="utf-8") as f:
        scaler_dict = json.load(f)

    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    lookback_len = ckpt["lookback_len"]  # 144 steps (24h)
    horizon_len = ckpt["horizon_len"]    # 24 steps (4h)
    target_cols = ckpt["target_cols"]

    print(f"[*] Loaded Model (Epoch {ckpt.get('epoch', '?')}, Val Loss: {ckpt.get('val_loss', 0.0):.6f})")

    model = TiDEModel(
        lookback_len=lookback_len,
        horizon_len=horizon_len,
        num_targets=len(target_cols),
        past_cov_dim=len(PAST_COV_COLS),
        future_cov_dim=len(FUTURE_COV_COLS),
        hidden_dim=256,
        proj_dim=16,
        num_encoder_layers=2,
        num_decoder_layers=2,
        decoder_output_dim=32,
        dropout=0.0
    ).to(device)

    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()

    # 2. Load Full-Year Raw Dataset
    annual_csv_path = DATA_DIR / "case2_ks_bipv_tide_dataset.csv"
    print(f"[*] Loading Annual Dataset from: {annual_csv_path.name}")
    df_annual = pd.read_csv(annual_csv_path)
    num_total = len(df_annual)
    print(f"[*] Total Raw Timesteps: {num_total:,} rows (Expected: 52,560)")

    # 3. Normalize Features
    df_norm = df_annual.copy()
    for col in target_cols + PAST_COV_COLS + FUTURE_COV_COLS:
        m, s = scaler_dict[col]
        df_norm[col] = (df_annual[col] - m) / s

    targets_norm = df_norm[target_cols].to_numpy(dtype=np.float32)
    past_cov_norm = df_norm[PAST_COV_COLS].to_numpy(dtype=np.float32)
    future_cov_norm = df_norm[FUTURE_COV_COLS].to_numpy(dtype=np.float32)

    # 4. Boundary Padding for Full 52,560 Coverage
    # Prepend lookback_len steps (using the first day's pattern)
    # Append horizon_len steps (using the last day's pattern)
    pad_front_targets = np.repeat(targets_norm[:1], lookback_len, axis=0)
    pad_front_past = np.repeat(past_cov_norm[:1], lookback_len, axis=0)
    pad_front_future = np.repeat(future_cov_norm[:1], lookback_len, axis=0)

    pad_back_future = np.repeat(future_cov_norm[-1:], horizon_len, axis=0)

    ext_targets = np.concatenate([pad_front_targets, targets_norm], axis=0)
    ext_past = np.concatenate([pad_front_past, past_cov_norm], axis=0)
    ext_future = np.concatenate([pad_front_future, future_cov_norm, pad_back_future], axis=0)

    # 5. Build Sequences for All 52,560 Timesteps
    # For timestep t in [0, num_total):
    # lookback target: ext_targets[t : t + lookback_len]
    # past cov: ext_past[t : t + lookback_len]
    # future cov: ext_future[t : t + lookback_len + horizon_len]
    print("[*] Preparing 52,560 sliding window input batches...")
    all_lb_targets = []
    all_past_covs = []
    all_future_covs = []

    for t in range(num_total):
        all_lb_targets.append(ext_targets[t : t + lookback_len])
        all_past_covs.append(ext_past[t : t + lookback_len])
        all_future_covs.append(ext_future[t : t + lookback_len + horizon_len])

    tensor_lb = torch.from_numpy(np.array(all_lb_targets, dtype=np.float32))
    tensor_past = torch.from_numpy(np.array(all_past_covs, dtype=np.float32))
    tensor_future = torch.from_numpy(np.array(all_future_covs, dtype=np.float32))

    dataset = TensorDataset(tensor_lb, tensor_past, tensor_future)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False)

    # 6. Run Inference
    print(f"[*] Running Batched GPU Inference across 52,560 timesteps (Batch size: {batch_size})...")
    preds_norm_list = []
    with torch.no_grad():
        for b_lb, b_past, b_future in loader:
            b_lb = b_lb.to(device)
            b_past = b_past.to(device)
            b_future = b_future.to(device)
            pred = model(b_lb, b_past, b_future)  # Shape: (B, H, num_targets)
            # We take horizon step 0 (immediate next 10-min step)
            preds_norm_list.append(pred[:, 0, :].cpu().numpy())

    preds_norm = np.concatenate(preds_norm_list, axis=0)  # Shape: (52560, 10)

    # 7. Inverse Scale Predictions to Physical Units
    preds_phys = np.zeros_like(preds_norm)
    for i, col in enumerate(target_cols):
        m, s = scaler_dict[col]
        preds_phys[:, i] = preds_norm[:, i] * s + m

    # 8. Optimal PV Angle Determination (argmin of predicted Net Energy)
    if strategy == 1:
        pred_opt_idx = np.argmin(preds_phys, axis=-1)  # Index 0 to 9
    elif strategy == 2:
        # Target layout: 10 PV, 10 Cooling, 10 Heating
        pv_pred = preds_phys[:, 0:10]
        cool_pred = preds_phys[:, 10:20]
        heat_pred = preds_phys[:, 20:30]
        net_pred = (cool_pred / 3.0) + (heat_pred / 2.5) - pv_pred
        pred_opt_idx = np.argmin(net_pred, axis=-1)

    angles_arr = np.array(ANGLES)
    pred_opt_angles = angles_arr[pred_opt_idx]      # Degrees (0 to 90)

    # 9. Extract True Values from Raw Dataset for Comparison
    true_net_cols = [f"net_energy_{a}" for a in ANGLES]
    true_net_phys = df_annual[true_net_cols].to_numpy()
    true_opt_angles = df_annual["optimal_angle"].to_numpy()

    # Calculate Regret (Energy penalty if chosen angle differs from true optimum)
    chosen_actual_net = np.take_along_axis(true_net_phys, pred_opt_idx[:, None], axis=-1).squeeze(-1)
    best_actual_net = np.min(true_net_phys, axis=-1)
    energy_regret = np.maximum(0.0, chosen_actual_net - best_actual_net)

    # 10. Assemble and Save Results DataFrame
    out_df = pd.DataFrame({
        "timestamp": df_annual["timestamp"],
        "optimal_angle_pred": pred_opt_angles,
        "optimal_angle_true": true_opt_angles,
        "angle_error_deg": np.abs(pred_opt_angles - true_opt_angles),
        "energy_regret_w": energy_regret,
        "sun_altitude": df_annual["sun_altitude"],
        "sun_azimuth": df_annual["sun_azimuth"],
        "direct_solar": df_annual["direct_solar"],
        "diffuse_solar": df_annual["diffuse_solar"],
        "outdoor_temp": df_annual["outdoor_temp"]
    })

    # Append predicted and true Net Energy for all 10 angles
    preds_net = preds_phys if strategy == 1 else net_pred
    for i, a in enumerate(ANGLES):
        out_df[f"net_energy_pred_{a}"] = preds_net[:, i]
        out_df[f"net_energy_true_{a}"] = true_net_phys[:, i]

    out_csv = PRED_DIR / f"annual_tide_strategy{strategy}_optimal_angles.csv"
    out_df.to_csv(out_csv, index=False)
    print(f"\n[*] Full-Year Optimal Angles CSV successfully created: {out_csv.name}")

    # Also update the primary BIPV schedule used by EnergyPlus plugin
    bipv_sched_local = PRED_DIR / "bipv_optimal_angles_annual.csv"
    sched_df = pd.DataFrame({
        "timestamp": df_annual["timestamp"],
        "optimal_angle": pred_opt_angles
    })
    sched_df.to_csv(bipv_sched_local, index=False)
    print(f"[*] Updated primary EnergyPlus simulation schedule at:")
    print(f"    -> {bipv_sched_local}")

    # 11. Annual Summary Statistics
    hit_rate = float(np.mean(pred_opt_angles == true_opt_angles) * 100.0)
    tol_hit_rate = float(np.mean(np.abs(pred_opt_angles - true_opt_angles) <= 10.0) * 100.0)
    mean_angle_err = float(np.mean(np.abs(pred_opt_angles - true_opt_angles)))
    mean_regret = float(np.mean(energy_regret))

    print("\n" + "=" * 80)
    print("Annual (52,560 Timesteps) Performance Summary")
    print("=" * 80)
    print(f"  * Exact Optimal Angle Hit Rate (Top-1 Accuracy) : {hit_rate:6.2f} %")
    print(f"  * Tolerance Hit Rate (Within +/-10 deg)         : {tol_hit_rate:6.2f} %")
    print(f"  * Mean Angle Absolute Error                     : {mean_angle_err:6.2f} deg")
    print(f"  * Annual Mean Net Energy Regret                 : {mean_regret:6.4f} W")
    print("=" * 80)

    print("\n--- Annual Optimal PV Angle Distribution (Predictions) ---")
    dist = out_df["optimal_angle_pred"].value_counts().sort_index()
    for angle, cnt in dist.items():
        pct = (cnt / num_total) * 100.0
        print(f"  Angle {angle:2d} deg : {cnt:6,d} times ({pct:5.1f} %)")
    print("=" * 80)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Predict annual optimal BIPV angles via TiDE")
    parser.add_argument("--strategy", type=int, default=2, choices=[1, 2], help="Strategy 1 or 2")
    parser.add_argument("--batch_size", type=int, default=256, help="Batch size")
    args = parser.parse_args()
    run_annual_prediction(strategy=args.strategy, batch_size=args.batch_size)

