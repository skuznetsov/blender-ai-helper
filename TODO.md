# TODO

Legend: [ ] TODO | [~] IN_PROGRESS | [x] DONE

## 0) Project bootstrap (SAFE)
- [x] Create TODO.md (project plan).
- [x] Create Blender add-on scaffold (bl_info, register/unregister, basic panel).
  - DoD: add-on loads without errors; panel visible in 3D View > N-panel.
  - Fallback: `python3 -m py_compile` on add-on modules.
- [x] Define config + logging (addon name, version, debug toggle).
  - DoD: config values exposed in Preferences panel.

## 1) Sketch data model (SAFE)
- [x] Data structures for sketch entities (Point, Line, Arc, Circle, Polyline).
  - DoD: unit tests or demo script that creates entities and serializes them.
- [x] Constraint objects (Distance, Angle, H/V, Parallel, Perpendicular, Coincident, Radius, Midpoint, Equal Length, Concentric, Symmetry, Tangent, Fix).
  - DoD: constraints can be created/serialized and validated.

## 2) Solver MVP (SAFE)
- [x] PBD / Gauss-Seidel solver core (iterative projection) with time budget.
  - DoD: synthetic sketch converges within tolerance in <10ms for 100 constraints.
- [x] Conflict handling policy (detect non-convergence + constraint diagnostics).
  - DoD: conflicting constraints produce readable error + soft fallback.
- [x] Optional DG relax (distance-only) as a pre-solve step.
  - DoD: toggled relax improves convergence on bad initial states.

## 3) Spatial indexing (SAFE)
- [x] Quadtree for 2D snapping and nearest queries.
  - DoD: query_radius / nearest returns correct points in tests.

## 4) Sketch UX (CAUTION)
- [~] Sketch Mode modal operator with command bar input.
  - Input formats: `x,y`, `@len<angle`, `dx,dy`.
  - DoD: user can draw line with numeric input.
  - [~] Axis lock toggle (X/Y) while drawing (needs Blender validation).
  - [~] Live length/angle preview while moving mouse (needs Blender validation).
  - [~] Angle snap toggle (Q) with configurable increment (needs Blender validation).
  - [~] Angle snap presets (15/30/45) (needs Blender validation).
- [~] Precision coordinate edit for vertices (dialog).
  - DoD: selected vertex can be set to exact XY coordinates.
- [~] Precision edge length edit (dialog).
  - DoD: selected edge can be set to exact length.
- [~] Precision edge angle edit (dialog).
  - DoD: selected edge can be set to exact angle.
- [~] Snapping (grid, endpoints, midpoints, intersections) using quadtree.
  - DoD: snap selection is stable and predictable.
- [x] Constraint storage on sketch mesh + solver bridge.
  - DoD: constraints stored on sketch mesh and solver updates geometry.
- [~] Dimension overlay objects (length/angle/radius) with direct edit.
  - DoD: editing a dimension updates geometry via solver.
  - [x] Distance labels as text objects.
  - [x] Direct edit on labels (dialog).
  - [~] Angle labels + direct edit (needs Blender validation).
  - [~] Radius labels + direct edit (needs Blender validation).
- [~] Constraint UI (toggle per entity + auto-constraints on draw).
  - DoD: constraints appear and can be edited or removed.
  - [x] Manual add/edit/remove for distance/h/v/fix via panel.
  - [~] Angle constraint add/edit (needs Blender validation).
  - [~] Radius constraint add/edit (needs Blender validation).
  - [~] Coincident constraint add (needs Blender validation).
  - [~] Midpoint constraint add (needs Blender validation).
  - [~] Equal length constraint add (needs Blender validation).
  - [~] Concentric constraint add (needs Blender validation).
  - [~] Symmetry constraint add (needs Blender validation).
  - [~] Tangent constraint add (needs Blender validation).
  - [~] Parallel/Perpendicular constraints in panel (needs Blender validation).
  - [x] Auto-constraints on draw (horizontal/vertical).
  - [~] Constraint add dialogs prefill current values (needs Blender validation).
  - [~] Constraint diagnostics list (needs Blender validation).
  - [~] Select constraint geometry from list (needs Blender validation).
  - [~] Select worst constraint from diagnostics (needs Blender validation).
  - [~] Clear diagnostics button (needs Blender validation).
- [~] Circle tool + radius constraints (needs Blender validation).
  - DoD: circle can be added and radius constraints solve against it.

## 5) 3D ops (SAFE)
- [~] Extrude + Revolve operators (parametric, editable).
  - DoD: parameters can be adjusted after creation.
  - [x] Extrude via edge extrusion + stored params.
  - [x] Revolve via Screw modifier + stored params.
- [~] Rebuild policy: sketch is source of truth; 3D ops regenerate on change.
  - DoD: changes propagate reliably without corrupting mesh.
  - [x] Rebuild operator for extrude/revolve.
  - [~] Auto-rebuild on sketch edits (handler implemented; needs Blender validation).

## 6) LLM integration (SAFE)
- [x] Selection serializer (compact summary, units, bbox, counts).
  - DoD: summary fits in small token budget; no raw mesh dumps.
- [x] Grok client adapter (wrap ../../ML/agents_assembly/llm_interfaces/grok.py).
  - DoD: mock call returns structured function calls.
- [x] Function dispatcher with preview/apply flow + undo safety.
  - DoD: operations are previewed before apply; undo works.

## 7) Performance & stability (SAFE)
- [x] Frame time budget for solver; early exit on low error.
  - DoD: keeps UI responsive under 200 constraints.
- [x] Stress tests on 500+ constraints.
  - DoD: no crashes; clear warnings on limits.

## 8) Documentation (SAFE)
- [x] Quick-start guide + UX cheat sheet (inputs, constraints, modes).
  - DoD: new user can draw lines and preview tool calls in <10 minutes.
- [x] Architecture notes (solver, data flow, LLM safety).
  - DoD: explains rebuild and conflict policy.

## Ideas backlog
- Constraint set parity (Fusion-like): tangent, equal, symmetry, midpoint, concentric implemented; needs Blender validation.
- Constraint diagnostics UI (highlight conflicting entities).
- History timeline for sketch edits.
- Parametric constraints on 3D ops (draft, shell, fillet).
- LLM: autogenerate constraints based on prompt.
