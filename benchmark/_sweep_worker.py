from __future__ import annotations

import json
import pathlib
import sys
from dataclasses import asdict

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "backend"))

from benchmark.run_comparison import ALGORITHMS, SEEDS, _run_one


def main() -> None:
    size = sys.argv[1]
    out_path = pathlib.Path(sys.argv[2])
    records = []
    for seed in SEEDS:
        for algorithm in ALGORITHMS:
            rec = _run_one(size, seed, algorithm)
            print(
                f"    {size}/{algorithm} seed={seed} {rec.execution_time:.0f}s "
                f"feasible={rec.feasible} F={rec.objective_f:.1f}",
                flush=True,
            )
            records.append(rec)
    out_path.write_text(
        json.dumps({"runs": [asdict(r) for r in records]}), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
