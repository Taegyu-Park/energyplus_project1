"""
train_tide.py
=============
Training Pipeline for TiDE (Time-series Dense Encoder) on BIPV Case2_KS Dataset.
Supports:
- Strategy 1: End-to-End Direct Net Energy Prediction (10 angles)
- Strategy 2: Component-wise Decomposition Prediction (10 PV + 10 Cooling + 10 Heating = 30 targets)

Handles monthly contiguous block sliding windows, GPU acceleration, feature normalization,
validation monitoring, early stopping, and model checkpoint saving.
"""

import os
import sys
import json
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Tuple, Dict, Optional

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

# Ensure ai_model directory is in Python path for local import
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

from tide_model import TiDEModel

# ── 1. Configuration & Feature Schema ─────────────────────────────────────────
DATA_DIR = PROJECT_ROOT / "data"
TRAIN_CSV = DATA_DIR / "case2_ks_train.csv"
VAL_CSV   = DATA_DIR / "case2_ks_val.csv"
TEST_CSV  = DATA_DIR / "case2_ks_test.csv"
CHECKPOINT_DIR = CURRENT_DIR / "checkpoints"

ANGLES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
COP_COOLING = 3.0
COP_HEATING = 2.5

# Dynamic Covariates
PAST_COV_COLS = ['outdoor_temp', 'direct_solar', 'diffuse_solar']
FUTURE_COV_COLS = ['sun_altitude', 'sun_azimuth', 'hour_sin', 'hour_cos', 'month_sin', 'month_cos']

# Strategy 1 Target Columns: 10 Net Energy values
STRATEGY_1_TARGETS = [f"net_energy_{a}" for a in ANGLES]

# Strategy 2 Target Columns: 30 component values (10 PV + 10 Cooling + 10 Heating)
STRATEGY_2_TARGETS = (
    [f"pv_gen_{a}" for a in ANGLES] +
    [f"cool_load_{a}" for a in ANGLES] +
    [f"heat_load_{a}" for a in ANGLES]
)


# ── 2. Time-Series Sliding Window Dataset ─────────────────────────────────────
class ContiguousBlockTiDEDataset(Dataset):
    """
    Sliding window dataset that extracts continuous sequences strictly within
    each contiguous monthly block, preventing artificial data jumps across gaps.
    """
    def __init__(
        self,
        df: pd.DataFrame,
        target_cols: List[str],
        past_cov_cols: List[str],
        future_cov_cols: List[str],
        lookback_len: int = 144,
        horizon_len: int = 24,
        scaler_dict: Optional[Dict[str, Tuple[float, float]]] = None
    ):
        super().__init__()
        self.lookback_len = lookback_len
        self.horizon_len = horizon_len
        self.window_len = lookback_len + horizon_len
        
        df = df.copy()
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # 1. Fit or apply normalization (Mean/Std scaling)
        self.target_cols = target_cols
        self.past_cov_cols = past_cov_cols
        self.future_cov_cols = future_cov_cols
        self.all_cols = target_cols + past_cov_cols + future_cov_cols
        
        if scaler_dict is None:
            self.scaler_dict = {}
            for col in self.all_cols:
                mean_val = float(df[col].mean())
                std_val  = float(df[col].std())
                if std_val < 1e-6:
                    std_val = 1.0
                self.scaler_dict[col] = (mean_val, std_val)
        else:
            self.scaler_dict = scaler_dict
            
        # Normalize columns
        df_norm = df.copy()
        for col in self.all_cols:
            m, s = self.scaler_dict[col]
            df_norm[col] = (df[col] - m) / s
            
        # 2. Extract sequences strictly within contiguous monthly blocks
        # Identify contiguous chunks by timestamp diff > 10 minutes
        df_norm['time_gap'] = df_norm['timestamp'].diff() > pd.Timedelta(minutes=10)
        df_norm['block_id'] = df_norm['time_gap'].cumsum()
        
        self.samples = []
        for _, block in df_norm.groupby('block_id'):
            if len(block) < self.window_len:
                continue
                
            targets_arr = block[target_cols].to_numpy(dtype=np.float32)
            past_cov_arr = block[past_cov_cols].to_numpy(dtype=np.float32)
            future_cov_arr = block[future_cov_cols].to_numpy(dtype=np.float32)
            
            num_windows = len(block) - self.window_len + 1
            for i in range(num_windows):
                idx_l_end = i + self.lookback_len
                idx_w_end = i + self.window_len
                
                lookback_tgt = targets_arr[i : idx_l_end]                  # (L, num_targets)
                past_cov     = past_cov_arr[i : idx_l_end]                 # (L, past_cov_dim)
                future_cov   = future_cov_arr[i : idx_w_end]               # (L+H, future_cov_dim)
                horizon_tgt  = targets_arr[idx_l_end : idx_w_end]          # (H, num_targets)
                
                self.samples.append((lookback_tgt, past_cov, future_cov, horizon_tgt))

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        lb_tgt, p_cov, f_cov, hz_tgt = self.samples[idx]
        return (
            torch.from_numpy(lb_tgt),
            torch.from_numpy(p_cov),
            torch.from_numpy(f_cov),
            torch.from_numpy(hz_tgt)
        )


