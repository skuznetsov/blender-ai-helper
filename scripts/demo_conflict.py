from ai_helper.solver import PointState, solve
from ai_helper.sketch.constraints import DistanceConstraint


def main() -> None:
    points = {
        "p1": PointState(0.0, 0.0, locked=True),
        "p2": PointState(5.0, 0.0),
    }

    constraints = [
        DistanceConstraint(id="d1", p1="p1", p2="p2", distance=5.0),
        DistanceConstraint(id="d2", p1="p1", p2="p2", distance=2.0),
    ]

    diag = solve(
        points,
        constraints,
        line_map={},
        max_iters=20,
        tolerance=1e-4,
        soft_fallback=True,
        max_soft_drops=1,
        fallback_error_threshold=0.5,
    )

    assert diag.fallback_applied
    assert diag.dropped_constraints


if __name__ == "__main__":
    main()
