import math

import bpy
import bmesh
from bpy_extras import view3d_utils
from mathutils import Matrix, Vector

from ..sketch.constraints import HorizontalConstraint, VerticalConstraint
from ..sketch.circles import (
    append_circle,
    clear_circles,
    find_circle_by_center,
    find_circle_by_vertex,
    load_circles,
    new_circle_id,
    save_circles,
)
from ..sketch.dimensions import clear_dimensions, update_dimensions
from ..sketch.history import snapshot_state
from ..sketch.quadtree import Point2D, Quadtree
from ..sketch.rectangles import (
    append_rectangle,
    clear_rectangles,
    load_rectangles,
    new_rectangle_id,
    save_rectangles,
)
from ..sketch.solver_bridge import solve_mesh
from ..sketch.store import (
    append_constraint,
    clear_constraints,
    load_constraints,
    new_constraint_id,
    save_constraints,
)
from ..sketch.tags import clear_tags, load_tags, register_tag, resolve_tags
from .constraints import _set_selection


def ensure_sketch_object(context):
    name = "AI_Sketch"
    obj = context.scene.objects.get(name)
    if obj is not None:
        if obj.type != "MESH":
            return None
        return obj

    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    context.collection.objects.link(obj)
    return obj


def add_line_to_sketch(
    context,
    start,
    end,
    *,
    tag=None,
    auto_constraints=True,
    hv_tolerance_deg=8.0,
):
    obj = ensure_sketch_object(context)
    if obj is None:
        return None

    if (end - start).length < 1e-8:
        return None

    bm = bmesh.new()
    bm.from_mesh(obj.data)

    v1 = bm.verts.new((start.x, start.y, 0.0))
    v2 = bm.verts.new((end.x, end.y, 0.0))
    edge = bm.edges.new((v1, v2))
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.verts.index_update()
    bm.edges.index_update()

    edge_index = edge.index
    v1_index = v1.index
    v2_index = v2.index

    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()

    if tag:
        register_tag(obj, tag, verts=[v1_index, v2_index], edges=[edge_index])

    if auto_constraints:
        dx = end.x - start.x
        dy = end.y - start.y
        if abs(dx) >= 1e-8 or abs(dy) >= 1e-8:
            angle = abs(math.degrees(math.atan2(dy, dx)))
            if angle < hv_tolerance_deg or abs(angle - 180.0) < hv_tolerance_deg:
                append_constraint(obj, HorizontalConstraint(id=new_constraint_id(), line=str(edge_index)))
            elif abs(angle - 90.0) < hv_tolerance_deg:
                append_constraint(obj, VerticalConstraint(id=new_constraint_id(), line=str(edge_index)))
            constraints = load_constraints(obj)
            if constraints:
                solve_mesh(obj, constraints)

    snapshot_state(obj, "Line")
    return {"edge": edge_index, "verts": [v1_index, v2_index]}


def add_circle_to_sketch(
    context,
    center,
    radius,
    *,
    segments=32,
    tag=None,
):
    if radius <= 0.0:
        return None

    obj = ensure_sketch_object(context)
    if obj is None:
        return None

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    matrix = Matrix.Translation((center.x, center.y, 0.0))
    result = bmesh.ops.create_circle(
        bm,
        cap_ends=False,
        segments=segments,
        radius=radius,
        matrix=matrix,
    )
    center_vert = bm.verts.new((center.x, center.y, 0.0))
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()

    circle_verts = result.get("verts", [])
    circle_ids = [int(v.index) for v in circle_verts]
    center_id = int(center_vert.index)

    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()

    circle_id = new_circle_id()
    append_circle(
        obj,
        {
            "id": circle_id,
            "center": str(center_id),
            "verts": [str(v) for v in circle_ids],
            "radius": float(radius),
        },
    )

    if tag:
        register_tag(
            obj,
            tag,
            verts=circle_ids,
            center=center_id,
            circle_id=circle_id,
        )

    snapshot_state(obj, "Circle")
    return {"id": circle_id, "center": center_id, "verts": circle_ids}


def add_arc_to_sketch(
    context,
    center,
    radius,
    start_angle_deg,
    end_angle_deg,
    *,
    segments=16,
    clockwise=False,
    tag=None,
):
    if radius <= 0.0:
        return None

    start = math.radians(start_angle_deg)
    end = math.radians(end_angle_deg)
    sweep = end - start
    if clockwise:
        if sweep > 0.0:
            sweep -= 2.0 * math.pi
    else:
        if sweep < 0.0:
            sweep += 2.0 * math.pi
    if abs(sweep) < 1e-8:
        return None

    segments = max(int(segments), 1)
    step = sweep / segments
    angles = [start + step * idx for idx in range(segments + 1)]

    obj = ensure_sketch_object(context)
    if obj is None:
        return None

    bm = bmesh.new()
    bm.from_mesh(obj.data)

    arc_verts = []
    for angle in angles:
        x = center.x + math.cos(angle) * radius
        y = center.y + math.sin(angle) * radius
        arc_verts.append(bm.verts.new((x, y, 0.0)))
    center_vert = bm.verts.new((center.x, center.y, 0.0))

    bm.verts.ensure_lookup_table()
    edges = []
    for idx in range(len(arc_verts) - 1):
        edges.append(bm.edges.new((arc_verts[idx], arc_verts[idx + 1])))

    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.verts.index_update()
    bm.edges.index_update()

    vert_indices = [v.index for v in arc_verts]
    edge_indices = [e.index for e in edges]
    center_index = center_vert.index

    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()

    circle_id = new_circle_id()
    append_circle(
        obj,
        {
            "id": circle_id,
            "center": str(center_index),
            "verts": [str(v) for v in vert_indices],
            "radius": float(radius),
            "is_arc": True,
            "start_angle": float(start_angle_deg),
            "end_angle": float(end_angle_deg),
            "clockwise": bool(clockwise),
        },
    )

    if tag:
        register_tag(
            obj,
            tag,
            verts=vert_indices,
            edges=edge_indices,
            center=center_index,
            circle_id=circle_id,
        )

    snapshot_state(obj, "Arc")
    return {"id": circle_id, "center": center_index, "verts": vert_indices, "edges": edge_indices}


def add_polyline_to_sketch(
    context,
    points,
    *,
    closed=False,
    tag=None,
    auto_constraints=True,
    hv_tolerance_deg=8.0,
):
    if not points or len(points) < 2:
        return None

    obj = ensure_sketch_object(context)
    if obj is None:
        return None

    bm = bmesh.new()
    bm.from_mesh(obj.data)

    bm_verts = [bm.verts.new((pt.x, pt.y, 0.0)) for pt in points]
    bm.verts.ensure_lookup_table()
    edges = []
    for idx in range(len(bm_verts) - 1):
        edges.append(bm.edges.new((bm_verts[idx], bm_verts[idx + 1])))
    if closed:
        edges.append(bm.edges.new((bm_verts[-1], bm_verts[0])))

    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.verts.index_update()
    bm.edges.index_update()

    vert_indices = [v.index for v in bm_verts]
    edge_indices = [e.index for e in edges]

    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()

    if tag:
        register_tag(obj, tag, verts=vert_indices, edges=edge_indices)

    if auto_constraints:
        constraints = load_constraints(obj)
        added = False
        pairs = list(zip(points[:-1], points[1:]))
        if closed:
            pairs.append((points[-1], points[0]))
        for edge_id, (start, end) in zip(edge_indices, pairs):
            dx = end.x - start.x
            dy = end.y - start.y
            if abs(dx) < 1e-8 and abs(dy) < 1e-8:
                continue
            angle = abs(math.degrees(math.atan2(dy, dx)))
            if angle < hv_tolerance_deg or abs(angle - 180.0) < hv_tolerance_deg:
                constraints.append(HorizontalConstraint(id=new_constraint_id(), line=str(edge_id)))
                added = True
            elif abs(angle - 90.0) < hv_tolerance_deg:
                constraints.append(VerticalConstraint(id=new_constraint_id(), line=str(edge_id)))
                added = True
        if added:
            save_constraints(obj, constraints)
            solve_mesh(obj, constraints)

    snapshot_state(obj, "Polyline")
    return {"edges": edge_indices, "verts": vert_indices}


