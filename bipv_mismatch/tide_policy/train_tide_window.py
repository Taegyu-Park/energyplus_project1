"""
bipv_mismatch/tide_policy/train_tide_window.py
==============================================
TiDE 가 조절 구간의 시작·끝과 구간 안 각도를 함께 고르는 정책 (2026-11-03 사용자 결정, 기존 스크립트는 그대로 둠).

- 하루 모양은 언제나  태양추적 → [조절 구간] → 태양추적  (버퍼-태양추적-버퍼 금지)
    조절 구간 = [s0 − a, s1 + b),  s0·s1 = 태양추적 잉여 첫 스텝·마지막 스텝+1,  a, b ∈ {0, …, K} (K = 18 = 3시간)
    구간 안 각도: θ ∈ [θ_ST + 10, 90] 아무 값 (오르내림 허용, 버퍼·90° 구분 없음), 구간 밖 θ_ST
    잉여 없는 날은 조절 구간 없음 (하루 종일 태양추적)
- TiDE 출력 3채널: z (구간 안 각도), 시작 로짓, 끝 로짓
    시작 a 의 확률 = softmax(시작 로짓[s0 − K … s0]), 끝도 같음 → 게이트 g(t) 는 앞에서 0→1 로만 오르고 뒤에서 1→0 로만 내림
    학습 θ = θ_ST + g·(θ_in − θ_ST)  (부드러운 게이트), 평가·출력은 확률 최대인 a, b 로 자른 hard 구간
- 정답(case2): 날마다 (a, b) 19 × 19 조합을 모두 따져 Σ|P − D| (1:1) 최소인 조합, 구간 안 각도는 10° 격자에서 스텝별 최소
- 손실: CE(시작) + CE(끝) + BCE(구간 안 각도 비율) + β · J/J_ST (부드러운 게이트, 1:1)
- 입력·분할은 train_tide_policy.py 와 같음 (lookback 타깃만 3채널: net_ST, P_ST, D_ST)

출력: tide_policy/out_window/{best.pt, scaler.json, history.json, summary.json}
사용: python bipv_mismatch/tide_policy/train_tide_window.py
"""

import argparse
import copy
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import train_tide_policy as T  # noqa: E402

T.OUT_DIR = HERE / "out_window"
T.LOOKBACK_COLS = ["net_st", "pv_st", "dem_st"]  # 출력 3채널을 위해 lookback 타깃도 3채널
K = 18
A10 = np.arange(0, 91, 10)


def bounds(sur):
    """(N, 144) 잉여 → s0, s1 (잉여 없는 날 -1)"""
    has = sur.any(1)
    s0 = np.where(has, sur.argmax(1), -1)
    s1 = np.where(has, sur.shape[1] - sur[:, ::-1].argmax(1), -1)
    return s0, s1


def theta_lo(th_st):
    return np.minimum(th_st + 10.0, 90.0) if isinstance(th_st, np.ndarray) else torch.clamp(th_st + 10.0, max=90.0)


def oracle(ds):
    """날짜별 정답 a*, b*, 구간 안 최적 각도 (N, 144)"""
    steps = np.stack([np.arange(s, s + T.DAY) for s in ds.idx])
    P, D, st = ds.P[steps], ds.D[steps], ds.theta_st[steps]
    c = np.abs(P - D)                                            # (N, 144, 10)
    c_st = np.take_along_axis(c, np.rint(st / 10).astype(int)[..., None], -1)[..., 0]
    lo = theta_lo(st)
    c_in_all = np.where(A10[None, None] >= lo[..., None] - 1e-6, c, np.inf)
    best_in = A10[c_in_all.argmin(-1)].astype(np.float32)
    c_in = c_in_all.min(-1)
    s0, s1 = bounds(ds.sur)
    a_star, b_star = np.zeros(len(ds), int), np.zeros(len(ds), int)
    for n in range(len(ds)):
        if s0[n] < 0:
            continue
        d = c_in[n] - c_st[n]                                     # 구간에 넣을 때 늘어나는 비용
        pre = np.array([d[max(s0[n] - a, 0):s0[n]].sum() for a in range(K + 1)])
        post = np.array([d[s1[n]:min(s1[n] + b, T.DAY)].sum() for b in range(K + 1)])
        a_star[n], b_star[n] = pre.argmin(), post.argmin()
    return a_star, b_star, best_in, s0, s1


class WinDataset(torch.utils.data.Dataset):
    def __init__(self, ds):
        self.ds = ds
        self.a, self.b, self.best, self.s0, self.s1 = oracle(ds)

    def __len__(self):
        return len(self.ds)

    def __getitem__(self, i):
        lb, pc, fc, P, D, th_st, _ = self.ds[i]
        return lb, pc, fc, P, D, th_st, torch.from_numpy(self.best[i]), *map(torch.tensor, (
            self.s0[i], self.s1[i], self.a[i], self.b[i]))


