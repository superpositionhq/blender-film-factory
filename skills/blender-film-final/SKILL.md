---
name: blender-film-final
description: 'Rules for a blender-film-factory film whose output is final: a fully rendered film with detailed models, real materials, designed lighting, animation with weight, deliberate camera work and colour, made after its grey-box stage. Use for every film created with --output final, when deciding about modelling detail, procedural materials and textures, lighting and atmosphere, depth of field, render engine and settings, colour management, compositing, critique rounds and render time. Pair it with blender-film-session and blender-film-commit-always.'
---

# Final output

A final film is a finished picture of the script: detailed models, real materials, designed light, animation with
weight, deliberate cameras. **It is built on its grey-box stage**: staging, cameras, cuts and timing are settled
there (and delivered as `out/greybox.mp4`); this skill covers what comes after. Everything in the
blender-film-session skill applies. Read the blender-film-greybox skill for the blockout stage: it uses the same
mannequins and blocks, which this stage then replaces or dresses.

## People

A script has people, and code-built people are the hardest thing here. Choose one way for the whole film, write it
in the treatment, and keep to it:

- **Stylised figures**: the mannequin's proportions with modelled forms (rounded limbs, a head with a simple
  profile, hands as mittens, clothes as shapes), finished materials, no faces beyond what the style carries.
- **Framing that avoids faces**: hands, backs, silhouettes, shadows, long shots, objects that tell the action.
Never a half-realistic face: it reads as broken. A speaking character is shown by posture and gesture.

## Models

- **Real scale and modelled edges.** Every object in a close shot has a bevel, a subdivision surface or modelled
  chamfers. Lathe profiles for turned things, boxes with bevel modifiers for joinery, tubes along curves for
  cables, branches and handles (`kit.lathe_bm`, `kit.box_between`, `kit.add_bevel`, `kit.tube`, `kit.smooth_path`).
- **Light base meshes, density from modifiers** (subdivision, bevel, solidify).
- **One object per step**, the objects the shots are about first; a large one in two or three steps. Replace a
  stand-in by swapping the mesh under the same object name (`kit.swap_mesh`).
- **Detail holds at the distance it is seen from.** Look at each model once from its closest shot.

## Materials

- **One material family per step**, each more than a bare shader: colour variation, roughness variation, a bump
  at the right scale. Procedural nodes, or an image your script paints into `textures/` (`kit.new_mat`,
  `kit.noise`, `kit.ramp`, `kit.mix`, `kit.bump`, `kit.coords`, `kit.wood_material`).
- **Check texture scale in the shot, at once.** A pattern that reads right in the node tree is often too large,
  too contrasty or too regular in the picture.
- A fine bump on a dark matte surface catches light as a grey haze: lower the specular before the colour.
- Object-space coordinates (`kit.coords(nt, 'Object')`) keep a texture fixed to a moving object.

## Lighting and atmosphere

- **One motivated key per place and time** (a lamp, the moon, the sun through a window), a weak coloured fill, and
  darkness left dark. The script's time of day and mood decide it. Light that changes with the story is keyed on
  the timeline (constant interpolation at a cut, eased inside a shot).
- **When a light does not read, render with the others off** (a read-only script that hides them and renders a
  frame into `.local/`): a fill that drowns the key is found in one picture.
- A surface that glows casts no shadow of its own (`ob.visible_shadow = False`).
- Atmosphere: a thin volume, thinner than you think (it greys the blacks). Small bright things stay away from the
  lens when depth of field is on.
- EEVEE reflections see only the screen: add reflection probes near the objects the close shots are about.

## Depth of field, motion, render

- **Depth of field** on the close shots (`kit.set_dof(cam, focus_object, fstop=2.8)`), stopped down in the wides.
- **Motion blur**: half shutter, and the shutter **opens at the frame** (`render.motion_blur_position = 'START'`).
  Centred blur samples the time before a cut and smears the first frame of every shot.
- **Engine**: EEVEE (engine id `BLENDER_EEVEE`): 48 samples, ray tracing on, soft shadows. It renders a 1080p frame
  in a few seconds and is stable from frame to frame. Cycles only when the time per frame fits the film.
- **Colour**: AgX with a look chosen on purpose; exposure set once, late. In Blender 5 the compositor is a node
  group on the scene (`scene.compositing_node_group`, tree type `CompositorNodeTree`). One concern per step.
- **Measure time per frame early**: `tools/render.py <film> --shots --pct 100` prints seconds per frame.

## Critique rounds: at least two

A round: `tools/render.py <film> --shots --sheet 3 --out critique` at the final settings, plus the first and last
frame of every shot once. Hold each frame against the script beat it shows and these questions:

- **Script**: does the frame show what the lines say, with the right people and things, in the right place?
- **Composition**: where does the eye go first; dead space, a tangent, something cut by the frame edge?
- **Light and colour**: one key; do the blacks hold; is anything burnt out; is the palette the treatment's plan?
- **Surface**: does any material look like plastic or like a pattern; does detail hold in the closest shot?
- **Motion**: does anything slide, pop, start or stop in one frame, float or sink; does the cut land on the action?
- **Cleanliness**: flicker between consecutive frames, noise, clipping, a smeared first frame.

Write what is still weak after the last round in the critique and the report; do not hide it.