def add_rectangle_to_sketch(
    context,
    center,
    width,
    height,
    *,
    rotation_deg=0.0,
    tag=None,
    auto_constraints=True,
    hv_tolerance_deg=8.0,
):
    if width <= 0.0 or height <= 0.0:
        return None

    if abs(rotation_deg) > 1e-6:
        auto_constraints = False

    half_w = width * 0.5
    half_h = height * 0.5
    offsets = [
        (-half_w, -half_h),
        (half_w, -half_h),
        (half_w, half_h),
        (-half_w, half_h),
    ]
    angle = math.radians(rotation_deg)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    points = []
    for dx, dy in offsets:
        rx = dx * cos_a - dy * sin_a
        ry = dx * sin_a + dy * cos_a
        points.append(Vector((center.x + rx, center.y + ry, 0.0)))
    obj = ensure_sketch_object(context)
    if obj is None:
        return None

    entry = add_polyline_to_sketch(
        context,
        points,
        closed=True,
        tag=tag,
        auto_constraints=auto_constraints,
        hv_tolerance_deg=hv_tolerance_deg,
    )
    if entry is None:
        return None

    rect_id = new_rectangle_id()
    append_rectangle(
        obj,
        {
            "id": rect_id,
            "center": [float(center.x), float(center.y)],
            "width": float(width),
            "height": float(height),
            "rotation": float(rotation_deg),
            "verts": [str(v) for v in entry.get("verts", [])],
            "edges": [str(e) for e in entry.get("edges", [])],
            "tag": tag or "",
        },
    )
    entry["rect_id"] = rect_id
    return entry


def clear_sketch_data(context) -> bool:
    obj = ensure_sketch_object(context)
    if obj is None:
        return False

    if hasattr(obj.data, "clear_geometry"):
        obj.data.clear_geometry()
    else:
        bm = bmesh.new()
        bm.to_mesh(obj.data)
        bm.free()
    obj.data.update()

    clear_constraints(obj)
    clear_circles(obj)
    clear_rectangles(obj)
    clear_tags(obj)
    if "ai_helper_history" in obj:
        del obj["ai_helper_history"]
    clear_dimensions(context)
    return True


def _selected_vertices(obj):
    return [v for v in obj.data.vertices if v.select]


def _selected_edges(obj):
    return [e for e in obj.data.edges if e.select]


def _selected_arc(obj):
    circles = load_circles(obj)
    if not circles:
        return None

    for vert in obj.data.vertices:
        if not vert.select:
            continue
        circle = find_circle_by_vertex(circles, str(vert.index))
        if circle and circle.get("is_arc"):
            return circle
        circle = find_circle_by_center(circles, str(vert.index))
        if circle and circle.get("is_arc"):
            return circle

    for edge in obj.data.edges:
        if not edge.select:
            continue
        for vid in edge.vertices:
            circle = find_circle_by_vertex(circles, str(vid))
            if circle and circle.get("is_arc"):
                return circle
    return None


def _arc_angles_for_circle(obj, circle):
    center_id = circle.get("center")
    if center_id is None:
        return None
    try:
        center = obj.data.vertices[int(center_id)].co
    except (ValueError, IndexError):
        return None
    vert_ids = [int(v) for v in circle.get("verts", [])]
    if len(vert_ids) < 2:
        return None
    try:
        start = obj.data.vertices[vert_ids[0]].co
        end = obj.data.vertices[vert_ids[-1]].co
    except (ValueError, IndexError):
        return None

    def _angle_deg(point):
        return (math.degrees(math.atan2(point.y - center.y, point.x - center.x)) + 360.0) % 360.0

    return _angle_deg(start), _angle_deg(end)


def _update_arc_geometry(obj, circle, center, radius, start_angle_deg, end_angle_deg, clockwise):
    center_id = circle.get("center")
    if center_id is None:
        return False

    try:
        center_vert = obj.data.vertices[int(center_id)]
    except (ValueError, IndexError):
        return False

    vert_ids = [int(v) for v in circle.get("verts", [])]
    if len(vert_ids) < 2:
        return False

    start = math.radians(start_angle_deg)
    end = math.radians(end_angle_deg)
    sweep = end - start
    if clockwise:
        if sweep > 0.0:
            sweep -= 2.0 * math.pi
    else:
        if sweep < 0.0:
            sweep += 2.0 * math.pi
    if abs(sweep) < 1e-8:
        return False

    segments = len(vert_ids) - 1
    step = sweep / segments
    angles = [start + step * idx for idx in range(segments + 1)]

    center_vert.co.x = center.x
    center_vert.co.y = center.y
    center_vert.co.z = 0.0

    for vid, angle in zip(vert_ids, angles):
        try:
            vert = obj.data.vertices[vid]
        except IndexError:
            return False
        vert.co.x = center.x + math.cos(angle) * radius
        vert.co.y = center.y + math.sin(angle) * radius
        vert.co.z = 0.0

    obj.data.update()
    return True


def _selected_rectangle(obj):
    rectangles = load_rectangles(obj)
    if not rectangles:
        return None

    selected_verts = {v.index for v in obj.data.vertices if v.select}
    selected_edges = {e.index for e in obj.data.edges if e.select}

    for rect in rectangles:
        rect_verts = {int(v) for v in rect.get("verts", [])}
        rect_edges = {int(e) for e in rect.get("edges", [])}
        if rect_verts & selected_verts or rect_edges & selected_edges:
            return rect
    return None


def _update_rectangle_geometry(obj, rect, center, width, height, rotation_deg):
    vert_ids = [int(v) for v in rect.get("verts", [])]
    if len(vert_ids) < 4:
        return False

    half_w = width * 0.5
    half_h = height * 0.5
    offsets = [
        (-half_w, -half_h),
        (half_w, -half_h),
        (half_w, half_h),
        (-half_w, half_h),
    ]
    angle = math.radians(rotation_deg)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    points = []
    for dx, dy in offsets:
        rx = dx * cos_a - dy * sin_a
        ry = dx * sin_a + dy * cos_a
        points.append(Vector((center.x + rx, center.y + ry, 0.0)))

    for vid, point in zip(vert_ids[:4], points):
        try:
            vert = obj.data.vertices[vid]
        except IndexError:
            return False
        vert.co.x = point.x
        vert.co.y = point.y
        vert.co.z = 0.0

    obj.data.update()
    return True


def _rectangle_metrics_from_verts(obj, vert_ids):
    coords = []
    for vid in vert_ids[:4]:
        try:
            coords.append(obj.data.vertices[vid].co.copy())
        except IndexError:
            return None
    if len(coords) < 4:
        return None

    center = sum((v for v in coords), Vector()) / len(coords)
    edges = [coords[(i + 1) % 4] - coords[i] for i in range(4)]
    lengths = [edge.length for edge in edges]
    width = max(lengths)
    height = min(lengths)
    rotation = 0.0
    if lengths:
        idx = lengths.index(width)
        vec = edges[idx]
        rotation = math.degrees(math.atan2(vec.y, vec.x))
    rotation = rotation % 360.0
    return center.x, center.y, width, height, rotation

