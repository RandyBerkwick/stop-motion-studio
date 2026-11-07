# Stop Motion Studio for Blender

Move-and-shoot stop-motion animation inside full Blender. No in-betweens: pose, press Enter, and the shot holds until the next one. Built as a Blender extension (not a fork), targeting Blender 5.2 LTS.

- Design brief: [docs/design-brief.md](docs/design-brief.md)
- UI mockups: https://claude.ai/artifact/HfsW9bj3bbP72cMpyEZbzC
- Hand-test checklist: [docs/TESTING.md](docs/TESTING.md)

## Install (to use it)
```sh
scripts/build.sh
```
This makes `dist/stop_motion_studio-<version>.zip`. Blender › Preferences › Get Extensions › ▾ › Install from Disk… › pick the zip.

## Develop on a Mac
```sh
scripts/link_dev_mac.sh
```
This links the add-on into the extensions folder of the Blender in /Applications (or pass a version, e.g. `scripts/link_dev_mac.sh 5.2`). Fully quit and restart Blender and enable **Stop Motion Studio** in Preferences › Add-ons. After editing code, press F3 › "Reload Scripts" in Blender: no reinstall needed.

Run the headless tests with the Blender app:
```sh
scripts/run_tests_mac.sh
```
Set `BLENDER=/path/to/Blender` if it isn't in /Applications. The tests cover the shot model (shoot, hold, pose over, delete, duplicate, ghost). Shot pictures need a real window, so they're skipped in headless runs.

## Layout
| Path | What |
|---|---|
| `stop_motion_studio/core.py` | Shot model: timing, keying (always constant), retiming, shot pictures, ghost |
| `stop_motion_studio/ops.py` | Shoot, delete, hold, duplicate, step, play, export |
| `stop_motion_studio/layout.py` | Stop Motion workspace (camera + free view), hide UI, camera only |
| `stop_motion_studio/ui.py` | Sidebar panels, shot grid, camera HUD, hotkeys, frame-change handler |
| `stop_motion_studio/props.py` | Scene settings and the shot list |

## Keys (3D view)
| Key | Does |
|---|---|
| Enter | Shoot (or replace the shot you're on) |
| ← / → | Previous / next shot |
| Alt+Backspace | Delete shot |
| F5 | Hide / show UI |
| Shift+F5 | Camera only, full window |
| F6 | Ghost on / off |

## Licence
GPL-3.0-or-later (required for Blender add-ons that use its Python API).
