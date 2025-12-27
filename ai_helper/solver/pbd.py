from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from ..sketch.constraints import (
    AngleConstraint,
    CoincidentConstraint,
    DistanceConstraint,
    FixConstraint,
    HorizontalConstraint,
    SketchConstraint,
    VerticalConstraint,
)


@dataclass
class PointState:
    x: float
    y: float
    locked: bool = False


@dataclass
class ConstraintError:
    constraint_id: str | None
    kind: str
    error: float


@dataclass
class SolverDiagnostics:
    iterations: int
    max_error: float
    converged: bool
    unsupported: List[str]
    worst_constraint_id: str | None
    worst_constraint_kind: str | None
    worst_constraints: List[ConstraintError]
    fallback_applied: bool
    dropped_constraints: List[str]


def solve(
    points: Dict[str, PointState],
    constraints: Iterable[SketchConstraint],
    line_map: Dict[str, Tuple[str, str]],
    max_iters: int = 25,
    tolerance: float = 1e-4,
    time_budget_ms: float = 10.0,
    pre_relax: bool = False,
    pre_relax_iters: int = 10,
    pre_relax_time_budget_ms: float = 2.0,
    soft_fallback: bool = True,
    max_soft_drops: int = 1,
    fallback_error_threshold: float | None = None,
) -> SolverDiagnostics:
    constraints_list = list(constraints)
    snapshot = _snapshot_points(points)
    start = time.perf_counter()
    max_error = 0.0
    worst_id = None
    worst_kind = None
    unsupported: List[str] = []
    iterations = 0
    dropped_constraints: List[str] = []
    fallback_applied = False

    if pre_relax:
        _apply_fix_constraints(points, constraints_list)
        _relax_distances(points, constraints_list, pre_relax_iters, pre_relax_time_budget_ms)
    _apply_fix_constraints(points, constraints_list)

    for iteration in range(max_iters):
        max_error = 0.0
        for constraint in constraints_list:
            if isinstance(constraint, DistanceConstraint):
                err = _apply_distance(points, constraint)
            elif isinstance(constraint, CoincidentConstraint):
                err = _apply_coincident(points, constraint)
            elif isinstance(constraint, HorizontalConstraint):
                err = _apply_horizontal(points, line_map, constraint)
            elif isinstance(constraint, VerticalConstraint):
                err = _apply_vertical(points, line_map, constraint)
            elif isinstance(constraint, AngleConstraint):
                err = _apply_angle(points, constraint)
            elif isinstance(constraint, FixConstraint):
                err = 0.0
            else:
                unsupported.append(type(constraint).__name__)
                err = 0.0

            abs_err = abs(err)
            if abs_err > max_error:
                max_error = abs_err
                worst_id = getattr(constraint, "id", None)
                worst_kind = type(constraint).__name__

        iterations = iteration + 1
        if max_error <= tolerance:
            break

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        if elapsed_ms >= time_budget_ms:
            break

    worst_constraints = _collect_errors(points, constraints_list, line_map, limit=5)
    diag = SolverDiagnostics(
        iterations=iterations,
        max_error=max_error,
        converged=max_error <= tolerance,
        unsupported=sorted(set(unsupported)),
        worst_constraint_id=worst_id,
        worst_constraint_kind=worst_kind,
        worst_constraints=worst_constraints,
        fallback_applied=fallback_applied,
        dropped_constraints=dropped_constraints,
    )

    if diag.converged or not soft_fallback or max_soft_drops <= 0:
        return diag

    threshold = fallback_error_threshold
    if threshold is None:
        threshold = max(tolerance * 10.0, 1e-3)

    candidates = [c for c in worst_constraints if abs(c.error) > threshold and c.constraint_id]
    if not candidates:
        return diag

    drop_ids = [c.constraint_id for c in candidates[:max_soft_drops] if c.constraint_id]
    if not drop_ids:
        return diag

    _restore_points(points, snapshot)
    _apply_fix_constraints(points, constraints_list)
    if pre_relax:
        _relax_distances(points, constraints_list, pre_relax_iters, pre_relax_time_budget_ms)

    filtered = [c for c in constraints_list if getattr(c, "id", None) not in drop_ids]

    fallback_applied = True
    max_error = 0.0
    worst_id = None
    worst_kind = None
    unsupported = []
    iterations = 0
    start = time.perf_counter()

    for iteration in range(max_iters):
        max_error = 0.0
        for constraint in filtered:
            if isinstance(constraint, DistanceConstraint):
                err = _apply_distance(points, constraint)
            elif isinstance(constraint, CoincidentConstraint):
                err = _apply_coincident(points, constraint)
            elif isinstance(constraint, HorizontalConstraint):
                err = _apply_horizontal(points, line_map, constraint)
            elif isinstance(constraint, VerticalConstraint):
                err = _apply_vertical(points, line_map, constraint)
            elif isinstance(constraint, AngleConstraint):
                err = _apply_angle(points, constraint)
            elif isinstance(constraint, FixConstraint):
                err = 0.0
            else:
                unsupported.append(type(constraint).__name__)
                err = 0.0

            abs_err = abs(err)
            if abs_err > max_error:
                max_error = abs_err
                worst_id = getattr(constraint, "id", None)
                worst_kind = type(constraint).__name__

        iterations = iteration + 1
        if max_error <= tolerance:
            break

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        if elapsed_ms >= time_budget_ms:
            break

    worst_constraints = _collect_errors(points, filtered, line_map, limit=5)
    return SolverDiagnostics(
        iterations=iterations,
        max_error=max_error,
        converged=max_error <= tolerance,
        unsupported=sorted(set(unsupported)),
        worst_constraint_id=worst_id,
        worst_constraint_kind=worst_kind,
        worst_constraints=worst_constraints,
        fallback_applied=fallback_applied,
        dropped_constraints=drop_ids,
    )


