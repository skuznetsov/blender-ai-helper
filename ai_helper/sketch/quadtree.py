from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class Point2D:
    x: float
    y: float
    payload: object = None

    def distance_to(self, other: "Point2D") -> float:
        dx = self.x - other.x
        dy = self.y - other.y
        return (dx * dx + dy * dy) ** 0.5


@dataclass(frozen=True)
class Bounds:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def center(self) -> Point2D:
        return Point2D(
            (self.min_x + self.max_x) / 2.0,
            (self.min_y + self.max_y) / 2.0,
        )

    def contains(self, p: Point2D) -> bool:
        return (
            self.min_x <= p.x <= self.max_x
            and self.min_y <= p.y <= self.max_y
        )

    def intersects_circle(self, center: Point2D, radius: float) -> bool:
        closest_x = min(max(center.x, self.min_x), self.max_x)
        closest_y = min(max(center.y, self.min_y), self.max_y)
        dx = closest_x - center.x
        dy = closest_y - center.y
        return (dx * dx + dy * dy) <= radius * radius

    def quadrant(self, idx: int) -> "Bounds":
        c = self.center()
        if idx == 0:
            return Bounds(self.min_x, self.min_y, c.x, c.y)
        if idx == 1:
            return Bounds(c.x, self.min_y, self.max_x, c.y)
        if idx == 2:
            return Bounds(self.min_x, c.y, c.x, self.max_y)
        return Bounds(c.x, c.y, self.max_x, self.max_y)


class Quadtree:
    MAX_POINTS_PER_NODE = 8
    MAX_DEPTH = 10

    def __init__(self, bounds: Bounds, depth: int = 0) -> None:
        self.bounds = bounds
        self.depth = depth
        self.points: List[Point2D] = []
        self.children: Optional[List["Quadtree"]] = None

    @classmethod
    def build(cls, points: List[Point2D]) -> "Quadtree":
        if not points:
            return cls(Bounds(0.0, 0.0, 1.0, 1.0))

        min_x = min(p.x for p in points)
        min_y = min(p.y for p in points)
        max_x = max(p.x for p in points)
        max_y = max(p.y for p in points)

        padding = 1.0
        bounds = Bounds(min_x - padding, min_y - padding, max_x + padding, max_y + padding)
        tree = cls(bounds)
        for p in points:
            tree.insert(p)
        return tree

    def insert(self, point: Point2D) -> bool:
        if not self.bounds.contains(point):
            return False

        if self.children is None:
            if len(self.points) < self.MAX_POINTS_PER_NODE or self.depth >= self.MAX_DEPTH:
                self.points.append(point)
                return True
            self._subdivide()

        for child in self.children or []:
            if child.insert(point):
                return True
        return False

    def query_radius(self, center: Point2D, radius: float) -> List[Point2D]:
        results: List[Point2D] = []
        self._query_radius_recursive(center, radius, results)
        return results

    def query_nearest(self, center: Point2D, k: int = 1) -> List[Point2D]:
        results: List[Point2D] = []
        self._query_nearest_recursive(center, k, results)
        results.sort(key=lambda p: p.distance_to(center))
        return results[:k]

    def _query_radius_recursive(self, center: Point2D, radius: float, results: List[Point2D]) -> None:
        if not self.bounds.intersects_circle(center, radius):
            return

        for p in self.points:
            if p.distance_to(center) <= radius:
                results.append(p)

        if self.children:
            for child in self.children:
                child._query_radius_recursive(center, radius, results)

    def _query_nearest_recursive(self, center: Point2D, k: int, results: List[Point2D]) -> None:
        for p in self.points:
            results.append(p)

        if len(results) > k:
            results.sort(key=lambda p: p.distance_to(center))
            while len(results) > k:
                results.pop()

        if self.children:
            max_dist = results[-1].distance_to(center) if len(results) >= k else float("inf")
            for child in self.children:
                if child.bounds.intersects_circle(center, max_dist):
                    child._query_nearest_recursive(center, k, results)
                    if len(results) > k:
                        results.sort(key=lambda p: p.distance_to(center))
                        while len(results) > k:
                            results.pop()

    def _subdivide(self) -> None:
        self.children = [
            Quadtree(self.bounds.quadrant(i), self.depth + 1)
            for i in range(4)
        ]

        for p in self.points:
            for child in self.children:
                if child.insert(p):
                    break
        self.points.clear()
