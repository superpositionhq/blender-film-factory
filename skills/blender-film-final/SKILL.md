---
name: blender-film-final
description: 'Rules for a blender-film-factory film whose output mode is final: a finished picture with detailed models, real materials, designed lighting, animation with weight, deliberate camera work, colour and an edit with rhythm. Use for every film created with --output final, when deciding about modelling detail, procedural materials and textures, lighting and atmosphere, depth of field, render engine and settings, colour management, compositing, critique rounds and render time. Pair it with blender-film-session and blender-film-commit-always.'
---

# Final output

A final film is a finished picture, not a white model: detailed models, real materials, designed light, animation
with weight, deliberate cameras and an edit with rhythm. **Taste is the point.** Everything in the
blender-film-session skill applies; this skill says how each stage is done in a final film and what was learned the
hard way.

## Choose what can be finished

Pick a subject that suits what Blender does well under code control: hard surfaces, still life, architecture,
mechanisms, weather, light. A small story with a beginning, a turn and an ending, told through objects and light,
finishes to a high standard; a talking human face does not. One location seen at different times, or two small
sets, is enough for 20 to 45 seconds and 5 to 9 shots. Write the palette as a plan in the treatment: what the
colour is in each part of the story and what the one accent is.

## Models

- **Real scale and modelled edges.** Every hero object has a bevel, a subdivision surface or modelled chamfers: no
  razor-sharp default primitives in a close shot. Lathe profiles for thrown and turned things, boxes with bevel
  modifiers for joinery, tubes along curves for branches, cords and handles (`kit.lathe_bm`, `kit.box_between`,
  `kit.add_bevel`, `kit.tube`, `kit.smooth_path`).
- **Keep base meshes light and let modifiers carry the density** (subdivision, bevel, solidify): the scene file
  stays small and the evaluated triangle count is what is counted.
- **One object per step**, hero objects first; a large object in two or three steps (main forms, secondary forms,
  small parts). Replace a stand-in by swapping the mesh under the same object name (`kit.swap_mesh`).
- **A thing that breaks** is cut once into pieces that share the whole object's surface coordinates (store the rest
  position on the mesh as an attribute and drive the material from it), so the texture continues across the breaks.
- **Detail holds at the distance it is seen from.** Look at each model once from its closest shot
  (`tools/render.py --frames <f>`), not only in the wide.

## Materials

- **One material family per step**, each more than a bare shader: colour variation, roughness variation, a bump
  at the right scale. Procedural nodes, or an image your script paints into `textures/` (`kit.new_mat`, `kit.noise`,
  `kit.ramp`, `kit.mix`, `kit.bump`, `kit.coords`, `kit.wood_material`).
- **Check texture scale in the shot**, at once. A wood grain that reads as zebra stripes, a weave that turns a
  dark cloth grey in the sun, a crackle the size of a hand: all read fine in the node tree and wrong in the picture.
- Fine bump on a dark matte surface catches light as a grey haze: lower the specular before you darken the colour.
- Metals: metallic 1 with roughness variation. Glazes and lacquers: a coat. Paper, petals, wax: a little
  subsurface. Cloth: roughness near 1, low specular.
- Object-space coordinates (`kit.coords(nt, 'Object')`) keep a texture fixed to a moving object.

## Lighting and atmosphere

- **One motivated key per time of day or per set** (a lamp, the moon, the sun through a window), a weak coloured
  fill, and darkness left dark. Light is designed per part of the story and keyed on the timeline (energy and
  colour keys, constant interpolation at a cut, eased inside a shot when time passes in it).
- **When a light does not read, render with the others off** (a read-only script that hides them and renders a
  frame into `.local/`): a fill that drowns the key is found in one picture, not in ten guesses.
- Shadows of window bars, blinds or leaves are graphic elements: aim the key so the subject sits in a pane of
  light, not under a bar.
- A paper shade or a window that glows casts no shadow of its own (`ob.visible_shadow = False`) and its emission is
  kept low enough that its texture still shows.
- Atmosphere: a thin volume for shafts and halos, thinner than you think (it greys the blacks). Dust motes and
  other small bright things stay away from the lens, or they become huge bokeh discs.
- EEVEE reflections see only the screen: add a few reflection probes near the hero objects.

## Depth of field, motion, render

- **Depth of field** on the close shots (`kit.set_dof(cam, focus_object, fstop=2.8)`), stopped down in the wides
  (f/4 and above). Check that the foreground still has shape.
- **Motion blur**: half shutter, and the shutter **opens at the frame** (`render.motion_blur_position = 'START'`).
  Centred blur samples the time before a cut and smears the first frame of every shot.
- **Engine**: EEVEE (engine id `BLENDER_EEVEE`) by default: 48 samples, ray tracing on, soft shadows, volumetric
  shadows; it renders a 1080p frame in a few seconds and is stable from frame to frame. Cycles only when the time
  per frame fits the film (measure one frame per shot first) and the picture needs it.
- **Colour**: AgX with a contrast look chosen on purpose; exposure set once, late. In Blender 5 the compositor is a
  node group on the scene (`scene.compositing_node_group`, tree type `CompositorNodeTree`): a soft bloom, a gentle
  vignette, a small lift/gain grade that ties the parts of the film together. One concern per step.
- **Measure time per frame early**: `tools/render.py <film> --shots --pct 100` prints seconds per frame. If the
  full render would not fit, lower samples or resolution scale before you cut shots or quality of the scene.

## Critique rounds: at least two

A round: `tools/render.py <film> --shots --sheet 3 --out critique<n>` at the final settings, plus the first and
last frame of every shot once; look at every frame; write `## Round <n>` in `Docs/Critique.md` as a table (shot,
what is weak, the fix) and one `critique.issue` row per line; commit; then one step per fix. Hold each frame against
the treatment and these questions:

- **Composition**: where does the eye go first; is the subject on a third or centred on purpose; is there dead
  space, a tangent, an object cut by the frame edge; are there depth layers?
- **Light and colour**: is there one key; do the blacks hold; is anything burnt out; is the palette the plan of the
  treatment; is the accent colour the only saturated thing?
- **Surface**: does any material look like plastic or like a pattern; does detail hold in the closest shot?
- **Motion**: does anything slide, pop, start or stop in one frame, float or sink; does the cut land on the action?
- **Story**: could a stranger say what happened from the contact sheet alone?
- **Cleanliness**: flicker between consecutive frames, noise, clipping, z-fighting, a smeared first frame.

Write what is still weak after the last round in the critique and the report; do not hide it.

## Floors

`tools/validate-film.py` reports these for a final film (errors at release): at least 300,000 evaluated triangles,
40 mesh objects, 12 materials of which 60 % are more than a bare shader, 3 lights, 5 animated objects besides the
cameras, depth of field on at least one shot, at least 40 successful steps, two critique rounds. A film built one
visible change at a time leaves 80 to 130 steps.