def heads(out, th_st, s0, s1):
    """TiDE 출력 → 구간 안 각도 θ_in, 시작·끝 로짓 (B, K+1), 유효 날짜 mask"""
    lo = theta_lo(th_st)
    th_in = lo + (90.0 - lo) * torch.sigmoid(out[..., 0])
    ok = s0 >= 0
    ar = torch.arange(K + 1, device=out.device)
    i_pre = (s0[:, None] - ar).clamp(0, T.DAY - 1)                 # a = 0..K 의 시작 스텝
    i_post = (s1[:, None] - 1 + ar).clamp(0, T.DAY - 1)           # b = 0..K 의 마지막 스텝
    lg_a = out[..., 1].gather(1, i_pre)
    lg_b = out[..., 2].gather(1, i_post)
    lg_a = lg_a.masked_fill((s0[:, None] - ar) < 0, -1e4)
    lg_b = lg_b.masked_fill((s1[:, None] - 1 + ar) > T.DAY - 1, -1e4)
    return th_in, lg_a, lg_b, ok


def gate(p_a, p_b, s0, s1):
    """시작·끝 확률 → 게이트 g (B, 144): P(t ∈ 구간)"""
    t = torch.arange(T.DAY, device=p_a.device)[None]
    ar = torch.arange(K + 1, device=p_a.device)[None]
    # t 가 구간 안 ⇔ s0 − a ≤ t  그리고  t < s1 + b
    in_pre = ((s0[:, None, None] - ar[:, :, None]) <= t[:, None, :]).float()   # (B, K+1, 144)
    in_post = (t[:, None, :] < (s1[:, None, None] + ar[:, :, None])).float()
    g_pre = (p_a[..., None] * in_pre).sum(1)
    g_post = (p_b[..., None] * in_post).sum(1)
    return g_pre * g_post


def hard_theta(out, th_st, s0, s1):
    th_in, lg_a, lg_b, ok = heads(out, th_st, s0, s1)
    a, b = lg_a.argmax(1), lg_b.argmax(1)
    t = torch.arange(T.DAY, device=out.device)[None]
    win = ok[:, None] & (t >= (s0 - a)[:, None]) & (t < (s1 + b)[:, None])
    return torch.where(win, th_in, th_st), win, a, b


def run_epoch(model, loader, device, args, opt=None):
    train = opt is not None
    model.train(train)
    tot, n = 0.0, 0
    with torch.set_grad_enabled(train):
        for batch in loader:
            lb, pc, fc, P, D, th_st, best, s0, s1, a_t, b_t = (t.to(device) for t in batch)
            out = model(lb, pc, fc)
            th_in, lg_a, lg_b, ok = heads(out, th_st, s0, s1)
            okf = ok.float()
            ce = ((F.cross_entropy(lg_a, a_t, reduction="none") + F.cross_entropy(lg_b, b_t, reduction="none"))
                  * okf).sum() / okf.sum().clamp(min=1)
            t = torch.arange(T.DAY, device=device)[None]
            win_t = ok[:, None] & (t >= (s0 - a_t)[:, None]) & (t < (s1 + b_t)[:, None])
            lo = theta_lo(th_st)
            r = ((best - lo) / (90.0 - lo).clamp(min=1e-6)).clamp(0, 1)
            bce = (F.binary_cross_entropy_with_logits(out[..., 0], r, reduction="none") * win_t).sum() \
                / win_t.sum().clamp(min=1)
            g = gate(lg_a.softmax(1), lg_b.softmax(1), s0, s1) * okf[:, None]
            theta = th_st + g * (th_in - th_st)
            J, *_ = T.day_cost(theta, P, D, 1.0, 1.0, 0.0, args.smooth if train else None)
            J_st, *_ = T.day_cost(th_st, P, D, 1.0, 1.0, 0.0)
            loss = ce + bce + args.beta * (J / J_st.clamp(min=1e-3)).mean()
            if train:
                opt.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()
            tot += loss.item() * len(lb)
            n += len(lb)
    return tot / n


@torch.no_grad()
def rollout(model, wds, device):
    """평가용 hard 각도 (N, 144, 연속값), 구간 (N, 144), a, b"""
    model.eval()
    th, wn, aa, bb = [], [], [], []
    for batch in DataLoader(wds, batch_size=64):
        lb, pc, fc, P, D, th_st, best, s0, s1, *_ = (t.to(device) for t in batch)
        x, w, a, b = hard_theta(model(lb, pc, fc), th_st, s0, s1)
        th.append(x.cpu()), wn.append(w.cpu()), aa.append(a.cpu()), bb.append(b.cpu())
    return torch.cat(th).numpy(), torch.cat(wn).numpy(), torch.cat(aa).numpy(), torch.cat(bb).numpy()


