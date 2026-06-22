from __future__ import annotations

import csv
import json
import pathlib
import statistics
import sys
import time as _time_module
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from random import Random

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "backend"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import wilcoxon

from app.optimization.cpsat import CPSATConfig, CPSATResult, run_cpsat
from app.optimization.evaluate import (
    Assignment,
    EvaluationResult,
    ScheduleContext,
    shift_duration_hours,
)
from app.optimization.ga import GAConfig, run_ga
from app.optimization.weights import STANDARD_WEEKLY_HOURS

from benchmark.instance import (
    SIZE_SPECS,
    SizeSpec,
    build_instance,
)

WALL_CLOCK_BUDGET = 400.0
# both algorithms get the same 400s ceiling
GA_NO_EARLY_STOP = 10**9
SEEDS = tuple(range(1, 21))  # 20 seeds per cell
ALGORITHMS = ("GA", "CP-SAT")
SNAPSHOTS = (30.0, 120.0, 400.0)

GA_COLOR = "#1f77b4"
CPSAT_COLOR = "#ff7f0e"
TRACE_GREY = "#bbbbbb"
PERFECT_PREFERENCE_RATE = 100.0

BENCH_DIR = pathlib.Path(__file__).parent
OUTPUT_DIR = BENCH_DIR / "data"
CURVES_DIR = BENCH_DIR / "curves"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

Trace = list[tuple[float, float, bool]]


@dataclass
class RunRecord:
    size: str
    seed: int
    algorithm: str
    execution_time: float
    feasible: bool
    hard_violations: int
    hard_per_constraint: dict[str, int]
    soft_violations: dict[str, int]
    soft_penalty: float
    objective_f: float
    preference_satisfaction_rate: float
    load_balance_stddev: float
    optimality_gap: float | None
    cpsat_status: str | None
    convergence_trace: Trace


def _count_total_preferences(ctx: ScheduleContext) -> int:
    total = 0
    days = _period_days(ctx)
    for emp in ctx.employees:
        preferred_off = ctx.employee_preferences.get(emp.id, frozenset())
        if not preferred_off:
            continue
        total += sum(1 for day in days if day.weekday() in preferred_off)
    return total


def _period_days(ctx: ScheduleContext) -> list[date]:
    span = (ctx.period_end - ctx.period_start).days
    return [ctx.period_start + timedelta(days=offset) for offset in range(span + 1)]


def _preference_satisfaction_rate(ctx: ScheduleContext, result: EvaluationResult) -> float:
    total = _count_total_preferences(ctx)
    if total == 0:
        return PERFECT_PREFERENCE_RATE
    return (total - result.s1) / total * 100.0


def _load_balance_stddev(ctx: ScheduleContext, assignments: list[Assignment]) -> float:
    duration_by_id = {st.id: shift_duration_hours(st) for st in ctx.shift_types}
    worked: dict[int, float] = {emp.id: 0.0 for emp in ctx.employees}
    for a in assignments:
        if a.shift_type_id is not None:
            worked[a.employee_id] += duration_by_id[a.shift_type_id]

    m_period = sum(ctx.monthly_norms.values())
    deviations = [
        worked[emp.id] - m_period * (emp.hours_per_week / STANDARD_WEEKLY_HOURS)
        for emp in ctx.employees
    ]
    if len(deviations) < 2:
        return 0.0
    return statistics.stdev(deviations)


def _compute_optimality_gap(
    soft_penalty: float, best_penalty_bound: float | None
) -> float | None:
    if best_penalty_bound is None:
        return None
    
    if soft_penalty == 0.0:
        return 0.0
    return (soft_penalty - best_penalty_bound) / soft_penalty


def _make_trace_collector() -> tuple[Trace, object]:
    trace: Trace = []

    def callback(elapsed: float, fitness: float, is_feasible: bool) -> None:
        trace.append((elapsed, fitness, is_feasible))

    return trace, callback


