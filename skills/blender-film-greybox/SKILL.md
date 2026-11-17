---
name: blender-film-greybox
description: 'Rules for a blender-film-factory film whose output is greybox: a grey-box video made of jointed mannequins and plain blocks, where staging, motion, camera and cuts are the whole result. Use for every film created with --output greybox, and for the grey-box stage of a final film, when deciding how far to model, how figures are built, posed and walked, which colour marks which character, how the scene is lit, and what done means. Pair it with blender-film-session and blender-film-commit-always.'
---

# Grey-box output

A grey-box video is a plan a crew or another model can shoot from: **who is where, who moves how, what the camera
does, where the cuts are**. It is judged on whether each beat of the script can be read from it and whether its
facts are right, not on surface. Nothing in it is textured or detailed beyond what a viewer needs to tell one thing
from another. Everything in the blender-film-session skill applies; this skill says how each stage is done here.

Build a readable film plan step by step. Add each set object, figure, prop, camera and movement separately.
Inspect the saved frame after every step and commit each correction individually. Complete staging,
shot order and timing before adding detail.

## What it is made of

- **People are mannequins**: `build/mannequin.py` in your film (`import kit, mannequin`).
  `fig = mannequin.build('Anna', height=1.68, colour='red', collection=kit.coll('Characters'))` makes a jointed
  figure of rounded boxes standing at the origin, facing -Y: the root `Anna` (an empty on the ground) and the parts
  `Anna_Hips`, `Anna_Torso`, `Anna_Head`, `Anna_UpperArm_L/R`, `Anna_LowerArm_L/R`, `Anna_UpperLeg_L/R`,
  `Anna_LowerLeg_L/R`. Real heights. One figure per step.
- **Everything else is grey blocks**: `mannequin.block('Table', (1.6, 0.8, 0.75), (2, 1, 0), 'grey', collection)`
  is a bevelled box with its origin at the centre of its base. A thing with an outline that matters (a car, a door
  that opens, a chair) is a few blocks under one named parent, enough to read at the size it is seen: a car is a
  body, a cabin and four wheels, not one box. Moving parts are their own objects.
- **Grey is the rule; colour only marks who is who.** The set and the props are grey (`grey`, `white`, `dark`).
  Each character has one flat colour for the whole film, written in the treatment; a prop the story turns on may
  have one too. `mannequin.greybox_mat(colour)`. No textures, no procedural materials, no emission.
- **Light is the plain rig**: `mannequin.light_rig()` once, in the start step. Interiors leave out the ceiling and
  the wall behind the camera so the rig reaches the action. No designed lighting, fog, depth of field, compositing
  or motion blur.
- **Format**: what `film.json` says (1280x720 at 24 fps unless the brief gives another). EEVEE.

## Posing and moving figures

- **Walk**: `mannequin.walk(fig, [(x, y, z), ...], f0, f1)` moves the root along the polyline, turns it into each
  leg of the path, swings legs and arms with the distance covered and bobs the hips; the figure starts and ends
  standing. A walk covers about 1.3 m per second, a run 3 to 5 (a larger `stride`). One figure's move per step.
- **Place**: `mannequin.place(fig, frame, (x, y, z), facing_deg)` keys where the figure stands and which way it
  faces (0 = -Y, 90 = +X).
- **Pose**: `mannequin.pose(fig, frame, UpperArm_R=(-70, 0, 0), LowerArm_R=(-40, 0, 0), Head=(10, 0, 25))` keys
  joint angles in degrees (x swings forward for negative values, y sideways, z twists);
  `mannequin.rest(fig, frame)`, `mannequin.sit(fig, frame, seat_height)`, `mannequin.stand(fig, frame)`. A gesture
  has at least a rest, the pose and a rest again, and the pose is held as long as a viewer needs to read it (half a
  second or more).
- **An action reads from its outline**: a reach shows the arm clear of the body, a look turns the head and then
  the torso, a pick-up bends the knees. Judge it in the picture from the shot's camera.
- **Someone who speaks** makes a small gesture at the start of the line (a hand, a nod, a lean in), the listener
  faces them, and the shot holds for the length of the line.
- A figure holds a prop by parenting the prop to the hand's part at the frame it is taken.
- Feet may slide a little; figures do not float, sink into the floor, or pass through each other or through blocks.

## The stages here

The stages of the blender-film-session skill, read like this: **blockout** is the set as blocks (one step per
object or wall), each figure standing at its first mark, each prop, one camera per shot, then the blocked
animation, one move of one figure per step. **Models** only makes outlines readable where the grey-box video
showed they were not. Materials, designed lighting and render settings are skipped. **Polish** is holds, overlaps
(the head leads a turn, the arm settles after a reach), eased starts and stops and eased camera moves.

## What done means

- Every beat of the script can be told from the video alone: who, where, doing what, in the script's order.
- Every figure and every prop the story turns on is a subject or an event on the shot list, and `tools/shots.py`
  says `SHOT FACTS HOLD`.
- No figure floats, sinks, slides sideways while standing, or passes through anything; no camera is inside a block.
- Not wanted, and removed if present: textures, designed light, atmosphere, depth of field, grading, detail
  modelling. They hide the plan and add steps that carry no information.
