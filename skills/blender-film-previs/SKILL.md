---
name: blender-film-previs
description: 'Rules for a blender-film-factory film whose output mode is previs: a white-model previsualisation made of jointed mannequins and blocks, where staging, motion, camera and cuts are the whole result. Use for every film created with --output previs, when deciding how far to model, how figures are built, posed and walked, which colours mark which character, how the previs is lit, and what done means. Pair it with blender-film-session and blender-film-commit-always.'
---

# Previs output

A previs film is a plan another model or a crew can shoot from: **who is where, who moves how, what the camera
does, where the cuts are**. It is judged on whether the event is readable and the facts are right, not on surface.
Nothing in it is textured, and nothing in it is detailed beyond what a viewer needs to tell one thing from another.
Everything in the blender-film-session skill applies; this skill says how each stage is done in a previs.

## What a previs is made of

- **People are mannequins**: `build/mannequin.py` in your film (`import kit, mannequin`).
  `fig = mannequin.build('Anna', height=1.68, colour='red', collection=kit.coll('Characters'))` makes a jointed
  figure of rounded boxes standing at the origin, facing -Y: root `Anna` (an empty on the ground) and parts
  `Anna_Hips`, `Anna_Torso`, `Anna_Head`, `Anna_UpperArm_L/R`, `Anna_LowerArm_L/R`, `Anna_UpperLeg_L/R`,
  `Anna_LowerLeg_L/R`. Real heights. One figure per step.
- **Everything else is blocks**: `mannequin.block('Table', (1.6, 0.8, 0.75), (2, 1, 0), 'brown', collection)` is a
  bevelled box with its origin at the centre of its base. A thing with a readable outline (a car, a tree, a door
  that opens, a chair) is a few blocks under one named parent, enough to read at the size it is seen: a car is a
  body, a cabin and four wheels, not one box. Moving parts are their own objects so they can move.
- **Colour marks identity, not surface**: each character has one flat previs colour for the whole film
  (`mannequin.COLOURS`: red, blue, green, yellow, orange, purple, teal, pink, brown, grey, white, dark), written in
  the treatment; props that matter to the story get a colour, the set stays grey. `mannequin.previs_mat(colour)`.
  No textures, no procedural materials, no emission.
- **Light is the plain rig**: `mannequin.light_rig()` once (one soft sun, an even world). Interiors leave out the
  ceiling and the wall behind the camera so the rig reaches the action. No designed lighting, no fog, no depth of
  field, no compositing, no motion blur.
- **Format**: what `film.json` says (1280x720 at 24 fps unless the brief gives another). EEVEE.

## Posing and moving figures

- **Walk**: `mannequin.walk(fig, [(x, y, z), ...], f0, f1)` moves the root along the polyline, turns it into each
  leg of the path, swings legs and arms in step with the distance and bobs the hips; the figure starts and ends
  standing. A walk covers about 1.3 m per second, a run 3 to 5 (pass `stride` larger for a run). One figure's move
  per step.
- **Place**: `mannequin.place(fig, frame, (x, y, z), facing_deg)` keys where the figure stands and which way it
  faces (0 = -Y, 90 = +X).
- **Pose**: `mannequin.pose(fig, frame, UpperArm_R=(-70, 0, 0), LowerArm_R=(-40, 0, 0), Head=(10, 0, 25))` keys
  joint angles in degrees (x swings forward for negative values, y sideways, z twists);
  `mannequin.rest(fig, frame)` keys the standing pose; `mannequin.sit(fig, frame, seat_height)` and
  `mannequin.stand(fig, frame)`. A gesture is three keys at least: rest, the pose, rest; hold a pose for the time a
  viewer needs to read it (half a second or more).
- **An action reads from its outline**: a reach shows the arm clear of the body, a look turns the head and then the
  torso, a pick-up bends the knees. Check it in the picture from the shot's camera, not in your head.
- A figure holds a prop by parenting the prop to the hand's part at the frame it is taken (key the prop's place at
  that frame in the hand's space; before that it sits where it was).
- Feet may slide a little; figures do not float, sink into the floor or pass through each other or through blocks.

## Build order in a previs

The stages of the blender-film-session skill, with these readings:

1. Start. 2. **Blockout**: the set as blocks, one step per object or wall; each figure, one step each, standing at
its first mark; each prop; one camera per shot, one step each; then the blocked animation, **one move of one
figure per step** (a walk, a turn, a reach, a sit). 3. **Blockout animatic** and its fixes.
4. **Models**: outlines made readable where the animatic showed they were not (the car that read as a crate). No
more than that. 5 and 8 are skipped. 6 is `mannequin.light_rig()`, one step, early (with the first camera).
7. **Animation polish**: holds, overlaps (the head leads a turn, the arm settles after a reach), eased starts and
stops, camera moves eased; one beat per step. 9. **One critique round at least**, on three frames of every shot.

A previs of 4 to 8 shots with 2 or 3 figures leaves roughly 30 to 60 steps.

## What done means

- The event of every shot can be told from the clip alone, without the brief: who, where, doing what.
- Every figure and every story prop is on the shot list where it is the subject, and `tools/shots.py` says
  `SHOT FACTS HOLD`. Events name the object that moves and the frame it starts.
- No figure floats, sinks, slides sideways while standing, or passes through anything; no camera is inside a block.
- `out/film.mp4` is the previs in its colours; `out/animatic_clay.mp4` is the same in one clay material (the
  release tool makes both).
- Not wanted, and removed if present: textures, designed light, atmosphere, depth of field, grading, detail
  modelling. They hide the plan and cost steps that carry no information.
