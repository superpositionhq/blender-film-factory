# Review

A released film is scored by a second person (a reviewer), not by its writer. Only an accepted film's trajectory is
used. A sample of accepted films is scored again by an auditor with the same rubric.

```
python3 tools/review.py <film> --reviewer <id> --decision accept|reject --note "<why>" --score story=4 --score staging=3 ...
```

## What the reviewer opens

1. `Brief.md` (the script; `storyboard/` if there is one), then `out/film.mp4` (and `out/greybox.mp4` of a final
   film) and `out/contact_sheet.png`.
2. `python3 tools/trajectory.py <film>`: its lines (events, coverage of notes and looks, leaks, secrets redacted), then
   `trajectory.md` in the folder it names. Read the first twenty steps, twenty from the middle and the critique
   rounds.
3. `Docs/Report.md` (the table of script beats and shots) and `python3 tools/validate-film.py <film> --release`.

## Scores: 1 to 5 per dimension

An accept needs every dimension scored, none under 3, and a mean of 3.5 or more. The note of a reject says what to
fix; the writer fixes it one step per point and releases again.

| Dimension | 1 | 3 | 5 |
|---|---|---|---|
| `story` | beats of the script are missing, out of order or contradicted | every beat is there and can be followed | a stranger could retell the script from the film alone |
| `staging` | who is where is unclear; people float, sink or pass through things | positions and facings are right and readable | the placement itself tells the relations between people and things |
| `motion` | sliding, linear, popping | eased, no pops, speeds believable | weight, timing and overlap; actions read from their outline |
| `camera` | random or unsteady moves; subject lost | each shot is steady, readable and the size the beat needs | every shot size, angle and move has a reason; screen direction holds |
| `editing` | cuts feel random; shots far too long or short | the order is clear, timing fits the lines | cuts land on action; pace builds and rests with the script |
| `cleanliness` | flicker, clipping, broken or smeared frames | minor artefacts | none visible |
| `reasoning` | steps taken in silence, or notes that only name the next action | most notes say what the picture shows and what comes next | every note says what was seen, what is wrong or missing, and why this change and not another; pictures are opened and mistakes are found from them |

Final films only:

| Dimension | 1 | 3 | 5 |
|---|---|---|---|
| `composition` | subject lost, tangents, dead space | readable, safe | deliberate in every frame: depth, balance, leading lines |
| `lighting` | flat or blown out | a motivated key, readable forms | light carries the mood of the scene the script describes |
| `colour` | default or clashing | one consistent palette | the palette follows the story; controlled accents |
| `materials` | plastic, uniform | believable base materials | surface detail holds in the closest shot |
| `modelling` | primitives visible | recognisable forms, correct proportions | silhouettes and detail hold in the closest shot |

`reasoning` is scored on the record alone. A beautiful film with a thin record is rejected: the record is the
product.
