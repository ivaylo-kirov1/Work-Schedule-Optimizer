import os


def _weight_int(env_name: str, default: int) -> int:
    raw = os.getenv(env_name)
    return int(raw) if raw is not None else default


def _weight_float(env_name: str, default: float) -> float:
    raw = os.getenv(env_name)
    return float(raw) if raw is not None else default


# hard constraint penalty
ALPHA: int = 1_000_000

# BENCH_W_S only for sweep-only
W_S1: int = _weight_int("BENCH_W_S1", 10)
W_S2: float = _weight_float("BENCH_W_S2", 1.0)  # penalty per hour of undershoot below the under-utilization band
W_S3: int = _weight_int("BENCH_W_S3", 8)
W_S4: int = _weight_int("BENCH_W_S4", 3)
W_S5: int = _weight_int("BENCH_W_S5", 3)
W_S6: float = _weight_float("BENCH_W_S6", 2.0)  # penalty per hour of max-min worked-hours spread across employees

# constant feasibility anchor for the objective
BASE_SCORE: int = 10_000

#  law constants 
T_REST: int = 12
C_MAX: int = 5
OT_MAX: int = 0
DELTA_PER_MONTH: int = 8
N_MAX_NIGHT: int = 7
MAX_SHIFT_HOURS: int = 12
LONG_SHIFT_THRESHOLD: int = 8

STANDARD_WEEKLY_HOURS: float = 40.0
