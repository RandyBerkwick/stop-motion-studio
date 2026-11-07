# Stop Motion Studio: install and hand-test checklist

## Install
Blender 5.2 › Edit › Preferences › Get Extensions › ▾ (top right) › Install from Disk… › pick the zip from `scripts/build.sh` (or use `scripts/link_dev_mac.sh` while developing).

## Already tested headless (Blender 5.2 Python module)
- Shoot appends shots; each holds for 1/2/3 frames; every key is constant.
- Rig bones, rig custom props (IK/FK etc.) and shape keys are keyed; meshes bent by a rig are not keyed separately.
- Pose over an earlier shot replaces it; later shots are untouched.
- Hold +/-, delete (gap closes), duplicate: later shots' keys move with them.
- Ghost shows the last 1–3 shots, fading; on an earlier shot it shows the shots before it.

- Make Puppet finds rings (head, body, hips, hands, feet) from bone names, and swap sets from shape keys named `Set_Part` and from meshes parented to the rig named `Set_Part`.
- Feet on simple two-bone legs get an IK pin: moving the hips leaves pinned feet where they are; unpinning doesn't make the foot jump.
- Swaps (shape keys and meshes) and pin on/off are saved with each shot.
- Camera setups: new from free view, lock (can't move or select), switch filming camera. Saved views round-trip.
- Studio presets build lights aimed at the puppet; picking another preset replaces them; your own lights switch off and come back with "Use My Own Lights". HDRI presets use Blender's own HDRIs, packed into the file.
- Lights are part of each shot: "Keep this lighting in" this shot / from here on / every shot; Flash, Flicker, Fade to night and Lights out write across shots; light keys move with shots when timing changes.

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

## Puppet (0.2.0)
10. Select your rig › sidebar › Stop Motion › Puppet › Make Puppet. Expect a report like "7 rings, 3 swap sets, 2 pins". Bones disappear from the free view.
11. Free view: blue rings at head, body, hips, hands; yellow rings on pinned feet. Rings don't show in the camera view.
12. Drag a hand ring: the hand follows the mouse; let go to drop. Alt+drag twists. Dragging the head ring twists it (heads are joined to the neck).
13. Drag the hips ring down: pinned feet stay on the floor and the knees bend.
14. Puppet panel › Pin left foot off: the foot doesn't jump, and now follows the leg.
15. Swap buttons (Mouth, Eyes…) change the part; D over a 3D view opens the same buttons at the mouse.
16. Shoot two shots with different mouths, step back: each shot keeps its own mouth.
17. Tell me if the rings are too big or too small (the size slider per ring helps for now).

## Cameras & lighting (0.3.0)
18. Stop Motion › Cameras & Views › New from free view: a new camera appears where the free view is looking from, and the camera view switches to it.
19. Lock a camera (padlock): it can't be clicked or moved. Move camera: navigate inside the camera view to move it; Move camera again to stop.
20. Save this view in the free view, look somewhere else, click the eye icon: the free view jumps back.
21. Lighting › Three-point, then Moonlight, then Golden hour: each relights the set (camera view shows the lighting). Use My Own Lights brings the test scene's lights back.
22. Shoot 3 shots, step to shot 2, drag the Lamp's brightness down, From here on: shots 2–3 dim, shot 1 stays.
23. On a shot, Lightning flash: just that shot goes bright white. Lights out: dark from there on.

## Known gaps
- Shot cards are a grid in the sidebar, not yet the strip from the mockup.
- Switching the filming camera isn't part of the shots yet (it's for checking angles).
- The ghost comes from whichever camera took each shot, so it lines up only on that camera.
- No solid world or sculpt yet (steps 4–5).
- Rigs that already have IK foot controls (e.g. Rigify) get rings on those controls and no extra pins.
- Pins can flip a knee the wrong way on extreme poses (no knee direction target yet).
- The top bar stays visible when hiding the UI, except in Shift+F5 camera-only mode.
