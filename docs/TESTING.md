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
- Solid twist: a stick tipped over on its edge stops flat on the floor (90°); a box turned beside a wall stops when its corner meets it; Bramble's arm swung down stops when the hand meets the table (the other way is free); turning back out of contact is always free; nothing ends up inside.
- 3D move and turn: X/Y/Z locks move only along that axis; Shift/wheel push along the line of sight so the part stays put on screen; an axis pointing at you moves with mouse up/down instead of jumping; trackball turns go the way you drag (right turns the front right, up turns it up); Shift is a quarter speed; X/Y/Z/V turns stay on one axis; a stick tipped corner-first about a slanted axis stops flat on the floor (90°); Bramble's arm turned down in 3D stops at the table in every direction that reaches it and never ends up inside; Esc puts things back; the axis line shows and goes away.
- Camera cuts: each shot keeps its camera; playback switches at the cuts and stays on the live camera; "to the next cut" and "this shot only" change just those shots; deleting, holding and duplicating keep every shot's camera; "just look" doesn't change the film; the ghost only shows earlier shots from the same camera.
- Export: the GIF has one frame per shot, held as long as the shot (total length matches the film), right way up; back-and-forth GIFs don't repeat the ends; final-render GIFs render each shot; the GIF encoder's output decodes correctly (checked against Pillow, including noisy frames). The Blender scene copy opens and the working file stays the same.
- Review: loop, back and forth (turns at both ends) and last N shots play the right frames; shooting stops playback; stopping goes back to live.
- Library: adding keeps rigs with their meshes and foot pins; files with collections list each; bringing in sets up a puppet (rings, swaps), a prop or a set piece, standing on the floor where the camera looks.
- Clay tools: all eight brushes switch in Blender 5.2; size and strength set.
- Own parts solid: a hand pushed into the belly stops at it and never ends up inside; one foot can't pass through the other; the joint a part turns at doesn't block it; can be switched off.
- Knee targets: adding pins and knee targets doesn't move the legs; knees keep pointing forward through deep crouches.
- Rigs with IK feet: their IK becomes the pin (switching off doesn't make the leg jump; the switch is keyed with each shot).
- Held props: placed exactly where asked and still follow the hand.
- Arranging: sliding along the floor stops at a box standing on it; moving onto the box puts it on top.
- Torch sweep: the beam turns one way across the run and is off before and after. Painting copies: about one per spacing along a stroke. Strip: cards are as wide as their holds; clicks find the card or its edge and miss everywhere else. Saving on quit writes the project and puts Blender's prompt setting back.
- Library pictures: made when something's added (three-quarter front view, clear background); files without one get theirs from the file, leaving nothing behind; project pictures are the last shot.
- Hand shapes: six per hand; a hand sculpted on one shot and kept becomes a new shape in that hand's set, used by that shot only, with the one-off sculpt removed.
- Puppet studio: a person from the kit has 8 parts (pairs for arms, legs, feet); bending parts are skinned with every point weighted, heads and feet ride their bone; feet on the floor; swapping and colouring parts; a bigger head makes a bigger head part, longer legs a taller puppet still on the floor, colours kept. Face sets (8 mouths, 5 eyes, 3 brows, both hands with 4 shapes) sit on the front of the face, eyes above the mouth, one showing, swapping works, remade when the head changes. Four legs: rings for head, body, hips, tail and four feet, all four pinned with knee targets; a person changed to four legs keeps only parts that fit. Test poses are tried and the puppet goes back to standing; a hard fold with volume keeping off is noticed; Soften joints remakes the parts softer. A sculpt made from a kit puppet: joints guessed within 2 cm; a click puts a joint in the middle of the clay and mirrors it; Make the rig gives 7 rings, 2 pins, every point weighted (separate bits like ears too), nodding moves the head and not the feet. Saved puppets come back from the library with rings, swaps and pins. The Studio's Puppets mode: steps, building, sliders applied after a pause, faces, trying, saving, a sculpt rigged. Screens rendered and checked by eye.
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

## Solid twist (0.8.0)
52. Solid world on. Alt+drag a hand ring and swing the arm down into the table: it stops on the table top. Turn back: free. Ctrl: passes through. Shift: fine turning. Esc: back where it was.
53. Drag the head ring (heads twist on a plain drag) round into the wall or another puppet: it stops.
54. Alt+drag the mug's ring to tip it: it stops against the table or wall; let go and a tipped mug settles back onto its surface.
55. Arranging: wheel-spinning a prop next to a wall never pushes it into the wall.

## 3D move and turn (0.9.0)
56. Drag a hand ring, then hold Shift and move the mouse up: the hand goes further away from you (it stays under the same spot on screen); down brings it nearer. The wheel does the same in steps. Let go of Shift: dragging is across the view again.
57. While dragging, press Z: a blue line appears and the hand only goes up and down. X (red): only side to side. Y (green): front to back. Press the same letter again: free.
58. Alt+drag a hand ring: the arm turns like a ball under your finger (right turns it right, up turns it up). While turning press X, Y or Z: it turns around that axis only; V: around the view (the old twist). Shift: fine.
59. Solid world on: turning the arm down into the table stops at the table, from any direction. Ctrl passes through.
60. Solid world off: the same tools work, they just don't stop at anything (and props don't drop).
61. In the Studio the hints show as a toast at the bottom; tell me if any of the keys clash with something.