def parse_polar(text, start):
    if start is None:
        return None
    if text.startswith("@"):
        text = text[1:]
    if "<" not in text:
        return None

    length_str, angle_str = [p.strip() for p in text.split("<", 1)]
    try:
        length = float(length_str)
        angle = float(angle_str)
    except ValueError:
        return None

    radians = math.radians(angle)
    dx = length * math.cos(radians)
    dy = length * math.sin(radians)
    return Vector((start.x + dx, start.y + dy, 0.0))


def parse_input(text, start, relative_mode):
    text = text.strip()
    if not text:
        return None

    if text.startswith("@"):
        return parse_polar(text, start)

    absolute = False
    if text.startswith("="):
        absolute = True
        text = text[1:]

    if "," not in text:
        return None

    parts = [p.strip() for p in text.split(",", 1)]
    if len(parts) != 2:
        return None

    try:
        x = float(parts[0])
        y = float(parts[1])
    except ValueError:
        return None

    if absolute or not relative_mode:
        return Vector((x, y, 0.0))
    if start is None:
        return None
    return Vector((start.x + x, start.y + y, 0.0))


def apply_axis_lock(location, start, axis_lock):
    if start is None or axis_lock is None:
        return location
    if axis_lock == "X":
        return Vector((location.x, start.y, 0.0))
    if axis_lock == "Y":
        return Vector((start.x, location.y, 0.0))
    return location


def apply_angle_snap(location, start, angle_snap_enabled, angle_snap_deg, axis_lock):
    if start is None or not angle_snap_enabled or axis_lock is not None:
        return location
    if angle_snap_deg <= 0.0:
        return location

    dx = location.x - start.x
    dy = location.y - start.y
    length = math.hypot(dx, dy)
    if length < 1e-8:
        return location

    step = math.radians(angle_snap_deg)
    angle = math.atan2(dy, dx)
    snapped = round(angle / step) * step
    return Vector(
        (
            start.x + math.cos(snapped) * length,
            start.y + math.sin(snapped) * length,
            0.0,
        )
    )


def format_preview(start, point):
    if start is None or point is None:
        return ""
    dx = point.x - start.x
    dy = point.y - start.y
    length = math.hypot(dx, dy)
    angle = (math.degrees(math.atan2(dy, dx)) + 360.0) % 360.0
    return f"len={length:.3f} ang={angle:.1f}"


def grid_step_value(grid_step, scale_length):
    scale = scale_length or 1.0
    return grid_step * scale


def snap_to_grid(location, grid_step, scale_length, snap_grid):
    if not snap_grid:
        return location

    step = grid_step_value(grid_step, scale_length)
    if step <= 0.0:
        return location

    x = math.floor(location.x / step + 0.5) * step
    y = math.floor(location.y / step + 0.5) * step
    return Vector((x, y, 0.0))


def point_on_segment(px, py, x1, y1, x2, y2):
    min_x = min(x1, x2) - 1e-6
    max_x = max(x1, x2) + 1e-6
    min_y = min(y1, y2) - 1e-6
    max_y = max(y1, y2) + 1e-6
    return min_x <= px <= max_x and min_y <= py <= max_y


def segment_intersection(p1, p2, p3, p4):
    x1, y1 = p1.x, p1.y
    x2, y2 = p2.x, p2.y
    x3, y3 = p3.x, p3.y
    x4, y4 = p4.x, p4.y

    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-8:
        return None

    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / denom
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / denom

    if not point_on_segment(px, py, x1, y1, x2, y2):
        return None
    if not point_on_segment(px, py, x3, y3, x4, y4):
        return None

    return Vector((px, py, 0.0))


def segment_intersections(segments):
    hits = []
    count = len(segments)
    for i in range(count):
        a1, a2, a_idx1, a_idx2 = segments[i]
        for j in range(i + 1, count):
            b1, b2, b_idx1, b_idx2 = segments[j]
            if a_idx1 in (b_idx1, b_idx2) or a_idx2 in (b_idx1, b_idx2):
                continue
            hit = segment_intersection(a1, a2, b1, b2)
            if hit is not None:
                hits.append(Point2D(hit.x, hit.y, payload=("inter", i, j)))
    return hits


def collect_feature_points(obj, snap_verts, snap_mids, snap_inters):
    if obj is None or obj.type != "MESH":
        return []

    verts = obj.data.vertices
    points = []
    segments = []

    for v in verts:
        pos = obj.matrix_world @ v.co
        if snap_verts:
            points.append(Point2D(pos.x, pos.y, payload=("vert", v.index)))

    for edge in obj.data.edges:
        v1 = verts[edge.vertices[0]]
        v2 = verts[edge.vertices[1]]
        p1 = obj.matrix_world @ v1.co
        p2 = obj.matrix_world @ v2.co
        segments.append((p1, p2, v1.index, v2.index))

        if snap_mids:
            mid = (p1 + p2) * 0.5
            points.append(Point2D(mid.x, mid.y, payload=("mid", edge.index)))

    if snap_inters and len(segments) > 1:
        points.extend(segment_intersections(segments))

    return points


def snap_to_features(location, obj, snap_radius, scale_length, snap_verts, snap_mids, snap_inters):
    points = collect_feature_points(obj, snap_verts, snap_mids, snap_inters)
    if not points:
        return None

    tree = Quadtree.build(points)
    nearest = tree.query_nearest(Point2D(location.x, location.y), k=1)
    if not nearest:
        return None

    radius = snap_radius * (scale_length or 1.0)
    candidate = nearest[0]
    if candidate.distance_to(Point2D(location.x, location.y)) <= radius:
        return Vector((candidate.x, candidate.y, 0.0))

    return None