# ── 3. Training & Validation Loop ─────────────────────────────────────────────
def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    criterion: nn.Module,
    device: torch.device
) -> float:
    model.train()
    total_loss = 0.0
    for lb_tgt, p_cov, f_cov, hz_tgt in loader:
        lb_tgt = lb_tgt.to(device)
        p_cov  = p_cov.to(device)
        f_cov  = f_cov.to(device)
        hz_tgt = hz_tgt.to(device)

        optimizer.zero_grad()
        pred = model(lb_tgt, p_cov, f_cov)
        loss = criterion(pred, hz_tgt)
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
        optimizer.step()

        total_loss += loss.item() * lb_tgt.size(0)

    return total_loss / len(loader.dataset)


def validate(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device
) -> Dict[str, float]:
    model.eval()
    total_loss = 0.0
    all_preds = []
    all_targets = []

    with torch.no_grad():
        for lb_tgt, p_cov, f_cov, hz_tgt in loader:
            lb_tgt = lb_tgt.to(device)
            p_cov  = p_cov.to(device)
            f_cov  = f_cov.to(device)
            hz_tgt = hz_tgt.to(device)

            pred = model(lb_tgt, p_cov, f_cov)
            loss = criterion(pred, hz_tgt)
            total_loss += loss.item() * lb_tgt.size(0)

            all_preds.append(pred.detach().cpu())
            all_targets.append(hz_tgt.detach().cpu())

    mse = total_loss / len(loader.dataset)
    rmse = np.sqrt(mse)

    # Concatenate all batches for exact MAE and R^2
    all_preds_tensor = torch.cat(all_preds, dim=0).numpy()
    all_targets_tensor = torch.cat(all_targets, dim=0).numpy()

    mae = float(np.mean(np.abs(all_preds_tensor - all_targets_tensor)))
    
    # R^2 score across all target dimensions and horizon steps
    ss_res = np.sum((all_targets_tensor - all_preds_tensor) ** 2)
    ss_tot = np.sum((all_targets_tensor - np.mean(all_targets_tensor)) ** 2)
    r2 = float(1.0 - (ss_res / (ss_tot + 1e-8)))

    return {
        "mse": mse,
        "rmse": rmse,
        "mae": mae,
        "r2": r2
    }