def round10(th, win, th_st):
    """E+ 용 10° 반올림, 구간 안은 θ_ST + 10 이상 유지"""
    return np.where(win, np.maximum(np.rint(th / 10) * 10, theta_lo(th_st)), th_st)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--beta", type=float, default=0.2)
    ap.add_argument("--smooth", type=float, default=50.0)
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--batch_size", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--hidden_dim", type=int, default=256)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    args.w_sur, args.lam_move, args.k_dilate = 1.0, 0.0, K

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    T.OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[*] device {device} | β {args.beta} | 구간 앞뒤 최대 {K * 10}분 | 1:1")
    raw = {n: T.load_split(n) for n in ["train", "val", "test"]}
    scaler = T.fit_scaler(raw["train"][0])
    dss = {n: T.DayDataset(df, P, D, scaler, 0) for n, (df, P, D) in raw.items()}
    wds = {n: WinDataset(d) for n, d in dss.items()}
    (T.OUT_DIR / "scaler.json").write_text(json.dumps(scaler, indent=2), encoding="utf-8")
    for n, w in wds.items():
        ok = w.s0 >= 0
        print(f"[*] {n}: 날짜 {len(w)}, 잉여 있는 날 {ok.sum()}, 정답 앞 구간 평균 {w.a[ok].mean() * 10:.0f}분 "
              f"(0분 {np.mean(w.a[ok] == 0):.0%}, {K * 10}분 {np.mean(w.a[ok] == K):.0%}), "
              f"뒤 구간 평균 {w.b[ok].mean() * 10:.0f}분 (0분 {np.mean(w.b[ok] == 0):.0%}, {K * 10}분 {np.mean(w.b[ok] == K):.0%})")

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    model = T.build_model(args).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs, eta_min=1e-5)
    tr_ld = DataLoader(wds["train"], batch_size=args.batch_size, shuffle=True)
    va_ld = DataLoader(wds["val"], batch_size=64)
    best, best_state, hist = (np.inf, 0), None, []
    for ep in range(1, args.epochs + 1):
        t = time.time()
        tr = run_epoch(model, tr_ld, device, args, opt)
        va = run_epoch(model, va_ld, device, args)
        sched.step()
        hist.append({"epoch": ep, "train": tr, "val": va})
        mark = ""
        if va < best[0]:
            best, best_state, mark = (va, ep), copy.deepcopy(model.state_dict()), " *"
        if ep == 1 or ep % 5 == 0 or mark:
            print(f"ep {ep:3d} | train {tr:.5f} | val {va:.5f} | {time.time() - t:4.1f}s{mark}", flush=True)
    model.load_state_dict(best_state)
    torch.save({"epoch": best[1], "model_state_dict": best_state, "args": vars(args)}, T.OUT_DIR / "best.pt")

    summary = {"args": vars(args)}
    for name in ["train", "val", "test"]:
        ds, w = dss[name], wds[name]
        steps = np.stack([np.arange(s, s + T.DAY) for s in ds.idx])
        st = ds.theta_st[steps]
        th, win, a, b = rollout(model, w, device)
        t = np.arange(T.DAY)[None]
        win_o = (w.s0 >= 0)[:, None] & (t >= (w.s0 - w.a)[:, None]) & (t < (w.s1 + w.b)[:, None])
        pol = T.baselines(ds)
        pol["구간 정답"] = np.where(win_o, w.best, st)
        pol["TiDE 구간학습"] = th
        pol["TiDE 구간학습(10°)"] = round10(th, win, st)
        tab = T.summarize(pol, ds, 1.0, args)
        ok = w.s0 >= 0
        summary[name] = {"table": tab.round(3).to_dict(orient="index"),
                         "앞 구간 평균 분 (정답, TiDE)": [float(w.a[ok].mean() * 10), float(a[ok].mean() * 10)],
                         "뒤 구간 평균 분 (정답, TiDE)": [float(w.b[ok].mean() * 10), float(b[ok].mean() * 10)]}
        print(f"\n===== {name} 겨울 평일 합계 (kWh, case2, 07~07시) =====\n{tab.round(2).to_string()}")
        print(f"앞 구간 평균 정답 {w.a[ok].mean() * 10:.0f}분 / TiDE {a[ok].mean() * 10:.0f}분, "
              f"뒤 구간 평균 정답 {w.b[ok].mean() * 10:.0f}분 / TiDE {b[ok].mean() * 10:.0f}분")
    (T.OUT_DIR / "history.json").write_text(json.dumps({"best_epoch": best[1], "history": hist}, indent=2), encoding="utf-8")
    (T.OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[*] {T.OUT_DIR / 'best.pt'}")


if __name__ == "__main__":
    main()
