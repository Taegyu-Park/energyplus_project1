"""
evaluate_tide.py
================
Comprehensive Evaluation Pipeline for TiDE Models on BIPV Test Dataset.

Evaluates:
1. Physical Units (W) Regression Metrics: MAE, RMSE, R² (per component & overall)
2. Derived Net Energy Metrics: MAE, RMSE, R²
3. Control Optimization Metrics:
   - Optimal Angle Hit Rate (%) (Exact Match)
   - Optimal Angle Tolerance Match (±10°) (%)
   - Optimal Angle Mean Absolute Error (MAE in degrees)
   - Energy Regret (W) (Difference between chosen angle's Net Energy vs True Optimal Net Energy)
4. Seasonal Breakdown (Spring/Mar, Summer/Jun, Autumn/Sep, Winter/Dec)

Outputs structured JSON and detailed terminal summary tables.
"""

import os
import sys
import json
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

from tide_model import TiDEModel
from train_tide import (
    ContiguousBlockTiDEDataset,
    ANGLES,
    COP_COOLING,
    COP_HEATING,
    PAST_COV_COLS,
    FUTURE_COV_COLS,
    STRATEGY_1_TARGETS,
    STRATEGY_2_TARGETS,
    CHECKPOINT_DIR,
    TEST_CSV,
)