class AIHELPER_OT_sketch_mode(bpy.types.Operator):
    bl_idname = "aihelper.sketch_mode"
    bl_label = "Sketch Mode"
    bl_description = "Enter sketch mode"
    bl_options = {"REGISTER", "UNDO"}

    def __init__(self):
        self.start = None
        self.input_str = ""
        self.relative_mode = True
        self.axis_lock = None
        self.preview_str = ""
        self.angle_snap_enabled = False
        self.angle_snap_deg = 15.0
        self.snap_enabled = True
        self.snap_grid = True
        self.snap_verts = True
        self.snap_mids = True
        self.snap_inters = True
        self.snap_radius = 0.25
        self.grid_step = 1.0
        self.auto_constraints = True
        self.hv_tolerance_deg = 8.0

    def invoke(self, context, event):
        if context.area.type != "VIEW_3D":
            self.report({"WARNING"}, "Sketch Mode requires a 3D View")
            return {"CANCELLED"}

        self.start = None
        self.input_str = ""
        self.relative_mode = True
        self.axis_lock = None
        self.preview_str = ""
        props = context.scene.ai_helper
        self.auto_constraints = props.auto_constraints
        self.hv_tolerance_deg = props.hv_tolerance_deg
        self.snap_enabled = props.snap_enabled
        self.snap_grid = props.snap_grid
        self.snap_verts = props.snap_verts
        self.snap_mids = props.snap_mids
        self.snap_inters = props.snap_inters
        self.angle_snap_enabled = props.angle_snap_enabled
        self.angle_snap_deg = props.angle_snap_deg
        self.snap_radius = props.snap_radius
        self.grid_step = props.grid_step
        context.window_manager.modal_handler_add(self)
        self._set_header(context)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type in {"RIGHTMOUSE", "ESC"}:
            self._clear_header(context)
            return {"CANCELLED"}

        if event.type == "TAB" and event.value == "PRESS":
            self.relative_mode = not self.relative_mode
            self._set_header(context)
            return {"RUNNING_MODAL"}

        if event.type == "A" and event.value == "PRESS":
            self.auto_constraints = not self.auto_constraints
            context.scene.ai_helper.auto_constraints = self.auto_constraints
            self._set_header(context)
            return {"RUNNING_MODAL"}

        if event.type == "Q" and event.value == "PRESS":
            self.angle_snap_enabled = not self.angle_snap_enabled
            context.scene.ai_helper.angle_snap_enabled = self.angle_snap_enabled
            self._set_header(context)
            return {"RUNNING_MODAL"}

        if event.type in {"X", "Y"} and event.value == "PRESS":
            if self.axis_lock == event.type:
                self.axis_lock = None
            else:
                self.axis_lock = event.type
            self._set_header(context)
            return {"RUNNING_MODAL"}

        if event.type == "S" and event.value == "PRESS":
            self.snap_enabled = not self.snap_enabled
            context.scene.ai_helper.snap_enabled = self.snap_enabled
            self._set_header(context)
            return {"RUNNING_MODAL"}

        if event.type == "BACK_SPACE" and event.value == "PRESS":
            self.input_str = self.input_str[:-1]
            self._set_header(context)
            return {"RUNNING_MODAL"}

        if event.type == "MOUSEMOVE":
            self._update_preview(context, event)
            self._set_header(context)
            return {"RUNNING_MODAL"}

        if event.value == "PRESS" and event.ascii:
            if event.ascii in "0123456789-+.,@<=":
                self.input_str += event.ascii
                self._set_header(context)
                return {"RUNNING_MODAL"}

        if event.type == "RET" and event.value == "PRESS":
            if self.start is None:
                self.report({"WARNING"}, "Click to set the start point")
                return {"RUNNING_MODAL"}

            end = self._parse_input(self.input_str)
            if end is None:
                self.report({"WARNING"}, "Invalid input")
                return {"RUNNING_MODAL"}

            edge_id = self._add_line(context, self.start, end)
            if edge_id and self.auto_constraints:
                self._apply_auto_constraints(context, edge_id, self.start, end)
            if edge_id:
                obj = ensure_sketch_object(context)
                if obj is not None:
                    snapshot_state(obj, "Line")
            self.start = end
            self.input_str = ""
            self.preview_str = ""
            self._set_header(context)
            return {"RUNNING_MODAL"}

        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            point = self._mouse_to_plane(context, event)
            if point is None:
                return {"RUNNING_MODAL"}

            if self.start is None:
                self.start = point
                self._set_header(context)
                return {"RUNNING_MODAL"}

            edge_id = self._add_line(context, self.start, point)
            if edge_id and self.auto_constraints:
                self._apply_auto_constraints(context, edge_id, self.start, point)
            if edge_id:
                obj = ensure_sketch_object(context)
                if obj is not None:
                    snapshot_state(obj, "Line")
            self.start = point
            self.input_str = ""
            self.preview_str = ""
            self._set_header(context)
            return {"RUNNING_MODAL"}

        return {"RUNNING_MODAL"}

    def _set_header(self, context):
        mode = "REL" if self.relative_mode else "ABS"
        auto = "AUTO" if self.auto_constraints else "MANUAL"
        snap = "SNAP" if self.snap_enabled else "FREE"
        axis = self.axis_lock if self.axis_lock else "-"
        ang = f"{self.angle_snap_deg:g}" if self.angle_snap_enabled else "-"
        text = self.input_str if self.input_str else "<input>"
        preview = f" | {self.preview_str}" if self.preview_str else ""
        context.area.header_text_set(
            f"Sketch Mode | {mode} | {auto} | {snap} | ANG:{ang} | LOCK:{axis} | {text}{preview}"
        )

    def _clear_header(self, context):
        context.area.header_text_set(None)

    def _parse_input(self, text):
        return parse_input(text, self.start, self.relative_mode)

    def _parse_polar(self, text):
        return parse_polar(text, self.start)

    def _mouse_to_plane(self, context, event):
        region = context.region
        rv3d = context.region_data
        coord = (event.mouse_region_x, event.mouse_region_y)

        origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
        direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)

        if abs(direction.z) < 1e-6:
            return None

        t = -origin.z / direction.z
        location = origin + direction * t
        location = Vector((location.x, location.y, 0.0))
        return self._snap_location(context, location, event)

    def _snap_location(self, context, location, event):
        if not self.snap_enabled or event.shift:
            return self._apply_angle_snap(self._apply_axis_lock(location))

        snapped = self._snap_to_features(context, location)
        if snapped is not None:
            return self._apply_angle_snap(self._apply_axis_lock(snapped))

        return self._apply_angle_snap(self._apply_axis_lock(self._snap_to_grid(context, location)))

    def _apply_axis_lock(self, location):
        return apply_axis_lock(location, self.start, self.axis_lock)

    def _apply_angle_snap(self, location):
        return apply_angle_snap(
            location,
            self.start,
            self.angle_snap_enabled,
            self.angle_snap_deg,
            self.axis_lock,
        )

    def _update_preview(self, context, event):
        if self.start is None:
            self.preview_str = ""
            return

        point = self._mouse_to_plane(context, event)
        if point is None:
            self.preview_str = ""
            return
        self.preview_str = format_preview(self.start, point)

    def _snap_to_grid(self, context, location):
        return snap_to_grid(
            location,
            self.grid_step,
            context.scene.unit_settings.scale_length,
            self.snap_grid,
        )

    def _grid_step(self, context):
        return grid_step_value(self.grid_step, context.scene.unit_settings.scale_length)

    def _snap_to_features(self, context, location):
        obj = context.scene.objects.get("AI_Sketch")
        return snap_to_features(
            location,
            obj,
            self.snap_radius,
            context.scene.unit_settings.scale_length,
            self.snap_verts,
            self.snap_mids,
            self.snap_inters,
        )

    def _collect_feature_points(self, context):
        obj = context.scene.objects.get("AI_Sketch")
        return collect_feature_points(obj, self.snap_verts, self.snap_mids, self.snap_inters)

    def _segment_intersections(self, segments):
        return segment_intersections(segments)

    def _segment_intersection(self, p1, p2, p3, p4):
        return segment_intersection(p1, p2, p3, p4)

    def _point_on_segment(self, px, py, x1, y1, x2, y2):
        return point_on_segment(px, py, x1, y1, x2, y2)

    def _add_line(self, context, start, end):
        obj = ensure_sketch_object(context)
        if obj is None:
            return None
        bm = bmesh.new()
        bm.from_mesh(obj.data)

        v1 = bm.verts.new((start.x, start.y, 0.0))
        v2 = bm.verts.new((end.x, end.y, 0.0))
        edge = bm.edges.new((v1, v2))
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.verts.index_update()
        bm.edges.index_update()
        edge_index = edge.index

        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()
        return str(edge_index)

    def _apply_auto_constraints(self, context, edge_id, start, end):
        obj = ensure_sketch_object(context)
        if obj is None:
            return
        dx = end.x - start.x
        dy = end.y - start.y
        if abs(dx) < 1e-8 and abs(dy) < 1e-8:
            return

        angle = abs(math.degrees(math.atan2(dy, dx)))
        constraints = []

        if angle < self.hv_tolerance_deg or abs(angle - 180.0) < self.hv_tolerance_deg:
            constraints.append(HorizontalConstraint(id=new_constraint_id(), line=edge_id))
        elif abs(angle - 90.0) < self.hv_tolerance_deg:
            constraints.append(VerticalConstraint(id=new_constraint_id(), line=edge_id))

        for constraint in constraints:
            append_constraint(obj, constraint)

        if constraints:
            solve_mesh(obj, load_constraints(obj))