## Round 2 (1.0.0)
62. Camera cuts. Add a Camera B (+ in the camera bar). Live, click Camera B: shoot a few. Back to Camera A, shoot a few. Play: the film cuts A → B → A. The strip shows yellow marks and camera names at the cuts.
63. Step onto an A shot in the middle of the A run, click Camera B: that shot and the rest of that run switch, the next cut stays. Blender panel: "This shot" switches just one.
64. Review: Play › Back & forth bounces; Last plays the last N shots (slider). Space plays and stops.
65. Export › GIF: a .gif in the films folder; each shot shows for its hold. With Back & forth chosen it bounces. Final render GIF takes longer but has full lighting.
66. Export › Blender scene: a *_scene.blend copy; open it in plain Blender: the animation and the camera cuts play without the add-on.
67. Bring in…: put a .blend with a rigged puppet in ~/Stop Motion/Library (or select Bramble › "Add what's selected"). Bring it in as Puppet: it stands on the set where the camera looks, with rings ready. A prop: green ring. A set piece: stays put.
68. D in the Studio: the swap pop-up at the mouse; clicks swap; click outside or Esc closes.
69. Sculpt tab › Sculpt here: clay tool buttons, size, strength; each tool feels right on clay.
70. Drag Bramble's body ring down and forward: his chest stops at his thighs. Drag a foot ring across the other foot: it stops. Set tab › "Puppets' own parts are solid" off: passes.
71. Deep crouch with pinned feet (hips ring right down): the knees stay pointing forward, no flipping.
72. Hold the mug, then drag its green ring: it moves with Shift/X/Y/Z like everything else, and stays in the hand. Alt+drag turns it in the hand.
73. During a drag press X twice: the line turns to the part's own X (useful on a tilted head or hand).
74. Arrange: slide the mug along the table into a vase or box standing on it: it stops against it. Move the mouse onto the box: it hops on top.
75. Stamp copies: press and drag across the bush: flowers along the stroke, spaced by "Copy spacing".
76. Light › Torch sweep on a shot: over the next 6 shots a warm beam sweeps across the set; off before and after.
77. Normal Blender, Stop Motion workspace: shot cards along the bottom of the camera view. Click one: goes there. Drag its right edge: hold changes. LIVE: back to live. View panel › "Shot strip on camera" turns it off.
78. Mac: rebuild the launcher (`scripts/make_mac_launcher.sh`): the app has the Studio icon, and the Dock shows it while the Studio is open.
79. Change something in the Studio and quit (Cmd+Q): no Blender dialog, and the work is saved (a never-saved project lands in ~/Stop Motion). In normal Blender, quitting asks as usual.

