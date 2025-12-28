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
- [x] Sketch Mode modal operator with command bar input.
  - Input formats: `x,y`, `@len<angle`, `dx,dy`.
  - DoD: user can draw line with numeric input.
  - [x] Axis lock toggle (X/Y) while drawing.
  - [x] Live length/angle preview while moving mouse.
  - [x] Angle snap toggle (Q) with configurable increment.
  - [x] Angle snap presets (15/30/45).
- [x] Precision coordinate edit for vertices (dialog).
  - DoD: selected vertex can be set to exact XY coordinates.
- [x] Precision edge length edit (dialog).
  - DoD: selected edge can be set to exact length.
- [x] Precision edge angle edit (dialog).
  - DoD: selected edge can be set to exact angle.
- [x] Snapping (grid, endpoints, midpoints, intersections) using quadtree.
  - DoD: snap selection is stable and predictable.
- [x] Constraint storage on sketch mesh + solver bridge.
  - DoD: constraints stored on sketch mesh and solver updates geometry.
- [x] Dimension overlay objects (length/angle/radius) with direct edit.
  - DoD: editing a dimension updates geometry via solver.
  - [x] Distance labels as text objects.
  - [x] Direct edit on labels (dialog).
  - [x] Angle labels + direct edit.
  - [x] Radius labels + direct edit.
- [x] Constraint UI (toggle per entity + auto-constraints on draw).
  - DoD: constraints appear and can be edited or removed.
  - [x] Manual add/edit/remove for distance/h/v/fix via panel.
  - [x] Angle constraint add/edit.
  - [x] Radius constraint add/edit.
  - [x] Coincident constraint add.
  - [x] Midpoint constraint add.
  - [x] Equal length constraint add.
  - [x] Concentric constraint add.
  - [x] Symmetry constraint add.
  - [x] Tangent constraint add.
  - [x] Parallel/Perpendicular constraints in panel.
  - [x] Auto-constraints on draw (horizontal/vertical).
  - [x] Constraint add dialogs prefill current values.
  - [x] Constraint diagnostics list.
  - [x] Select constraint geometry from list.
  - [x] Select worst constraint from diagnostics.
  - [x] Clear diagnostics button.
- [x] Circle tool + radius constraints.
  - DoD: circle can be added and radius constraints solve against it.

## 5) 3D ops (SAFE)
- [x] Extrude + Revolve operators (parametric, editable).
  - DoD: parameters can be adjusted after creation.
  - [x] Extrude via edge extrusion + stored params.
  - [x] Revolve via Screw modifier + stored params.
- [x] Rebuild policy: sketch is source of truth; 3D ops regenerate on change.
  - DoD: changes propagate reliably without corrupting mesh.
  - [x] Rebuild operator for extrude/revolve.
  - [x] Auto-rebuild on sketch edits.

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

## 9) Phase 2 features (CAUTION)
- [x] Parametric shell modifier for 3D ops.
  - DoD: Solidify modifier applied with stored params; rebuild preserves thickness.
- [x] Parametric fillet/bevel modifier for 3D ops.
  - DoD: Bevel modifier applied with stored params; rebuild preserves settings.
- [x] Sketch history timeline (last N ops).
  - DoD: timeline UI lists ops; user can jump to previous state.
- [x] LLM auto-constraints from prompt.
  - DoD: prompt yields constraint suggestions; preview & apply flow.

## 10) LLM sketch generation (SAFE)
- [x] Text-to-sketch tool calls (add_line, add_circle, clear_sketch, select_sketch_entities).
  - DoD: `blender -b --python scripts/validate_blender_ops.py` passes new LLM sketch tests.
- [x] LLM tag mapping for sketch entities (selection by tag).
  - DoD: tags resolve to correct verts/edges in tests.
- [x] Image-assisted prompt support (path + notes; payload packaging).
  - DoD: preview accepts image path without errors (mock mode).
- [x] Docs: update LLM preview section for sketch + image prompts.

## 11) Grok vision bridge (SAFE)
- [x] Use Grok multimodal message format when image path is provided.
  - DoD: `python -m py_compile ../../ML/agents_assembly/llm_interfaces/grok.py`.
- [x] LLM adapter chooses vision path when available; fallback to JSON-only.
  - DoD: `blender -b --python scripts/validate_blender_ops.py`.
- [x] Add mock-mode test for image prompt path.
  - DoD: `blender -b --python scripts/validate_blender_ops.py`.

## 12) Sketch primitives (SAFE)
- [x] Add polyline + rectangle helpers for LLM sketch generation.
  - DoD: `blender -b --python scripts/validate_blender_ops.py`.
- [x] Expose polyline/rectangle tool calls and dispatcher handlers.
  - DoD: LLM tests cover new tools.
- [x] Add optional UI operators for rectangle/polyline.
  - DoD: operators show in UI and run without errors.
- [x] Update docs for new sketch tools.

## 13) Arc tool (SAFE)
- [x] Add arc helper + circle metadata support (start/end angle).
  - DoD: `blender -b --python scripts/validate_blender_ops.py`.
- [x] Expose add_arc tool call + dispatcher handler.
  - DoD: LLM tests cover add_arc.
- [x] Add UI operator for arc creation.
  - DoD: operator runs without errors.
- [x] Update docs for arc usage.

## 14) Rotated rectangle (SAFE)
- [x] Add rotation support to rectangle helper and UI.
  - DoD: `blender -b --python scripts/validate_blender_ops.py`.
