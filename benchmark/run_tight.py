from __future__ import annotations

import json
import pathlib
import sys
from dataclasses import asdict

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "backend"))

from benchmark.instance import TIGHT_SPEC
from benchmark.run_comparison import (
    ALGORITHMS,
    CURVES_DIR,
    OUTPUT_DIR,
    SEEDS,
    SNAPSHOTS,
    WALL_CLOCK_BUDGET,
    RunRecord,
    _best_feasible_objective_by,
    _plot_one,
    _records_for,
    _run_one,
    _significance_row,
    _summary_row,
    _write_csv,
)

SUMMARY_FIELDS = [
    "size", "algorithm", "budget_s", "n_feasible", "mean_objective", "std_objective",
    "min_objective", "max_objective", "mean_time", "feasibility_rate",
    "mean_pref_sat", "mean_load_stddev",
]
SIGNIFICANCE_FIELDS = [
    "size", "budget_s", "n_pairs", "ga_mean", "cpsat_mean",
    "mean_diff", "median_diff", "rank_biserial", "ci95_low", "ci95_high",
    "wilcoxon_statistic", "p_value",
]


def run_tight() -> list[RunRecord]:
    records: list[RunRecord] = []
    for seed in SEEDS:
        for algorithm in ALGORITHMS:
            print(f"Running tight/{algorithm} seed={seed} ...", end="", flush=True)
            record = _run_one(TIGHT_SPEC.name, seed, algorithm)
            print(
                f"  done in {record.execution_time:.1f}s"
                f"  feasible={record.feasible}"
                f"  F={record.objective_f:.1f}"
            )
            records.append(record)
    return records


def _summary_rows(records: list[RunRecord]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for algorithm in ALGORITHMS:
        group = _records_for(records, TIGHT_SPEC.name, algorithm)
        for budget in SNAPSHOTS:
            objectives = [
                obj
                for r in group
                if (obj := _best_feasible_objective_by(r.convergence_trace, budget)) is not None
            ]
            rows.append(_summary_row(TIGHT_SPEC.name, algorithm, budget, group, objectives))
    return rows


def _significance_rows(records: list[RunRecord]) -> list[dict[str, object]]:
    ga_by_seed = {r.seed: r for r in _records_for(records, TIGHT_SPEC.name, "GA")}
    cp_by_seed = {r.seed: r for r in _records_for(records, TIGHT_SPEC.name, "CP-SAT")}
    paired_seeds = sorted(set(ga_by_seed) & set(cp_by_seed))
    rows: list[dict[str, object]] = []
    for budget in SNAPSHOTS:
        ga_obj: list[float] = []
        cp_obj: list[float] = []
        for seed in paired_seeds:
            gv = _best_feasible_objective_by(ga_by_seed[seed].convergence_trace, budget)
            cv = _best_feasible_objective_by(cp_by_seed[seed].convergence_trace, budget)
            # pair only when both are feasible by this budget
            if gv is not None and cv is not None:
                ga_obj.append(gv)
                cp_obj.append(cv)
        rows.append(_significance_row(TIGHT_SPEC.name, budget, ga_obj, cp_obj))
    return rows


def write_tight_outputs(records: list[RunRecord]) -> None:
    with (OUTPUT_DIR / "tight_results.json").open("w", encoding="utf-8") as fh:
        json.dump({"runs": [asdict(r) for r in records]}, fh, indent=2)
    _write_csv(OUTPUT_DIR / "tight_summary.csv", SUMMARY_FIELDS, _summary_rows(records))
    _write_csv(OUTPUT_DIR / "tight_significance.csv", SIGNIFICANCE_FIELDS, _significance_rows(records))


def write_tight_curves(records: list[RunRecord]) -> None:
    CURVES_DIR.mkdir(parents=True, exist_ok=True)
    grid = [WALL_CLOCK_BUDGET * i / 200 for i in range(201)]
    for algorithm in ALGORITHMS:
        group = _records_for(records, TIGHT_SPEC.name, algorithm)
        _plot_one(TIGHT_SPEC, algorithm, group, grid)


def main() -> None:
    records = run_tight()
    print("Writing tight_results.json, tight_summary.csv, tight_significance.csv ...")
    write_tight_outputs(records)
    print("Plotting tight convergence curves ...")
    write_tight_curves(records)
    print("Done. Tight-variant results in benchmark/data/ and benchmark/curves/")


if __name__ == "__main__":
    main()
