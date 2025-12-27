import math

from ai_helper.solver import PointState, solve
from ai_helper.sketch.constraints import (
    AngleConstraint,
    DistanceConstraint,
    HorizontalConstraint,
)


def main() -> None:
    p1 = PointState(0.0, 0.0, locked=True)
    p2 = PointState(3.0, 0.0)
    p3 = PointState(3.0, 4.0)

    points = {"p1": p1, "p2": p2, "p3": p3}
    line_map = {"l1": ("p1", "p2")}

    constraints = [
        DistanceConstraint(id="d1", p1="p1", p2="p2", distance=5.0),
        HorizontalConstraint(id="h1", line="l1"),
        AngleConstraint(id="a1", p1="p1", vertex="p2", p2="p3", degrees=90.0),
    ]

    diag = solve(points, constraints, line_map, max_iters=100, tolerance=1e-3)

    dist = math.hypot(p2.x - p1.x, p2.y - p1.y)
    assert abs(dist - 5.0) < 1e-2
    assert abs(p1.y - p2.y) < 1e-2
    assert diag.iterations > 0


if __name__ == "__main__":
    main()
