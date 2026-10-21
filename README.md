# AutoPocket

Automatic triangular-truss pocketing for flat FTC plates (STEP or 3MF in,
STEP / 3MF / STL out). Built around FTC parts: 1/8 in plates that fit in the
18 x 18 in sizing box.

## Quick start (Windows)

```bat
setup.bat      :: once: creates the venv in %USERPROFILE%\.venvs\autopocket and installs deps
start.bat      :: opens http://127.0.0.1:8765 in your browser
```

Drop a plate, pick the material, press **Generate pockets**. Compare *Original* /
*Pocketed*, click another row under **Options** to trade weight for stiffness,
and download.

Command line:

```bat
python cli.py plate.step -o plate_light.step --material "Aluminum 6061-T6" --target 0.33
```

## Pocket rules (fixed)

| Rule | Value |
|---|---|
| Pattern | Triangular truss |
| Rib width | 8 mm |
| Offset from plate edges and hole edges | 4 mm (rib centre line), so pockets stay 8 mm from edges and holes |
| Tool radius | 2 mm (every inside corner is at least R2) |
| Depth | Through |

These match the example plates in `examples/` (8.0 mm ribs, R2 corners).

## How it works

1. **Plate** – the largest flat face gives the 2D profile (outline + holes) and the
   thickness (`autopocket/pocketer.py`).
2. **Features** – every hole, bearing, slot or cutout gets an 8 mm keep-out band.
   Overlapping bands merge, so a bearing with its bolt circle or a bolt cluster is one
   feature; bands that reach the plate edge become bumps on the frame.
3. **Symmetry** – if the outline and most holes are mirror-symmetric, the layout is
   built on one half and mirrored (holes missing their twin still steer the ribs).
4. **Truss** – the space between the frame and the big features is meshed with a
   constrained quality triangulation (small holes are fixed nodes), then ribs are
   pruned wherever two cells can merge into one compact pocket. Oversized pockets are
   split, and any feature a pocket wraps more than 120° around gets an extra strut,
   so every hole is held from several sides.
5. **Pockets** – what is left between 8 mm ribs, opened with the 2 mm tool radius and
   cut through the plate with true arcs (OpenCascade).
6. **Structure** – `autopocket/fea.py` runs a plate FEA on the blank and pocketed
   profiles (out-of-plane bending, in-plane bending, torsion); `autopocket/runner.py`
   tries truss spacings from 32 to 72 mm and keeps the lightest layout that holds the
   stiffness target (default 33%, about what the example plates keep).

The FEA is a relative estimate with a generic load case – check critical parts
against your real loads.

`examples/` holds the hand-pocketed reference plates; `examples/classify.py` separates
their pockets from real features and `examples/make_blanks.py` rebuilds the blanks.

## Materials

| Material | Density g/cmÂ³ | E GPa | Strength MPa |
|---|---|---|---|
| Aluminum 6061-T6 | 2.70 | 68.9 | 276 (yield) |
| Delrin (acetal) | 1.41 | 3.1 | 72 (tensile yield) |
| Polycarbonate | 1.20 | 2.4 | 62 |
| PLA (3D printed) | 1.24 | 3.5 | ~50 |
| PETG (3D printed) | 1.27 | 2.1 | ~50 |
| Carbon fiber sheet | 1.55 | ~55 | ~500 (woven, quasi-isotropic) |

Typical datasheet values; printed and composite parts vary a lot with process and layup.

## Layout

| Path | What |
|---|---|
| `autopocket/cadio.py` | STEP/3MF/STL read & write, 3MF mesh â†’ B-rep, tessellation |
| `autopocket/pocketer.py` | plate detection, truss layout, pocket outlines, cutting |
| `autopocket/fea.py` | plate FEA stiffness / stress comparison |
| `autopocket/runner.py` | spacing search, materials, report |
| `autopocket/server.py`, `static/index.html` | local web app (FastAPI + three.js) |
| `examples/` | hand-pocketed reference plates and their blanks (`make_blanks.py`) |
| `samples/` | plates offered in the app's "Try a sample" list |

The 3D viewer loads three.js from a CDN, so the browser needs internet access.