def _apply_distance(points: Dict[str, PointState], c: DistanceConstraint) -> float:
    p1 = points.get(c.p1)
    p2 = points.get(c.p2)
    if p1 is None or p2 is None:
        return 0.0

    dx = p2.x - p1.x
    dy = p2.y - p1.y
    dist = math.hypot(dx, dy)
    if dist < 1e-8:
        return c.distance

    delta = c.distance - dist
    w1 = 0.0 if p1.locked else 1.0
    w2 = 0.0 if p2.locked else 1.0
    wsum = w1 + w2
    if wsum == 0.0:
        return -delta

    nx = dx / dist
    ny = dy / dist

    if not p1.locked:
        p1.x -= nx * delta * (w1 / wsum)
        p1.y -= ny * delta * (w1 / wsum)
    if not p2.locked:
        p2.x += nx * delta * (w2 / wsum)
        p2.y += ny * delta * (w2 / wsum)

    return -delta


def _apply_coincident(points: Dict[str, PointState], c: CoincidentConstraint) -> float:
    return _apply_distance(points, DistanceConstraint(id=c.id, p1=c.p1, p2=c.p2, distance=0.0))


def _apply_horizontal(
    points: Dict[str, PointState],
    line_map: Dict[str, Tuple[str, str]],
    c: HorizontalConstraint,
) -> float:
    line = line_map.get(c.line)
    if not line:
        return 0.0

    p1 = points.get(line[0])
    p2 = points.get(line[1])
    if p1 is None or p2 is None:
        return 0.0

    diff = p2.y - p1.y
    w1 = 0.0 if p1.locked else 1.0
    w2 = 0.0 if p2.locked else 1.0
    wsum = w1 + w2
    if wsum == 0.0:
        return diff

    if not p1.locked:
        p1.y += diff * (w1 / wsum)
    if not p2.locked:
        p2.y -= diff * (w2 / wsum)

    return diff


def _apply_vertical(
    points: Dict[str, PointState],
    line_map: Dict[str, Tuple[str, str]],
    c: VerticalConstraint,
) -> float:
    line = line_map.get(c.line)
    if not line:
        return 0.0

    p1 = points.get(line[0])
    p2 = points.get(line[1])
    if p1 is None or p2 is None:
        return 0.0

    diff = p2.x - p1.x
    w1 = 0.0 if p1.locked else 1.0
    w2 = 0.0 if p2.locked else 1.0
    wsum = w1 + w2
    if wsum == 0.0:
        return diff

    if not p1.locked:
        p1.x += diff * (w1 / wsum)
    if not p2.locked:
        p2.x -= diff * (w2 / wsum)

    return diff


def _apply_angle(points: Dict[str, PointState], c: AngleConstraint) -> float:
    p1 = points.get(c.p1)
    pv = points.get(c.vertex)
    p2 = points.get(c.p2)
    if p1 is None or pv is None or p2 is None:
        return 0.0

    v1x = p1.x - pv.x
    v1y = p1.y - pv.y
    v2x = p2.x - pv.x
    v2y = p2.y - pv.y

    len1 = math.hypot(v1x, v1y)
    len2 = math.hypot(v2x, v2y)
    if len1 < 1e-8 or len2 < 1e-8:
        return 0.0

    dot = v1x * v2x + v1y * v2y
    cross = v1x * v2y - v1y * v2x
    current = math.atan2(cross, dot)
    target = math.radians(c.degrees)

    desired = abs(target)
    delta = abs(current) - desired
    if abs(delta) < 1e-8:
        return 0.0

    sign = 1.0 if current >= 0.0 else -1.0

    if not p1.locked and not p2.locked:
        _rotate_around(p1, pv, sign * (-delta / 2.0))
        _rotate_around(p2, pv, sign * (delta / 2.0))
    elif not p1.locked and p2.locked:
        _rotate_around(p1, pv, sign * (-delta))
    elif p1.locked and not p2.locked:
        _rotate_around(p2, pv, sign * (delta))

    return delta


