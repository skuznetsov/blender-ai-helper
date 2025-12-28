# UX Spec: AI Helper Sketch + LLM (Fusion-like)

## Goals
- AutoCAD-like precision in 2D with fast numeric input.
- Fusion-like param workflow (sketch as source of truth, editable ops).
- LLM assistance that is safe (preview/apply) and predictable.
- Fast iteration: quick prototyping, easy edits in 2D and 3D.

## Non-Goals (for now)
- Full assembly/constraints between objects.
- CAM toolpaths or manufacturing output.
- Multi-user collaboration.

## Core Modes
1) Sketch Mode (2D)
   - Create/modify lines, arcs, circles, rectangles, polylines.
   - Constraints + dimensions are first-class.
2) 3D Ops Mode
   - Extrude, Revolve, and later Loft/Sweep.
   - Ops store parameters; rebuild from sketch.
3) LLM Assist
   - Prompt-driven edits with preview, selection tagging, and undo.

## Layout + Interaction Model
- Left toolbar: sketch tools, constraint tools, 3D ops.
- Right sidebar panels:
  - Sketch Settings (snap, angle snap, auto-constraints).
  - Constraints + Diagnostics.
  - Dimensions (edit labels).
  - Tags (LLM-created).
  - History (snapshots).
  - LLM Preview (prompt, image, presets, recipes).
- Bottom command bar: numeric entry (x,y, @len<angle, dx,dy).

## Primary Workflows

### A) Precise 2D Sketch
- Click to place, then type in command bar for exact coordinates.
- Axis lock (X/Y), angle snap presets (15/30/45), grid/endpoint/midpoint snap.
- Quick dialogs for exact vertex coords, edge length, edge angle.
- Constraints are discoverable: add from panel or auto-constraints on draw.

### B) Direct Numeric Edit (Fusion-like)
- Select entity and edit in a Property Inspector:
  - Vertex: X/Y
  - Line: length, angle
  - Arc: center, radius, start/end angle
  - Rectangle: width, height, rotation
- Dimension labels are editable and act as constraints.

### C) LLM-Assisted Edits
- Select geometry → prompt → preview tool calls → apply.
- Tags provide stable referencing across edits (e.g., "hole_1").
- Image prompts: sketch from annotated reference; user adds notes.
- Safety: always preview, show diff/summary, allow undo.

### D) 3D Ops from Sketch
- Extrude/Revolve from selected edges or full sketch.
- Rebuild 3D ops when sketch changes.
- Parametric modifiers (shell/fillet) attached to ops.

## Predictability Rules (Speed + Trust)
- Snapping priority order: endpoint > intersection > midpoint > grid.
- Deterministic solve order (stable results for same inputs).
- Time budget per solve; show diagnostics if not converging.
- No hidden mutations: all ops recorded in history/snapshots.

## LLM Safety + UX
- Preview/apply flow with explicit confirmation.
- Selection summary is compact; no raw mesh dump.
- Image data: prefer HTTPS URL; data URL allowed for PNG/JPEG <20MB.
- If a tool call would delete/clear, require extra confirmation.

## Performance Targets
- Sketch solve: <16ms for 200 constraints (interactive).
- Prompt preview: <1.5s for cached/frequent prompts.
- Rebuild: incremental when possible, full rebuild only on topology change.

## Data Flow Summary
Sketch Entities + Constraints
  -> Solver (PBD + optional DG relax)
  -> 3D Ops (Extrude/Revolve/Loft/Sweep)
  -> History Snapshots + LLM Preview

## Future Extensions
- Loft/Sweep with multi-section profiles.
- Constraint conflict visualization (highlight entities).
- Assembly constraints between objects.
- Parametric feature timeline (Fusion-like edit stack).
