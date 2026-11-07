# Stop Motion Studio 0.1.0: install and hand-test checklist

## Install
Blender 5.2 › Edit › Preferences › Get Extensions › ▾ (top right) › Install from Disk… › pick `stop_motion_studio-0.1.0.zip`.

## Already tested headless (Blender 5.2 Python module)
- Shoot appends shots; each holds for 1/2/3 frames; every key is constant.
- Rig bones, rig custom props (IK/FK etc.) and shape keys are keyed; meshes bent by a rig are not keyed separately.
- Pose over an earlier shot replaces it; later shots are untouched.
- Hold +/-, delete (gap closes), duplicate: later shots' keys move with them.
- Ghost shows the last 1–3 shots, fading; on an earlier shot it shows the shots before it.

## Needs a real screen (please check)
1. Open a file with a camera and a rigged puppet. In the 3D view sidebar (N) › Stop Motion › "Set Up Stop Motion Workspace". Expect: a new "Stop Motion" tab with the camera view on the left and the free view on the right.
2. Pose in the free view, press Enter with the mouse over a 3D view. Expect: "LIVE · shot 2" in the camera view's corner and a thumbnail in Shots.
3. Pose again, Enter. Expect a faint ghost of the previous shot in the camera view, not in the free view.
4. ← → step through shots. On an earlier shot the corner says "POSING OVER". Move the puppet, Enter. That shot is replaced.
5. Alt+Backspace on a shot deletes it; Ctrl+Z brings it back.
6. F5 hides headers, sidebar and status bar; F5 again restores. Shift+F5 is camera only, full window.
7. F6 ghost on/off.
8. Review & Export › Movie: a `films` folder next to the .blend gets an MP4.
9. Save, close, reopen: shots, thumbnails and ghost still there.

## Known gaps in 0.1.0
- Shot cards are a grid in the sidebar, not yet the strip from the mockup.
- No grab rings, swap panel, cameras, lighting, solid world or sculpt yet (steps 2–5).
- The top bar stays visible when hiding the UI, except in Shift+F5 camera-only mode.