# ── 4. Main Training Pipeline Runner ──────────────────────────────────────────
def run_training(
    strategy: int = 1,
    lookback_len: int = 144,
    horizon_len: int = 24,
    epochs: int = 40,
    batch_size: int = 64,
    lr: float = 1e-3,
    hidden_dim: int = 256,
    proj_dim: int = 16,
    device_name: str = "auto"
):
    print("=" * 70)
    print(f"Starting TiDE Training Pipeline - [Strategy {strategy}]")
    print("=" * 70)
    
    # Device setup
    if device_name == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(device_name)
    print(f"[*] Compute Device: {device} ({torch.cuda.get_device_name(0) if device.type == 'cuda' else 'CPU'})")

    # Select target configuration
    if strategy == 1:
        target_cols = STRATEGY_1_TARGETS
        strategy_desc = "End-to-End Net Energy (10 angles)"
    elif strategy == 2:
        target_cols = STRATEGY_2_TARGETS
        strategy_desc = "Component-wise Decomposition (10 PV + 10 Cool + 10 Heat = 30 targets)"
    else:
        raise ValueError(f"Invalid strategy {strategy}. Must be 1 or 2.")
        
    print(f"[*] Strategy {strategy}: {strategy_desc}")
    print(f"[*] Target dimensions: {len(target_cols)}")

    # Load datasets
    print(f"[*] Loading train data from: {TRAIN_CSV.name}")
    df_train = pd.read_csv(TRAIN_CSV)
    print(f"[*] Loading val data from: {VAL_CSV.name}")
    df_val = pd.read_csv(VAL_CSV)

    train_ds = ContiguousBlockTiDEDataset(
        df=df_train,
        target_cols=target_cols,
        past_cov_cols=PAST_COV_COLS,
        future_cov_cols=FUTURE_COV_COLS,
        lookback_len=lookback_len,
        horizon_len=horizon_len
    )
    
    val_ds = ContiguousBlockTiDEDataset(
        df=df_val,
        target_cols=target_cols,
        past_cov_cols=PAST_COV_COLS,
        future_cov_cols=FUTURE_COV_COLS,
        lookback_len=lookback_len,
        horizon_len=horizon_len,
        scaler_dict=train_ds.scaler_dict
    )

    print(f"    -> Extracted Train Samples: {len(train_ds):,}")
    print(f"    -> Extracted Val Samples  : {len(val_ds):,}")

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, drop_last=True)
    val_loader   = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

    # Instantiate Model
    model = TiDEModel(
        lookback_len=lookback_len,
        horizon_len=horizon_len,
        num_targets=len(target_cols),
        past_cov_dim=len(PAST_COV_COLS),
        future_cov_dim=len(FUTURE_COV_COLS),
        hidden_dim=hidden_dim,
        proj_dim=proj_dim,
        num_encoder_layers=2,
        num_decoder_layers=2,
        decoder_output_dim=32,
        dropout=0.1
    ).to(device)

    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"[*] Initialized TiDE Model (Trainable Params: {total_params:,})")

    criterion = nn.MSELoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-5)

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    best_val_loss = float('inf')
    best_ckpt_path = CHECKPOINT_DIR / f"tide_strategy{strategy}_best.pt"
    scaler_path = CHECKPOINT_DIR / f"tide_strategy{strategy}_scaler.json"

    # Save scaler parameters
    with open(scaler_path, 'w', encoding='utf-8') as f:
        json.dump(train_ds.scaler_dict, f, indent=2)
    print(f"[*] Saved Normalization Scaler to: {scaler_path.name}")

    print("\n" + "=" * 90)
    print(f"{'Epoch':^7} | {'Train MSE':^13} | {'Val MSE':^11} | {'Val RMSE':^10} | {'Val MAE':^10} | {'Val R²':^9} | {'Status':^12}")
    print("=" * 90)

    for ep in range(1, epochs + 1):
        train_loss = train_one_epoch(model, train_loader, optimizer, criterion, device)
        val_metrics = validate(model, val_loader, criterion, device)
        scheduler.step()

        status = ""
        if val_metrics["mse"] < best_val_loss:
            best_val_loss = val_metrics["mse"]
            torch.save({
                'epoch': ep,
                'strategy': strategy,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'val_loss': val_metrics["mse"],
                'val_metrics': val_metrics,
                'lookback_len': lookback_len,
                'horizon_len': horizon_len,
                'target_cols': target_cols
            }, best_ckpt_path)
            status = "★ Best Saved"

        print(
            f"{ep:^7d} | {train_loss:^13.6f} | {val_metrics['mse']:^11.6f} | "
            f"{val_metrics['rmse']:^10.4f} | {val_metrics['mae']:^10.4f} | "
            f"{val_metrics['r2']:^9.4f} | {status:^12}"
        )

    print("=" * 90)
    print(f"Training Complete! Best Validation Loss (MSE): {best_val_loss:.6f}")
    print(f"Best Model Weights saved to: {best_ckpt_path}")
    print("=" * 90)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train TiDE model on BIPV Case2_KS dataset")
    parser.add_argument("--strategy", type=int, default=1, choices=[1, 2], help="1: End-to-End, 2: Component-wise")
    parser.add_argument("--epochs", type=int, default=30, help="Number of training epochs")
    parser.add_argument("--batch_size", type=int, default=64, help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    parser.add_argument("--hidden_dim", type=int, default=256, help="Hidden layer dimension")
    parser.add_argument("--device", type=str, default="auto", help="Compute device ('cuda', 'cpu', or 'auto')")

    args = parser.parse_args()
    run_training(
        strategy=args.strategy,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        hidden_dim=args.hidden_dim,
        device_name=args.device
    )