## Puppet studio (1.1.0)
80. Puppets tab › Start from: Parts kit › A person. Pip appears on the set, on a wire armature, fully dressed. The live view is the free view, looking at him.
81. Build: pick Head › Long head, Body › Barrel body, colours: each swaps at once. Drag the Head size slider: a moment after you let go, the head is remade bigger and the face stays on it.
82. Armature › Four legs: Biscuit appears with paws and a tail. Back to Person: Pip's parts that fit come back.
83. Next: face & hands › Make mouths, eyes and hands. Click a mouth on the right: it shows on Pip. Mitten / 4 fingers changes the hands.
84. Try it: four test poses with pictures; anything marked has a fix button. Fix, then Try it again.
85. Save: Pip goes into the library with his picture. Bring in… shows him; bring him into another project: rings and swaps work.
86. Start from: A sculpt. Bring in a one-piece sculpt (or click one in the live view). Guess them all, then click a joint in the list and click in the clay where it should go: the dot jumps there (and its mirror). Make the rig: rings and pins appear; pose it in Animate.
87. Animate a built puppet: everything from before works (shoot, swaps per shot, pins, solid world).
88. Blender sidebar › Stop Motion › Puppet Studio does the same with plain buttons.
89. Tell me how the kit parts and proportions feel, and which parts you'd want next.
90. Fingers by swapping: each hand has Open, Relaxed, Fist, Point, Grip and Thumbs up; swap them shot by shot (D, or the Puppet tab).
91. Fingers by sculpting: on a shot, click Pip's hand in the live view › Sculpt tab › Sculpt here, push the fingers into a new pose, Done. "Keep shape" on that shot's row: it becomes a new shape in that hand's set (Left hand › Shape 1), that shot uses it, other shots don't, and you can pick it on any later shot.

## Sketchbook look (1.2.0)
92. Studio top bar › Sketchbook: the Studio turns into squared paper with ink-outlined, slightly wobbly buttons, a little shadow under each, hand-lettered text, and a yellow highlighter on whatever is picked. The button now says "Dark look" and switches back.
93. Quit and reopen Blender: the look you picked is kept (it's in Edit › Preferences › Add-ons › Stop Motion Studio, too).
94. In Sketchbook, check every tab (Puppets steps, Animate › Puppet/Set/Light/Sculpt, Review & export) and the Bring in…, Projects and swap pop-ups: no text you can't read, nothing cut off with "…" that isn't in the dark look.
95. Tell me how it feels on your screen: wobble too much or too little, text size, paper grid strength.

## Known gaps
- In normal Blender the Dock still says "Blender" (the icon changes only while the Studio is open), and Blender's crash report window looks like Blender.
- "As shot" GIFs use the shot pictures: a lighting effect added after shooting shows only in a final-render GIF (or re-shoot those shots).
- Own parts: the joint a part turns at is never counted as in the way, so a hand can still sink into the shoulder it hangs from on an extreme pose.
- Arranging checks things standing on the surface you're sliding on; hopping onto another object doesn't check what's in between.
- Sculpting is on the mesh at rest (the shape is added on top of the pose), so very big posed changes are easier in Blender than in Nomad.
- Nomad remesh, Dynamic Topology or Multires change the mesh: the sculpt is then fitted to the surface (close, not exact).
- Puppet studio: kit parts are made by code (simple clay shapes); your own parts come in through the library or a sculpt. Proportion sliders don't apply to a rigged sculpt (move its joints instead). Fingers are posed by swapping hand shapes or sculpting (no finger bones, by design).
- Rigs with their own IK feet: the pin switches the rig's IK constraint; rigs that drive IK/FK with their own sliders (Rigify) keep using their sliders.
- Knee targets come with new pins: run Make Puppet again on a puppet set up before 1.0.0 to get them.
- Sketchbook look: a few small marks drawn in fixed colours (hover glows, some badge text) were tuned for the dark look and are faint on paper.
- The top bar stays visible when hiding the UI, except in Shift+F5 camera-only mode.
