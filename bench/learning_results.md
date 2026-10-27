# Does v2's learning help? (leave-one-plate-out)

Knowledge base: 8 plates, 767 FEA-checked designs.

## Surrogate, each plate predicted from the others only

- designs tested: 767
- mean stiffness error: 12.2 percentage points
- FEA runs the skip rule would save: 0
- designs it would wrongly skip (met the target): 0

## Re-pocketing each plate: learned from the other plates vs. no knowledge

| Plate | no knowledge | with knowledge (plate held out) | FEA runs | time |
|---|---|---|---|---|
| side_plate.step | 43.5% / 35% | 40.1% / 37% | 113 → 104 | 121s → 179s |
| blank_example.step | 38.1% / 34% | 36.9% / 35% | 129 → 105 | 139s → 122s |
| blank_top.step | 32.4% / 41% | 32.4% / 41% | 177 → 167 | 32432s → 252s |
| round_plate.step | 28.0% / 35% | 28.0% / 35% | 98 → 95 | 161s → 241s |