class AIHELPER_OT_add_circle(bpy.types.Operator):
    bl_idname = "aihelper.add_circle"
    bl_label = "Add Circle"
    bl_description = "Add a circle to the sketch mesh"
    bl_options = {"REGISTER", "UNDO"}

    radius: bpy.props.FloatProperty(
        name="Radius",
        description="Circle radius",
        min=0.0,
        default=1.0,
    )
    segments: bpy.props.IntProperty(
        name="Segments",
        description="Circle resolution",
        min=3,
        max=256,
        default=32,
    )
    center_x: bpy.props.FloatProperty(
        name="Center X",
        description="Circle center X",
        default=0.0,
    )
    center_y: bpy.props.FloatProperty(
        name="Center Y",
        description="Circle center Y",
        default=0.0,
    )
    tag: bpy.props.StringProperty(
        name="Tag",
        description="Optional tag for LLM selection",
        default="",
    )

    def invoke(self, context, _event):
        cursor = context.scene.cursor.location
        self.center_x = cursor.x
        self.center_y = cursor.y
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if self.radius <= 0.0:
            self.report({"WARNING"}, "Radius must be greater than 0")
            return {"CANCELLED"}

        entry = add_circle_to_sketch(
            context,
            Vector((self.center_x, self.center_y, 0.0)),
            self.radius,
            segments=self.segments,
            tag=self.tag.strip() or None,
        )
        if entry is None:
            self.report({"WARNING"}, "Unable to add circle")
            return {"CANCELLED"}

        self.report({"INFO"}, "Circle added")
        return {"FINISHED"}


class AIHELPER_OT_add_arc(bpy.types.Operator):
    bl_idname = "aihelper.add_arc"
    bl_label = "Add Arc"
    bl_description = "Add a circular arc to the sketch mesh"
    bl_options = {"REGISTER", "UNDO"}

    radius: bpy.props.FloatProperty(
        name="Radius",
        description="Arc radius",
        min=0.0,
        default=1.0,
    )
    segments: bpy.props.IntProperty(
        name="Segments",
        description="Arc resolution",
        min=1,
        max=256,
        default=16,
    )
    center_x: bpy.props.FloatProperty(
        name="Center X",
        description="Arc center X",
        default=0.0,
    )
    center_y: bpy.props.FloatProperty(
        name="Center Y",
        description="Arc center Y",
        default=0.0,
    )
    start_angle: bpy.props.FloatProperty(
        name="Start Angle",
        description="Start angle in degrees",
        default=0.0,
    )
    end_angle: bpy.props.FloatProperty(
        name="End Angle",
        description="End angle in degrees",
        default=90.0,
    )
    clockwise: bpy.props.BoolProperty(
        name="Clockwise",
        description="Sweep clockwise",
        default=False,
    )
    tag: bpy.props.StringProperty(
        name="Tag",
        description="Optional tag for LLM selection",
        default="",
    )

    def invoke(self, context, _event):
        cursor = context.scene.cursor.location
        self.center_x = cursor.x
        self.center_y = cursor.y
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if self.radius <= 0.0:
            self.report({"WARNING"}, "Radius must be greater than 0")
            return {"CANCELLED"}

        entry = add_arc_to_sketch(
            context,
            Vector((self.center_x, self.center_y, 0.0)),
            self.radius,
            self.start_angle,
            self.end_angle,
            segments=self.segments,
            clockwise=self.clockwise,
            tag=self.tag.strip() or None,
        )
        if entry is None:
            self.report({"WARNING"}, "Unable to add arc")
            return {"CANCELLED"}

        self.report({"INFO"}, "Arc added")
        return {"FINISHED"}


class AIHELPER_OT_edit_arc(bpy.types.Operator):
    bl_idname = "aihelper.edit_arc"
    bl_label = "Edit Arc"
    bl_description = "Edit the selected arc"
    bl_options = {"REGISTER", "UNDO"}

    radius: bpy.props.FloatProperty(
        name="Radius",
        description="Arc radius",
        min=0.0,
        default=1.0,
    )
    center_x: bpy.props.FloatProperty(
        name="Center X",
        description="Arc center X",
        default=0.0,
    )
    center_y: bpy.props.FloatProperty(
        name="Center Y",
        description="Arc center Y",
        default=0.0,
    )
    start_angle: bpy.props.FloatProperty(
        name="Start Angle",
        description="Start angle in degrees",
        default=0.0,
    )
    end_angle: bpy.props.FloatProperty(
        name="End Angle",
        description="End angle in degrees",
        default=90.0,
    )
    clockwise: bpy.props.BoolProperty(
        name="Clockwise",
        description="Sweep clockwise",
        default=False,
    )

    def invoke(self, context, _event):
        obj = ensure_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        circle = _selected_arc(obj)
        if not circle:
            self.report({"WARNING"}, "Select an arc")
            return {"CANCELLED"}

        center_id = circle.get("center")
        if center_id is None:
            self.report({"WARNING"}, "Arc center missing")
            return {"CANCELLED"}

        try:
            center = obj.data.vertices[int(center_id)].co
        except (ValueError, IndexError):
            self.report({"WARNING"}, "Arc center invalid")
            return {"CANCELLED"}

        self.center_x = center.x
        self.center_y = center.y
        self.radius = float(circle.get("radius", self.radius))
        self.clockwise = bool(circle.get("clockwise", False))

        start_angle = circle.get("start_angle")
        end_angle = circle.get("end_angle")
        if start_angle is None or end_angle is None:
            angles = _arc_angles_for_circle(obj, circle)
            if angles:
                start_angle, end_angle = angles
        if start_angle is not None:
            self.start_angle = float(start_angle)
        if end_angle is not None:
            self.end_angle = float(end_angle)

        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = ensure_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        circles = load_circles(obj)
        circle = _selected_arc(obj)
        if not circle:
            self.report({"WARNING"}, "Select an arc")
            return {"CANCELLED"}

        if self.radius <= 0.0:
            self.report({"WARNING"}, "Radius must be greater than 0")
            return {"CANCELLED"}

        center = Vector((self.center_x, self.center_y, 0.0))
        ok = _update_arc_geometry(
            obj,
            circle,
            center,
            self.radius,
            self.start_angle,
            self.end_angle,
            self.clockwise,
        )
        if not ok:
            self.report({"WARNING"}, "Unable to update arc")
            return {"CANCELLED"}

        circle_id = circle.get("id")
        for entry in circles:
            if entry.get("id") == circle_id:
                entry["radius"] = float(self.radius)
                entry["start_angle"] = float(self.start_angle)
                entry["end_angle"] = float(self.end_angle)
                entry["clockwise"] = bool(self.clockwise)
                entry["is_arc"] = True
                break
        save_circles(obj, circles)

        constraints = load_constraints(obj)
        if constraints:
            solve_mesh(obj, constraints)
        update_dimensions(context, obj, constraints)

        snapshot_state(obj, "Edit Arc")
        self.report({"INFO"}, "Arc updated")
        return {"FINISHED"}