def _run_one(size: str, seed: int, algorithm: str) -> RunRecord:
    ctx = build_instance(size, seed)
    trace, callback = _make_trace_collector()

    t0 = _time_module.perf_counter()
    if algorithm == "GA":
        config = GAConfig(
            wall_clock_limit=WALL_CLOCK_BUDGET,
            convergence_patience=GA_NO_EARLY_STOP,
            max_generations=GA_NO_EARLY_STOP,
        )
        result, assignments = run_ga(ctx, config, Random(seed), callback)
        optimality_gap: float | None = None
        cpsat_status: str | None = None
    else:
        cp_config = CPSATConfig(time_limit_seconds=WALL_CLOCK_BUDGET, num_workers=1)
        cpsat_result: CPSATResult = run_cpsat(ctx, cp_config, callback)
        result, assignments = cpsat_result.evaluation, cpsat_result.assignments
        optimality_gap = _compute_optimality_gap(
            result.soft_penalty, cpsat_result.best_penalty_bound
        )
        cpsat_status = cpsat_result.status_name
    execution_time = _time_module.perf_counter() - t0

    return RunRecord(
        size=size,
        seed=seed,
        algorithm=algorithm,
        execution_time=execution_time,
        feasible=result.is_feasible,
        hard_violations=result.hard_total,
        hard_per_constraint={
            "h1": result.h1, "h2": result.h2, "h3": result.h3,
            "h4": result.h4, "h5": result.h5, "h6": result.h6,
            "h7": result.h7, "h8": result.h8, "h9": result.h9,
        },
        soft_violations={
            "s1": result.s1, "s2": result.s2, "s3": result.s3,
            "s4": result.s4, "s5": result.s5,
        },
        soft_penalty=result.soft_penalty,
        objective_f=result.fitness,
        preference_satisfaction_rate=_preference_satisfaction_rate(ctx, result),
        load_balance_stddev=_load_balance_stddev(ctx, assignments),
        optimality_gap=optimality_gap,
        cpsat_status=cpsat_status,
        convergence_trace=trace,
    )


def _best_feasible_objective_by(trace: Trace, budget: float) -> float | None:
    feasible = [
        fitness
        for elapsed, fitness, is_feasible in trace
        if elapsed <= budget and is_feasible
    ]
    return max(feasible) if feasible else None


def run_all() -> list[RunRecord]:
    records: list[RunRecord] = []
    for spec in SIZE_SPECS:
        for seed in SEEDS:
            for algorithm in ALGORITHMS:
                print(f"Running {spec.name}/{algorithm} seed={seed} ...", end="", flush=True)
                record = _run_one(spec.name, seed, algorithm)
                print(
                    f"  done in {record.execution_time:.1f}s"
                    f"  feasible={record.feasible}"
                    f"  F={record.objective_f:.1f}"
                )
                records.append(record)
    return records


def write_results_json(records: list[RunRecord]) -> None:
    payload = {"runs": [asdict(r) for r in records]}
    with (OUTPUT_DIR / "results.json").open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


def _records_for(records: list[RunRecord], size: str, algorithm: str) -> list[RunRecord]:
    return [r for r in records if r.size == size and r.algorithm == algorithm]


def write_summary_csv(records: list[RunRecord]) -> None:
    rows: list[dict[str, object]] = []
    for spec in SIZE_SPECS:
        for algorithm in ALGORITHMS:
            group = _records_for(records, spec.name, algorithm)
            for budget in SNAPSHOTS:
                objectives = [
                    obj
                    for r in group
                    if (obj := _best_feasible_objective_by(r.convergence_trace, budget)) is not None
                ]
                rows.append(_summary_row(spec.name, algorithm, budget, group, objectives))

    fields = [
        "size", "algorithm", "budget_s", "n_feasible", "mean_objective", "std_objective",
        "min_objective", "max_objective", "mean_time", "feasibility_rate",
        "mean_pref_sat", "mean_load_stddev",
    ]
    _write_csv(OUTPUT_DIR / "summary.csv", fields, rows)


def _summary_row(
    size: str,
    algorithm: str,
    budget: float,
    group: list[RunRecord],
    objectives: list[float],
) -> dict[str, object]:
    # objectives has one entry per run feasible by this budget so its length is the per-budget feasible count and the denominator for the stats
    feasibility_rate = len(objectives) / len(group) if group else 0.0
    # secondary metrics are quality measures, averaged over feasible runs only
    feasible_runs = [r for r in group if r.feasible]
    return {
        "size": size,
        "algorithm": algorithm,
        "budget_s": budget,
        "n_feasible": len(objectives),
        "mean_objective": statistics.mean(objectives) if objectives else None,
        "std_objective": statistics.stdev(objectives) if len(objectives) > 1 else None,
        "min_objective": min(objectives) if objectives else None,
        "max_objective": max(objectives) if objectives else None,
        "mean_time": statistics.mean(r.execution_time for r in group) if group else None,
        "feasibility_rate": feasibility_rate,
        "mean_pref_sat": statistics.mean(r.preference_satisfaction_rate for r in feasible_runs)
        if feasible_runs else None,
        "mean_load_stddev": statistics.mean(r.load_balance_stddev for r in feasible_runs)
        if feasible_runs else None,
    }


