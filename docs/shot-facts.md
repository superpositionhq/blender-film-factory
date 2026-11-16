# Shot facts

`shotlist.json` declares each shot; `tools/shots.py <film>` measures the same things from `scene.blend` and reports
every declared fact that does not hold. The scene is sampled with `scene.frame_set` on **every frame** of the shot
and the evaluated world matrices are read (not F-Curves, which miss constraints, parents and drivers).

A **shot** is a timeline marker with a camera bound to it, up to the frame before the next such marker (the last
shot ends at the scene's `frame_end`). The first marker is at `frame_start`. Each shot has its own camera object.

## Subject

The object the shot is about, by name. Its box is the box around the object **and everything parented under it**
(a mannequin's root is an empty: its box is the box of its parts). The centre of that box must be inside the frame
for at least **90 %** of the shot's frames. An object that enters late or leaves early is not the subject of that
shot: name what the camera holds.

## Camera move

From the camera's first and last position in the shot, its view directions, its focal length, and the angle it
sweeps around the subject. A translation counts when it is more than **2 % of the distance to the subject** (and at
least 2 cm); a rotation when it is more than **1.5 degrees**; a zoom when the focal length changes by more than 1 %.

| Move | Measured as |
|---|---|
| `static` | none of the below |
| `dolly` | translation along the view axis (in or out) |
| `truck` | translation sideways |
| `pedestal` | translation up or down, with no dolly or truck |
| `crane` | translation up or down together with a dolly or a truck |
| `pan` | rotation about the vertical axis |
| `tilt` | rotation up or down |
| `orbit` | the camera sweeps more than 5 degrees around the subject, turning with it, at a distance that changes by less than 20 % (replaces truck, dolly and pan) |
| `zoom` | the focal length changes |
| `handheld` | the frame-to-frame motion reverses direction on more than a fifth of the frames (replaces everything but zoom) |

Two moves are joined with `+` in any order (`dolly+tilt`). A camera that looks straight down (pitch over 60
degrees) moves along its view axis when it rises: that is a `dolly`, not a pedestal. `largest camera step` in the
tool's output is the biggest move between two frames: a jump inside a shot is a mistake.

## Shot size

The height of the subject's box in the frame, as a share of the frame height, at the shot's middle frame.

| Size | An object as subject | A whole figure as subject (root carries the property `figure`) |
|---|---|---|
| `extreme wide` | under 0.12 | under 0.25 |
| `wide` | 0.12 to 0.35 | 0.25 to 1.1 (the whole body in frame) |
| `medium` | 0.35 to 0.75 | 1.1 to 2.4 (about the waist up) |
| `close` | 0.75 to 1.5 | 2.4 to 6 (head and shoulders) |
| `extreme close` | over 1.5 | over 6 |

A close shot of a person is better declared on the head (`<Name>_Head` as the subject, object scale).

## Camera angle

The pitch of the line from the camera to the subject's centre at the middle frame: `top-down` over 60 degrees
down, `high` over 15 down, `low` over 10 up, `eye level` between.

## Events

`{"name": ..., "object": ..., "frame": ...}`: the object exists in the scene and the frame is inside the shot. The
frame is when the thing starts (the object begins to move, the light starts to change).

## Time

`video_start_s = (frame_start - scene frame_start) / fps` and `video_end_s = (frame_end + 1 - scene frame_start) /
fps`. The shots tile the scene's range with no gap or overlap.