class AIHELPER_OT_add_line(bpy.types.Operator):
    bl_idname = "aihelper.add_line"
    bl_label = "Add Line"
    bl_description = "Add a line segment to the sketch mesh"
    bl_options = {"REGISTER", "UNDO"}

    start_x: bpy.props.FloatProperty(
        name="Start X",
        description="Start X coordinate",
        default=0.0,
    )
    start_y: bpy.props.FloatProperty(
        name="Start Y",
        description="Start Y coordinate",
        default=0.0,
    )
    end_x: bpy.props.FloatProperty(
        name="End X",
        description="End X coordinate",
        default=1.0,
    )
    end_y: bpy.props.FloatProperty(
        name="End Y",
        description="End Y coordinate",
        default=0.0,
    )
    auto_constraints: bpy.props.BoolProperty(
        name="Auto Constraints",
        description="Apply horizontal/vertical constraints when applicable",
        default=True,
    )
    tag: bpy.props.StringProperty(
        name="Tag",
        description="Optional tag for LLM selection",
        default="",
    )

    def execute(self, context):
        hv_tolerance = getattr(context.scene.ai_helper, "hv_tolerance_deg", 8.0)
        entry = add_line_to_sketch(
            context,
            Vector((self.start_x, self.start_y, 0.0)),
            Vector((self.end_x, self.end_y, 0.0)),
            tag=self.tag.strip() or None,
            auto_constraints=self.auto_constraints,
            hv_tolerance_deg=hv_tolerance,
        )
        if entry is None:
            self.report({"WARNING"}, "Unable to add line")
            return {"CANCELLED"}

        self.report({"INFO"}, "Line added")
        return {"FINISHED"}


class AIHELPER_OT_add_rectangle(bpy.types.Operator):
    bl_idname = "aihelper.add_rectangle"
    bl_label = "Add Rectangle"
    bl_description = "Add an axis-aligned rectangle to the sketch mesh"
    bl_options = {"REGISTER", "UNDO"}

    width: bpy.props.FloatProperty(
        name="Width",
        description="Rectangle width",
        min=0.0,
        default=1.0,
    )
    height: bpy.props.FloatProperty(
        name="Height",
        description="Rectangle height",
        min=0.0,
        default=1.0,
    )
    center_x: bpy.props.FloatProperty(
        name="Center X",
        description="Rectangle center X",
        default=0.0,
    )
    center_y: bpy.props.FloatProperty(
        name="Center Y",
        description="Rectangle center Y",
        default=0.0,
    )
    rotation_deg: bpy.props.FloatProperty(
        name="Rotation",
        description="Rotation in degrees",
        default=0.0,
    )
    auto_constraints: bpy.props.BoolProperty(
        name="Auto Constraints",
        description="Apply horizontal/vertical constraints",
        default=True,
    )
    tag: bpy.props.StringProperty(
        name="Tag",
        description="Optional tag for LLM selection",
        default="",
    )

    def invoke(self, context, _event):
        cursor = context.scene.cursor.location
        self.center_x = cursor.x
        self.center_y = cursor.y
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        hv_tolerance = getattr(context.scene.ai_helper, "hv_tolerance_deg", 8.0)
        entry = add_rectangle_to_sketch(
            context,
            Vector((self.center_x, self.center_y, 0.0)),
            self.width,
            self.height,
            rotation_deg=self.rotation_deg,
            tag=self.tag.strip() or None,
            auto_constraints=self.auto_constraints,
            hv_tolerance_deg=hv_tolerance,
        )
        if entry is None:
            self.report({"WARNING"}, "Unable to add rectangle")
            return {"CANCELLED"}

        self.report({"INFO"}, "Rectangle added")
        return {"FINISHED"}


class AIHELPER_OT_add_polyline(bpy.types.Operator):
    bl_idname = "aihelper.add_polyline"
    bl_label = "Add Polyline"
    bl_description = "Add a polyline to the sketch mesh"
    bl_options = {"REGISTER", "UNDO"}

    points: bpy.props.StringProperty(
        name="Points",
        description="Points as x,y; x,y; x,y",
        default="",
    )
    closed: bpy.props.BoolProperty(
        name="Closed",
        description="Close the polyline",
        default=False,
    )
    auto_constraints: bpy.props.BoolProperty(
        name="Auto Constraints",
        description="Apply horizontal/vertical constraints",
        default=True,
    )
    tag: bpy.props.StringProperty(
        name="Tag",
        description="Optional tag for LLM selection",
        default="",
    )

    def invoke(self, context, _event):
        cursor = context.scene.cursor.location
        self.points = f"{cursor.x:.3f},{cursor.y:.3f}; {cursor.x + 1.0:.3f},{cursor.y:.3f}"
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        points = self._parse_points(self.points)
        if points is None:
            self.report({"WARNING"}, "Invalid points format")
            return {"CANCELLED"}

        hv_tolerance = getattr(context.scene.ai_helper, "hv_tolerance_deg", 8.0)
        entry = add_polyline_to_sketch(
            context,
            points,
            closed=self.closed,
            tag=self.tag.strip() or None,
            auto_constraints=self.auto_constraints,
            hv_tolerance_deg=hv_tolerance,
        )
        if entry is None:
            self.report({"WARNING"}, "Unable to add polyline")
            return {"CANCELLED"}

        self.report({"INFO"}, "Polyline added")
        return {"FINISHED"}

    def _parse_points(self, text):
        raw = text.strip()
        if not raw:
            return None
        points = []
        for chunk in raw.split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            if "," not in chunk:
                return None
            xs, ys = [part.strip() for part in chunk.split(",", 1)]
            try:
                x = float(xs)
                y = float(ys)
            except ValueError:
                return None
            points.append(Vector((x, y, 0.0)))
        if len(points) < 2:
            return None
        return points


class AIHELPER_OT_edit_rectangle(bpy.types.Operator):
    bl_idname = "aihelper.edit_rectangle"
    bl_label = "Edit Rectangle"
    bl_description = "Edit the selected rectangle"
    bl_options = {"REGISTER", "UNDO"}

    width: bpy.props.FloatProperty(
        name="Width",
        description="Rectangle width",
        min=0.0,
        default=1.0,
    )
    height: bpy.props.FloatProperty(
        name="Height",
        description="Rectangle height",
        min=0.0,
        default=1.0,
    )
    center_x: bpy.props.FloatProperty(
        name="Center X",
        description="Rectangle center X",
        default=0.0,
    )
    center_y: bpy.props.FloatProperty(
        name="Center Y",
        description="Rectangle center Y",
        default=0.0,
    )
    rotation_deg: bpy.props.FloatProperty(
        name="Rotation",
        description="Rotation in degrees",
        default=0.0,
    )

    def invoke(self, context, _event):
        obj = ensure_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        rect = _selected_rectangle(obj)
        if not rect:
            self.report({"WARNING"}, "Select a rectangle")
            return {"CANCELLED"}

        center = rect.get("center", [0.0, 0.0])
        if isinstance(center, list) and len(center) >= 2:
            self.center_x = float(center[0])
            self.center_y = float(center[1])
        self.width = float(rect.get("width", self.width))
        self.height = float(rect.get("height", self.height))
        self.rotation_deg = float(rect.get("rotation", self.rotation_deg))
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = ensure_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        rect = _selected_rectangle(obj)
        if not rect:
            self.report({"WARNING"}, "Select a rectangle")
            return {"CANCELLED"}

        if self.width <= 0.0 or self.height <= 0.0:
            self.report({"WARNING"}, "Width/height must be greater than 0")
            return {"CANCELLED"}

        center = Vector((self.center_x, self.center_y, 0.0))
        ok = _update_rectangle_geometry(
            obj,
            rect,
            center,
            self.width,
            self.height,
            self.rotation_deg,
        )
        if not ok:
            self.report({"WARNING"}, "Unable to update rectangle")
            return {"CANCELLED"}

        constraints = load_constraints(obj)
        if constraints:
            solve_mesh(obj, constraints)
        update_dimensions(context, obj, constraints)

        rect_id = rect.get("id")
        if rect_id:
            rectangles = load_rectangles(obj)
            for entry in rectangles:
                if entry.get("id") != rect_id:
                    continue
                vert_ids = [int(v) for v in entry.get("verts", [])]
                metrics = _rectangle_metrics_from_verts(obj, vert_ids)
                if metrics:
                    cx, cy, width, height, rotation = metrics
                    entry["center"] = [float(cx), float(cy)]
                    entry["width"] = float(width)
                    entry["height"] = float(height)
                    entry["rotation"] = float(rotation)
                else:
                    entry["center"] = [float(self.center_x), float(self.center_y)]
                    entry["width"] = float(self.width)
                    entry["height"] = float(self.height)
                    entry["rotation"] = float(self.rotation_deg)
                break
            save_rectangles(obj, rectangles)

        snapshot_state(obj, "Edit Rectangle")
        self.report({"INFO"}, "Rectangle updated")
        return {"FINISHED"}


