# Quick Start

## Install
1. Open Blender 5.0.
2. Edit > Preferences > Add-ons > Install.
3. Select the `ai_helper` folder from this repo.
4. Enable the add-on.

## LLM Preview
1. Open View3D > Sidebar > AI Helper.
2. Enter a prompt.
3. Click Preview to generate tool calls.
4. Inspect the preview and click Apply.

## Sketch (WIP)
- Sketch Mode creates line segments on the XY plane.
- Click to set a start point, then type `x,y` and press Enter.
- Default mode is REL; press Tab to toggle ABS/REL or prefix `=` for absolute.
- Polar input: `@len<angle` (degrees).
- Constraints: select an edge or vertices, then use the Constraints panel to add Distance/Horizontal/Vertical/Fix.
- Dimensions: use Update Dimensions to create text labels for distance constraints.
- Dimension edit: select a label and use Edit Selected Dimension to update the distance.

## Notes
- The LLM adapter defaults to mock mode unless a Grok adapter path is set.
- Large mesh data is not sent to the LLM; only selection summaries.