- [x] Expose rotation in add_rectangle tool call.
  - DoD: LLM tests cover rotated rectangle.
- [x] Update docs for rectangle rotation.

## 15) Arc edit (SAFE)
- [x] Add edit-arc operator (center/radius/angles).
  - DoD: `blender -b --python scripts/validate_blender_ops.py`.
- [x] Update docs for arc editing.

## 16) LLM arc edit (SAFE)
- [x] Expose edit_arc tool call (optional tag targeting).
  - DoD: `blender -b --python scripts/validate_blender_ops.py`.
- [x] Add LLM test for edit_arc.
  - DoD: `blender -b --python scripts/validate_blender_ops.py`.

## 17) Prompt presets (SAFE)
- [x] Add prompt preset selector + apply operator.
  - DoD: `blender -b --python scripts/validate_blender_ops.py`.
- [x] Add tests for prompt preset operator.
  - DoD: `blender -b --python scripts/validate_blender_ops.py`.
- [x] Update docs for prompt presets.

## 18) Rectangle edit (SAFE)
- [x] Add edit-rectangle operator (size/center/rotation).
  - DoD: `blender -b --python scripts/validate_blender_ops.py`.
- [x] Store rectangle metadata for edits.
  - DoD: `blender -b --python scripts/validate_blender_ops.py`.
- [x] Update docs and tests for edit rectangle.
  - DoD: `blender -b --python scripts/validate_blender_ops.py`.

## 19) LLM rectangle edit (SAFE)
- [x] Expose edit_rectangle tool call (optional tag targeting).
  - DoD: `blender -b --python scripts/validate_blender_ops.py`.
- [x] Add LLM test for edit_rectangle.
  - DoD: `blender -b --python scripts/validate_blender_ops.py`.

## 20) Parametric presets (SAFE)
- [x] Add parameterized preset operator + dialog.
  - DoD: `blender -b --python scripts/validate_blender_ops.py`.
- [x] Add tests for parameterized presets.
  - DoD: `blender -b --python scripts/validate_blender_ops.py`.
- [x] Update docs for parameterized presets.

## 21) Grok vision smoke test (SAFE)
- [x] Make Grok smoke test runnable outside Blender (avoid bpy dependency; correct adapter path).
  - DoD: `python3 scripts/grok_vision_smoke.py` reaches API client without bpy errors.
- [x] Run vision smoke test with real API.
  - DoD: `GROK_VISION_IMAGE_URL=... /tmp/ai_helper_grok_venv/bin/python scripts/grok_vision_smoke.py` returns 0 and prints tool calls.
  - Note: xAI vision accepts HTTPS image URLs; data URLs/local files fail with decode errors.

## 22) Preset expansion (SAFE)
- [x] Add new parameterized presets (frame, bolt circle, slot pair) + operator fields.
  - DoD: `blender -b --python scripts/validate_blender_ops.py`.

## 23) LLM recipes UI (SAFE)
- [x] Add recipe list + operator + UI description + tests + docs.
  - DoD: `blender -b --python scripts/validate_blender_ops.py`.

## 24) Vision settings UI (SAFE)
- [x] Add Grok model + vision model + vision URL settings in Preferences and wire into preview.
  - DoD: `blender -b --python scripts/validate_blender_ops.py`.

## 25) Blender aiohttp helper (CAUTION)
- [x] Add UI action and guidance to install aiohttp into Blender Python (no auto-run in tests).
  - DoD: `blender -b --python scripts/validate_blender_ops.py`.

## 26) Vision upload hook (CAUTION)
- [x] Add optional upload command for local images; use URL in vision requests.
  - DoD: `blender -b --python scripts/validate_blender_ops.py`.

## 27) Grok 4.1 data URL support (SAFE)
- [x] Gate data URL usage to grok-4-1-fast-* models and allow up to 20MB.
  - DoD: `blender -b --python scripts/validate_blender_ops.py`.

## 28) Grok base64 validation (SAFE)
- [x] Validate data URL with real JPEG and update smoke test to download a JPEG.
  - DoD: `GROK_VISION_USE_DATA_URL=1 /tmp/ai_helper_grok_venv/bin/python scripts/grok_vision_smoke.py`.

## 29) Data URL fallback (SAFE)
- [x] Retry vision requests via upload command when data URL decode fails.
  - DoD: `blender -b --python scripts/validate_blender_ops.py`.

## 30) Tag selection UI (SAFE)
- [x] Add tag list panel + select/add operators for sketch tags.
  - DoD: `blender -b --python scripts/validate_blender_ops.py`.

## 31) Extrude selection (SAFE)
- [x] Extrude selected edges when present; store selection for rebuild.
  - DoD: `blender -b --python scripts/validate_blender_ops.py`.

## 32) Fusion-like UX spec (SAFE)
- [x] Draft UX spec for precise 2D sketch + parametric 3D + LLM assist.
  - DoD: `docs/ux_spec.md` exists with workflows, panels, and predictability rules.

## 33) Property Inspector panel (SAFE)
- [x] Add Property Inspector for numeric edits (vertex/edge/arc/rectangle).
  - DoD: inspector edits update geometry via solver.

## 34) Loft/Sweep ops (CAUTION)
- [ ] Add profile-based Loft/Sweep with rebuild support.
  - DoD: `blender -b --python scripts/validate_blender_ops.py` passes loft/sweep tests.
