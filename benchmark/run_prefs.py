from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "backend"))

from benchmark.run_comparison import OUTPUT_DIR, _write_csv
from benchmark._sweep import run_env_sweep, significance_fields, summary_fields

# preference-density levels (baseline 0.30 comes from the grid)
DENSITIES: dict[str, dict[str, str]] = {
    "sparse_0.10": {"BENCH_PREF_PROB": "0.10"},
    "dense_0.50": {"BENCH_PREF_PROB": "0.50"},
}
SWEEP_SIZES: tuple[str, ...] = ("medium",)


def main() -> None:
    summary_rows, signif_rows = run_env_sweep(DENSITIES, SWEEP_SIZES, "density")
    _write_csv(OUTPUT_DIR / "prefs_summary.csv", summary_fields("density"), summary_rows)
    _write_csv(OUTPUT_DIR / "prefs_significance.csv", significance_fields("density"), signif_rows)
    print("Done. Preference-density results in benchmark/data/prefs_summary.csv, prefs_significance.csv")


if __name__ == "__main__":
    main()
