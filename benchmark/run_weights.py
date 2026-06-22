from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "backend"))

from benchmark.run_comparison import OUTPUT_DIR, _write_csv
from benchmark._sweep import run_env_sweep, significance_fields, summary_fields

# alternative soft-weight profiles
PROFILES: dict[str, dict[str, str]] = {
    "preference": {"BENCH_W_S1": "30"},
    "fairness": {"BENCH_W_S4": "9", "BENCH_W_S5": "9", "BENCH_W_S6": "6"},
}
# "medium" is the cleanest weight-sensitivity test (both feasible)
SWEEP_SIZES: tuple[str, ...] = ("medium",)


def main() -> None:
    summary_rows, signif_rows = run_env_sweep(PROFILES, SWEEP_SIZES, "profile")
    _write_csv(OUTPUT_DIR / "weights_summary.csv", summary_fields("profile"), summary_rows)
    _write_csv(OUTPUT_DIR / "weights_significance.csv", significance_fields("profile"), signif_rows)
    print("Done. Weight-sweep results in benchmark/data/weights_summary.csv, weights_significance.csv")


if __name__ == "__main__":
    main()
