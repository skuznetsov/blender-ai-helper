from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from ..sketch.constraints import (
    AngleConstraint,
    CoincidentConstraint,
    ConcentricConstraint,
    DistanceConstraint,
    FixConstraint,
    HorizontalConstraint,
    ParallelConstraint,
    MidpointConstraint,
    EqualLengthConstraint,
    SymmetryConstraint,
    TangentConstraint,
    SketchConstraint,
    PerpendicularConstraint,
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
            elif isinstance(constraint, ParallelConstraint):
                err = _apply_parallel(points, line_map, constraint)
            elif isinstance(constraint, PerpendicularConstraint):
                err = _apply_perpendicular(points, line_map, constraint)
            elif isinstance(constraint, ConcentricConstraint):
                err = _apply_concentric(points, constraint)
            elif isinstance(constraint, SymmetryConstraint):
                err = _apply_symmetry(points, line_map, constraint)
            elif isinstance(constraint, TangentConstraint):
                err = _apply_tangent(points, line_map, constraint)
            elif isinstance(constraint, MidpointConstraint):
                err = _apply_midpoint(points, line_map, constraint)
            elif isinstance(constraint, EqualLengthConstraint):
                err = _apply_equal_length(points, line_map, constraint)
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
            elif isinstance(constraint, ParallelConstraint):
                err = _apply_parallel(points, line_map, constraint)
            elif isinstance(constraint, PerpendicularConstraint):
                err = _apply_perpendicular(points, line_map, constraint)
            elif isinstance(constraint, ConcentricConstraint):
                err = _apply_concentric(points, constraint)
            elif isinstance(constraint, SymmetryConstraint):
                err = _apply_symmetry(points, line_map, constraint)
            elif isinstance(constraint, TangentConstraint):
                err = _apply_tangent(points, line_map, constraint)
            elif isinstance(constraint, MidpointConstraint):
                err = _apply_midpoint(points, line_map, constraint)
            elif isinstance(constraint, EqualLengthConstraint):
                err = _apply_equal_length(points, line_map, constraint)
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
    target_mag = abs(target)
    if abs(current) < 1e-8:
        target_signed = target_mag
    else:
        target_signed = math.copysign(target_mag, current)

    delta = current - target_signed
    if abs(delta) < 1e-8:
        return 0.0

    if not p1.locked and not p2.locked:
        _rotate_around(p1, pv, delta / 2.0)
        _rotate_around(p2, pv, -delta / 2.0)
    elif not p1.locked and p2.locked:
        _rotate_around(p1, pv, delta)
    elif p1.locked and not p2.locked:
        _rotate_around(p2, pv, -delta)

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
    if isinstance(constraint, ParallelConstraint):
        return _line_angle_error(points, line_map, constraint.line_a, constraint.line_b, target_degrees=0.0)
    if isinstance(constraint, PerpendicularConstraint):
        return _line_angle_error(points, line_map, constraint.line_a, constraint.line_b, target_degrees=90.0)
    if isinstance(constraint, ConcentricConstraint):
        return _distance_error(points, constraint.p1, constraint.p2, 0.0)
    if isinstance(constraint, SymmetryConstraint):
        return _symmetry_error(points, line_map, constraint)
    if isinstance(constraint, TangentConstraint):
        return _tangent_error(points, line_map, constraint)
    if isinstance(constraint, MidpointConstraint):
        return _midpoint_error(points, line_map, constraint)
    if isinstance(constraint, EqualLengthConstraint):
        return _equal_length_error(points, line_map, constraint)
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
    target_mag = abs(target)
    if abs(current) < 1e-8:
        target_signed = target_mag
    else:
        target_signed = math.copysign(target_mag, current)
    return current - target_signed


def _apply_parallel(points: Dict[str, PointState], line_map: Dict[str, Tuple[str, str]], c: ParallelConstraint) -> float:
    return _apply_line_angle(points, line_map, c.line_a, c.line_b, target_degrees=0.0)


def _apply_perpendicular(
    points: Dict[str, PointState],
    line_map: Dict[str, Tuple[str, str]],
    c: PerpendicularConstraint,
) -> float:
    return _apply_line_angle(points, line_map, c.line_a, c.line_b, target_degrees=90.0)


def _apply_line_angle(
    points: Dict[str, PointState],
    line_map: Dict[str, Tuple[str, str]],
    line_a: str,
    line_b: str,
    target_degrees: float,
) -> float:
    a = line_map.get(line_a)
    b = line_map.get(line_b)
    if not a or not b:
        return 0.0

    va = _line_vector(points, a[0], a[1])
    vb = _line_vector(points, b[0], b[1])
    if va is None or vb is None:
        return 0.0

    angle = _signed_angle(va, vb)
    target = math.radians(target_degrees)
    delta = _wrap_period(angle - target, math.pi)
    if abs(delta) < 1e-8:
        return 0.0

    a_free = _line_free_count(points, a[0], a[1])
    b_free = _line_free_count(points, b[0], b[1])

    if a_free == 0 and b_free == 0:
        return delta
    if a_free == 0:
        _rotate_line(points, b[0], b[1], -delta)
    elif b_free == 0:
        _rotate_line(points, a[0], a[1], delta)
    else:
        _rotate_line(points, a[0], a[1], delta / 2.0)
        _rotate_line(points, b[0], b[1], -delta / 2.0)

    return delta


def _line_vector(points: Dict[str, PointState], p1_id: str, p2_id: str):
    p1 = points.get(p1_id)
    p2 = points.get(p2_id)
    if p1 is None or p2 is None:
        return None
    return (p2.x - p1.x, p2.y - p1.y)


def _line_free_count(points: Dict[str, PointState], p1_id: str, p2_id: str) -> int:
    p1 = points.get(p1_id)
    p2 = points.get(p2_id)
    if p1 is None or p2 is None:
        return 0
    locked = int(p1.locked) + int(p2.locked)
    return 2 - locked


def _signed_angle(v1, v2) -> float:
    v1x, v1y = v1
    v2x, v2y = v2
    dot = v1x * v2x + v1y * v2y
    cross = v1x * v2y - v1y * v2x
    return math.atan2(cross, dot)


def _wrap_period(value: float, period: float) -> float:
    return (value + period / 2.0) % period - period / 2.0


def _rotate_line(points: Dict[str, PointState], p1_id: str, p2_id: str, angle: float) -> None:
    p1 = points.get(p1_id)
    p2 = points.get(p2_id)
    if p1 is None or p2 is None:
        return

    if p1.locked and p2.locked:
        return

    if p1.locked and not p2.locked:
        _rotate_around(p2, p1, -angle)
        return
    if p2.locked and not p1.locked:
        _rotate_around(p1, p2, angle)
        return

    center = PointState((p1.x + p2.x) / 2.0, (p1.y + p2.y) / 2.0)
    _rotate_around(p1, center, angle)
    _rotate_around(p2, center, angle)


def _line_angle_error(
    points: Dict[str, PointState],
    line_map: Dict[str, Tuple[str, str]],
    line_a: str,
    line_b: str,
    target_degrees: float,
) -> float:
    a = line_map.get(line_a)
    b = line_map.get(line_b)
    if not a or not b:
        return 0.0

    va = _line_vector(points, a[0], a[1])
    vb = _line_vector(points, b[0], b[1])
    if va is None or vb is None:
        return 0.0

    angle = _signed_angle(va, vb)
    target = math.radians(target_degrees)
    return _wrap_period(angle - target, math.pi)


def _apply_midpoint(
    points: Dict[str, PointState],
    line_map: Dict[str, Tuple[str, str]],
    c: MidpointConstraint,
) -> float:
    line = line_map.get(c.line)
    if not line:
        return 0.0

    p1 = points.get(line[0])
    p2 = points.get(line[1])
    pm = points.get(c.point)
    if p1 is None or p2 is None or pm is None:
        return 0.0

    mid_x = (p1.x + p2.x) / 2.0
    mid_y = (p1.y + p2.y) / 2.0
    err_x = pm.x - mid_x
    err_y = pm.y - mid_y
    err = math.hypot(err_x, err_y)
    if err < 1e-8:
        return 0.0

    w1 = 0.0 if p1.locked else 1.0
    w2 = 0.0 if p2.locked else 1.0
    wm = 0.0 if pm.locked else 1.0

    if wm == 0.0:
        wsum = w1 + w2
        if wsum == 0.0:
            return err
        alpha = 2.0 / wsum
        if w1 > 0.0:
            p1.x += err_x * alpha
            p1.y += err_y * alpha
        if w2 > 0.0:
            p2.x += err_x * alpha
            p2.y += err_y * alpha
        return err

    alpha = 1.0 / (1.0 + (w1 + w2) / 2.0) if (w1 + w2) > 0.0 else 1.0
    pm.x -= err_x * alpha
    pm.y -= err_y * alpha
    if w1 > 0.0:
        p1.x += err_x * alpha
        p1.y += err_y * alpha
    if w2 > 0.0:
        p2.x += err_x * alpha
        p2.y += err_y * alpha
    return err


def _midpoint_error(
    points: Dict[str, PointState],
    line_map: Dict[str, Tuple[str, str]],
    c: MidpointConstraint,
) -> float:
    line = line_map.get(c.line)
    if not line:
        return 0.0

    p1 = points.get(line[0])
    p2 = points.get(line[1])
    pm = points.get(c.point)
    if p1 is None or p2 is None or pm is None:
        return 0.0

    mid_x = (p1.x + p2.x) / 2.0
    mid_y = (p1.y + p2.y) / 2.0
    return math.hypot(pm.x - mid_x, pm.y - mid_y)


def _apply_concentric(points: Dict[str, PointState], c: ConcentricConstraint) -> float:
    return _apply_distance(points, DistanceConstraint(id=c.id, p1=c.p1, p2=c.p2, distance=0.0))


def _apply_symmetry(
    points: Dict[str, PointState],
    line_map: Dict[str, Tuple[str, str]],
    c: SymmetryConstraint,
) -> float:
    line = line_map.get(c.line)
    if not line:
        return 0.0

    a = points.get(line[0])
    b = points.get(line[1])
    p1 = points.get(c.p1)
    p2 = points.get(c.p2)
    if a is None or b is None or p1 is None or p2 is None:
        return 0.0

    vx = b.x - a.x
    vy = b.y - a.y
    len2 = vx * vx + vy * vy
    if len2 < 1e-8:
        return 0.0

    r1x, r1y = _reflect_point(p1.x, p1.y, a.x, a.y, vx, vy, len2)
    r2x, r2y = _reflect_point(p2.x, p2.y, a.x, a.y, vx, vy, len2)

    if p1.locked and p2.locked:
        return math.hypot(p2.x - r1x, p2.y - r1y)
    if p1.locked and not p2.locked:
        p2.x = r1x
        p2.y = r1y
        return 0.0
    if p2.locked and not p1.locked:
        p1.x = r2x
        p1.y = r2y
        return 0.0

    p1.x = (p1.x + r2x) / 2.0
    p1.y = (p1.y + r2y) / 2.0
    p2.x = (p2.x + r1x) / 2.0
    p2.y = (p2.y + r1y) / 2.0
    return math.hypot(p2.x - r1x, p2.y - r1y)


def _symmetry_error(
    points: Dict[str, PointState],
    line_map: Dict[str, Tuple[str, str]],
    c: SymmetryConstraint,
) -> float:
    line = line_map.get(c.line)
    if not line:
        return 0.0

    a = points.get(line[0])
    b = points.get(line[1])
    p1 = points.get(c.p1)
    p2 = points.get(c.p2)
    if a is None or b is None or p1 is None or p2 is None:
        return 0.0

    vx = b.x - a.x
    vy = b.y - a.y
    len2 = vx * vx + vy * vy
    if len2 < 1e-8:
        return 0.0

    r1x, r1y = _reflect_point(p1.x, p1.y, a.x, a.y, vx, vy, len2)
    return math.hypot(p2.x - r1x, p2.y - r1y)


def _reflect_point(px, py, ax, ay, vx, vy, len2):
    t = ((px - ax) * vx + (py - ay) * vy) / len2
    proj_x = ax + vx * t
    proj_y = ay + vy * t
    return (2.0 * proj_x - px, 2.0 * proj_y - py)


def _apply_tangent(
    points: Dict[str, PointState],
    line_map: Dict[str, Tuple[str, str]],
    c: TangentConstraint,
) -> float:
    line = line_map.get(c.line)
    if not line:
        return 0.0

    a = points.get(line[0])
    b = points.get(line[1])
    center = points.get(c.center)
    if a is None or b is None or center is None:
        return 0.0

    radius = c.radius
    if radius <= 0.0:
        return 0.0

    vx = b.x - a.x
    vy = b.y - a.y
    length = math.hypot(vx, vy)
    if length < 1e-8:
        return 0.0

    nx = -vy / length
    ny = vx / length
    d = (center.x - a.x) * nx + (center.y - a.y) * ny
    sign = 1.0 if d >= 0.0 else -1.0
    target = sign * radius
    err = d - target
    if abs(err) < 1e-8:
        return 0.0

    w_center = 0.0 if center.locked else 1.0
    w_line = (0.5 if not a.locked else 0.0) + (0.5 if not b.locked else 0.0)
    total = w_center + w_line
    if total == 0.0:
        return err

    delta_center = err * (w_center / total)
    delta_line = err * (w_line / total)

    if w_center > 0.0:
        center.x -= nx * delta_center
        center.y -= ny * delta_center

    if w_line > 0.0:
        if not a.locked and not b.locked:
            a.x += nx * delta_line
            a.y += ny * delta_line
            b.x += nx * delta_line
            b.y += ny * delta_line
        elif not a.locked:
            a.x += nx * (delta_line * 2.0)
            a.y += ny * (delta_line * 2.0)
        elif not b.locked:
            b.x += nx * (delta_line * 2.0)
            b.y += ny * (delta_line * 2.0)

    return err


def _tangent_error(
    points: Dict[str, PointState],
    line_map: Dict[str, Tuple[str, str]],
    c: TangentConstraint,
) -> float:
    line = line_map.get(c.line)
    if not line:
        return 0.0

    a = points.get(line[0])
    b = points.get(line[1])
    center = points.get(c.center)
    if a is None or b is None or center is None:
        return 0.0

    radius = c.radius
    if radius <= 0.0:
        return 0.0

    vx = b.x - a.x
    vy = b.y - a.y
    length = math.hypot(vx, vy)
    if length < 1e-8:
        return 0.0

    nx = -vy / length
    ny = vx / length
    d = (center.x - a.x) * nx + (center.y - a.y) * ny
    return abs(d) - radius


def _apply_equal_length(
    points: Dict[str, PointState],
    line_map: Dict[str, Tuple[str, str]],
    c: EqualLengthConstraint,
) -> float:
    line_a = line_map.get(c.line_a)
    line_b = line_map.get(c.line_b)
    if not line_a or not line_b:
        return 0.0

    a1 = points.get(line_a[0])
    a2 = points.get(line_a[1])
    b1 = points.get(line_b[0])
    b2 = points.get(line_b[1])
    if a1 is None or a2 is None or b1 is None or b2 is None:
        return 0.0

    avx = a2.x - a1.x
    avy = a2.y - a1.y
    bvx = b2.x - b1.x
    bvy = b2.y - b1.y

    len_a = math.hypot(avx, avy)
    len_b = math.hypot(bvx, bvy)
    if len_a < 1e-8 or len_b < 1e-8:
        return 0.0

    err = len_a - len_b
    if abs(err) < 1e-8:
        return 0.0

    w_a = (0.0 if a1.locked else 1.0) + (0.0 if a2.locked else 1.0)
    w_b = (0.0 if b1.locked else 1.0) + (0.0 if b2.locked else 1.0)
    if w_a == 0.0 and w_b == 0.0:
        return err

    total = w_a + w_b
    move_a = -err * (w_b / total)
    move_b = err * (w_a / total)

    _scale_line(points, line_a[0], line_a[1], move_a / len_a)
    _scale_line(points, line_b[0], line_b[1], move_b / len_b)
    return err


def _scale_line(points: Dict[str, PointState], p1_id: str, p2_id: str, scale_delta: float) -> None:
    p1 = points.get(p1_id)
    p2 = points.get(p2_id)
    if p1 is None or p2 is None:
        return

    if p1.locked and p2.locked:
        return

    cx = (p1.x + p2.x) / 2.0
    cy = (p1.y + p2.y) / 2.0
    dx1 = p1.x - cx
    dy1 = p1.y - cy
    dx2 = p2.x - cx
    dy2 = p2.y - cy
    factor = 1.0 + scale_delta

    if p1.locked and not p2.locked:
        p2.x = p1.x + (p2.x - p1.x) * factor
        p2.y = p1.y + (p2.y - p1.y) * factor
        return
    if p2.locked and not p1.locked:
        p1.x = p2.x + (p1.x - p2.x) * factor
        p1.y = p2.y + (p1.y - p2.y) * factor
        return

    if not p1.locked:
        p1.x = cx + dx1 * factor
        p1.y = cy + dy1 * factor
    if not p2.locked:
        p2.x = cx + dx2 * factor
        p2.y = cy + dy2 * factor


def _equal_length_error(
    points: Dict[str, PointState],
    line_map: Dict[str, Tuple[str, str]],
    c: EqualLengthConstraint,
) -> float:
    line_a = line_map.get(c.line_a)
    line_b = line_map.get(c.line_b)
    if not line_a or not line_b:
        return 0.0

    a1 = points.get(line_a[0])
    a2 = points.get(line_a[1])
    b1 = points.get(line_b[0])
    b2 = points.get(line_b[1])
    if a1 is None or a2 is None or b1 is None or b2 is None:
        return 0.0

    len_a = math.hypot(a2.x - a1.x, a2.y - a1.y)
    len_b = math.hypot(b2.x - b1.x, b2.y - b1.y)
    return len_a - len_b
