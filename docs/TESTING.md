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
- Solid world: moves stop at surfaces and slide along them, continue past edges (hand slides off the table and on down to the floor), can always back out of something they started inside; a body drag with pinned feet stops when a hand lands on the table; a pinned foot slides along the floor and bumps the table leg.
- Props drop onto whatever is under them (mug onto the table top, ball onto the floor); holding a prop doesn't make it jump, it then follows the hand; letting go leaves it in place.
- Sculpt a shot: a shape key per shot, on only for that shot (or carry on from it); it follows its shot through deletes and survives a pose over; Save as Swap Part renames it into a swap set (Face › Surprised).
- Nomad bridge: Send writes an OBJ (Y-up, exact round trip); the folder watcher spots the re-exported file and puts the sculpt on that shot; same vertex count is matched point for point, a reordered or triangulated mesh is fitted to the surface.
- Studio: layout (live box centred, panels tile the window), widget clicks, drags, sliders, wheel, hold handles; shot pictures rendered off-screen and saved; free-view picture renders; drag-to-hold changes holds a frame per card width, never below 1; a failed start rolls back so Blender is never left half-hidden. Screens rendered off-screen and checked by eye.
- Arrange: rays skip the dragged object and anything not solid; a cup slid onto the floor sits on it upright; a flower stuck to the side of a lumpy bush leans out along the surface (or stays upright) and nothing is left inside the bush; 21 stamped flowers are linked copies with varied size and spin, none buried; set pieces aren't keyed, moving one sticks in every shot, Make Set Piece clears old keys without moving it. Rendered and checked by eye.
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

## Solid world & props (0.4.0)
24. Run `scripts/make_test_puppet.py` again (it now adds a floating Mug prop), Make Puppet, Set Up Workspace.
25. Free view: a green ring on the mug. Drag it over the table and let go: it drops onto the table top. Drag it off the edge: it lands on the floor.
26. Drag the hips ring down: Bramble crouches until his left hand meets the table (or his body meets the floor). The header says "Touching something solid". Hold Ctrl to pass through.
27. Drag a foot ring down and sideways: it slides along the floor, and stops at a table leg.
28. Props & Solid World › Mug › Hold in hand (with the mug near a hand): the mug follows the hand as you pose. Let Go: it stays, then drops.
29. Shoot with the mug held, let go, shoot again, step back: each shot remembers whether it was held.
30. Turn Solid world off: rings drag freely again (Blender's normal move).

## Sculpt a shot & Nomad (0.5.0)
31. Shoot a few shots, step onto one. Stop Motion › Sculpt a Shot › Sculpt here: Blender goes into sculpt mode on Bramble's body. Sculpt something big (puff the cheeks). Done Sculpting.
32. Step through: only that shot is sculpted. "Carry on" on its row: it stays from that shot on. "Just this" puts it back to one shot.
33. Pose over the sculpted shot: the sculpt stays.
34. Save as Swap Part (the + icon): name it Face › Surprised. It appears in the Puppet panel's swaps, usable on any shot.
35. Nomad: Send to Nomad. Show Nomad Folder opens iCloud Drive › Stop Motion Nomad (or the folder you set). On the iPad, in Nomad: Files › Import, turn on **Keep topology** in the advanced options, open the .obj, sculpt (no remesh / dynamic topology), then Files › Export › OBJ, saving over the same file name in the same folder.
36. Within a couple of seconds of iCloud syncing, the row says "Back from Nomad (same points)" and the shot shows the sculpt. If it says "fitted to surface", the vertices changed in Nomad: the result is close, not exact. Bring Back Now forces it.

## The Studio (0.6.0)
37. `git pull`, then `scripts/link_dev_mac.sh` (now also links the app template) and `scripts/make_mac_launcher.sh`.
38. Open ~/Applications › Stop Motion Studio (first time: right-click › Open). Blender starts straight into the Studio, full screen: no Blender menus, top bar or panels. Expect the empty stage (floor, wall, camera). Bring Bramble in for now with Ctrl+Alt+Shift+B › run `scripts/make_test_puppet.py` › Ctrl+Alt+Shift+B back.
39. Live box shows the camera with an orange frame; the left picture shows the free view. Drag on the picture to turn it, scroll to zoom, click (or Tab) to swap: now the live box is the free view (orbit with the trackpad/middle mouse) and the picture is the camera.
40. Puppets tab › select the rig (click it in the live view) › Make puppet. Animate tab: rings appear in the live view (only inside the live box, not over the panels). Drag rings, swap parts on the right, Enter to shoot. Thumbnails appear in the strip; ghost shows in the camera.
41. Click a card to go to it (POSING OVER badge); drag a card's right edge to hold it longer or shorter; − / + and Duplicate / Delete in the shoot bar.
42. Right tabs: Props, Light, Sculpt work as in the Blender panels. Review & export: Play, speed, Make the movie.
43. F5 hides everything but the shot number; F5 or Esc brings it back. Save (Cmd+S) puts the project in ~/Stop Motion; Projects lists and opens them.
44. Ctrl+Alt+Shift+B: normal Blender, same scene. Again: back to the Studio.
45. Tell me anything that lets Blender's own UI show through (menus, pop-ups, tooltips), and anything that feels slow.

## Arranging the set (0.7.0)
46. Studio › Animate › Set tab (or Blender: Stop Motion › Props & Solid World › Arrange the set). Click Arrange: the rings hide.
47. Press on the table, the mug or the wall and drag: it slides along whatever surface is under the mouse and sits on it, never inside. Wheel spins it. Alt flips leaning. Ctrl: free move. Esc while dragging: back where it was. Esc again (or Stop): arranging ends.
48. Lean with surface on: drag the mug up the wall or round a curved object: it tips to follow. Off: it stays upright.
49. Make a bush (any lumpy mesh) and a small flower. Select the flower, Stamp copies, click all over the bush: each click places a flower standing out of the surface, each a bit different. Esc stops.
50. Shoot a few shots, then drag a stamped flower: it moves in every shot (set piece). Make the table a set piece, move it: same. Click Set piece: off on something to put it back in the shots.
51. Tell me how dragging feels on heavy meshes (the bush), and whether the lean is right on your real set pieces.

## Known gaps
- In normal Blender the shot cards are still a grid in the sidebar (the Studio has the strip).
- Studio: no file browser for bringing in a puppet yet (use the hidden way back); swap pop-up (D) not in the Studio; sculpt brushes are Blender's default brush.
- Studio: Blender's own dialogs (save changes on quit, crash reports) still look like Blender.
- The Mac launcher still shows Blender's icon in the Dock.
- Switching the filming camera isn't part of the shots yet (it's for checking angles).
- The ghost comes from whichever camera took each shot, so it lines up only on that camera.
- Twisting (Alt+drag, and joined parts like the head) isn't stopped by solids yet; only moves are.
- Arranging pushes things out of what they land on; things it passes on the way aren't checked (it follows the mouse, not a path).
- Stamp places one copy per click (no brush/drag-painting yet).
- A puppet's own parts can pass through each other (hand into own body).
- Sculpting is on the mesh at rest (the shape is added on top of the pose), so very big posed changes are easier in Blender than in Nomad.
- Nomad remesh, Dynamic Topology or Multires change the mesh: the sculpt is then fitted to the surface (close, not exact).
- Rigs that already have IK foot controls (e.g. Rigify) get rings on those controls and no extra pins.
- Pins can flip a knee the wrong way on extreme poses (no knee direction target yet).
- The top bar stays visible when hiding the UI, except in Shift+F5 camera-only mode.