def write_significance_csv(records: list[RunRecord]) -> None:
    rows: list[dict[str, object]] = []
    for spec in SIZE_SPECS:
        ga_group = _records_for(records, spec.name, "GA")
        cpsat_group = _records_for(records, spec.name, "CP-SAT")
        ga_by_seed = {r.seed: r for r in ga_group}
        cpsat_by_seed = {r.seed: r for r in cpsat_group}
        paired_seeds = sorted(set(ga_by_seed) & set(cpsat_by_seed))

        for budget in SNAPSHOTS:
            ga_obj: list[float] = []
            cpsat_obj: list[float] = []
            for seed in paired_seeds:
                ga_val = _best_feasible_objective_by(ga_by_seed[seed].convergence_trace, budget)
                cp_val = _best_feasible_objective_by(cpsat_by_seed[seed].convergence_trace, budget)
                # pair only when BOTH are feasible by this budget
                if ga_val is not None and cp_val is not None:
                    ga_obj.append(ga_val)
                    cpsat_obj.append(cp_val)
            rows.append(_significance_row(spec.name, budget, ga_obj, cpsat_obj))

    fields = [
        "size", "budget_s", "n_pairs", "ga_mean", "cpsat_mean",
        "mean_diff", "median_diff", "rank_biserial", "ci95_low", "ci95_high",
        "wilcoxon_statistic", "p_value",
    ]
    _write_csv(OUTPUT_DIR / "significance.csv", fields, rows)


def _significance_row(
    size: str, budget: float, ga_obj: list[float], cpsat_obj: list[float]
) -> dict[str, object]:
    stat, p_value = _wilcoxon(ga_obj, cpsat_obj)
    diff = _paired_diff_stats(ga_obj, cpsat_obj)
    return {
        "size": size,
        "budget_s": budget,
        "n_pairs": len(ga_obj),
        "ga_mean": statistics.mean(ga_obj) if ga_obj else None,
        "cpsat_mean": statistics.mean(cpsat_obj) if cpsat_obj else None,
        "mean_diff": diff["mean_diff"],
        "median_diff": diff["median_diff"],
        "rank_biserial": diff["rank_biserial"],
        "ci95_low": diff["ci95_low"],
        "ci95_high": diff["ci95_high"],
        "wilcoxon_statistic": stat,
        "p_value": p_value,
    }


def _wilcoxon(
    ga_obj: list[float], cpsat_obj: list[float]
) -> tuple[float | None, float]:
    if len(ga_obj) < 2 or len(cpsat_obj) < 2:
        return None, 1.0
    if len(ga_obj) == len(cpsat_obj) and all(g == c for g, c in zip(ga_obj, cpsat_obj)):
        return 0.0, 1.0
    stat, p_value = wilcoxon(ga_obj, cpsat_obj)
    return float(stat), float(p_value)


def _rank_biserial(diffs: list[float]) -> float:
    nonzero = [d for d in diffs if d != 0.0]
    if not nonzero:
        return 0.0
    order = sorted(range(len(nonzero)), key=lambda i: abs(nonzero[i]))
    ranks = [0.0] * len(nonzero)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and abs(nonzero[order[j + 1]]) == abs(nonzero[order[i]]):
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0  # mean of the 1-based ranks i+1 .. j+1
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    w_pos = sum(rank for d, rank in zip(nonzero, ranks) if d > 0)
    w_neg = sum(rank for d, rank in zip(nonzero, ranks) if d < 0)
    total = w_pos + w_neg
    return (w_pos - w_neg) / total if total else 0.0


