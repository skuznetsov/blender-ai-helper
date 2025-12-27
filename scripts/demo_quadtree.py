from ai_helper.sketch.quadtree import Bounds, Point2D, Quadtree


def main() -> None:
    points = [Point2D(x * 1.0, y * 1.0, payload=f"p{x}{y}") for x in range(5) for y in range(5)]
    tree = Quadtree.build(points)

    center = Point2D(2.0, 2.0)
    found = tree.query_radius(center, 1.5)
    nearest = tree.query_nearest(center, k=3)

    assert len(found) > 0
    assert len(nearest) == 3

    bounds = Bounds(0.0, 0.0, 10.0, 10.0)
    assert bounds.contains(Point2D(5.0, 5.0))


if __name__ == "__main__":
    main()
