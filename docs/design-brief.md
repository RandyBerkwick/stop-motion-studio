# Stop Motion for Blender — design brief

Mockups (canvas): https://claude.ai/artifact/HfsW9bj3bbP72cMpyEZbzC

## What it is
A Blender extension (add-on) that turns full Blender into an animator-friendly, non-technical stop-motion studio. Aardman-style clay feel, not cut-out. Not a fork: everything runs on the Python API so it survives Blender updates. Target: Blender 5.2 LTS.

## Decisions
- Extension, not a fork (fork only if an add-on limit below ever matters).
- Developed on macOS (Apple Silicon); runs on Windows and Linux too.
- The app hides Blender completely: the Studio is a full-screen interface drawn by the add-on around one live 3D view, opened by an app template and a Mac launcher (no fork). Hidden way back: Ctrl+Alt+Shift+B.
- Code lives in GitHub: https://github.com/RandyBerkwick/stop-motion-studio (the claude.ai Project holds the brief and status).

## Core principles
- Move and shoot. No in-betweens: every key is constant, every shot is exactly the pose you shot.
- A shot = one pose held for N frames (on 1s / 2s / 3s). The timeline is shot cards, not curves.
- Go back easily: delete a shot (gap closes, undo), pose over a shot (old pose shown as ghost), change hold, duplicate, insert after.
- Camera view (what gets filmed) + free 3D view (pose and walk round the set), with saved views to go back to.
- UI can be hidden completely for a clean camera view (F5).

## Features (from design rounds)
1. Animate: Shoot (Enter), ghost of last shot, hold length, shot strip, swap parts panel (eyes / mouth / hands, single-key swaps).
2. Go back: pose over, delete, duplicate, insert, hold +/-.
3. Clean camera: UI gone, only shot number; fading key hints.
4. Puppet setup (rigging component): auto grab rings from the rig (animator never sees bones), swap sets from shape keys or a folder of meshes, "feels real" switches.
5. Review & export: loop / back-and-forth / last 10 shots, 8/12/24 fps, Movie / Frames / GIF / Blender scene; "as shot" (instant) or final render.
6. Lighting: studio presets + HDRI presets, light per shot with effect drops (flicker, lightning flash, fade to night, torch sweep, lights out); scope every shot / from here / this shot only.
7. Sculpt one shot: Blender clay tools or Nomad Sculpt round trip (OBJ in a synced folder such as iCloud Drive, auto bring-back); keep as one-off, save as swap part, or carry on.
- Multiple camera setups, each lockable.
- Solid world: parts can't pass through floor, walls or other puppets; props drop onto surfaces; feet pin; hands can hold props.
- Arranging the set: objects slide along whatever surface is under the mouse and stick to it without intersecting, leaning with the surface or staying upright; stamp copies onto surfaces (flowers on a bush); set pieces stay put in every shot.

## Build order and status
1. Core: workspace layout, Shoot with holds, shot list, ghost, hide UI, preview/export. **0.1.0 hand-tested OK on Mac.**
2. Puppet component: rings, swap sets, pin feet. **0.2.0 hand-tested OK on Mac; merged.**
3. Cameras & light: camera setups + locks, saved views, presets, light per shot. **0.3.0 hand-tested OK on Mac; merged.**
4. Solid world: collision-aware drag tool, drop to surface. **0.4.0 hand-tested OK on Mac; merged.**
5. Sculpt: per-shot sculpt, Nomad bridge. **0.5.0 built; logic and file round trip tested headless; merged.**
6. Studio (Blender hidden): full-screen interface, left picture + centre live view + right tabs + shot strip, drag a card edge to change its hold. **0.6.0 launcher working on Mac; merged.**
7. Arranging the set: slide and stick on surfaces, stamp copies, set pieces. **0.7.0 tested headless and rendered; merged.**
8. Solid twist: turning parts and props stops where they'd touch something. **0.8.0 tested headless; merged.**
9. 3D move and turn: further/nearer (Shift or wheel), X/Y/Z locks with a guide line, trackball turning, turns around one axis or the view; solid or not. **0.9.0 built; tested headless.**
10. Round 2: camera cuts, GIF and Blender-scene export, review modes (loop, back and forth, last N); library (bring in puppets/props/sets), swap pop-up and clay tools in the Studio; own parts solid, knee targets, rigs with IK feet, held props in 3D, own-axis locks, arranging stops at things on the surface; painting copies, torch sweep, shot strip in normal Blender, Studio Dock icon, save on quit. **1.0.0 built on branch finish; tested headless and rendered.**
11. Library pictures; puppet studio: build from a parts kit on a wire armature (person, small child, tall, four legs) with proportions, or place joints on a sculpt; face & hands swap sets (mouths picked by hand); try it with test poses and fixes; save to the library. **1.1.0 built on branch finish; tested headless and rendered.**

## Keys (normal Blender; the Studio's keys are in the README)
Enter shoot / replace · ← → step shots · Alt+Backspace delete shot · F5 hide UI · Shift+F5 camera only · F6 ghost · D swap parts.

## Known add-on limits (fork-only if they ever matter)
- Blender's top bar can't be hidden from Python except via Focus mode (Shift+F5).
- Python can't add a new editor type; the shot timeline is drawn in panels/viewport.
- Licence: add-ons using bpy are GPL.

## Decided defaults (can change)
- Camera cuts: each shot remembers its camera. Live, picking a camera sets the next shots; on a shot, it changes that shot and the rest of its run up to the next cut. Cuts are camera markers, so playback, export and the Blender-scene copy follow them.
- Quitting from the Studio saves instead of asking (unsaved projects go to ~/Stop Motion).
- The library is a folder of .blend files (~/Stop Motion/Library).
- Light changes hold until changed again: lights are keyed with every shot.
- Posing over a sculpted shot keeps its sculpt.
- Nomad bridge is a file round trip (OBJ in iCloud Drive › Stop Motion Nomad); in Nomad, import with "Keep topology" for an exact match.

- Puppet studio: a parts-kit puppet skips the Joints step (the armature is the rig). Mouths are picked by hand, shot by shot (no automatic lip sync). Four-legged puppets are in from the start.

## Open questions
- Which kit parts to add next (hair, hats, clothes, animal kinds)?