def _bootstrap_mean_ci(
    diffs: list[float], resamples: int = 5000, alpha: float = 0.05
) -> tuple[float, float]:
    rng = Random(20260618)
    n = len(diffs)
    means = sorted(
        sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(resamples)
    )
    lo = means[int((alpha / 2.0) * resamples)]
    hi = means[min(resamples - 1, int((1.0 - alpha / 2.0) * resamples))]
    return lo, hi


def _paired_diff_stats(
    ga_obj: list[float], cpsat_obj: list[float]
) -> dict[str, float | None]:
    if len(ga_obj) < 2 or len(ga_obj) != len(cpsat_obj):
        return {
            "mean_diff": None, "median_diff": None, "rank_biserial": None,
            "ci95_low": None, "ci95_high": None,
        }
    diffs = [g - c for g, c in zip(ga_obj, cpsat_obj)]
    lo, hi = _bootstrap_mean_ci(diffs)
    return {
        "mean_diff": statistics.mean(diffs),
        "median_diff": statistics.median(diffs),
        "rank_biserial": _rank_biserial(diffs),
        "ci95_low": lo,
        "ci95_high": hi,
    }


CPSAT_STATUSES = ("OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN")


def write_cpsat_status_csv(records: list[RunRecord]) -> None:
    rows = [
        _cpsat_status_row(spec.name, _records_for(records, spec.name, "CP-SAT"))
        for spec in SIZE_SPECS
    ]
    fields = [
        "size", "n_runs", "optimal", "feasible", "infeasible", "unknown", "other",
        "proven_optimal_rate", "mean_optimality_gap",
    ]
    _write_csv(OUTPUT_DIR / "cpsat_status.csv", fields, rows)


def _cpsat_status_row(size: str, group: list[RunRecord]) -> dict[str, object]:
    counts = {status: 0 for status in CPSAT_STATUSES}
    other = 0
    for r in group:
        if r.cpsat_status in counts:
            counts[r.cpsat_status] += 1
        else:
            other += 1
    n = len(group)
    gaps = [r.optimality_gap for r in group if r.optimality_gap is not None]
    return {
        "size": size,
        "n_runs": n,
        "optimal": counts["OPTIMAL"],
        "feasible": counts["FEASIBLE"],
        "infeasible": counts["INFEASIBLE"],
        "unknown": counts["UNKNOWN"],
        "other": other,
        "proven_optimal_rate": counts["OPTIMAL"] / n if n else None,
        "mean_optimality_gap": statistics.mean(gaps) if gaps else None,
    }


# differential feasibility check when GA-feasible and CP-SAT-infeasible

VERDICT_CONTRADICTION = "CONTRADICTION"
VERDICT_GA_FOUND = "GA_FOUND_CPSAT_MISSED"


