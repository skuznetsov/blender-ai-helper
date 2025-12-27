import time

from ai_helper.solver import PointState, solve
from ai_helper.sketch.constraints import DistanceConstraint, HorizontalConstraint


def main() -> None:
    points = {}
    line_map = {}
    constraints = []

    prev = None
    for i in range(50):
        pid = f"p{i}"
        points[pid] = PointState(float(i), 0.5)
        if prev is not None:
            constraints.append(DistanceConstraint(id=f"d{i}", p1=prev, p2=pid, distance=1.0))
            line_map[f"l{i}"] = (prev, pid)
            constraints.append(HorizontalConstraint(id=f"h{i}", line=f"l{i}"))
        prev = pid

    start = time.perf_counter()
    diag = solve(points, constraints, line_map, max_iters=50, tolerance=1e-4, time_budget_ms=10.0)
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    print(f"elapsed_ms={elapsed_ms:.3f} iterations={diag.iterations} max_error={diag.max_error:.6f}")


if __name__ == "__main__":
    main()
