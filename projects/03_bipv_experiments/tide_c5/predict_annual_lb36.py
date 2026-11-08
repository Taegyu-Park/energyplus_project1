"""lookback 36 재학습 모델(시드 5개)로 연간 52,560스텝 최적 각도 산출 (ST1/ST2).
기존 predict_annual_tide.py 로직을 복사. 출력은 이 폴더의 predictions/ 에만 저장(원본 predictions 미수정).
시드 앙상블: 시드별 물리단위 net 예측을 평균한 뒤 argmin."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai_model" / "tide"))
from tide_model import TiDEModel
from train_tide import ANGLES, PAST_COV_COLS, FUTURE_COV_COLS, DATA_DIR

HERE = Path(__file__).resolve().parent
CK = HERE / "checkpoints"
OUT = HERE / "predictions"; OUT.mkdir(exist_ok=True)
SEEDS = [0, 1, 2, 3, 4]
LB, H = 36, 24
dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")

df = pd.read_csv(DATA_DIR / "case2_ks_bipv_tide_dataset.csv")
N = len(df); assert N == 52560, N
true_net = df[[f"net_energy_{a}" for a in ANGLES]].to_numpy()
true_idx = true_net.argmin(1)


def predict_seed(strategy, seed):
    ck = torch.load(CK / f"tide_strategy{strategy}_lb{LB}_seed{seed}.pt", map_location=dev, weights_only=False)
    cols, sc = ck["target_cols"], ck["scaler"]
    model = TiDEModel(lookback_len=LB, horizon_len=H, num_targets=len(cols), past_cov_dim=3, future_cov_dim=6,
                      hidden_dim=256, proj_dim=16, num_encoder_layers=2, num_decoder_layers=2,
                      decoder_output_dim=32, dropout=0.0).to(dev)
    model.load_state_dict(ck["model_state_dict"]); model.eval()
    nz = lambda cs: np.stack([(df[c].to_numpy() - sc[c][0]) / sc[c][1] for c in cs], 1).astype(np.float32)
    tg, pc, fc = nz(cols), nz(PAST_COV_COLS), nz(FUTURE_COV_COLS)
    ext_t = np.concatenate([np.repeat(tg[:1], LB, 0), tg])
    ext_p = np.concatenate([np.repeat(pc[:1], LB, 0), pc])
    ext_f = np.concatenate([np.repeat(fc[:1], LB, 0), fc, np.repeat(fc[-1:], H, 0)])
    preds = []
    with torch.no_grad():
        for s in range(0, N, 512):
            ix = np.arange(s, min(s + 512, N))
            lb = torch.from_numpy(np.stack([ext_t[t:t + LB] for t in ix])).to(dev)
            pp = torch.from_numpy(np.stack([ext_p[t:t + LB] for t in ix])).to(dev)
            ff = torch.from_numpy(np.stack([ext_f[t:t + LB + H] for t in ix])).to(dev)
            preds.append(model(lb, pp, ff)[:, 0, :].cpu().numpy())
    X = np.concatenate(preds)
    X = X * np.array([sc[c][1] for c in cols]) + np.array([sc[c][0] for c in cols])
    return X if strategy == 1 else X[:, 10:20] / 3.0 + X[:, 20:] / 2.5 - X[:, :10]


# test 구간(블록 내 위치 >= 144) 마스크 — 시드/앙상블 비교용
te = pd.read_csv(DATA_DIR / "case2_ks_test.csv")
ts_te = pd.to_datetime(te["timestamp"]); pos = ts_te.groupby((ts_te.diff() > pd.Timedelta(minutes=10)).cumsum()).cumcount()
te_mask = df["timestamp"].isin(te["timestamp"][pos.values >= 144]).to_numpy()


def metrics(net_pred, mask):
    idx = net_pred.argmin(1)
    ch = true_net[np.arange(N), idx]
    return ch[mask].sum(), np.abs(np.array(ANGLES)[idx] - np.array(ANGLES)[true_idx])[mask].mean()


for strategy in (1, 2):
    per = [predict_seed(strategy, s) for s in SEEDS]
    ens = np.mean(per, axis=0)
    print(f"\n=== Strategy {strategy} === (test 구간 n={te_mask.sum()}, oracle {true_net.min(1)[te_mask].sum():.0f})")
    for s, p in zip(SEEDS, per):
        print(f"  seed {s}: net {metrics(p, te_mask)[0]:8.1f}  angle_mae {metrics(p, te_mask)[1]:.1f}")
    print(f"  ENSEMBLE: net {metrics(ens, te_mask)[0]:8.1f}  angle_mae {metrics(ens, te_mask)[1]:.1f}")
    print(f"  (전체 연간, 학습 구간 포함) net {metrics(ens, np.ones(N, bool))[0]:.1f}, "
          f"oracle {true_net.min(1).sum():.1f}, 태양추적 별도")

    idx = ens.argmin(1); ang = np.array(ANGLES)[idx]
    out = pd.DataFrame({
        "timestamp": df["timestamp"], "optimal_angle_pred": ang, "optimal_angle_true": df["optimal_angle"],
        "angle_error_deg": np.abs(ang - df["optimal_angle"].to_numpy()),
        "energy_regret_w": np.maximum(0.0, true_net[np.arange(N), idx] - true_net.min(1)),
        "sun_altitude": df["sun_altitude"], "sun_azimuth": df["sun_azimuth"],
        "direct_solar": df["direct_solar"], "diffuse_solar": df["diffuse_solar"], "outdoor_temp": df["outdoor_temp"]})
    for i, a in enumerate(ANGLES):
        out[f"net_energy_pred_{a}"] = ens[:, i]; out[f"net_energy_true_{a}"] = true_net[:, i]
    out.to_csv(OUT / f"annual_tide_strategy{strategy}_lb36_optimal_angles.csv", index=False)
    pd.DataFrame({"timestamp": df["timestamp"], "optimal_angle": ang}).to_csv(
        OUT / f"bipv_optimal_angles_annual_strategy{strategy}_lb36.csv", index=False)
    print("  각도 분포(%):", {int(a): round(float((ang == a).mean() * 100), 1) for a in ANGLES})
