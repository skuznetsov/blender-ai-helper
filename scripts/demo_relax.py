from ai_helper.solver import PointState, solve
from ai_helper.sketch.constraints import DistanceConstraint, HorizontalConstraint, VerticalConstraint


def _make_points():
    return {
        "p1": PointState(0.0, 0.0, locked=True),
        "p2": PointState(10.0, -4.0),
        "p3": PointState(12.0, 9.0),
        "p4": PointState(-3.0, 11.0),
    }


def main() -> None:
    constraints = [
        DistanceConstraint(id="d12", p1="p1", p2="p2", distance=2.0),
        DistanceConstraint(id="d23", p1="p2", p2="p3", distance=2.0),
        DistanceConstraint(id="d34", p1="p3", p2="p4", distance=2.0),
        DistanceConstraint(id="d41", p1="p4", p2="p1", distance=2.0),
        HorizontalConstraint(id="h12", line="l12"),
        HorizontalConstraint(id="h34", line="l34"),
        VerticalConstraint(id="v23", line="l23"),
        VerticalConstraint(id="v41", line="l41"),
    ]
    line_map = {
        "l12": ("p1", "p2"),
        "l23": ("p2", "p3"),
        "l34": ("p3", "p4"),
        "l41": ("p4", "p1"),
    }

    points_no = _make_points()
    diag_no = solve(
        points_no,
        constraints,
        line_map,
        max_iters=2,
        tolerance=1e-4,
        time_budget_ms=1.0,
        pre_relax=False,
    )

    points_relax = _make_points()
    diag_relax = solve(
        points_relax,
        constraints,
        line_map,
        max_iters=2,
        tolerance=1e-4,
        time_budget_ms=1.0,
        pre_relax=True,
        pre_relax_iters=40,
        pre_relax_time_budget_ms=5.0,
    )

    assert diag_relax.max_error < diag_no.max_error


if __name__ == "__main__":
    main()