def _rotate_around(p: PointState, center: PointState, angle: float) -> None:
    s = math.sin(angle)
    c = math.cos(angle)
    ox = p.x - center.x
    oy = p.y - center.y
    rx = ox * c - oy * s
    ry = ox * s + oy * c
    p.x = center.x + rx
    p.y = center.y + ry


def _snapshot_points(points: Dict[str, PointState]) -> Dict[str, Tuple[float, float, bool]]:
    return {pid: (p.x, p.y, p.locked) for pid, p in points.items()}


def _restore_points(points: Dict[str, PointState], snapshot: Dict[str, Tuple[float, float, bool]]) -> None:
    for pid, state in snapshot.items():
        p = points.get(pid)
        if p is None:
            continue
        p.x, p.y, p.locked = state


def _apply_fix_constraints(points: Dict[str, PointState], constraints: List[SketchConstraint]) -> None:
    for constraint in constraints:
        if isinstance(constraint, FixConstraint):
            target = points.get(constraint.point)
            if target is not None:
                target.locked = True


def _relax_distances(
    points: Dict[str, PointState],
    constraints: List[SketchConstraint],
    iterations: int,
    time_budget_ms: float,
) -> None:
    start = time.perf_counter()
    for _ in range(iterations):
        for constraint in constraints:
            if isinstance(constraint, DistanceConstraint):
                _apply_distance(points, constraint)
            elif isinstance(constraint, CoincidentConstraint):
                _apply_coincident(points, constraint)

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        if elapsed_ms >= time_budget_ms:
            break


def _collect_errors(
    points: Dict[str, PointState],
    constraints: List[SketchConstraint],
    line_map: Dict[str, Tuple[str, str]],
    limit: int = 5,
) -> List[ConstraintError]:
    errors: List[ConstraintError] = []
    for constraint in constraints:
        error = _constraint_error(points, line_map, constraint)
        kind = getattr(constraint, "kind", type(constraint).__name__)
        errors.append(ConstraintError(getattr(constraint, "id", None), str(kind), error))

    errors.sort(key=lambda e: abs(e.error), reverse=True)
    return errors[:limit]


def _constraint_error(
    points: Dict[str, PointState],
    line_map: Dict[str, Tuple[str, str]],
    constraint: SketchConstraint,
) -> float:
    if isinstance(constraint, DistanceConstraint):
        return _distance_error(points, constraint.p1, constraint.p2, constraint.distance)
    if isinstance(constraint, CoincidentConstraint):
        return _distance_error(points, constraint.p1, constraint.p2, 0.0)
    if isinstance(constraint, HorizontalConstraint):
        line = line_map.get(constraint.line)
        if not line:
            return 0.0
        p1 = points.get(line[0])
        p2 = points.get(line[1])
        if p1 is None or p2 is None:
            return 0.0
        return p2.y - p1.y
    if isinstance(constraint, VerticalConstraint):
        line = line_map.get(constraint.line)
        if not line:
            return 0.0
        p1 = points.get(line[0])
        p2 = points.get(line[1])
        if p1 is None or p2 is None:
            return 0.0
        return p2.x - p1.x
    if isinstance(constraint, AngleConstraint):
        return _angle_error(points, constraint)
    if isinstance(constraint, FixConstraint):
        return 0.0
    return 0.0


def _distance_error(points: Dict[str, PointState], p1_id: str, p2_id: str, target: float) -> float:
    p1 = points.get(p1_id)
    p2 = points.get(p2_id)
    if p1 is None or p2 is None:
        return 0.0
    dx = p2.x - p1.x
    dy = p2.y - p1.y
    dist = math.hypot(dx, dy)
    return dist - target


def _angle_error(points: Dict[str, PointState], c: AngleConstraint) -> float:
    p1 = points.get(c.p1)
    pv = points.get(c.vertex)
    p2 = points.get(c.p2)
    if p1 is None or pv is None or p2 is None:
        return 0.0

    v1x = p1.x - pv.x
    v1y = p1.y - pv.y
    v2x = p2.x - pv.x
    v2y = p2.y - pv.y

    len1 = math.hypot(v1x, v1y)
    len2 = math.hypot(v2x, v2y)
    if len1 < 1e-8 or len2 < 1e-8:
        return 0.0

    dot = v1x * v2x + v1y * v2y
    cross = v1x * v2y - v1y * v2x
    current = math.atan2(cross, dot)
    target = math.radians(c.degrees)
    return abs(current) - abs(target)
