# AutoPocket

Automatically adds lightening pockets to a CAD part (STEP or 3MF) to cut weight
while keeping it stiff, then exports STEP / 3MF / STL.

## Quick start (Windows)

```bat
setup.bat      :: once: creates the venv in %USERPROFILE%\.venvs\autopocket and installs deps
start.bat      :: opens http://127.0.0.1:8765 in your browser
```

Drop a `.step`, `.stp` or `.3mf` file, pick a pattern, press **Generate pockets**,
compare *Original* / *Pocketed* in the 3D view, and download the result.
Click faces on the original to **protect** them (no pockets, and no through-pockets breaking out of them).

Command line:

```bat
python cli.py part.step -o part_light.step --pattern triangle --target 0.5
```

## How it works

1. **Find pocketable faces** – every planar face above a minimum area (`autopocket/pocketer.py`).
2. **Lay out pockets** – the face outline is inset by the *edge wall* (holes grow by the same
   amount, so bolt holes keep a ring of material), then split by a rib network:
   isogrid triangles, a rectangular grid, or one single pocket. Cells too small for the
   cutter (corner radius) are dropped.
3. **Pick depth** – rays measure material under each pocket. Thin uniform plates
   (≤ *max through thickness*) get through-pockets; everything else gets blind pockets that
   leave the *floor thickness*.
4. **Safety check** – each pocket (slightly enlarged) is tested against the current solid so it
   never breaks into holes, other pockets or outside walls; failures back off in depth.
5. **Cut** – pocket outlines get true-arc corner radii (≥ end-mill radius) and are subtracted
   with OpenCascade booleans, so STEP output stays a clean B-rep for CAM.
6. **Structural check** (`autopocket/fea.py`) – original and pocketed parts are voxelised and
   solved with a linear hex8 FEA under three cantilever load cases (weak-axis bending,
   strong-axis bending, torsion). If any case keeps less stiffness than the target, the
   pockets are regenerated with thicker ribs/walls, smaller cells and finally blind
   pockets (`autopocket/runner.py`) until the target is met.

The FEA is a relative estimate with a generic load case – verify critical parts with a
real analysis for your actual loads.

## Layout

| Path | What |
|---|---|
| `autopocket/cadio.py` | STEP/3MF/STL read & write, 3MF mesh → B-rep, tessellation |
| `autopocket/pocketer.py` | pocket layout, depth, validation and cutting |
| `autopocket/fea.py` | voxel FEA stiffness / stress comparison |
| `autopocket/runner.py` | pocket → check → back-off loop, materials, report |
| `autopocket/server.py`, `static/index.html` | local web app (FastAPI + three.js) |
| `samples/` | sample parts (`python samples/make_samples.py` regenerates them) |

The 3D viewer loads three.js from a CDN, so the browser needs internet access.