class AIHELPER_OT_set_vertex_coords(bpy.types.Operator):
    bl_idname = "aihelper.set_vertex_coords"
    bl_label = "Set Vertex Coords"
    bl_description = "Set coordinates for the selected vertex"
    bl_options = {"REGISTER", "UNDO"}

    x: bpy.props.FloatProperty(
        name="X",
        description="X coordinate",
        default=0.0,
    )
    y: bpy.props.FloatProperty(
        name="Y",
        description="Y coordinate",
        default=0.0,
    )
    relative: bpy.props.BoolProperty(
        name="Relative",
        description="Apply coordinates as offsets",
        default=False,
    )

    def invoke(self, context, _event):
        obj = ensure_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        verts = _selected_vertices(obj)
        if len(verts) != 1:
            self.report({"WARNING"}, "Select 1 vertex")
            return {"CANCELLED"}

        v = verts[0]
        self.x = v.co.x
        self.y = v.co.y
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = ensure_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        verts = _selected_vertices(obj)
        if len(verts) != 1:
            self.report({"WARNING"}, "Select 1 vertex")
            return {"CANCELLED"}

        v = verts[0]
        if self.relative:
            v.co.x += self.x
            v.co.y += self.y
        else:
            v.co.x = self.x
            v.co.y = self.y
        v.co.z = 0.0
        obj.data.update()

        constraints = load_constraints(obj)
        if constraints:
            solve_mesh(obj, constraints)
        update_dimensions(context, obj, constraints)

        snapshot_state(obj, "Set Vertex Coords")
        self.report({"INFO"}, "Vertex updated")
        return {"FINISHED"}


class AIHELPER_OT_set_edge_length(bpy.types.Operator):
    bl_idname = "aihelper.set_edge_length"
    bl_label = "Set Edge Length"
    bl_description = "Set length for the selected edge"
    bl_options = {"REGISTER", "UNDO"}

    length: bpy.props.FloatProperty(
        name="Length",
        description="Target edge length",
        min=0.0,
        default=1.0,
    )
    anchor: bpy.props.EnumProperty(
        name="Anchor",
        description="Which part of the edge to keep fixed",
        items=[
            ("START", "Start", "Keep the first vertex fixed"),
            ("END", "End", "Keep the second vertex fixed"),
            ("CENTER", "Center", "Keep the midpoint fixed"),
        ],
        default="START",
    )

    def invoke(self, context, _event):
        obj = ensure_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        edges = _selected_edges(obj)
        if len(edges) != 1:
            self.report({"WARNING"}, "Select 1 edge")
            return {"CANCELLED"}

        edge = edges[0]
        v1 = obj.data.vertices[edge.vertices[0]]
        v2 = obj.data.vertices[edge.vertices[1]]
        self.length = (v2.co - v1.co).length
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = ensure_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        edges = _selected_edges(obj)
        if len(edges) != 1:
            self.report({"WARNING"}, "Select 1 edge")
            return {"CANCELLED"}

        edge = edges[0]
        v1 = obj.data.vertices[edge.vertices[0]]
        v2 = obj.data.vertices[edge.vertices[1]]
        vec = v2.co - v1.co
        length = vec.length
        if length < 1e-8:
            self.report({"WARNING"}, "Edge length too small")
            return {"CANCELLED"}

        direction = vec.normalized()
        target = max(self.length, 0.0)
        if self.anchor == "END":
            v1.co = v2.co - direction * target
        elif self.anchor == "CENTER":
            mid = (v1.co + v2.co) * 0.5
            offset = direction * (target * 0.5)
            v1.co = mid - offset
            v2.co = mid + offset
        else:
            v2.co = v1.co + direction * target

        v1.co.z = 0.0
        v2.co.z = 0.0
        obj.data.update()

        constraints = load_constraints(obj)
        if constraints:
            solve_mesh(obj, constraints)
        update_dimensions(context, obj, constraints)

        snapshot_state(obj, "Set Edge Length")
        self.report({"INFO"}, "Edge length updated")
        return {"FINISHED"}


class AIHELPER_OT_set_edge_angle(bpy.types.Operator):
    bl_idname = "aihelper.set_edge_angle"
    bl_label = "Set Edge Angle"
    bl_description = "Set angle for the selected edge"
    bl_options = {"REGISTER", "UNDO"}

    angle: bpy.props.FloatProperty(
        name="Angle",
        description="Target angle in degrees",
        default=0.0,
    )
    anchor: bpy.props.EnumProperty(
        name="Anchor",
        description="Which part of the edge to keep fixed",
        items=[
            ("START", "Start", "Keep the first vertex fixed"),
            ("END", "End", "Keep the second vertex fixed"),
            ("CENTER", "Center", "Keep the midpoint fixed"),
        ],
        default="START",
    )

    def invoke(self, context, _event):
        obj = ensure_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        edges = _selected_edges(obj)
        if len(edges) != 1:
            self.report({"WARNING"}, "Select 1 edge")
            return {"CANCELLED"}

        edge = edges[0]
        v1 = obj.data.vertices[edge.vertices[0]]
        v2 = obj.data.vertices[edge.vertices[1]]
        vec = v2.co - v1.co
        if vec.length > 1e-8:
            self.angle = math.degrees(math.atan2(vec.y, vec.x))
        else:
            self.angle = 0.0
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = ensure_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        edges = _selected_edges(obj)
        if len(edges) != 1:
            self.report({"WARNING"}, "Select 1 edge")
            return {"CANCELLED"}

        edge = edges[0]
        v1 = obj.data.vertices[edge.vertices[0]]
        v2 = obj.data.vertices[edge.vertices[1]]
        vec = v2.co - v1.co
        length = vec.length
        if length < 1e-8:
            self.report({"WARNING"}, "Edge length too small")
            return {"CANCELLED"}

        angle = math.radians(self.angle)
        direction = Vector((math.cos(angle), math.sin(angle), 0.0))
        if self.anchor == "END":
            v1.co = v2.co - direction * length
        elif self.anchor == "CENTER":
            mid = (v1.co + v2.co) * 0.5
            offset = direction * (length * 0.5)
            v1.co = mid - offset
            v2.co = mid + offset
        else:
            v2.co = v1.co + direction * length

        v1.co.z = 0.0
        v2.co.z = 0.0
        obj.data.update()

        constraints = load_constraints(obj)
        if constraints:
            solve_mesh(obj, constraints)
        update_dimensions(context, obj, constraints)

        snapshot_state(obj, "Set Edge Angle")
        self.report({"INFO"}, "Edge angle updated")
        return {"FINISHED"}


class AIHELPER_OT_set_angle_snap_preset(bpy.types.Operator):
    bl_idname = "aihelper.set_angle_snap_preset"
    bl_label = "Angle Snap Preset"
    bl_description = "Set the angle snap increment"
    bl_options = {"REGISTER", "UNDO"}

    angle: bpy.props.FloatProperty(
        name="Angle",
        description="Angle snap increment in degrees",
        default=15.0,
        min=1.0,
        max=90.0,
    )
    enable: bpy.props.BoolProperty(
        name="Enable",
        description="Enable angle snap",
        default=True,
        options={"HIDDEN"},
    )

    def execute(self, context):
        props = context.scene.ai_helper
        props.angle_snap_deg = self.angle
        if self.enable:
            props.angle_snap_enabled = True
        self.report({"INFO"}, f"Angle snap set to {self.angle:g} deg")
        return {"FINISHED"}