def _differential_rows(records: list[RunRecord]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for spec in SIZE_SPECS:
        ga_by_seed = {r.seed: r for r in _records_for(records, spec.name, "GA")}
        cpsat_by_seed = {r.seed: r for r in _records_for(records, spec.name, "CP-SAT")}
        for seed in sorted(set(ga_by_seed) & set(cpsat_by_seed)):
            ga_run = ga_by_seed[seed]
            cpsat_run = cpsat_by_seed[seed]
            if not ga_run.feasible or cpsat_run.feasible:
                continue
            verdict = (
                VERDICT_CONTRADICTION
                if cpsat_run.cpsat_status == "INFEASIBLE"
                else VERDICT_GA_FOUND
            )
            rows.append(
                {
                    "size": spec.name,
                    "seed": seed,
                    "cpsat_status": cpsat_run.cpsat_status,
                    "ga_hard_violations": ga_run.hard_violations,
                    "cpsat_hard_violations": cpsat_run.hard_violations,
                    "verdict": verdict,
                }
            )
    return rows


def write_differential_csv(records: list[RunRecord]) -> None:
    rows = _differential_rows(records)
    fields = [
        "size", "seed", "cpsat_status",
        "ga_hard_violations", "cpsat_hard_violations", "verdict",
    ]
    _write_csv(OUTPUT_DIR / "differential.csv", fields, rows)
    _report_differential(rows)


def _report_differential(rows: list[dict[str, object]]) -> None:
    if not rows:
        print("  no GA-feasible / CP-SAT-infeasible cases")
        return
    contradictions = [r for r in rows if r["verdict"] == VERDICT_CONTRADICTION]
    ga_wins = [r for r in rows if r["verdict"] == VERDICT_GA_FOUND]
    print(
        f"  {len(rows)} case(s): {len(contradictions)} CONTRADICTION, "
        f"{len(ga_wins)} GA_FOUND_CPSAT_MISSED"
    )
    for r in contradictions:
        print(
            f"  !! CONTRADICTION {r['size']}/seed={r['seed']}: GA feasible but "
            f"CP-SAT status={r['cpsat_status']} (CP-SAT hard violations="
            f"{r['cpsat_hard_violations']}). Check the CP-SAT model or evaluate_schedule()."
        )


def _cumulative_best(trace: Trace) -> tuple[list[float], list[float]]:
    times: list[float] = []
    best_values: list[float] = []
    running_best = float("-inf")
    for elapsed, fitness, _ in sorted(trace, key=lambda t: t[0]):
        running_best = max(running_best, fitness)
        times.append(elapsed)
        best_values.append(running_best)
    return times, best_values


def _step_value_at(times: list[float], best_values: list[float], moment: float) -> float | None:
    visible = [value for t, value in zip(times, best_values) if t <= moment]
    return visible[-1] if visible else None


def _median_curve(traces: list[Trace], grid: list[float]) -> list[float | None]:
    per_trace = [_cumulative_best(t) for t in traces]
    median: list[float | None] = []
    for moment in grid:
        values = [
            value
            for times, best_values in per_trace
            if (value := _step_value_at(times, best_values, moment)) is not None
        ]
        median.append(statistics.median(values) if values else None)
    return median


def _plot_curves(records: list[RunRecord]) -> None:
    CURVES_DIR.mkdir(parents=True, exist_ok=True)
    grid = [WALL_CLOCK_BUDGET * i / 200 for i in range(201)]
    for spec in SIZE_SPECS:
        for algorithm in ALGORITHMS:
            group = _records_for(records, spec.name, algorithm)
            _plot_one(spec, algorithm, group, grid)


def _plot_one(spec: SizeSpec, algorithm: str, group: list[RunRecord], grid: list[float]) -> None:
    color = GA_COLOR if algorithm == "GA" else CPSAT_COLOR
    fig, ax = plt.subplots(figsize=(8, 5))

    traces = [r.convergence_trace for r in group]
    for trace in traces:
        times, best_values = _cumulative_best(trace)
        if times:
            ax.step(times, best_values, where="post", color=TRACE_GREY, linewidth=0.8)

    median = _median_curve(traces, grid)
    median_grid = [t for t, value in zip(grid, median) if value is not None]
    median_values = [value for value in median if value is not None]
    if median_values:
        ax.step(
            median_grid, median_values, where="post",
            color=color, linewidth=2.0, label="median",
        )


    feasible_values = [f for trace in traces for _, f, is_feasible in trace if is_feasible]
    if feasible_values:
        lo, hi = min(feasible_values), max(feasible_values)
        pad = max((hi - lo) * 0.05, 1.0)
        ax.set_ylim(lo - pad, hi + pad)

    ax.set_xlim(0, WALL_CLOCK_BUDGET)
    ax.set_title(f"{algorithm} — {spec.name.capitalize()} ({spec.n_employees} employees)")
    ax.set_xlabel("Elapsed (s)")
    ax.set_ylabel("Best objective (F)")
    if median_values:  # only a drawn median line carries a label
        ax.legend(loc="lower right")
    fig.tight_layout()

    filename = f"{spec.name}_{_algo_slug(algorithm)}.png"
    fig.savefig(CURVES_DIR / filename, dpi=120)
    plt.close(fig)


def _algo_slug(algorithm: str) -> str:
    return "ga" if algorithm == "GA" else "cpsat"


def _write_csv(path: pathlib.Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    records = run_all()

    print("Writing results.json ...")
    write_results_json(records)
    print("Writing summary.csv ...")
    write_summary_csv(records)
    print("Writing significance.csv ...")
    write_significance_csv(records)
    print("Writing cpsat_status.csv ...")
    write_cpsat_status_csv(records)
    print("Writing differential.csv ...")
    write_differential_csv(records)
    print("Plotting curves ...")
    _plot_curves(records)
    print("Done. Results in benchmark/data/ and curves in benchmark/curves/")


if __name__ == "__main__":
    main()
