# Stop Motion Studio for Blender

Move-and-shoot stop-motion animation inside full Blender. No in-betweens: pose, press Enter, and the shot holds until the next one. Built as a Blender extension (not a fork), targeting Blender 5.2 LTS.

- Design brief: [docs/design-brief.md](docs/design-brief.md)
- UI mockups: https://claude.ai/artifact/HfsW9bj3bbP72cMpyEZbzC
- Hand-test checklist: [docs/TESTING.md](docs/TESTING.md)

## The Studio (Blender hidden)
Stop Motion Studio opens as its own full-screen app: one live 3D view in the middle and the rest of the interface (shoot bar, shot strip, puppet swaps, lighting, sculpt, export) drawn by the add-on around it. Blender's menus, panels and top bar never appear.

- **Mac app:** `scripts/make_mac_launcher.sh` makes *Stop Motion Studio.app* in ~/Applications. It starts Blender with the Stop Motion Studio app template, which opens straight into the Studio.
- **From Blender:** Ctrl+Alt+Shift+B (or Stop Motion › View › Open the Studio).
- **The hidden way back:** Ctrl+Alt+Shift+B in the Studio switches to normal Blender for rigging or fixes, and back again.

Your normal Blender theme, preferences and keymap are never changed: the app template keeps its own settings.

`tools/preview_studio.py` renders the Studio off-screen to a PNG (software GPU), for checking the interface without a window.

## Install (to use it)
```sh
scripts/build.sh
```
This makes `dist/stop_motion_studio-<version>.zip`. Blender › Preferences › Get Extensions › ▾ › Install from Disk… › pick the zip.

## Test puppet
`scripts/make_test_puppet.py` builds a new scene, "Puppet Test", with a clay figure (Bramble) whose rig, swap parts (eyes, mouth, right hand) and shape-key brows are named the way Make Puppet expects, plus a floor, table, camera and lights. In Blender: Scripting tab › Open › `scripts/make_test_puppet.py` › Run Script. Your current scene is left alone.

## Develop on a Mac
```sh
scripts/link_dev_mac.sh
```
This links the add-on into the extensions folder of the Blender in /Applications (or pass a version, e.g. `scripts/link_dev_mac.sh 5.2`). Fully quit and restart Blender and enable **Stop Motion Studio** in Preferences › Add-ons. After editing code, press F3 › "Reload Scripts" in Blender: no reinstall needed.

Run the headless tests with the Blender app:
```sh
scripts/run_tests_mac.sh
```
Set `BLENDER=/path/to/Blender` if it isn't in /Applications. The tests cover the shot model (shoot, hold, pose over, delete, duplicate, ghost) and puppets (rings, swaps, pins). Shot pictures need a real window, so they're skipped in headless runs.

## Layout
| Path | What |
|---|---|
| `stop_motion_studio/core.py` | Shot model: timing, keying (always constant), retiming, shot pictures, ghost |
| `stop_motion_studio/ops.py` | Shoot, delete, hold, duplicate, step, play, export |
| `stop_motion_studio/layout.py` | Stop Motion workspace (camera + free view), hide UI, camera only |
| `stop_motion_studio/ui.py` | Sidebar panels, shot grid, camera HUD, hotkeys, frame-change handler |
| `stop_motion_studio/props.py` | Scene settings and the shot list |
| `stop_motion_studio/arrange.py` | Arranging: slide and stick on surfaces, stamp copies, set pieces |
| `stop_motion_studio/studio.py` | The Studio: full-screen mode, input filter, screens, off-screen views and captures |
| `stop_motion_studio/studio_kit.py` | Studio widgets and layout (no GPU: testable) |
| `stop_motion_studio/studio_paint.py` | Draws the Studio with Blender's gpu/blf |
| `app_template/StopMotionStudio` | App template: opens straight into the Studio |
| `stop_motion_studio/puppet.py` | Make Puppet: ring guessing, swap sets, foot pins |
| `stop_motion_studio/rings.py` | Grab ring gizmos in the free view and the drag operator |

## Keys in the Studio
| Key | Does |
|---|---|
| Enter | Shoot (or replace the shot you're on) |
| ← / → | Previous / next shot |
| Tab | Swap the live view and the picture (camera ↔ free view) |
| Space | Play / pause |
| Alt+Backspace or Delete | Delete shot |
| 1–5 | Saved free views |
| F5 / Esc | Hide / show the interface |
| F6 | Ghost on / off |
| Cmd+S / Cmd+O | Save / Projects |
| Cmd+Z | Undo |
| Ctrl+Alt+Shift+B | Normal Blender (and back) |

Drag the right edge of a card in the shot strip to hold that shot longer or shorter.

**Moving and turning parts** (rings, in the Studio and in Blender):

| While dragging a ring | Does |
|---|---|
| Drag | Move across the view |
| Shift + drag up/down, or the wheel | Push it further away / pull it nearer (it stays put on screen) |
| X / Y / Z | Move along that one direction only (a coloured line shows it); again: free |
| Alt + drag (heads: plain drag) | Turn it like rolling a ball |
| X / Y / Z while turning | Turn around that axis only; V: around the view |
| Shift while turning | Fine turning |
| Ctrl | Pass through solid things |
| Esc / right-click | Put it back |

**Arranging the set** (Set tab): Arrange, then drag anything along surfaces; it sticks without sinking in. Wheel spins, Alt leans or stands upright, Ctrl moves freely, Esc puts it back. Stamp copies: select an object, then click on surfaces to place varied copies (flowers on a bush). Set pieces stay put in every shot.

## Keys in normal Blender (3D view)
| Key | Does |
|---|---|
| Enter | Shoot (or replace the shot you're on) |
| ← / → | Previous / next shot |
| Alt+Backspace | Delete shot |
| F5 | Hide / show UI |
| Shift+F5 | Camera only, full window |
| F6 | Ghost on / off |
| D | Swap parts pop-up (eyes, mouth, hands) |

## Licence
GPL-3.0-or-later (required for Blender add-ons that use its Python API).
