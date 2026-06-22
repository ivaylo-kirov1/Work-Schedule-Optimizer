from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "backend"))

from benchmark.run_comparison import (
    ALGORITHMS,
    SNAPSHOTS,
    RunRecord,
    _best_feasible_objective_by,
    _records_for,
    _significance_row,
    _summary_row,
)

REPO_ROOT = pathlib.Path(__file__).parent.parent


def summary_fields(label_key: str) -> list[str]:
    return [
        label_key, "size", "algorithm", "budget_s", "n_feasible", "mean_objective",
        "std_objective", "min_objective", "max_objective", "mean_time",
        "feasibility_rate", "mean_pref_sat", "mean_load_stddev",
    ]


def significance_fields(label_key: str) -> list[str]:
    return [
        label_key, "size", "budget_s", "n_pairs", "ga_mean", "cpsat_mean",
        "mean_diff", "median_diff", "rank_biserial", "ci95_low", "ci95_high",
        "wilcoxon_statistic", "p_value",
    ]


def _run_profile_size(overrides: dict[str, str], size: str) -> list[RunRecord]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("BENCH_")}
    env.update(overrides)
    
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "records.json"
        subprocess.run(
            [sys.executable, "-m", "benchmark._sweep_worker", size, str(out)],
            env=env, check=True, cwd=str(REPO_ROOT),
        )
        payload = json.loads(out.read_text(encoding="utf-8"))
    return [RunRecord(**rec) for rec in payload["runs"]]


def _summary_rows(label_key, label_value, size, records):
    rows = []
    for algorithm in ALGORITHMS:
        group = _records_for(records, size, algorithm)
        for budget in SNAPSHOTS:
            objectives = [
                obj
                for r in group
                if (obj := _best_feasible_objective_by(r.convergence_trace, budget)) is not None
            ]
            rows.append({label_key: label_value, **_summary_row(size, algorithm, budget, group, objectives)})
    return rows


def _significance_rows(label_key, label_value, size, records):
    ga_by_seed = {r.seed: r for r in _records_for(records, size, "GA")}
    cp_by_seed = {r.seed: r for r in _records_for(records, size, "CP-SAT")}
    paired_seeds = sorted(set(ga_by_seed) & set(cp_by_seed))
    rows = []
    for budget in SNAPSHOTS:
        ga_obj, cp_obj = [], []
        for seed in paired_seeds:
            gv = _best_feasible_objective_by(ga_by_seed[seed].convergence_trace, budget)
            cv = _best_feasible_objective_by(cp_by_seed[seed].convergence_trace, budget)
            if gv is not None and cv is not None:
                ga_obj.append(gv)
                cp_obj.append(cv)
        rows.append({label_key: label_value, **_significance_row(size, budget, ga_obj, cp_obj)})
    return rows


def run_env_sweep(profiles: dict[str, dict[str, str]], sizes, label_key: str):
    summary_rows, signif_rows = [], []
    for name, overrides in profiles.items():
        for size in sizes:
            print(f"  {label_key}={name!r} / size={size!r} weights/env={overrides or 'baseline'}", flush=True)
            records = _run_profile_size(overrides, size)
            summary_rows += _summary_rows(label_key, name, size, records)
            signif_rows += _significance_rows(label_key, name, size, records)
    return summary_rows, signif_rows
