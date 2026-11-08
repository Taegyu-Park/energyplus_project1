"""
bipv_mismatch/tide_policy/train_tide_policy_free.py
===================================================
train_tide_policy.py 변형 (원본은 그대로 두고 불러와서 바꿈, 2026-11-02 사용자 지적 반영):
- 태양추적을 벗어나는 구간 = 태양추적 잉여 스텝 그대로 (확장 없음, k_dilate = 0)
- 그 구간 안에서 각도는 50~90° 아무 값: θ = LO + (90 − LO)·sigmoid(z), 구간 밖은 θ_ST
- 각도 이동 벌점 없음 (λ_move = 0): 버퍼 개수·90° 유지 강제 없음
- 출력: tide_policy/out_free/ (원본 out/ 과 같은 파일 구성)

사용: python bipv_mismatch/tide_policy/train_tide_policy_free.py --weights 1.0,3.0 --week_split train
"""

import sys
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import train_tide_policy as T  # noqa: E402

LO = 50.0
T.OUT_DIR = HERE / "out_free"


def to_theta(z, theta_st, mask):
    lo = torch.clamp(theta_st, min=LO)
    theta = lo + (90.0 - lo) * torch.sigmoid(z.squeeze(-1))
    return torch.where(mask, theta, theta_st)


T.to_theta = to_theta


if __name__ == "__main__":
    defaults = {"--lam_move": "0", "--k_dilate": "0"}
    argv = sys.argv[1:]
    for k, v in defaults.items():
        if k not in argv:
            argv += [k, v]
    sys.argv = [sys.argv[0]] + argv
    T.main()
