"""
label_mismatch.py
=================
2026-10-29 사용자 결정 각도 규칙으로 라벨(오라클 각도 스케줄)을 만든다. build_dataset.py 의 1단계 라벨은 그대로 둔다.

규칙
1. 모든 각도에서 수요 > PV (구매 최소값 > 0): 구매 전력이 최소인 각도. (TIE_TOL 이내 동점은 규칙 2의 움직임 기준으로 가린다)
2. PV ≥ 수요가 되는 각도가 있음 (구매 최소값 = 0): 수요만큼만 쓰고 나머지 PV는 버린다(curtail, 미스매치에 넣지 않음).
   구매 0 인 각도들 중 채광이 크고 움직임이 적은 각도.

구현: 연간 52,560 스텝 × 10 각도 Viterbi
  비용 = Σ_t [허용 안 되는 각도 ∞, 규칙 2 시점 −채광점수_t(a)] + λ · Σ_t |θ_t − θ_{t−1}| / 10°
  규칙 1 시점은 구매 최소 각도(±TIE_TOL)만 허용, 채광점수 0 → 움직임만 따진다(야간 동점이 대부분 여기).
채광점수 (--daylight)
  raw    : 조도 / 1000 lx (문자 그대로 최대화, 남측 2개 존 기준점 평균)
  useful : min(조도, 500) / 500 − OVER_PENALTY · max(조도 − 1500, 0) / 500
           (2026-10-29 사용자 결정: 점수 상한 500 lx, 1500 lx부터 벌점. 500~1500 lx는 같은 점수 → 움직임으로 가림)
규칙 1 허용오차 (--rel_tol): 0 이면 엄격(구매 최소만). r 이면 구매 ≤ 최소×(1+r) 각도도 허용하고 움직임으로 가린다.
λ (--lam): 10° 이동 1회의 벌점, 채광점수 단위. raw 에서 λ=0.05 → 10° 덜 움직이려고 50 lx 까지 양보.

입력: dataset_final/case2_mm_{split}.csv, dataset_final/daylight_{split}.csv (extract_daylight.py)
출력: labels/mm_label_{split}_{daylight}_lam{λ}.csv (timestamp, angle, rule, purchase, curtailed_pv, illum)
"""

import argparse
import numpy as np
import pandas as pd
from pathlib import Path

from build_dataset import ANGLES

BASE_DIR = Path(__file__).resolve().parent
TIE_TOL_KWH = 1e-4  # 규칙 1 동점 (10분당 0.1 Wh)
LUX_SETPOINT = 400.0
LUX_CAP = 500.0  # useful 채광점수 상한
LUX_PENALTY_FROM = 1500.0  # 이 조도부터 벌점
OVER_PENALTY = 10.0  # 1500 lx 초과 500 lx당 벌점. λ 0.05 보다 훨씬 커서 이동보다 초과 회피가 우선
EVAL_MONTHS = [11, 12, 1, 2, 3]


def load(split: str) -> pd.DataFrame:
    cols = ["timestamp", "sun_altitude", "is_weekend", "optimal_angle"] + [
        f"{c}_{a}" for c in ["purchase", "surplus_pv", "pv_gen", "demand_elec"] for a in ANGLES]
    df = pd.read_csv(BASE_DIR / "dataset_final" / f"case2_mm_{split}.csv", usecols=cols)
    dl = pd.read_csv(BASE_DIR / "dataset_final" / f"daylight_{split}.csv")
    if not (dl["timestamp"].to_numpy() == df["timestamp"].to_numpy()).all():
        raise ValueError("daylight 테이블 timestamp 불일치")
    return pd.concat([df, dl.drop(columns="timestamp")], axis=1)


def mat(df: pd.DataFrame, prefix: str) -> np.ndarray:
    return df[[f"{prefix}_{a}" for a in ANGLES]].to_numpy()


def viterbi(stage_cost: np.ndarray, lam: float) -> np.ndarray:
    """stage_cost (T, K), 이동 비용 λ·|i−j| (각도 인덱스 차 = 10° 단위). 최소 비용 경로의 인덱스."""
    T, K = stage_cost.shape
    move = lam * np.abs(np.arange(K)[:, None] - np.arange(K)[None, :])  # [이전, 현재]
    back = np.empty((T, K), dtype=np.int8)
    acc = stage_cost[0].copy()
    for t in range(1, T):
        tot = acc[:, None] + move
        back[t] = tot.argmin(0)
        acc = tot[back[t], np.arange(K)] + stage_cost[t]
    path = np.empty(T, dtype=np.int64)
    path[-1] = acc.argmin()
    for t in range(T - 1, 0, -1):
        path[t - 1] = back[t, path[t]]
    return path


def choose_path(P: np.ndarray, E: np.ndarray, daylight: str, lam: float, rel_tol: float = 0.0, free=None):
    """구매 (T,10)·조도 (T,10) → (각도 인덱스, 규칙 2 시점 여부). 실제값·예측값 모두에 쓴다.
    free (T,) bool: 모든 각도를 동점으로 볼 시점 (예측 경로의 야간: 실제 각도 간 차이가 거의 0인데 예측 오차로 각도가 튐)."""
    p_min = P.min(axis=1, keepdims=True)
    surplus_step = p_min[:, 0] <= TIE_TOL_KWH  # 규칙 2 시점
    rel_tol = np.reshape(rel_tol, (-1, 1)) if np.ndim(rel_tol) else rel_tol  # 스텝별 (T,) 도 가능
    allowed = P <= p_min * (1 + rel_tol) + TIE_TOL_KWH  # rel_tol > 0 이면 규칙 1에서 구매 최소의 (1+rel_tol) 배까지 허용
    if free is not None:
        allowed |= free[:, None]
    if daylight == "raw":
        score = E / 1000.0
    else:
        score = (np.minimum(E, LUX_CAP) - OVER_PENALTY * np.maximum(E - LUX_PENALTY_FROM, 0.0)) / LUX_CAP
    score = np.where(surplus_step[:, None], score, 0.0)
    return viterbi(np.where(allowed, -score, np.inf), lam), surplus_step


