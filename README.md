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

**Help:** ? Help in the top bar (or H, or F1) opens a "How to…" column for the view you're on: step-by-step guides with small moving pictures for animating, building a scene, bringing things in, lighting, sculpting, sharing, and building, rigging and saving puppets. `tools/preview_help.py` renders every picture to a contact sheet.

**Two looks:** the dark studio, or **Sketchbook** (squared paper, hand-drawn ink outlines, a highlighter on what's picked, hand-lettered text): friendlier for kids and first-time animators. Switch with the button in the Studio's top bar; your pick is kept as a preference. Sketchbook's fonts, Patrick Hand and Kalam, ship in `stop_motion_studio/fonts` under the SIL Open Font Licence.

Your normal Blender theme, preferences and keymap are never changed: the app template keeps its own settings.

`tools/preview_studio.py` renders the Studio off-screen to a PNG (software GPU), for checking the interface without a window. Set `SM_PREVIEW_LOOK=SKETCH` for the Sketchbook look.

While the Studio is open, quitting saves your work instead of showing Blender's "save changes?" box (a project that was never saved goes into ~/Stop Motion). On a Mac the Dock shows the Studio's icon.

## What's in it
- **Shoot:** pose, Enter; each shot holds for 1, 2 or 3 frames (drag a card's edge for any length). Go back to pose over, delete, duplicate. Ghost of the shots before.
- **Camera cuts:** each shot remembers the camera that filmed it. Click a camera while live: the next shots film with it. Click one while on a shot: that shot and the rest of its run (up to the next cut) cut to it. Playback and export follow the cuts; cuts show as yellow marks in the strip.
- **Puppets:** Make Puppet turns a rig into grab rings (drag moves, Alt+drag turns, Shift: nearer/further, X/Y/Z: one direction, twice: the part's own axis), swap parts (D for the pop-up), foot pins with knee targets. Rigs with their own IK feet use their IK as the pin.
- **Solid world:** parts and props stop at the set and at the puppet's own other parts; props drop onto surfaces and can be held in a hand.
- **Puppet studio (Puppets tab):** build a puppet three ways. *Parts kit:* pick a person, small child, tall or four-legged wire armature; it starts with a full set of clay parts (heads, bodies, arms, legs, feet, paws, tails) to swap and colour; sliders set height, head size, arm or body length and leg length, and the parts are remade to fit. *A sculpt:* joints are guessed on a one-piece sculpt (from Nomad, say); click in the clay to move one (it goes in the middle of the clay), left copies to right; Make the rig skins it. *A rig:* the original setup for a rig you already have. Then face & hands (replacement mouths, eyes, brows, mitten or finger hands, picked shot by shot), Try it (test poses that flag folding clay, parts running into each other and flipped knees, each with a fix), and Save to the library with its picture.
- **Hair, hats and extras:** the kit has hair (mop, bun, spiky), hats (cap, bobble hat, top hat) and extras (a name tag with the puppet's name on it, a scarf, glasses). They're fitted to whatever head and body are on, and stay on when those change.
- **Your own kit parts:** model a part in Blender and save it in `~/Stop Motion/Library/Kit/<kind>` (Heads, Bodies, Arms, Legs, Feet, Tails, Hair, Hats, Extras). Each file is a part named after the file; a file with collections gives one part per collection, named after it (`Hats.blend` with collections Cap, Beret, Crown). They show under *Yours* in the parts kit with their pictures. Model at any size and anywhere: a part is fitted when it goes on (heads, hair and hats to the head, bodies along the spine, arms and legs from joint to joint, feet to the floor). Model one arm, leg or foot: the other side is mirrored. Textures and materials are kept (pack them into the file so they travel); an untextured part takes the kit colour. A part is read once and kept in the project, so the puppet still works if the file moves.
- **Wear it:** put any prop on a puppet: click Wear it, then click the puppet where it goes. It sits on the surface there and rides on that part (head, chest, hand…) in every shot. Make it part of a swap set (Hat, Hair, Glasses, Badge, Extra) to pick it shot by shot, with None to take it off. Take off makes it a prop again.
- **Library (Bring in…):** puppets, props and set pieces kept as .blend files in ~/Stop Motion/Library; bring one in and it stands where the camera is looking, set up and ready. "Add what's selected" keeps something for other projects.
- **Arranging the set:** slide things along surfaces (they stop at what stands there), stamp copies by clicking or painting a stroke, set pieces stay put in every shot.
- **Light:** studio and sky presets, light per shot, effects: flicker, lightning flash, fade to night, lights out, torch sweep.
- **Sculpt a shot:** clay tools (build up, clay, thumb, smooth, push & pull, puff, crease, flatten) or a round trip through Nomad Sculpt.
- **Review & export:** loop, back and forth, or the last few shots; Movie, Frames, GIF (one frame per shot, held as long as the shot) or a Blender scene copy.

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
| `stop_motion_studio/solid.py` | Solid world: 3D drag and turn that stop at surfaces, props, holding |
| `stop_motion_studio/library.py` | The library: bring in / add puppets, props and set pieces |
| `stop_motion_studio/gif.py` | Animated GIF writer (palette, LZW) |
| `stop_motion_studio/strip.py` | Shot strip along the bottom of the camera view in normal Blender |
| `stop_motion_studio/macos.py` | Dock icon (macOS) |
| `stop_motion_studio/assembly.py` | Puppet studio: armature templates, proportions, the clay parts kit, skinning |
| `stop_motion_studio/faces.py` | Puppet studio: mouths, eyes, brows and hands as swap parts |
| `stop_motion_studio/rigsculpt.py` | Puppet studio: joints on a sculpt, making its rig |
| `stop_motion_studio/trial.py` | Puppet studio: test poses, problem checks and fixes, saving |
| `stop_motion_studio/studio_puppets.py` | The Studio's Puppets mode |

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
| D | Swap parts pop-up at the mouse |
| H or F1 | Help for this view (Esc closes it) |
| Esc | Also cancels waiting for a Wear it click |
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
The Sketchbook fonts in `stop_motion_studio/fonts` are under the SIL Open Font Licence 1.1 (licence files alongside).