def compute_regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Computes MAE, RMSE, and R²."""
    mae = float(np.mean(np.abs(y_true - y_pred)))
    mse = float(np.mean((y_true - y_pred) ** 2))
    rmse = float(np.sqrt(mse))
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = float(1.0 - (ss_res / (ss_tot + 1e-8)))
    return {"mae": mae, "rmse": rmse, "r2": r2}


def evaluate_model(
    strategy: int = 1,
    batch_size: int = 64,
    device_name: str = "auto"
):
    print("=" * 85)
    print(f"TiDE Model Quantitative Evaluation - [Strategy {strategy}] on Unseen Test Dataset")
    print("=" * 85)

    if device_name == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(device_name)
    print(f"[*] Compute Device: {device}")

    ckpt_path = CHECKPOINT_DIR / f"tide_strategy{strategy}_best.pt"
    scaler_path = CHECKPOINT_DIR / f"tide_strategy{strategy}_scaler.json"

    if not ckpt_path.exists() or not scaler_path.exists():
        raise FileNotFoundError(
            f"Checkpoint or scaler not found for Strategy {strategy}.\n"
            f"Expected: {ckpt_path}\n"
            f"Please run `python ai_model/train_tide.py --strategy {strategy}` first."
        )

    # 1. Load Scaler
    with open(scaler_path, "r", encoding="utf-8") as f:
        scaler_dict = json.load(f)

    # 2. Load Checkpoint & Instantiate Model
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    lookback_len = ckpt["lookback_len"]
    horizon_len = ckpt["horizon_len"]
    target_cols = ckpt["target_cols"]

    print(f"[*] Loaded Best Checkpoint from Epoch {ckpt.get('epoch', '?')} (Val MSE: {ckpt.get('val_loss', 0.0):.6f})")
    print(f"[*] Model Lookback: {lookback_len} steps (24h), Horizon: {horizon_len} steps (4h)")
    print(f"[*] Evaluated Target Columns: {len(target_cols)}")

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

    # 3. Load Test Dataset
    print(f"[*] Loading Test Data from: {TEST_CSV.name}")
    df_test = pd.read_csv(TEST_CSV)
    df_test["timestamp"] = pd.to_datetime(df_test["timestamp"])

    test_ds = ContiguousBlockTiDEDataset(
        df=df_test,
        target_cols=target_cols,
        past_cov_cols=PAST_COV_COLS,
        future_cov_cols=FUTURE_COV_COLS,
        lookback_len=lookback_len,
        horizon_len=horizon_len,
        scaler_dict=scaler_dict
    )
    print(f"[*] Test Sliding Window Samples: {len(test_ds):,}")
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)

    # 4. Perform Inference
    preds_norm_list = []
    targets_norm_list = []

    print("[*] Running Forward Inference across Test Dataset...")
    with torch.no_grad():
        for lb_tgt, p_cov, f_cov, hz_tgt in test_loader:
            lb_tgt = lb_tgt.to(device)
            p_cov  = p_cov.to(device)
            f_cov  = f_cov.to(device)
            pred   = model(lb_tgt, p_cov, f_cov)

            preds_norm_list.append(pred.cpu().numpy())
            targets_norm_list.append(hz_tgt.cpu().numpy())

    preds_norm = np.concatenate(preds_norm_list, axis=0)     # Shape: (N, H, T)
    targets_norm = np.concatenate(targets_norm_list, axis=0) # Shape: (N, H, T)

    # 5. Inverse Scale to Physical Units (Watts)
    preds_phys = np.zeros_like(preds_norm)
    targets_phys = np.zeros_like(targets_norm)

    for i, col in enumerate(target_cols):
        mean_val, std_val = scaler_dict[col]
        preds_phys[:, :, i] = preds_norm[:, :, i] * std_val + mean_val
        targets_phys[:, :, i] = targets_norm[:, :, i] * std_val + mean_val

    # 6. Evaluation Logic per Strategy
    results = {
        "strategy": strategy,
        "checkpoint_epoch": ckpt.get("epoch", 1),
        "num_samples": int(preds_phys.shape[0]),
        "horizon_len": horizon_len,
        "metrics": {}
    }

    if strategy == 1:
        # Strategy 1: Targets are Net Energy for 10 angles directly
        print("\n" + "=" * 85)
        print("1. Strategy 1 (Direct Net Energy) Physical Units (W) Metrics")
        print("=" * 85)
        print(f"{'Target Variable':^25} | {'MAE (W)':^14} | {'RMSE (W)':^14} | {'R2 Score':^14}")
        print("-" * 85)

        net_true = targets_phys  # (N, H, 10)
        net_pred = preds_phys    # (N, H, 10)

        for i, col in enumerate(target_cols):
            m = compute_regression_metrics(net_true[:, :, i], net_pred[:, :, i])
            results["metrics"][col] = m
            print(f"{col:^25} | {m['mae']:^14.2f} | {m['rmse']:^14.2f} | {m['r2']:^14.4f}")

        overall_m = compute_regression_metrics(net_true, net_pred)
        results["metrics"]["overall_net_energy"] = overall_m
        print("-" * 85)
        print(f"{'OVERALL NET ENERGY':^25} | {overall_m['mae']:^14.2f} | {overall_m['rmse']:^14.2f} | {overall_m['r2']:^14.4f}")
        print("=" * 85)

    elif strategy == 2:
        # Strategy 2: Targets are 10 PV + 10 Cooling + 10 Heating
        pv_true, pv_pred = targets_phys[:, :, 0:10], preds_phys[:, :, 0:10]
        cool_true, cool_pred = targets_phys[:, :, 10:20], preds_phys[:, :, 10:20]
        heat_true, heat_pred = targets_phys[:, :, 20:30], preds_phys[:, :, 20:30]

        # Component metrics
        pv_m   = compute_regression_metrics(pv_true, pv_pred)
        cool_m = compute_regression_metrics(cool_true, cool_pred)
        heat_m = compute_regression_metrics(heat_true, heat_pred)

        results["metrics"]["pv_generation"] = pv_m
        results["metrics"]["cooling_load"]  = cool_m
        results["metrics"]["heating_load"]  = heat_m

        print("\n" + "=" * 85)
        print("1. Strategy 2 Physical Component Regression Metrics (W)")
        print("=" * 85)
        print(f"{'Physical Component':^25} | {'MAE (W)':^14} | {'RMSE (W)':^14} | {'R2 Score':^14}")
        print("-" * 85)
        print(f"{'PV Generation (P_pv)':^25} | {pv_m['mae']:^14.2f} | {pv_m['rmse']:^14.2f} | {pv_m['r2']:^14.4f}")
        print(f"{'Cooling Load (Q_cool)':^25} | {cool_m['mae']:^14.2f} | {cool_m['rmse']:^14.2f} | {cool_m['r2']:^14.4f}")
        print(f"{'Heating Load (Q_heat)':^25} | {heat_m['mae']:^14.2f} | {heat_m['rmse']:^14.2f} | {heat_m['r2']:^14.4f}")
        print("=" * 85)

        # Derive Net Energy via Physical Equation
        net_pred = (cool_pred / COP_COOLING + heat_pred / COP_HEATING) - pv_pred
        net_true = (cool_true / COP_COOLING + heat_true / COP_HEATING) - pv_true

        derived_net_m = compute_regression_metrics(net_true, net_pred)
        results["metrics"]["derived_net_energy"] = derived_net_m

        print("\n" + "=" * 85)
        print("2. Derived Net Energy Accuracy via Physical Formula (W)")
        print("=" * 85)
        print(f"{'Derived Net Energy':^25} | {derived_net_m['mae']:^14.2f} | {derived_net_m['rmse']:^14.2f} | {derived_net_m['r2']:^14.4f}")
        print("=" * 85)

    # 7. Control Optimization & Optimal Angle Evaluation
    # Optimal angle index (0 to 9, representing 0 deg to 90 deg)
    opt_idx_true = np.argmin(net_true, axis=-1) # Shape: (N, H)
    opt_idx_pred = np.argmin(net_pred, axis=-1) # Shape: (N, H)

    angle_arr = np.array(ANGLES)
    opt_angle_true = angle_arr[opt_idx_true]    # Shape: (N, H) in degrees
    opt_angle_pred = angle_arr[opt_idx_pred]    # Shape: (N, H) in degrees

    # Exact Match Hit Rate (%)
    hit_rate = float(np.mean(opt_angle_true == opt_angle_pred) * 100.0)
    
    # Tolerance Match (within +/-10 deg)
    tol_rate = float(np.mean(np.abs(opt_angle_true - opt_angle_pred) <= 10.0) * 100.0)
    
    # Angle MAE (degrees)
    angle_mae = float(np.mean(np.abs(opt_angle_true - opt_angle_pred)))

    # Net Energy Regret (W): Actual Net Energy of chosen angle minus Actual Net Energy of optimal angle
    chosen_actual_net = np.take_along_axis(net_true, opt_idx_pred[..., None], axis=-1).squeeze(-1)
    best_actual_net   = np.take_along_axis(net_true, opt_idx_true[..., None], axis=-1).squeeze(-1)
    energy_regret = float(np.mean(np.maximum(0.0, chosen_actual_net - best_actual_net)))

    results["control_performance"] = {
        "exact_hit_rate_pct": hit_rate,
        "tolerance_10deg_hit_rate_pct": tol_rate,
        "angle_mae_degrees": angle_mae,
        "mean_energy_regret_watts": energy_regret
    }

    print("\n" + "=" * 85)
    print("3. BIPV Tilt Angle Optimization & Control Performance")
    print("=" * 85)
    print(f"  * Exact Optimal Angle Hit Rate (Top-1 Accuracy) : {hit_rate:6.2f} %")
    print(f"  * Tolerance Hit Rate (Within +/-10 deg Error)   : {tol_rate:6.2f} %")
    print(f"  * Mean Angle Absolute Error                     : {angle_mae:6.2f} deg")
    print(f"  * Mean Net Energy Regret (Loss vs Perfect Truth): {energy_regret:6.2f} W")
    print("=" * 85)

    # 8. Save Evaluation Metrics JSON
    out_json = CHECKPOINT_DIR / f"eval_strategy{strategy}_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n[*] Metrics Summary JSON saved to: {out_json.name}")

    # 9. Save Detailed Time-Series Predictions CSV (Horizon Step 1: t+10min)
    print("[*] Generating detailed time-series prediction CSV...")
    timestamps = []
    df_temp = df_test.copy()
    df_temp["time_gap"] = df_temp["timestamp"].diff() > pd.Timedelta(minutes=10)
    df_temp["block_id"] = df_temp["time_gap"].cumsum()
    window_len = lookback_len + horizon_len

    for _, block in df_temp.groupby("block_id"):
        if len(block) < window_len:
            continue
        for i in range(len(block) - window_len + 1):
            timestamps.append(block["timestamp"].iloc[i + lookback_len])

    # Horizon step 0 corresponds to the immediate next 10-min timestep
    h_step = 0
    pred_df = pd.DataFrame({
        "timestamp": timestamps,
        "optimal_angle_true": opt_angle_true[:, h_step],
        "optimal_angle_pred": opt_angle_pred[:, h_step],
        "angle_error_deg": np.abs(opt_angle_true[:, h_step] - opt_angle_pred[:, h_step]),
        "chosen_actual_net_w": chosen_actual_net[:, h_step],
        "best_actual_net_w": best_actual_net[:, h_step],
        "energy_regret_w": np.maximum(0.0, chosen_actual_net[:, h_step] - best_actual_net[:, h_step])
    })

    if strategy == 1:
        for a_idx, a in enumerate(ANGLES):
            pred_df[f"net_energy_pred_{a}"] = net_pred[:, h_step, a_idx]
            pred_df[f"net_energy_true_{a}"] = net_true[:, h_step, a_idx]
    elif strategy == 2:
        for a_idx, a in enumerate(ANGLES):
            pred_df[f"pv_pred_{a}"] = pv_pred[:, h_step, a_idx]
            pred_df[f"pv_true_{a}"] = pv_true[:, h_step, a_idx]
            pred_df[f"cool_pred_{a}"] = cool_pred[:, h_step, a_idx]
            pred_df[f"cool_true_{a}"] = cool_true[:, h_step, a_idx]
            pred_df[f"heat_pred_{a}"] = heat_pred[:, h_step, a_idx]
            pred_df[f"heat_true_{a}"] = heat_true[:, h_step, a_idx]
            pred_df[f"derived_net_pred_{a}"] = net_pred[:, h_step, a_idx]
            pred_df[f"derived_net_true_{a}"] = net_true[:, h_step, a_idx]

    out_csv = CHECKPOINT_DIR / f"eval_strategy{strategy}_predictions.csv"
    pred_df.to_csv(out_csv, index=False)
    print(f"[*] Detailed Predictions CSV ({len(pred_df):,} rows) saved to: {out_csv.name}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate trained TiDE model on unseen Test dataset")
    parser.add_argument("--strategy", type=int, default=1, choices=[1, 2], help="Strategy (1 or 2)")
    parser.add_argument("--batch_size", type=int, default=64, help="Batch size for evaluation")
    parser.add_argument("--device", type=str, default="auto", help="Compute device ('cuda', 'cpu', or 'auto')")

    args = parser.parse_args()
    evaluate_model(
        strategy=args.strategy,
        batch_size=args.batch_size,
        device_name=args.device
    )