def label(df: pd.DataFrame, daylight: str, lam: float, rel_tol: float = 0.0) -> pd.DataFrame:
    P = mat(df, "purchase")
    E = mat(df, "illum")
    idx, surplus_step = choose_path(P, E, daylight, lam, rel_tol)
    rows = np.arange(len(df))
    return pd.DataFrame({
        "timestamp": df["timestamp"],
        "angle": np.array(ANGLES)[idx],
        "rule": np.where(surplus_step, 2, 1),
        "purchase": P[rows, idx],
        "curtailed_pv": mat(df, "surplus_pv")[rows, idx],
        "pv_gen": mat(df, "pv_gen")[rows, idx],
        "demand": mat(df, "demand_elec")[rows, idx],
        "illum": E[rows, idx],
    })


def metrics(df: pd.DataFrame, angle: np.ndarray, name: str) -> dict:
    """평가 기간(11~3월 평일)과 연간 지표. angle 은 각 스텝의 선택 각도."""
    idx = np.searchsorted(ANGLES, angle)
    rows = np.arange(len(df))
    P = mat(df, "purchase")[rows, idx]
    S = mat(df, "surplus_pv")[rows, idx]
    E = mat(df, "illum")[rows, idx]
    ts = pd.to_datetime(df["timestamp"]) - pd.Timedelta(minutes=10)
    ev = ts.dt.month.isin(EVAL_MONTHS).to_numpy() & (df["is_weekend"].to_numpy() == 0)
    surplus_step = mat(df, "purchase").min(axis=1) <= TIE_TOL_KWH
    move = np.r_[0, np.abs(np.diff(angle))]
    out = {"안": name}
    for tag, m in [("평가", ev), ("연간", np.ones(len(df), bool))]:
        n_days = m.sum() / 144
        r2 = m & surplus_step
        out.update({
            f"{tag}_구매MWh": P[m].sum() / 1000,
            f"{tag}_버림PV_MWh": S[m].sum() / 1000,
            f"{tag}_잉여시점조도lx": E[r2].mean(),
            f"{tag}_잉여시점<400lx%": (E[r2] < LUX_SETPOINT).mean() * 100,
            f"{tag}_잉여시점<500lx%": (E[r2] < LUX_CAP).mean() * 100,
            f"{tag}_잉여시점>500lx%": (E[r2] > LUX_CAP).mean() * 100,
            f"{tag}_잉여시점>1500lx%": (E[r2] > LUX_PENALTY_FROM).mean() * 100,
            f"{tag}_잉여시점>2000lx%": (E[r2] > 2000).mean() * 100,
            f"{tag}_부족시점(주간)>1500lx%": (E[m & ~surplus_step & (E > 0)] > LUX_PENALTY_FROM).mean() * 100,
            f"{tag}_이동횟수/일": (move[m] > 0).sum() / n_days,
            f"{tag}_이동각도°/일": move[m].sum() / n_days,
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="train", choices=["train", "val", "test"])
    ap.add_argument("--daylight", default="useful", choices=["raw", "useful"])
    ap.add_argument("--lam", type=float, default=0.05)
    ap.add_argument("--rel_tol", type=float, default=0.0, help="규칙 1 허용오차(구매 최소 대비 비율), 0 = 엄격")
    ap.add_argument("--sweep", action="store_true", help="채광 2종 × λ 여러 값 비교표만 출력")
    ap.add_argument("--sweep_tol", action="store_true", help="raw·λ 고정, 규칙 1 허용오차별 비교표만 출력")
    args = ap.parse_args()

    df = load(args.split)
    if args.sweep:
        rows = [metrics(df, df["optimal_angle"].to_numpy(), "기존(동점→수요최소)")]
        for d in ["raw", "useful"]:
            for lam in [0.0, 0.01, 0.05, 0.2, 1.0]:
                rows.append(metrics(df, label(df, d, lam)["angle"].to_numpy(), f"{d} λ={lam}"))
        pd.set_option("display.width", 250)
        print(pd.DataFrame(rows).set_index("안").round(2).T.to_string())
        return

    if args.sweep_tol:
        rows = [metrics(df, label(df, args.daylight, args.lam, t)["angle"].to_numpy(), f"허용 {t * 100:g}%")
                for t in [0.0, 0.01, 0.02, 0.05, 0.1]]
        pd.set_option("display.width", 250)
        print(pd.DataFrame(rows).set_index("안").round(2).T.to_string())
        return

    lab = label(df, args.daylight, args.lam, args.rel_tol)
    out_dir = BASE_DIR / "labels"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"mm_label_{args.split}_{args.daylight}_lam{args.lam}_tol{args.rel_tol}.csv"
    lab.to_csv(path, index=False)
    print(pd.Series(metrics(df, lab["angle"].to_numpy(), path.stem)).drop("안").astype(float).round(2).to_string())
    print(f"[*] → {path}")


if __name__ == "__main__":
    main()