class AIHELPER_OT_select_tag(bpy.types.Operator):
    bl_idname = "aihelper.select_tag"
    bl_label = "Select Tag"
    bl_description = "Select sketch entities by tag"
    bl_options = {"REGISTER", "UNDO"}

    tag: bpy.props.StringProperty(
        name="Tag",
        description="Tag to select",
        default="",
    )
    extend: bpy.props.BoolProperty(
        name="Extend",
        description="Extend current selection",
        default=False,
    )

    def execute(self, context):
        obj = ensure_sketch_object(context)
        if obj is None or obj.type != "MESH":
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        tag = self.tag.strip()
        if not tag:
            self.report({"WARNING"}, "Tag is empty")
            return {"CANCELLED"}

        tags = load_tags(obj)
        if tag not in tags:
            self.report({"WARNING"}, f"Tag not found: {tag}")
            return {"CANCELLED"}

        verts, edges = resolve_tags(obj, [tag], prefer_center=True)
        if not verts and not edges:
            self.report({"WARNING"}, f"Tag has no geometry: {tag}")
            return {"CANCELLED"}

        _set_selection(obj, verts=verts, edges=edges, extend=self.extend)
        context.view_layer.objects.active = obj
        self.report({"INFO"}, f"Selected tag: {tag}")
        return {"FINISHED"}


class AIHELPER_OT_inspector_apply_vertex(bpy.types.Operator):
    bl_idname = "aihelper.inspector_apply_vertex"
    bl_label = "Apply Vertex"
    bl_description = "Apply inspector vertex values"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.ai_helper
        result = bpy.ops.aihelper.set_vertex_coords(
            x=props.inspector_vertex_x,
            y=props.inspector_vertex_y,
            relative=False,
        )
        if "FINISHED" not in result:
            self.report({"WARNING"}, "Inspector vertex update failed")
            return {"CANCELLED"}
        return {"FINISHED"}


class AIHELPER_OT_inspector_apply_edge_length(bpy.types.Operator):
    bl_idname = "aihelper.inspector_apply_edge_length"
    bl_label = "Apply Edge Length"
    bl_description = "Apply inspector edge length"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.ai_helper
        result = bpy.ops.aihelper.set_edge_length(
            length=props.inspector_edge_length,
            anchor=props.inspector_edge_anchor,
        )
        if "FINISHED" not in result:
            self.report({"WARNING"}, "Inspector edge length update failed")
            return {"CANCELLED"}
        return {"FINISHED"}


class AIHELPER_OT_inspector_apply_edge_angle(bpy.types.Operator):
    bl_idname = "aihelper.inspector_apply_edge_angle"
    bl_label = "Apply Edge Angle"
    bl_description = "Apply inspector edge angle"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.ai_helper
        result = bpy.ops.aihelper.set_edge_angle(
            angle=props.inspector_edge_angle,
            anchor=props.inspector_edge_anchor,
        )
        if "FINISHED" not in result:
            self.report({"WARNING"}, "Inspector edge angle update failed")
            return {"CANCELLED"}
        return {"FINISHED"}


class AIHELPER_OT_inspector_apply_arc(bpy.types.Operator):
    bl_idname = "aihelper.inspector_apply_arc"
    bl_label = "Apply Arc"
    bl_description = "Apply inspector arc values"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.ai_helper
        result = bpy.ops.aihelper.edit_arc(
            radius=props.inspector_arc_radius,
            center_x=props.inspector_arc_center_x,
            center_y=props.inspector_arc_center_y,
            start_angle=props.inspector_arc_start_angle,
            end_angle=props.inspector_arc_end_angle,
            clockwise=props.inspector_arc_clockwise,
        )
        if "FINISHED" not in result:
            self.report({"WARNING"}, "Inspector arc update failed")
            return {"CANCELLED"}
        return {"FINISHED"}


class AIHELPER_OT_inspector_apply_rectangle(bpy.types.Operator):
    bl_idname = "aihelper.inspector_apply_rectangle"
    bl_label = "Apply Rectangle"
    bl_description = "Apply inspector rectangle values"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.ai_helper
        result = bpy.ops.aihelper.edit_rectangle(
            width=props.inspector_rect_width,
            height=props.inspector_rect_height,
            center_x=props.inspector_rect_center_x,
            center_y=props.inspector_rect_center_y,
            rotation_deg=props.inspector_rect_rotation,
        )
        if "FINISHED" not in result:
            self.report({"WARNING"}, "Inspector rectangle update failed")
            return {"CANCELLED"}
        return {"FINISHED"}


def register():
    bpy.utils.register_class(AIHELPER_OT_sketch_mode)
    bpy.utils.register_class(AIHELPER_OT_add_line)
    bpy.utils.register_class(AIHELPER_OT_add_circle)
    bpy.utils.register_class(AIHELPER_OT_add_arc)
    bpy.utils.register_class(AIHELPER_OT_edit_arc)
    bpy.utils.register_class(AIHELPER_OT_add_rectangle)
    bpy.utils.register_class(AIHELPER_OT_add_polyline)
    bpy.utils.register_class(AIHELPER_OT_edit_rectangle)
    bpy.utils.register_class(AIHELPER_OT_set_vertex_coords)
    bpy.utils.register_class(AIHELPER_OT_set_edge_length)
    bpy.utils.register_class(AIHELPER_OT_set_edge_angle)
    bpy.utils.register_class(AIHELPER_OT_set_angle_snap_preset)
    bpy.utils.register_class(AIHELPER_OT_select_tag)
    bpy.utils.register_class(AIHELPER_OT_inspector_apply_vertex)
    bpy.utils.register_class(AIHELPER_OT_inspector_apply_edge_length)
    bpy.utils.register_class(AIHELPER_OT_inspector_apply_edge_angle)
    bpy.utils.register_class(AIHELPER_OT_inspector_apply_arc)
    bpy.utils.register_class(AIHELPER_OT_inspector_apply_rectangle)


def unregister():
    bpy.utils.unregister_class(AIHELPER_OT_inspector_apply_rectangle)
    bpy.utils.unregister_class(AIHELPER_OT_inspector_apply_arc)
    bpy.utils.unregister_class(AIHELPER_OT_inspector_apply_edge_angle)
    bpy.utils.unregister_class(AIHELPER_OT_inspector_apply_edge_length)
    bpy.utils.unregister_class(AIHELPER_OT_inspector_apply_vertex)
    bpy.utils.unregister_class(AIHELPER_OT_select_tag)
    bpy.utils.unregister_class(AIHELPER_OT_set_angle_snap_preset)
    bpy.utils.unregister_class(AIHELPER_OT_set_edge_angle)
    bpy.utils.unregister_class(AIHELPER_OT_set_edge_length)
    bpy.utils.unregister_class(AIHELPER_OT_set_vertex_coords)
    bpy.utils.unregister_class(AIHELPER_OT_edit_rectangle)
    bpy.utils.unregister_class(AIHELPER_OT_add_polyline)
    bpy.utils.unregister_class(AIHELPER_OT_add_rectangle)
    bpy.utils.unregister_class(AIHELPER_OT_edit_arc)
    bpy.utils.unregister_class(AIHELPER_OT_add_arc)
    bpy.utils.unregister_class(AIHELPER_OT_add_circle)
    bpy.utils.unregister_class(AIHELPER_OT_add_line)
    bpy.utils.unregister_class(AIHELPER_OT_sketch_mode)
