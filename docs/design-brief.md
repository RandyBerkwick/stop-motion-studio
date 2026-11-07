# Stop Motion for Blender — design brief

Mockups (canvas): https://claude.ai/artifact/HfsW9bj3bbP72cMpyEZbzC

## What it is
A Blender extension (add-on) that turns full Blender into an animator-friendly, non-technical stop-motion studio. Aardman-style clay feel, not cut-out. Not a fork: everything runs on the Python API so it survives Blender updates. Target: Blender 5.2 LTS.

## Decisions
- Extension, not a fork (fork only if an add-on limit below ever matters).
- Developed on macOS (Apple Silicon); runs on Windows and Linux too.
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
7. Sculpt one shot: Blender clay tools or Nomad Sculpt round trip (glb in a synced folder such as iCloud Drive, auto bring-back); keep as one-off, save as swap part, or carry on.
- Multiple camera setups, each lockable.
- Solid world: parts can't pass through floor, walls or other puppets; props drop onto surfaces; feet pin; hands can hold props.

## Build order and status
1. Core: workspace layout, Shoot with holds, shot list, ghost, hide UI, preview/export. **0.1.0 hand-tested OK on Mac.**
2. Puppet component: rings, swap sets, pin feet. **0.2.0 hand-tested OK on Mac; merged.**
3. Cameras & light: camera setups + locks, saved views, presets, light per shot. **0.3.0 built on branch step3-cameras-light; logic tested headless; renders checked.**
4. Solid world: collision-aware drag tool, drop to surface.
5. Sculpt: per-shot sculpt, Nomad bridge.

## Keys
Enter shoot / replace · ← → step shots · Alt+Backspace delete shot · F5 hide UI · Shift+F5 camera only · F6 ghost · D swap parts.

## Known add-on limits (fork-only if they ever matter)
- Blender's top bar can't be hidden from Python except via Focus mode (Shift+F5).
- Python can't add a new editor type; the shot timeline is drawn in panels/viewport.
- Licence: add-ons using bpy are GPL.

## Decided defaults (can change)
- Switching camera setups is for checking angles; it isn't recorded in shots (yet).
- Light changes hold until changed again: lights are keyed with every shot.

## Open questions
- Should camera switches become edit points in the film (cut to camera B for shots 20–30)?
- Pose over a sculpted shot: keep sculpt or reset?
